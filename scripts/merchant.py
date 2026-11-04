#!/usr/bin/env python3
"""Google Merchant: catálogo V4 -> RSS 2.0 com namespace g. Somente formato; nada é inventado.

Imóveis são categoria restrita no Google Shopping: feed válido não assegura aprovação.
"""
import xml.etree.ElementTree as ET

G = 'http://base.google.com/ns/1.0'
ET.register_namespace('g', G)
FIELDS = ('id', 'title', 'description', 'availability', 'condition', 'price', 'image_link', 'link', 'brand')


def eligible(entry):
    """(valores do item, None) ou (None, motivo)."""
    if not entry.get('googleEnabled'):
        return None, 'publicação Google desligada'
    availability, cond, price = entry.get('googleAvailability', ''), entry.get('condition', ''), entry.get('minimum')
    if availability not in ('in_stock', 'out_of_stock'):
        return None, 'disponibilidade Google não confirmada'
    desc = entry.get('description') or entry.get('highlight', '')
    if not (entry.get('brand') and cond in ('new', 'used') and price and entry.get('image') and entry.get('url') and desc):
        return None, 'falta marca, condição, preço, imagem, URL ou descrição'
    return {'id': entry.get('merchantId') or entry['id'], 'title': entry['name'], 'description': desc,
            'availability': availability, 'condition': cond, 'price': f'{float(price):.2f} BRL',
            'image_link': entry['image'], 'link': entry['url'], 'brand': entry['brand']}, None


def build(catalog):
    """Devolve (bytes do XML, [(id, motivo) dos imóveis fora do feed]). Zero itens é válido (retira ofertas antigas)."""
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')
    for tag, value in (('title', catalog.get('nome', 'Portal Imobiliário')), ('link', catalog.get('url_principal', '')),
                       ('description', 'Registros imobiliários (formato técnico de feed)')):
        ET.SubElement(channel, tag).text = value
    skipped = []
    for entry in catalog['items']:
        values, reason = eligible(entry)
        if values is None:
            skipped.append((entry.get('id'), reason))
            continue
        item = ET.SubElement(channel, 'item')
        for key in FIELDS:
            ET.SubElement(item, f'{{{G}}}{key}').text = str(values[key])
    ET.indent(rss, space='  ')
    content = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding='utf-8') + b'\n'
    ET.fromstring(content)
    return content, skipped
