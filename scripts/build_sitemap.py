#!/usr/bin/env python3
"""Etapa 4: imóveis CONSTRUÍDOS em imoveis/ -> sitemap.xml (página principal + páginas, com as imagens de cada uma) e robots.txt.

A URL e as imagens de cada imóvel vêm da própria página gerada (canonical e galeria, já com as imagens baixadas);
o catálogo só diz quais imóveis estão ativos. Página ausente ou fora do padrão interrompe a publicação.
Sem lastmod/changefreq/priority: o catálogo não tem esses dados e nada é inventado.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape
from core_lib import ROOT, settings, put, valid_url, load_catalog
from site_files import read_page, absolute

SM = 'http://www.sitemaps.org/schemas/sitemap/0.9'
IMG = 'http://www.google.com/schemas/sitemap-image/1.1'


def run(root=ROOT):
    root = Path(root)
    site = settings()['site_url']
    catalog = load_catalog(root)
    pages = {site: []}  # dict: URL repetida some; valor = imagens da página (https, sem repetição, principal primeiro)
    for entry in catalog['items']:
        expected = site + 'imoveis/' + entry['id'] + '/'
        page = root / 'imoveis' / entry['id'] / 'index.html'
        if not page.is_file():
            raise RuntimeError(f'página não construída para {entry["id"]}: execute build_pages.py antes')
        canonical, sources = read_page(page)
        if canonical != expected or not valid_url(canonical):
            raise RuntimeError(f'canonical da página {entry["id"]} é {canonical!r}; esperado {expected}')
        images = list(dict.fromkeys(absolute(canonical, src) for src in sources))
        if not images or not all(valid_url(i) for i in images):
            raise RuntimeError(f'página {entry["id"]} sem imagens https válidas')
        pages[canonical] = images
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', f'<urlset xmlns="{SM}" xmlns:image="{IMG}">']
    for url, images in pages.items():
        lines.append(f'  <url>\n    <loc>{escape(url)}</loc>')
        lines.extend(f'    <image:image>\n      <image:loc>{escape(i)}</image:loc>\n    </image:image>' for i in images)
        lines.append('  </url>')
    lines.append('</urlset>')
    content = ('\n'.join(lines) + '\n').encode('utf-8')
    ET.fromstring(content)
    put(root / 'sitemap.xml', content)
    put(root / 'robots.txt', f'User-agent: *\nAllow: /\n\nSitemap: {site}sitemap.xml\n')
    print(f'[sitemap] GERADO sitemap.xml: {len(pages)} URLs canônicas, {sum(len(v) for v in pages.values())} imagens; robots.txt atualizado.', flush=True)


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        print('::error::build_sitemap:', exc, file=sys.stderr)
        sys.exit(1)
