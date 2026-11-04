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


def run():
    # Ambos os XMLs são produzidos no motor 2, junto do mesmo catalogo.json.
    # Nunca tentar fabricar aqui: staging deve falhar se um artefato estiver ausente.
    for name in ('catalogo.json', 'merchant-produtos.xml', 'marketplace-produtos.xml',
                 'sitemap.xml', 'robots.txt', 'llms.txt'):
        file = ROOT / name
        if not file.is_file() or not file.stat().st_size:
            raise RuntimeError(f'[Pages V9.4] Arquivo obrigatório ausente antes da montagem: {name}')
    # Falhar se o XML for antigo ou não corresponder ao snapshot recebido.
    validate_marketplace()
    print('[Pages V9.4] Dois feeds e sitemap existentes: montando artefato.', flush=True)
    if DEST.exists():
        shutil.rmtree(DEST)
    shutil.copytree(ROOT, DEST, ignore=ignore, symlinks=False)
    # JSON arbitrarios do repositorio (fixtures, backups, IDs etc.) nao sao publicos.
    for path in DEST.iterdir():
        if path.is_file() and path.suffix.lower() == '.json' and path.name not in ROOT_JSON_ALLOW:
            path.unlink()
    (DEST / '.nojekyll').touch()
    print(f'[Pages] Site estatico preparado em {DEST} (HTMLs e catalogo incluidos).', flush=True)


if __name__ == '__main__':
    run()
