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

REQUIRED = ('index.html', 'app.js', 'config.js', 'hero-mcmv-rs.png', 'icon.jpeg', 'catalogo.json',
            'merchant-produtos.xml', 'marketplace-produtos.xml', 'sitemap.xml', 'robots.txt', 'llms.txt')
OPTIONAL = ('CNAME', 'google-ads-imoveis.csv')


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
    for uid in pages:
        (work / 'imoveis' / uid).mkdir(parents=True)
        shutil.copy2(root / 'imoveis' / uid / 'index.html', work / 'imoveis' / uid / 'index.html')
    (work / '.nojekyll').touch()
    shutil.rmtree(root / '_site', ignore_errors=True)  # só depois de o novo estar completo
    work.rename(root / '_site')
    for name in ('merchant-produtos.xml', 'marketplace-produtos.xml', 'sitemap.xml', 'llms.txt'):
        print(f'[site] INCLUÍDO no artefato: {name} ({(root / "_site" / name).stat().st_size} bytes)', flush=True)
    print(f'[site] _site montado: catalogo.json, 3 XMLs, robots.txt, llms.txt, vitrine e {len(pages)} páginas de imóveis.', flush=True)


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        print('::error::stage_site:', exc, file=sys.stderr)
        sys.exit(1)
