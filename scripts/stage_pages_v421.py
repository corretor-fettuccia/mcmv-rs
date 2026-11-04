#!/usr/bin/env python3
"""Estagia arquivos publicos; todo o build ocorre no runner GitHub Actions.

Nao inclui codigo-fonte, workflows, dados de teste ou .git no site publicado.
"""
import shutil
from pathlib import Path
import json
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
    # Fallback deliberado: o Core legado (4 motores) tambem executa este script.
    # Garantimos que o Meta seja GERADO com o mesmo catalogo da execucao,
    # sem exigir a atualizacao de .github/workflows no GitHub.
    catalog = ROOT / 'catalogo.json'
    merchant = ROOT / 'merchant-produtos.xml'
    marketplace = ROOT / 'marketplace-produtos.xml'
    for filename, path in [('catalogo.json', catalog), ('merchant-produtos.xml', merchant)]:
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f'[Pages V9.3] Arquivo obrigatorio ausente: {filename}')
    try:
        doc = json.loads(catalog.read_text(encoding='utf-8-sig'))
        meta_xml, report = compile_xml(doc)
    except Exception as exc:
        raise RuntimeError(f'[Pages V9.3] Nao foi possivel gerar Marketplace a partir do catalogo: {exc}') from exc
    # Geracao atomica: uma falha na conversao nao substitui XML anterior.
    atomic_write(marketplace, meta_xml)
    validate_marketplace()
    print(f'[V9.3] FEED META GERADO: {marketplace.name} '
          f'({len(meta_xml)} bytes; {report["incluidos"]} imoveis, '
          f'{len(report["excluidos"])} ignorados)', flush=True)
    print(f'[V9.3] MERCHANT PRESERVADO: {merchant.stat().st_size} bytes', flush=True)
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
