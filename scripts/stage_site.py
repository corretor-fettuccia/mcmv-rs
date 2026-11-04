#!/usr/bin/env python3
"""Etapa 7: monta _site/ (o que o GitHub Pages publica) por LISTA DE PERMISSÃO.

Só entram os arquivos abaixo e as páginas dos imóveis do catálogo. Código, workflows, testes, documentos
e arquivos antigos esquecidos no repositório nunca vão para o site. Se algo obrigatório faltar, falha
antes de tocar em _site.
"""
import shutil
import sys
from pathlib import Path
from core_lib import ROOT, load_catalog
from site_files import read_page

REQUIRED = ('index.html', 'app.js', 'config.js', 'hero-mcmv-rs.png', 'icon.jpeg', 'catalogo.json',
            'merchant-produtos.xml', 'marketplace-produtos.xml', 'sitemap.xml', 'robots.txt', 'llms.txt')
OPTIONAL = ('CNAME', 'google-ads-imoveis.csv')
MAX_SITE_BYTES = 900 * 1024 * 1024  # shortcut: o GitHub Pages aceita até 1 GB; 900 MB deixa folga. Se estourar, o job falha antes de publicar.


def run(root=ROOT):
    root = Path(root)
    catalog = load_catalog(root)
    for name in REQUIRED:
        path = root / name
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f'arquivo obrigatório ausente ou vazio: {name}')
    pages = []
    for item in catalog['items']:
        page = root / 'imoveis' / item['id'] / 'index.html'
        if not page.is_file():
            raise RuntimeError(f'página ausente: imoveis/{item["id"]}/index.html')
        pages.append(item['id'])
    work = root / '_site.tmp'
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    for name in REQUIRED + tuple(n for n in OPTIONAL if (root / n).is_file()):
        shutil.copy2(root / name, work / name)
    photos = 0
    for uid in pages:
        folder = root / 'imoveis' / uid
        (work / 'imoveis' / uid).mkdir(parents=True)
        shutil.copy2(folder / 'index.html', work / 'imoveis' / uid / 'index.html')
        for src in read_page(folder / 'index.html')[1]:
            if not src.startswith('https://'):  # imagem baixada: só entra o que a página usa
                if not (folder / src).is_file():
                    raise RuntimeError(f'imagem usada pela página ausente: imoveis/{uid}/{src}')
                shutil.copy2(folder / src, work / 'imoveis' / uid / src)
                photos += 1
    size = sum(p.stat().st_size for p in work.rglob('*') if p.is_file())
    if size > MAX_SITE_BYTES:
        shutil.rmtree(work)
        raise RuntimeError(f'site com {size // 1024 // 1024} MB passa do limite de {MAX_SITE_BYTES // 1024 // 1024} MB do GitHub Pages')
    (work / '.nojekyll').touch()
    shutil.rmtree(root / '_site', ignore_errors=True)  # só depois de o novo estar completo
    work.rename(root / '_site')
    for name in ('merchant-produtos.xml', 'marketplace-produtos.xml', 'sitemap.xml', 'llms.txt'):
        print(f'[site] INCLUÍDO no artefato: {name} ({(root / "_site" / name).stat().st_size} bytes)', flush=True)
    print(f'[site] _site montado: catalogo.json, 3 XMLs, robots.txt, llms.txt, vitrine, {len(pages)} páginas de imóveis e {photos} imagens baixadas ({size / 1024 / 1024:.1f} MB no total).', flush=True)


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        print('::error::stage_site:', exc, file=sys.stderr)
        sys.exit(1)
