#!/usr/bin/env python3
"""Etapa 4: catalogo.json -> sitemap.xml (página principal + imóveis ativos, com imagens) e robots.txt.

Só URLs canônicas deste portal. Imóvel desativado não está no catálogo, logo não entra no sitemap.
Sem lastmod/changefreq/priority: o catálogo não tem esses dados e nada é inventado.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape
from core_lib import ROOT, settings, put, gallery, valid_url, load_catalog

SM = 'http://www.sitemaps.org/schemas/sitemap/0.9'
IMG = 'http://www.google.com/schemas/sitemap-image/1.1'


def run(root=ROOT):
    root = Path(root)
    site = settings()['site_url']
    catalog = load_catalog(root)
    pages = {site: []}  # dict: URL repetida some; valor = imagens do imóvel (https, sem repetição, principal primeiro)
    for entry in catalog['items']:
        url = entry.get('pageUrl')
        if url != site + 'imoveis/' + entry['id'] + '/' or not valid_url(url):
            raise RuntimeError(f'URL da página não confere para {entry["id"]}: {url}')
        pages[url] = gallery(entry.get('gallery'), entry.get('image'))
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
