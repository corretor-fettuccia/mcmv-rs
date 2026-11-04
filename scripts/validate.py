#!/usr/bin/env python3
"""Validação independente dos geradores: contrato do catálogo, dos 3 XMLs, das páginas e do site montado.

Uso: validate.py [--root DIR] [--check catalog|feeds|sitemap|pages|site|all]
  all  = catalog + feeds + sitemap + pages (diretório de trabalho)
  site = all + arquivos estáticos obrigatórios (use --root _site)
Falha (exit 1) em qualquer divergência: nada é publicado.
"""
import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from core_lib import ROOT, settings, valid_url, load_catalog, attribute_key, attribute_label
from marketplace import make_item, distinct_images
from site_files import LOCAL_NAME, kind, read_page, absolute

G = '{http://base.google.com/ns/1.0}'
ATOM = '{http://www.w3.org/2005/Atom}'
SM = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
IMG = '{http://www.google.com/schemas/sitemap-image/1.1}'
MERCHANT_FIELDS = ('id', 'title', 'description', 'availability', 'condition', 'price', 'image_link', 'link', 'brand')
PRICE = re.compile(r'\d+\.\d{2} BRL')
HEADER = b'<?xml version="1.0" encoding="UTF-8"?>'
PAGE_TOKENS = ('Acessar página do imóvel', 'Compartilhar', 'Descrição completa')
STATIC = ('index.html', 'app.js', 'config.js', 'catalogo.json', 'merchant-produtos.xml', 'marketplace-produtos.xml',
          'sitemap.xml', 'robots.txt', 'llms.txt', '.nojekyll')


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
    """Catálogo de produtos da Meta: RSS 2.0 + g:. Pelo menos um item. Retorna {g:id: [imagem principal + extras]}."""
    root = parse(data, 'marketplace-produtos.xml')
    channel = root.find('channel')
    if root.tag != 'rss' or root.get('version') != '2.0' or channel is None or not (channel.findtext('title') or '').strip():
        raise ValueError('marketplace-produtos.xml: esperado <rss version="2.0"><channel><title>')
    link = channel.find(ATOM + 'link')
    if link is None or link.get('rel') != 'self' or not valid_url(link.get('href')) \
            or not link.get('href').endswith('/marketplace-produtos.xml'):
        raise ValueError('marketplace-produtos.xml: <atom:link rel="self" href=".../marketplace-produtos.xml"> ausente ou inválido')
    rows = channel.findall('item')
    if not rows:
        raise ValueError('marketplace-produtos.xml: nenhum <item>; feed vazio não é publicado')
    found = {}
    for row in rows:
        values = {k: (row.findtext(G + k) or '').strip() for k in MERCHANT_FIELDS}
        where = f'marketplace-produtos.xml item {values["id"] or "?"}'
        empty = [k for k, v in values.items() if not v]
        if empty:
            raise ValueError(f'{where}: campos g: ausentes {empty}')
        if values['availability'] not in ('in stock', 'out of stock') or values['condition'] not in ('new', 'used', 'refurbished'):
            raise ValueError(f'{where}: availability/condition fora do vocabulário da Meta (in stock, out of stock / new, used, refurbished)')
        for key, limit in (('id', 100), ('title', 200), ('description', 9999), ('brand', 100)):
            if len(values[key]) > limit:
                raise ValueError(f'{where}: {key} com mais de {limit} caracteres')
        positive_price(values['price'], where)
        https_urls([values['link']], where)
        images = [values['image_link']] + [(u.text or '').strip() for u in row.findall('additional_image_link')]
        if len(images) > 21:
            raise ValueError(f'{where}: mais de 20 additional_image_link')
        https_urls(images, where + ' imagens')
        if values['id'] in found:
            raise ValueError(f'{where}: g:id repetido')
        found[values['id']] = images
    if items is not None:  # mesmo conjunto, mesma ordem e mesmas imagens do catálogo
        expected = {i['id']: distinct_images(i) for i in items if make_item(i)[0] is not None}
        if list(found) != list(expected) or found != expected:
            raise ValueError('marketplace-produtos.xml: itens/imagens divergem do catálogo desta execução')
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
        if list(found) != [site] + [i['pageUrl'] for i in items]:
            raise ValueError('sitemap.xml: URLs divergem do catálogo (página inexistente, desativada, fora de ordem ou repetida)')
        for i in items:
            if len(found[i['pageUrl']]) != len(i['gallery']):
                raise ValueError(f'sitemap.xml: {i["pageUrl"]} tem {len(found[i["pageUrl"]])} imagens; a galeria tem {len(i["gallery"])}')
    return found


def check_catalog(catalog, site):
    items = catalog['items']
    keys = set()
    for item in items:
        for attr in item.get('attributes', []):
            if attr != attribute_label(attr):
                raise ValueError(f'catálogo: atributo sem padronização no imóvel {item.get("id")}: {attr}')
            keys.add(attribute_key(attr))
    visible = catalog.get('atributos_disponiveis')
    if not isinstance(visible, list) or {attribute_key(a) for a in visible} != keys or len(visible) != len(keys) \
            or any(a != attribute_label(a) for a in visible):
        raise ValueError('catálogo: atributos_disponiveis diverge dos filtros efetivos da vitrine')
    ids = [i['id'] for i in items]
    if len(ids) != len(set(ids)):
        raise ValueError('catálogo: IDs duplicados')
    for item in items:
        if not isinstance(item.get('attributes'), list) or not isinstance(item.get('gallery'), list) \
                or not isinstance(item.get('description'), str):
            raise ValueError(f'catálogo: attributes/gallery/description inválidos em {item["id"]}')
        if item.get('pageUrl') != site + 'imoveis/' + item['id'] + '/':
            raise ValueError(f'catálogo: pageUrl divergente em {item["id"]}')
        if not valid_url(item.get('image')) or not valid_url(item.get('url')):
            raise ValueError(f'catálogo: imagem ou URL https inválida em {item["id"]}')
    feeds = catalog.get('feeds', {})
    for key, name in (('google_merchant_xml', 'merchant-produtos.xml'), ('meta_marketplace_xml', 'marketplace-produtos.xml'),
                      ('sitemap_xml', 'sitemap.xml')):
        if feeds.get(key) != site + name:
            raise ValueError(f'catálogo: feeds.{key} deve apontar para {site}{name}')


def check_merchant_matches(ids, items):
    """Elegibilidade conferida sem usar o gerador: mesmos g:id que as regras do contrato produzem."""
    expected = [i.get('merchantId') or i['id'] for i in items
                if i.get('googleEnabled') and i.get('googleAvailability') in ('in_stock', 'out_of_stock')
                and i.get('minimum') and i.get('brand') and i.get('condition') in ('new', 'used')
                and (i.get('description') or i.get('highlight')) and i.get('image') and i.get('url')]
    if ids != expected:
        raise ValueError('merchant-produtos.xml: itens divergem dos imóveis elegíveis do catálogo')


def check_pages(root, items):
    for item in items:
        page = root / 'imoveis' / item['id'] / 'index.html'
        if not page.is_file():
            raise ValueError(f'página ausente: imoveis/{item["id"]}/index.html')
        source = page.read_text(encoding='utf-8')
        for token in PAGE_TOKENS + (item['url'],):
            if token not in source:
                raise ValueError(f'página {item["id"]} incompleta (falta {token!r})')
        if 'name="robots" content="noindex' in source:
            raise ValueError(f'imóvel ativo com noindex: {item["id"]}')
        canonical, sources = read_page(page)
        if canonical != item['pageUrl']:
            raise ValueError(f'página {item["id"]}: canonical {canonical!r} diferente de {item["pageUrl"]}')
        if len(sources) != len(item['gallery']):
            raise ValueError(f'página {item["id"]} mostra {len(sources)} imagens; a galeria do catálogo tem {len(item["gallery"])}')
        for src, original in zip(sources, item['gallery']):
            if src.startswith('https://'):  # imagem que não pôde ser baixada: precisa ser o endereço original
                if src != original:
                    raise ValueError(f'página {item["id"]}: imagem remota {src} não é a da galeria')
                continue
            file = page.parent / src
            if not LOCAL_NAME.fullmatch(src) or not file.is_file() or not file.stat().st_size or not kind(file.read_bytes()):
                raise ValueError(f'página {item["id"]}: imagem local ausente ou inválida: {src}')


def check_sitemap_vs_pages(root, items, found):
    """O sitemap precisa listar exatamente as imagens das páginas construídas."""
    for item in items:
        canonical, sources = read_page(root / 'imoveis' / item['id'] / 'index.html')
        expected = list(dict.fromkeys(absolute(canonical, src) for src in sources))
        if found[item['pageUrl']] != expected:
            raise ValueError(f'sitemap.xml: imagens de {item["pageUrl"]} divergem da página construída')


def check_discovery(root, site, items):
    if f'Sitemap: {site}sitemap.xml' not in (root / 'robots.txt').read_text(encoding='utf-8'):
        raise ValueError('robots.txt: linha Sitemap ausente ou fora do domínio')
    llms = (root / 'llms.txt').read_text(encoding='utf-8')
    if not llms.startswith('# ') or '\n> ' not in llms:
        raise ValueError('llms.txt: esperado título (#) e resumo em citação (>)')
    absent = [i['id'] for i in items if f']({i["pageUrl"]})' not in llms]
    if absent:
        raise ValueError(f'llms.txt não tem link para os imóveis {absent}')
    for name in ('catalogo.json', 'sitemap.xml', 'merchant-produtos.xml', 'marketplace-produtos.xml'):
        if f']({site}{name})' not in llms:
            raise ValueError(f'llms.txt sem link para {name}')

def run(root=ROOT, check='all'):
    root = Path(root)
    site = settings()['site_url']
    if check == 'site':
        gone = [f for f in STATIC if not (root / f).is_file() or not (root / f).stat().st_size and f != '.nojekyll']
        if gone:
            raise ValueError(f'site montado sem: {gone}')
    catalog = load_catalog(root)
    items = catalog['items']
    do = lambda *names: check in names or check in ('all', 'site')
    if do('catalog'):
        check_catalog(catalog, site)
        print(f'[validate] OK catalogo.json: {len(items)} imóveis, {len(catalog["atributos_disponiveis"])} atributos filtráveis', flush=True)
    if do('feeds'):
        merchant = check_merchant((root / 'merchant-produtos.xml').read_bytes())
        check_merchant_matches(merchant, items)
        meta = check_marketplace((root / 'marketplace-produtos.xml').read_bytes(), items)
        print(f'[validate] OK merchant-produtos.xml: {len(merchant)} itens', flush=True)
        print(f'[validate] OK marketplace-produtos.xml: {len(meta)} anúncios, {sum(len(v) for v in meta.values())} imagens', flush=True)
    if do('sitemap'):
        pages = check_sitemap((root / 'sitemap.xml').read_bytes(), site, items)
        check_sitemap_vs_pages(root, items, pages)
        check_discovery(root, site, items)
        print(f'[validate] OK sitemap.xml: {len(pages)} URLs, {sum(len(v) for v in pages.values())} imagens; robots.txt e llms.txt', flush=True)
    if do('pages'):
        check_pages(root, items)
        print(f'[validate] OK {len(items)} páginas individuais completas e indexáveis', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=str(ROOT))
    parser.add_argument('--check', choices=['catalog', 'feeds', 'sitemap', 'pages', 'site', 'all'], default='all')
    args = parser.parse_args()
    try:
        run(args.root, args.check)
    except Exception as exc:
        print('::error::validate:', exc, file=sys.stderr)
        sys.exit(1)
