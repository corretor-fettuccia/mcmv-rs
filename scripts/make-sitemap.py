#!/usr/bin/env python3
"""Motor 3: catalogo.json -> sitemap.xml (paginas + imagens), robots.txt e llms.txt.

Somente URLs deste portal e imoveis ativos do catalogo (imovel inativo nao esta no catalogo).
"""
import json
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from core_lib import ROOT, settings, put, gallery, valid_url

SM = 'http://www.sitemaps.org/schemas/sitemap/0.9'
IMG = 'http://www.google.com/schemas/sitemap-image/1.1'


def run():
    conf = settings()
    catalog = json.loads((ROOT / 'catalogo.json').read_text(encoding='utf-8'))
    if catalog.get('schemaVersion') != 4 or not isinstance(catalog.get('items'), list):
        raise RuntimeError('catalogo.json V4 não encontrado: execute sinc-data antes.')
    site = conf['site_url']
    pages = {site: []}  # dict: URL repetida some; valor = imagens do imóvel, sem repetição
    for entry in catalog['items']:
        uri = entry.get('pageUrl')
        expected = site + 'imoveis/' + entry['id'] + '/'
        if uri != expected or not valid_url(uri):
            raise RuntimeError(f'URL da subpágina não confere para {entry["id"]}: {uri}')
        pages[uri] = gallery(entry.get('gallery'), entry.get('image'))  # https, sem repetição, principal primeiro
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<urlset xmlns="{SM}" xmlns:image="{IMG}">']
    for uri, images in pages.items():
        lines.append(f'  <url>\n    <loc>{escape(uri)}</loc>')
        lines.extend(f'    <image:image>\n      <image:loc>{escape(img)}</image:loc>\n    </image:image>' for img in images)
        lines.append('  </url>')
    lines.append('</urlset>')
    content = ('\n'.join(lines) + '\n').encode('utf-8')
    ET.fromstring(content)
    put(ROOT / 'sitemap.xml', content)
    robots = f'User-agent: *\nAllow: /\n\nSitemap: {site}sitemap.xml\n'
    put(ROOT / 'robots.txt', robots)
    # Arquivo de descoberta para agentes: sempre consistente com o catálogo público.
    llms = [f'# {conf.get("name","Portal Imobiliário")} — imóveis', '',
             f'Portal: {site}', f'Catálogo: {site}catalogo.json', '', '## Imóveis publicados', '']
    for entry in catalog['items']:
        llms.extend([f'### {entry["name"]}', f'- Detalhes: {entry["pageUrl"]}',
                      f'- Landing page: {entry["url"]}',
                      f'- Cidade: {entry.get("city","")}',
                      f'- Atributos: {", ".join(entry.get("attributes", []))}',
                      f'- Resumo: {(entry.get("description") or "")[:500]}', ''])
    llms.extend(['## Aviso', '', 'Condições sujeitas a confirmação com o anunciante.', ''])
    put(ROOT / 'llms.txt', '\n'.join(llms) + '\n')
    total_images = sum(len(v) for v in pages.values())
    print(f'[make-sitemap V9.4] GERADO sitemap.xml: {len(pages)} URLs canônicas, {total_images} imagens; '
          'robots.txt e llms.txt atualizados.', flush=True)

if __name__ == '__main__':
    try: run()
    except Exception as exc:
        print('[make-sitemap] ERRO:', exc, file=sys.stderr)
        sys.exit(1)
