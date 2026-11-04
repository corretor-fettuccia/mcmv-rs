#!/usr/bin/env python3
"""Exige as subpaginas no artefato que sera efetivamente publicado."""
import json
import sys
from pathlib import Path
from core_lib import ROOT, settings
from gerar_marketplace import make_listing


def run():
    dest = ROOT / '_site'
    catalog = json.loads((dest / 'catalogo.json').read_text(encoding='utf-8'))
    conf = settings()
    needed = ['index.html', 'app.js', 'catalogo.json', 'sitemap.xml', 'robots.txt', 'merchant-produtos.xml', 'marketplace-produtos.xml', '.nojekyll']
    for filename in needed:
        if not (dest / filename).is_file():
            raise RuntimeError('Arquivo ausente do artefato Pages: ' + filename)
    items = catalog.get('items')
    if catalog.get('schemaVersion') != 4 or not isinstance(items, list):
        raise RuntimeError('Catálogo não está no formato V4')
    from xml.etree import ElementTree as ET
    meta_xml = ET.parse(dest / 'marketplace-produtos.xml').getroot()
    if meta_xml.tag != 'listings' or len(meta_xml.findall('listing')) != sum(make_listing(item)[0] is not None for item in items):
        raise RuntimeError('Feed Marketplace não corresponde ao catálogo deste deploy')
    for item in items:
        target = dest / 'imoveis' / item['id'] / 'index.html'
        if not target.is_file():
            raise RuntimeError('SUBPÁGINA AUSENTE DO DEPLOY: ' + str(target))
        source = target.read_text(encoding='utf-8')
        if item['pageUrl'] != conf['site_url'] + 'imoveis/' + item['id'] + '/':
            raise RuntimeError('URL divergente da subpágina: ' + item['id'])
        if not all(x in source for x in ('Acessar página do imóvel', 'Compartilhar', item['url'])):
            raise RuntimeError('Subpágina incompleta: ' + item['id'])
    if not (dest/'CNAME').is_file():
        print('[Pages] AVISO: CNAME não encontrado; domínio customizado precisa ser configurado.', flush=True)
    print(f'[Pages] Validado: {len(items)} subpáginas no artefato, pronto para publicar.', flush=True)


if __name__ == '__main__':
    try: run()
    except Exception as exc:
        print('[Pages] ERRO:', exc, file=sys.stderr)
        sys.exit(1)
