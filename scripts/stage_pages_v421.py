#!/usr/bin/env python3
"""Estagia arquivos publicos; todo o build ocorre no runner GitHub Actions.

Nao inclui codigo-fonte, workflows, dados de teste ou .git no site publicado.
"""
import shutil
import json
from pathlib import Path
from core_lib import ROOT
from gerar_marketplace import compile_xml, atomic_write
from validate_marketplace_v8 import run as validate_marketplace

DEST = ROOT / '_site'
OMIT_DIRS = {'.git', '.github', 'scripts', '_site', '__pycache__', 'node_modules', '.venv', 'tests', '.pytest_cache'}
OMIT_FILES = {'INSTALAR_GIT.py'}
OMIT_SUFFIXES = {'.zip', '.py', '.pyc', '.md', '.docx', '.pdf', '.bak', '.tmp'}
ROOT_JSON_ALLOW = {'catalogo.json', 'portal-config.json', 'ai-catalog.json', 'manifest.json', 'site.webmanifest'}


def ignore(_folder, names):
    return [n for n in names if n in OMIT_DIRS or n in OMIT_FILES or n.endswith('~') or Path(n).suffix.lower() in OMIT_SUFFIXES]


def run():
    # Usa o catalogo.json recém-baixado do Core, não uma versão antiga da branch.
    doc = json.loads((ROOT / 'catalogo.json').read_text(encoding='utf-8'))
    marketplace = ROOT / 'marketplace-produtos.xml'
    try:
        content, stats = compile_xml(doc)
    except ValueError as exc:
        # Sem anúncios Meta elegíveis, não publicar um XML antigo por engano.
        if str(exc).startswith('Nenhum item válido:'):
            marketplace.unlink(missing_ok=True)
            print(f'::warning::Marketplace sem imóveis elegíveis: {exc}. Merchant permanece independente.', flush=True)
        else:
            raise
    else:
        atomic_write(marketplace, content)
        validate_marketplace()
        print(f'[Pages] Feed Meta gerado: {stats["incluidos"]} imóveis; {len(stats["excluidos"])} excluídos.', flush=True)
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
