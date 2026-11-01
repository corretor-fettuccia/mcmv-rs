#!/usr/bin/env python3
"""Motor 3: catalogo.json -> sitemap.xml e robots.txt (somente URLs deste portal)."""
import json
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from core_lib import ROOT, settings, put

SM = 'http://www.sitemaps.org/schemas/sitemap/0.9'
ET.register_namespace('', SM)


def run():
    conf = settings()
    catalog = json.loads((ROOT / 'catalogo.json').read_text(encoding='utf-8'))
    if catalog.get('schemaVersion') != 4 or not isinstance(catalog.get('items'), list):
        raise RuntimeError('catalogo.json V4 não encontrado: execute sinc-data antes.')
    site = conf['site_url']
    urls = [site]
    for entry in catalog['items']:
        uri = entry.get('pageUrl')
        expected = site + 'imoveis/' + entry['id'] + '/'
        if uri != expected:
            raise RuntimeError(f'URL da subpágina não confere para {entry["id"]}: {uri}')
        urls.append(uri)
    root = ET.Element(f'{{{SM}}}urlset')
    for uri in dict.fromkeys(urls):
        ET.SubElement(ET.SubElement(root, f'{{{SM}}}url'), f'{{{SM}}}loc').text = uri
    ET.indent(root, space='  ')
    content = b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding='utf-8') + b'\n'
    ET.fromstring(content)
    put(ROOT / 'sitemap.xml', content)
    robots = f'User-agent: *\nAllow: /\n\nSitemap: {site}sitemap.xml\n'
    put(ROOT / 'robots.txt', robots)
    # Arquivo de descoberta para agentes: sempre consistente com o catálogo público.
    lines = [f'# {conf.get("name","Portal Imobiliário")} — imóveis', '',
             f'Portal: {site}', f'Catálogo: {site}catalogo.json', '', '## Imóveis publicados', '']
    for entry in catalog['items']:
        lines.extend([f'### {entry["name"]}', f'- Detalhes: {entry["pageUrl"]}',
                      f'- Landing page: {entry["url"]}',
                      f'- Cidade: {entry.get("city","")}',
                      f'- Atributos: {", ".join(entry.get("attributes", []))}',
                      f'- Resumo: {(entry.get("description") or "")[:500]}', ''])
    lines.extend(['## Aviso', '', 'Condições sujeitas a confirmação com o anunciante.', ''])
    put(ROOT / 'llms.txt', '\n'.join(lines) + '\n')
    print(f'[make-sitemap] {len(urls)} URLs canônicas; sitemap.xml e robots.txt atualizados.', flush=True)

if __name__ == '__main__':
    try: run()
    except Exception as exc:
        print('[make-sitemap] ERRO:', exc, file=sys.stderr)
        sys.exit(1)
