#!/usr/bin/env python3
"""Motor 2 isolado: recebe catalogo.json v4, emite RSS XML Google (somente formato).

Não consulta planilha, Apps Script, landing pages nem merchant.md. Não inventa valores.
Imóveis são categoria restrita no Shopping; feed válido não assegura aprovação.
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
G='http://base.google.com/ns/1.0'
ET.register_namespace('g',G)
FIELDS=['id','title','description','availability','condition','price','image_link','link','brand']


def build(catalog):
    if catalog.get('schemaVersion')!=4 or not isinstance(catalog.get('items'),list):
        raise ValueError('Catálogo completo V4 obrigatório')
    title=catalog.get('nome','Portal Imobiliário')
    site=catalog.get('url_principal','')
    rss=ET.Element('rss',{'version':'2.0'});channel=ET.SubElement(rss,'channel')
    for name,value in [('title',title),('link',site),('description','Registros imobiliários (formato técnico de feed)')]:
        ET.SubElement(channel,name).text=value
    included=0
    for entry in catalog['items']:
        if not entry.get('googleEnabled',False):
            continue
        availability=entry.get('googleAvailability','')
        if availability not in ('in_stock','out_of_stock'):
            print('Motor 2: disponibilidade não confirmada:',entry.get('id'))
            continue
        brand=entry.get('brand','');cond=entry.get('condition','');price=entry.get('minimum')
        image=entry.get('image','');link=entry.get('url','')
        if not brand or cond not in ('new','used') or not price or not image or not link:
            print('Motor 2: item ignorado por ausência de dados:',entry.get('id'))
            continue
        values={'id':entry.get('merchantId') or entry['id'], 'title':entry['name'],
                'description':entry.get('description') or entry.get('highlight',''),
                'availability':availability,'condition':cond,'price':f'{float(price):.2f} BRL',
                'image_link':image,'link':link,'brand':brand}
        if not values['description']:
            print('Motor 2: item sem descrição:',entry.get('id'));continue
        item=ET.SubElement(channel,'item')
        for key in FIELDS: ET.SubElement(item,f'{{{G}}}{key}').text=str(values[key])
        included+=1
    if not included:
        print('Motor 2: nenhum registro elegível: publicar RSS vazio para retirar ofertas antigas.')
    ET.indent(rss,space='  ')
    content=b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(rss,encoding='utf-8')+b'\n'
    ET.fromstring(content)
    return content


if __name__=='__main__':
    try:
        catalog=json.loads((ROOT/'catalogo.json').read_text(encoding='utf-8'))
        output=build(catalog)
        tmp=ROOT/'merchant-produtos.xml.tmp';tmp.write_bytes(output);tmp.replace(ROOT/'merchant-produtos.xml')
        print('Motor 2: merchant-produtos.xml atualizado')
    except (OSError,ValueError,KeyError) as exc:
        print('Erro Motor 2:',exc,file=sys.stderr);sys.exit(1)
