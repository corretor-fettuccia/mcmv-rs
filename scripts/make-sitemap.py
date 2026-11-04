#!/usr/bin/env python3
"""Motor 3: catalogo.json -> sitemap.xml e robots.txt (somente URLs deste portal)."""
import json
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from core_lib import ROOT, settings, put

SM = 'http://www.sitemaps.org/schemas/sitemap/0.9'
IM = 'http://www.google.com/schemas/sitemap-image/1.1'
ET.register_namespace('', SM)
ET.register_namespace('image', IM)


def images(item):
    # A primeira imagem e a galeria vêm do mesmo catálogo público.
    # HTTPS e URLs sem espaços; não inventar URLs nem repetir imagens.
    from core_lib import valid_url
    selected = []
    for raw in [item.get('image'), *(item.get('gallery') or [])]:
        if valid_url(raw) and raw not in selected:
            selected.append(raw)
    return selected[:1000]


def build_sitemap(catalog, conf):
    site = conf['site_url']
    items = catalog['items']
    root = ET.Element(f'{{{SM}}}urlset')
    main = ET.SubElement(root, f'{{{SM}}}url')
    ET.SubElement(main, f'{{{SM}}}loc').text = site
    for entry in items:
        expected = site + 'imoveis/' + entry['id'] + '/'
        if entry.get('pageUrl') != expected:
            raise RuntimeError(f'URL da subpágina não confere para {entry["id"]}: {entry.get("pageUrl")}')
        node = ET.SubElement(root, f'{{{SM}}}url')
        ET.SubElement(node, f'{{{SM}}}loc').text = expected
        for photo in images(entry):
            im_node = ET.SubElement(node, f'{{{IM}}}image')
            ET.SubElement(im_node, f'{{{IM}}}loc').text = photo
    ET.indent(root, space='  ')
    result = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='utf-8') + b'\n'
    ET.fromstring(result)
    return result


def run():
    conf = settings()
    catalog = json.loads((ROOT / 'catalogo.json').read_text(encoding='utf-8'))
    if catalog.get('schemaVersion') != 4 or not isinstance(catalog.get('items'), list):
        raise RuntimeError('catalogo.json V4 não encontrado: execute sinc-data antes.')
    site = conf['site_url']
    content = build_sitemap(catalog, conf)
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
    total_imagens = sum(len(images(item)) for item in catalog['items'])
    print(f'[make-sitemap V9.4] {len(catalog["items"])+1} URLs canônicas; {total_imagens} fotos; sitemap.xml e robots.txt atualizados.', flush=True)

if __name__ == '__main__':
    try: run()
    except Exception as exc:
        print('[make-sitemap] ERRO:', exc, file=sys.stderr)
        sys.exit(1)
