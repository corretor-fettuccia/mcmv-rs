#!/usr/bin/env python3
"""Auditora contrato V4, URLs internas, paginas individuais e feed apos execução."""
import json, sys
import xml.etree.ElementTree as ET
from core_lib import ROOT, settings

def run():
    conf = settings()
    catalog = json.loads((ROOT / 'catalogo.json').read_text(encoding='utf-8'))
    items = catalog.get('items')
    if catalog.get('schemaVersion') != 4 or not isinstance(items, list):
        raise ValueError('JSON sem items[] V4')
    ids = [item['id'] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError('IDs duplicados no catálogo')
    for item in items:
        if 'attributes' not in item or not isinstance(item['attributes'], list):
            raise ValueError('Imóvel sem attributes[]: '+item['id'])
        if not isinstance(item.get('gallery'), list) or not isinstance(item.get('description'),str):
            raise ValueError('Galeria ou descrição inválida: '+item['id'])
        expected = conf['site_url'] + 'imoveis/' + item['id'] + '/'
        if item['pageUrl'] != expected:
            raise ValueError('pageUrl divergente: '+item['id'])
        page = ROOT / 'imoveis' / item['id'] / 'index.html'
        if not page.is_file():
            raise ValueError('SUBPÁGINA AUSENTE: '+str(page))
        source = page.read_text(encoding='utf-8')
        for token in ('Acessar página do imóvel','Compartilhar', 'Descrição completa', 'rel="canonical"',item['url']):
            if token not in source:
                raise ValueError(f'HTML incompleto ({token}): {item["id"]}')
        if 'name="robots" content="noindex' in source:
            raise ValueError('Imóvel ativo recebeu noindex: '+item['id'])
    sitemap = ET.parse(ROOT / 'sitemap.xml')
    ns = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
    urls = [el.text for el in sitemap.findall('.//' + ns + 'loc')]
    expected_urls = [conf['site_url']] + [item['pageUrl'] for item in items]
    if set(urls) != set(expected_urls) or len(urls) != len(expected_urls):
        raise ValueError('Sitemap incompleto ou contém URLs antigas')
    rss = ET.parse(ROOT / 'merchant-produtos.xml')
    channel = rss.find('channel')
    if channel is None: raise ValueError('Feed sem channel')
    eligible_ids = {x['merchantId'] for x in items if x.get('googleEnabled') and
                    x.get('googleAvailability') in ('in_stock','out_of_stock') and
                    x.get('minimum') and x.get('brand') and x.get('condition') in ('new','used') and
                    x.get('description') and x.get('image') and x.get('url')}
    ns_g='{http://base.google.com/ns/1.0}'
    feed_ids=[item.findtext(ns_g+'id') for item in channel.findall('item')]
    if set(feed_ids) != eligible_ids or len(feed_ids) != len(eligible_ids):
        raise ValueError('Feed não coincide com os imóveis elegíveis do catálogo')
    print(f'VALIDADO: catálogo={len(items)} imóveis; páginas={len(items)}; sitemap={len(urls)} URLs; feed={len(feed_ids)}; atributos={len(catalog.get("atributos_disponiveis", []))}.')

if __name__ == '__main__':
    try: run()
    except Exception as exc:
        print('VALIDAÇÃO FALHOU:', exc,file=sys.stderr)
        sys.exit(1)
