#!/usr/bin/env python3
"""Estagia arquivos publicos; todo o build ocorre no runner GitHub Actions.

Nao inclui codigo-fonte, workflows, dados de teste ou .git no site publicado.
"""
import shutil
from pathlib import Path
from core_lib import ROOT
from validate_marketplace_v8 import run as validate_marketplace

DEST = ROOT / '_site'
OMIT_DIRS = {'.git', '.github', 'scripts', '_site', '__pycache__', 'node_modules', '.venv', 'tests', '.pytest_cache'}
OMIT_FILES = {'INSTALAR_GIT.py'}
OMIT_SUFFIXES = {'.zip', '.py', '.pyc', '.md', '.docx', '.pdf', '.bak', '.tmp'}
ROOT_JSON_ALLOW = {'catalogo.json', 'portal-config.json', 'ai-catalog.json', 'manifest.json', 'site.webmanifest'}


def ignore(_folder, names):
    return [n for n in names if n in OMIT_DIRS or n in OMIT_FILES or n.endswith('~') or Path(n).suffix.lower() in OMIT_SUFFIXES]


PUBLIC_XML = ('merchant-produtos.xml', 'marketplace-produtos.xml', 'sitemap.xml')


def run():
    # V9.4: os feeds nascem no motor unificado (02 make-feed-merchantcenter). Aqui so se confere:
    # ausente ou invalido => falha ANTES de tocar em _site.
    for filename in ('catalogo.json', *PUBLIC_XML):
        path = ROOT / filename
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f'[Pages V9.4] Arquivo obrigatorio ausente: {filename}. '
                               'Confira se .github/workflows (V9.4) foi instalado: o motor 02 gera Merchant e Marketplace.')
    try:
        validate_marketplace()
    except Exception as exc:
        raise RuntimeError(f'[Pages V9.4] Marketplace invalido para este catalogo: {exc}') from exc
    if DEST.exists():
        shutil.rmtree(DEST)
    shutil.copytree(ROOT, DEST, ignore=ignore, symlinks=False)
    # JSON arbitrarios do repositorio (fixtures, backups, IDs etc.) nao sao publicos.
    for path in DEST.iterdir():
        if path.is_file() and path.suffix.lower() == '.json' and path.name not in ROOT_JSON_ALLOW:
            path.unlink()
    (DEST / '.nojekyll').touch()
    for filename in PUBLIC_XML:
        print(f'[Pages V9.4] INCLUIDO no artefato: {filename} ({(DEST / filename).stat().st_size} bytes)', flush=True)
    print(f'[Pages] Site estatico preparado em {DEST} (HTMLs e catalogo incluidos).', flush=True)


if __name__ == '__main__':
    run()
