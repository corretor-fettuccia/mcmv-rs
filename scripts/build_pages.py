#!/usr/bin/env python3
"""Etapa 3: catalogo.json -> imoveis/{id}/index.html + imagens da galeria baixadas para a mesma pasta.

Imagem que não baixa (erro, não é imagem, grande demais) volta ao endereço original e entra no log como aviso.
Só imóveis ativos têm página. Pasta de imóvel que saiu do catálogo é removida do diretório de trabalho.
"""
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path
from core_lib import ROOT, settings, put, valid_url, load_catalog
from site_files import LOCAL_NAME, fetch_all, kind, local_name

SAFE_ID = re.compile(r'[A-Za-z0-9_-]{2,120}')


def h(s): return html.escape(str(s if s is not None else ''), quote=True)

def money(amount):
    if amount is None: return None
    return 'R$ {:,.2f}'.format(float(amount)).replace(',', 'X').replace('.', ',').replace('X', '.')

def render(item, conf, images=None):
    """images: [(src no HTML, URL absoluta)] da galeria; sem ele usa os endereços originais do catálogo."""
    url = item['pageUrl']
    name = item['name']
    title = item.get('seoTitle') or f'{name} | {conf["name"]}'
    detail = item.get('description') or item.get('highlight') or ''
    teaser = item.get('highlight') or detail
    meta = ' '.join(teaser.split())[:160]
    brand = item.get('brand') or ''
    location = ', '.join(v for v in [item.get('address'), item.get('city'), item.get('uf')] if v)
    if images is None:
        images = [(u, u) for u in item.get('gallery', []) if valid_url(u)]
    cover = images[0][1] if images else item.get('image', '')
    photographs = '\n'.join(
        f'<figure><img src="{h(src)}" alt="{h(name)} — imagem {n}" loading="{ "eager" if n == 1 else "lazy" }" decoding="async"></figure>'
        for n, (src, _absolute) in enumerate(images, 1))
    specs = [
        ('Tipo de imóvel', 'propertyType'), ('Dormitórios', 'bedrooms'),
        ('Suítes', 'suites'), ('Banheiros', 'bathrooms'), ('Vagas', 'parking'),
        ('Área privativa', 'privateArea'), ('Área total', 'totalArea'),
        ('Área do terreno', 'lotArea'), ('Situação', 'state')]
    details = ''
    for label, field in specs:
        value = item.get(field)
        if value is None or value == '': continue
        unit = ' m²' if field in ('privateArea', 'totalArea', 'lotArea') else ''
        details += f'<div class="metric"><dt>{h(label)}</dt><dd>{h(value)}{unit}</dd></div>\n'
    tags = ''.join(f'<li>{h(value)}</li>' for value in item.get('attributes', []))
    price_min, price_max = money(item.get('minimum')), money(item.get('maximum'))
    price = (f'{price_min} a {price_max}' if price_min and price_max and price_min != price_max
             else f'A partir de {price_min}' if price_min else 'Consulte as condições')
    business = item.get('campaignText') or ''
    page_json = {
        '@context':'https://schema.org', '@type':'WebPage',
        'url':url, 'name':title, 'description':meta, 'inLanguage':'pt-BR',
        'primaryImageOfPage':cover,
        'about': {'@type':'Place','name':name,'address': {'@type':'PostalAddress',
            'streetAddress':item.get('address',''), 'addressLocality':item.get('city',''),
            'addressRegion':item.get('uf',''), 'addressCountry':'BR'}}}
    ld = json.dumps(page_json, ensure_ascii=False).replace('<', '\\u003c')
    return '''<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>''' + h(title) + '''</title>
<meta name="description" content="''' + h(meta) + '''">
<link rel="canonical" href="''' + h(url) + '''">
<meta property="og:type" content="website"><meta property="og:url" content="''' + h(url) + '''">
<meta property="og:title" content="''' + h(title) + '''">
<meta property="og:description" content="''' + h(meta) + '''">
<meta property="og:image" content="''' + h(cover) + '''">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">''' + ld + '''</script>
<style>
:root{color-scheme:light;--ink:#193247;--teal:#087d77;--line:#e0e9e8;--muted:#617380;--bg:#f8faf9}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 system-ui,-apple-system,Arial,sans-serif}
a{color:inherit}.top{background:#153d4c;color:#fff;padding:16px max(20px,calc((100vw - 1120px)/2))}
.top a{text-decoration:none;font-weight:700}.layout{max-width:1120px;margin:auto;padding:24px 20px 70px}
.breadcrumb{font-size:13px;color:var(--muted)}h1{font-size:clamp(26px,4vw,44px);line-height:1.15;margin:13px 0}
.lead{font-size:17px;color:#476171;max-width:90ch}.muted{color:var(--muted)}
.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:12px;margin:24px 0}
.gallery figure{margin:0;background:#dce5e6;min-height:210px;border-radius:12px;overflow:hidden}
.gallery img{width:100%;height:260px;display:block;object-fit:cover}
.panel{background:#fff;border:1px solid var(--line);border-radius:14px;padding:clamp(18px,4vw,28px);margin-top:16px}
.panel h2{font-size:21px;margin:0 0 13px}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:14px}
.metric dt{font-size:12px;color:var(--muted)}.metric dd{font-size:18px;font-weight:700;margin:0}
.benefits{display:flex;gap:8px;flex-wrap:wrap;list-style:none;padding:0}.benefits li{background:#eaf4f1;color:#175851;padding:6px 12px;border-radius:999px;font-size:13px}
.description{white-space:pre-wrap;overflow-wrap:anywhere}.price{font-size:clamp(21px,4vw,29px);font-weight:800;margin:0}
.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}.button{display:inline-flex;justify-content:center;align-items:center;min-height:44px;padding:12px 18px;border:0;border-radius:8px;font-size:15px;font-weight:700;text-decoration:none;cursor:pointer;background:var(--teal);color:#fff}
.button.secondary{background:#193d55}.button.ghost{background:#e8f1f2;color:#193d55}.notice{font-size:12px;color:var(--muted);margin-top:22px}
@media(max-width:650px){.layout{padding:16px 14px 55px}.gallery img{height:230px}.actions{flex-direction:column}.button{width:100%}}
</style></head>
<body><header class="top"><a href="''' + h(conf['site_url']) + '''">‹ ''' + h(conf.get('name','Portal Imobiliário')) + ''' · Voltar à vitrine</a></header>
<main class="layout"><nav class="breadcrumb" aria-label="Navegação">''' + h(item.get('region') or '') + ''' / ''' + h(item.get('city') or '') + ''' / ''' + h(item.get('neighborhood') or '') + '''</nav>
<h1>''' + h(name) + '''</h1><p class="lead">''' + h(teaser) + '''</p>
<p class="muted">''' + h(location) + '''</p>
<section class="gallery" aria-label="Galeria de imagens">''' + photographs + '''</section>
<section class="panel"><h2>Características do imóvel</h2><dl class="metrics">''' + details + '''</dl></section>
<section class="panel"><h2>Características e benefícios</h2>''' + ('<ul class="benefits">'+tags+'</ul>' if tags else '<p>Características adicionais não informadas.</p>') + '''</section>
<section class="panel"><h2>Descrição completa</h2><div class="description">''' + h(detail) + '''</div></section>
<section class="panel"><h2>Condições e informações</h2><p class="price">''' + h(price) + '''</p><p>''' + h(business) + '''</p>''' + ('<p>Empreendimento: '+h(brand)+'</p>' if brand else '') + '''
<div class="actions"><a class="button" href="''' + h(item['url']) + '''" target="_blank" rel="noopener noreferrer">Acessar página do imóvel</a>
<button class="button secondary" type="button" id="shareButton">Compartilhar</button>
<a class="button ghost" href="''' + h(conf['site_url']) + '''">Voltar à vitrine</a></div>
<p id="shareStatus" role="status" aria-live="polite"></p>
<p class="notice">Informações, preços e condições sujeitos a confirmação com o anunciante.</p></section></main>
<script>
(function(){'use strict';
 const button=document.getElementById('shareButton');
 const status=document.getElementById('shareStatus');
 const url=document.querySelector('link[rel="canonical"]').href;
 button.addEventListener('click',async function(){
   try {
     if(navigator.share){await navigator.share({title:document.title,url:url});status.textContent='Compartilhamento aberto.';return;}
     if(navigator.clipboard&&navigator.clipboard.writeText){await navigator.clipboard.writeText(url);status.textContent='Link copiado para compartilhar.';return;}
     window.prompt('Copie o endereço do imóvel:',url);
   }catch(error){if(error.name!=='AbortError')window.prompt('Copie o endereço do imóvel:',url);}
 });
})();
</script></body></html>
'''


def download_gallery(item, folder, conf):
    """Baixa a galeria para a pasta do imóvel. Devolve ([(src, URL absoluta)], baixadas, já existentes, falhas)."""
    urls = item['gallery']
    folder.mkdir(parents=True, exist_ok=True)
    existing = {}
    for n, url in enumerate(urls, 1):  # arquivo do mesmo endereço já baixado antes (execução local): reaproveita
        for path in folder.glob(f'{n:02d}-{hashlib.sha1(url.encode()).hexdigest()[:8]}.*'):
            if LOCAL_NAME.fullmatch(path.name) and path.stat().st_size and kind(path.read_bytes()):
                existing[url] = path.name
    pending = [u for u in urls if u not in existing]
    results = dict(zip(pending, fetch_all(pending)))
    images, got, reused, failed = [], 0, 0, []
    for n, url in enumerate(urls, 1):
        if url in existing:
            name, reused = existing[url], reused + 1
        elif isinstance(results[url], tuple):
            data, ext = results[url]
            name = local_name(n, url, ext)
            put(folder / name, data)
            got += 1
        else:
            failed.append((url, results[url]))
            images.append((url, url))  # fallback: endereço original; a página continua completa
            continue
        images.append((name, conf['site_url'] + 'imoveis/' + item['id'] + '/' + name))
    keep = {src for src, _ in images}
    for path in folder.iterdir():  # imagens de galerias antigas deste imóvel
        if LOCAL_NAME.fullmatch(path.name) and path.name not in keep:
            path.unlink()
    return images, got, reused, failed


def run(root=ROOT):
    root = Path(root)
    conf = settings()
    catalog = load_catalog(root)
    pages_dir = root / 'imoveis'
    totals = {'baixadas': 0, 'existentes': 0, 'remotas': 0}
    written = 0
    for item in catalog['items']:
        uid = item['id']
        if not SAFE_ID.fullmatch(uid):
            raise RuntimeError('ID não seguro para criar página: ' + str(uid))
        if item.get('pageUrl') != conf['site_url'] + 'imoveis/' + uid + '/':
            raise RuntimeError('pageUrl não corresponde ao ID: ' + uid)
        images, got, reused, failed = download_gallery(item, pages_dir / uid, conf)
        written += int(put(pages_dir / uid / 'index.html', render(item, conf, images)))
        totals['baixadas'] += got
        totals['existentes'] += reused
        totals['remotas'] += len(failed)
        for url, reason in failed:
            print(f'::warning::imagem não baixada (a página usa o endereço original) {uid}: {url} ({reason})', flush=True)
        print(f'[pages] imoveis/{uid}/: {len(images)} imagens (baixadas {got}, já existentes {reused}, remotas {len(failed)})', flush=True)
    active = {i['id'] for i in catalog['items']}
    removed = []
    for folder in pages_dir.glob('*/') if pages_dir.is_dir() else []:
        # só apaga o que o próprio Core cria: pasta de nome seguro com index.html e imagens baixadas
        own = all(p.name == 'index.html' or LOCAL_NAME.fullmatch(p.name) for p in folder.iterdir())
        if folder.name not in active and SAFE_ID.fullmatch(folder.name) and own:
            shutil.rmtree(folder)
            removed.append(folder.name)
    print(f'[pages] GERADO imoveis/: {len(active)} páginas ({written} gravadas/alteradas); imagens baixadas {totals["baixadas"]}, '
          f'já existentes {totals["existentes"]}, remotas {totals["remotas"]}; pastas removidas: {len(removed)} {removed}', flush=True)
    for uid in sorted(active):  # listagem de ./imoveis/
        for path in sorted((pages_dir / uid).iterdir()):
            print(f'[pages]   imoveis/{uid}/{path.name}  {path.stat().st_size / 1024:.0f} KB', flush=True)


if __name__ == '__main__':
    try:
        run(ROOT)
    except Exception as exc:
        print('::error::build_pages:', exc, file=sys.stderr)
        sys.exit(1)
