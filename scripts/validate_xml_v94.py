#!/usr/bin/env python3
"""Contrato V9.4 dos XMLs publicados: merchant-produtos, marketplace-produtos e sitemap.

Valida a ESTRUTURA de cada arquivo (independente do gerador) e, quando recebe os
imoveis do catalogo, a CORRESPONDENCIA com eles. Uso:
  validate_xml_v94.py [--root DIR] [--check feeds|sitemap|all]
Contrato completo: MD/CONTRATO-FEEDS-V9.4.md.
"""
import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from core_lib import ROOT, settings, valid_url, gallery
from gerar_marketplace import make_listing, distinct_images

G = '{http://base.google.com/ns/1.0}'
SM = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
IMG = '{http://www.google.com/schemas/sitemap-image/1.1}'
MERCHANT_FIELDS = ('id', 'title', 'description', 'availability', 'condition', 'price', 'image_link', 'link', 'brand')
PRICE = re.compile(r'\d+\.\d{2} BRL')
HEADER = b'<?xml version="1.0" encoding="UTF-8"?>'


def parse(data, label):
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f'{label}: XML malformado ({exc})') from exc


def positive_price(value, where):
    if not PRICE.fullmatch(value or '') or float(value.split()[0]) <= 0:
        raise ValueError(f'{where}: preço inválido {value!r} (esperado 250000.00 BRL, maior que zero)')


def https_urls(urls, where):
    for url in urls:
        if not valid_url(url):  # barra data:/base64, http, espaços e credenciais
            raise ValueError(f'{where}: URL inválida {str(url)[:80]!r} (https público obrigatório)')
    if len(set(urls)) != len(urls):
        raise ValueError(f'{where}: URLs repetidas')


def check_merchant(data):
    """RSS 2.0 + namespace g. Zero itens é válido (retira ofertas antigas). Retorna os g:id."""
    root = parse(data, 'merchant-produtos.xml')
    channel = root.find('channel')
    if root.tag != 'rss' or root.get('version') != '2.0' or channel is None:
        raise ValueError('merchant-produtos.xml: esperado <rss version="2.0"><channel>')
    ids = []
    for item in channel.findall('item'):
        row = {k: (item.findtext(G + k) or '').strip() for k in MERCHANT_FIELDS}
        where = f'merchant-produtos.xml item {row["id"] or "?"}'
        empty = [k for k, v in row.items() if not v]
        if empty:
            raise ValueError(f'{where}: campos g: ausentes {empty}')
        if row['availability'] not in ('in_stock', 'out_of_stock') or row['condition'] not in ('new', 'used'):
            raise ValueError(f'{where}: availability/condition fora do contrato')
        positive_price(row['price'], where)
        https_urls([row['image_link'], row['link']], where)
        ids.append(row['id'])
    if len(set(ids)) != len(ids):
        raise ValueError('merchant-produtos.xml: g:id repetido')
    return ids


def check_marketplace(data, items=None):
    """<listings> Meta. Pelo menos um anúncio. Retorna {home_listing_id: [urls de imagem]}."""
    root = parse(data, 'marketplace-produtos.xml')
    link = root.find('link')
    if root.tag != 'listings' or not (root.findtext('title') or '').strip():
        raise ValueError('marketplace-produtos.xml: esperado <listings> com <title>')
    if link is None or link.get('rel') != 'self' or not valid_url(link.get('href')) \
            or not link.get('href').endswith('/marketplace-produtos.xml'):
        raise ValueError('marketplace-produtos.xml: <link rel="self" href=".../marketplace-produtos.xml"> ausente ou inválido')
    rows = root.findall('listing')
    if not rows:
        raise ValueError('marketplace-produtos.xml: nenhum <listing>; feed vazio não é publicado')
    found = {}
    for row in rows:
        ident = (row.findtext('home_listing_id') or '').strip()
        where = f'marketplace-produtos.xml listing {ident or "?"}'
        for tag in ('home_listing_id', 'name', 'description', 'price', 'url', 'listing_type'):
            if not (row.findtext(tag) or '').strip():
                raise ValueError(f'{where}: <{tag}> ausente')
        if row.findtext('availability') != 'for_sale':
            raise ValueError(f'{where}: availability deve ser for_sale')
        positive_price(row.findtext('price'), where)
        https_urls([row.findtext('url')], where)
        address = row.find('address')
        parts = {c.get('name'): (c.text or '').strip() for c in address.findall('component')} if address is not None else {}
        if address is None or address.get('format') != 'simple' or not all(parts.get(k) for k in ('addr1', 'city', 'region', 'country')):
            raise ValueError(f'{where}: <address format="simple"> sem addr1/city/region/country')
        images = [(u.text or '').strip() for u in row.findall('image/url')]
        if not images:
            raise ValueError(f'{where}: sem <image><url>')
        https_urls(images, where + ' imagens')
        if ident in found:
            raise ValueError(f'{where}: home_listing_id repetido')
        found[ident] = images
    if items is not None:  # mesmo conjunto, mesma ordem e mesmas imagens do catálogo
        expected = {i['id']: distinct_images(i) for i in items if make_listing(i)[0] is not None}
        if list(found) != list(expected) or found != expected:
            raise ValueError('marketplace-produtos.xml: anúncios/imagens divergem do catálogo desta execução')
    return found


def check_sitemap(data, site, items=None):
    """urlset + image:image. Home primeiro; sem URL ou imagem repetida. Retorna {url: [imagens]}."""
    if not data.startswith(HEADER) or f'xmlns:image="{IMG[1:-1]}"'.encode() not in data:
        raise ValueError('sitemap.xml: declaração UTF-8 ou namespace image ausentes')
    root = parse(data, 'sitemap.xml')
    if root.tag != SM + 'urlset':
        raise ValueError('sitemap.xml: raiz deve ser urlset do namespace sitemaps.org')
    found = {}
    for url in root.findall(SM + 'url'):
        loc = (url.findtext(SM + 'loc') or '').strip()
        https_urls([loc], 'sitemap.xml loc')
        images = [(i.findtext(IMG + 'loc') or '').strip() for i in url.findall(IMG + 'image')]
        https_urls(images, f'sitemap.xml {loc} imagens')
        if loc in found:
            raise ValueError(f'sitemap.xml: URL repetida {loc}')
        if len(images) > 1000:
            raise ValueError(f'sitemap.xml: {loc} excede 1000 imagens')
        found[loc] = images
    if not found or next(iter(found)) != site:
        raise ValueError('sitemap.xml: a página principal deve ser a primeira URL')
    if len(found) > 50000 or len(data) > 50 * 1024 * 1024:
        raise ValueError('sitemap.xml: acima do limite de 50.000 URLs / 50 MB')
    if items is not None:
        expected = {site: []}
        expected.update({i['pageUrl']: gallery(i.get('gallery'), i.get('image')) for i in items})
        if found != expected:
            raise ValueError('sitemap.xml: URLs ou imagens divergem do catálogo (página inexistente, desativada ou imagem fora da galeria)')
    return found


def run(root=ROOT, check='all'):
    root = Path(root)
    site = settings()['site_url']
    items = json.loads((root / 'catalogo.json').read_text(encoding='utf-8'))['items']
    if check in ('feeds', 'all'):
        merchant = check_merchant((root / 'merchant-produtos.xml').read_bytes())
        meta = check_marketplace((root / 'marketplace-produtos.xml').read_bytes(), items)
        print(f'[validate V9.4] OK merchant-produtos.xml: {len(merchant)} itens', flush=True)
        print(f'[validate V9.4] OK marketplace-produtos.xml: {len(meta)} anúncios, '
              f'{sum(len(v) for v in meta.values())} imagens', flush=True)
    if check in ('sitemap', 'all'):
        pages = check_sitemap((root / 'sitemap.xml').read_bytes(), site, items)
        if f'Sitemap: {site}sitemap.xml' not in (root / 'robots.txt').read_text(encoding='utf-8'):
            raise ValueError('robots.txt: linha Sitemap ausente ou fora do domínio')
        if not (root / 'llms.txt').is_file() or not (root / 'llms.txt').stat().st_size:
            raise ValueError('llms.txt ausente ou vazio')
        print(f'[validate V9.4] OK sitemap.xml: {len(pages)} URLs, {sum(len(v) for v in pages.values())} imagens; robots.txt e llms.txt', flush=True)
    if check == 'all':  # páginas existem no mesmo diretório e nenhuma está desativada
        for item in items:
            page = root / 'imoveis' / item['id'] / 'index.html'
            if not page.is_file() or 'name="robots" content="noindex' in page.read_text(encoding='utf-8'):
                raise ValueError(f'sitemap.xml aponta para página inexistente ou desativada: {item["id"]}')
        print(f'[validate V9.4] OK {len(items)} páginas individuais existem e estão indexáveis', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=str(ROOT))
    parser.add_argument('--check', choices=['feeds', 'sitemap', 'all'], default='all')
    args = parser.parse_args()
    try:
        run(args.root, args.check)
    except Exception as exc:
        print('::error::Validação V9.4:', exc, file=sys.stderr)
        sys.exit(1)
