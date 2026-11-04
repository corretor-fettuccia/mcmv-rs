#!/usr/bin/env python3
"""Meta (Facebook/Instagram): catálogo V4 -> RSS 2.0 com namespace g, o formato do catálogo de produtos do Gerenciador de Comércio.

A Meta recusa o formato <listings> nesse tipo de catálogo ("formato XML errado"); ele só vale para catálogo de imóveis,
que exige aluguel, CEP e coordenadas que a planilha não tem. Nada é inventado: o que falta deixa o imóvel fora do feed.
"""
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse, urljoin

DEFAULT_OUTPUT = 'marketplace-produtos.xml'
FEED_PUBLIC_URL = 'https://mcmv-rs.com.br/marketplace-produtos.xml'
G = 'http://base.google.com/ns/1.0'
ATOM = 'http://www.w3.org/2005/Atom'
ET.register_namespace('g', G)
ET.register_namespace('atom', ATOM)
MAX_ADDITIONAL = 20  # image_link + até 20 additional_image_link
# Vocabulário da Meta (em inglês, com espaço). O da planilha/Google usa sublinhado.
AVAILABILITY = {'in_stock': 'in stock', 'out_of_stock': 'out of stock'}
CONDITIONS = ('new', 'used', 'refurbished')
LIMITS = {'id': 100, 'title': 200, 'description': 9999, 'brand': 100}


def valid_https_url(value):
    if not isinstance(value, str):
        return False
    v = urlparse(value.strip())
    return v.scheme == 'https' and bool(v.netloc) and not any(c.isspace() for c in value)


def text_value(value, limit):
    s = re.sub(r'\s+', ' ', str(value or '')).strip()
    return ''.join(ch for ch in s if ch in '\t\n\r' or ord(ch) >= 32)[:limit]


def money(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        d = Decimal(str(value))
        if not d.is_finite() or d <= 0:
            return None
        return f'{d:.2f} BRL'
    except (InvalidOperation, ValueError):
        return None


def distinct_images(item):
    """Imagem principal + galeria: https, sem repetição, no máximo 1 + MAX_ADDITIONAL."""
    candidates = []
    first = item.get('image')
    if isinstance(first, str):
        candidates.append(first)
    if isinstance(item.get('gallery'), list):
        candidates.extend(item['gallery'])
    seen = set()
    result = []
    for value in candidates:
        if not valid_https_url(value):
            continue
        url = value.strip()
        if url in seen:
            continue
        seen.add(url)
        result.append(url)
        if len(result) > MAX_ADDITIONAL:
            break
    return result


def make_item(item):
    """(<item> RSS, None) ou (None, motivo)."""
    if item.get('marketplaceEnabled') is False:
        return None, 'publicação Meta desativada explicitamente'
    values = {
        'id': text_value(item.get('id'), LIMITS['id']),
        'title': text_value(item.get('name'), LIMITS['title']),
        'description': text_value(item.get('description') or item.get('highlight'), LIMITS['description']),
        'availability': AVAILABILITY.get(item.get('googleAvailability')),
        'condition': item.get('condition') if item.get('condition') in CONDITIONS else None,
        'price': money(item.get('minimum')),
        'link': item.get('pageUrl') if valid_https_url(item.get('pageUrl')) else item.get('url'),
        'brand': text_value(item.get('brand'), LIMITS['brand']),
    }
    images = distinct_images(item)
    if not (all(values.values()) and valid_https_url(values['link']) and images):
        return None, 'falta ID, título, descrição, disponibilidade, condição, preço, marca, URL ou imagem'
    node = ET.Element('item')
    for key in ('id', 'title', 'description', 'availability', 'condition', 'price', 'link'):
        ET.SubElement(node, f'{{{G}}}{key}').text = values[key]
    ET.SubElement(node, f'{{{G}}}image_link').text = images[0]
    for extra in images[1:]:  # a Meta lista essas sem prefixo, uma tag por imagem
        ET.SubElement(node, 'additional_image_link').text = extra
    ET.SubElement(node, f'{{{G}}}brand').text = values['brand']
    return node, None


def compile_xml(doc, feed_url=None):
    items = doc['items']  # contrato já conferido por core_lib.load_catalog; só items[] entra (não empreendimentos[])
    site_url = doc.get('url_principal')
    if not valid_https_url(feed_url):
        feed_url = urljoin(site_url.rstrip('/') + '/', DEFAULT_OUTPUT) if valid_https_url(site_url) else FEED_PUBLIC_URL
    title = text_value(doc.get('nome'), 150) or 'MCMV-RS'
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = f'{title} — Empreendimentos'
    ET.SubElement(channel, 'description').text = 'Registros imobiliários (formato técnico de feed)'
    ET.SubElement(channel, 'link').text = site_url if valid_https_url(site_url) else FEED_PUBLIC_URL.rsplit('/', 1)[0] + '/'
    ET.SubElement(channel, f'{{{ATOM}}}link', {'href': feed_url, 'rel': 'self', 'type': 'application/rss+xml'})
    included = 0
    excluded = []
    for item in items:
        node, reason = make_item(item)
        if node is not None:
            channel.append(node)
            included += 1
        else:
            excluded.append({'id': str(item.get('id', '?')), 'motivo': reason})
    if included == 0:
        raise ValueError('Nenhum imóvel elegível à Meta (id, título, descrição, disponibilidade, condição, preço, marca, URL e imagem https)')
    ET.indent(rss, space='  ')
    content = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding='utf-8') + b'\n'
    ET.fromstring(content)
    return content, {'recebidos': len(items), 'incluidos': included, 'excluidos': excluded}
