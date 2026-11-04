#!/usr/bin/env python3
"""Valida workflows indispensáveis para a execução do Core V8."""
from pathlib import Path
import sys

folder = Path(__file__).resolve().parent.parent / '.github' / 'workflows'
required = {'core-imobiliario.yml', 'sinc-data.yml', 'make-feed-merchantcenter.yml',
            'make-sitemap.yml', 'make-subpage.yml', 'gerar-marketplace.yml'}
optional = set()
found = {path.name for path in folder.glob('*.yml')} | {path.name for path in folder.glob('*.yaml')}
missing = required - found
unknown = found - required - optional
if missing or unknown:
    if missing:
        print('::error::Workflows essenciais ausentes:', ', '.join(sorted(missing)))
    if unknown:
        print('::error::Workflows antigos/duplicados:', ', '.join(sorted(unknown)))
    sys.exit(1)
for name in sorted(found):
    if 'workflow_dispatch:' not in (folder / name).read_text(encoding='utf-8'):
        print('::error::Falta workflow_dispatch em', name)
        sys.exit(1)
print('OK: seis workflows essenciais do Core V8, incluindo Marketplace.')
