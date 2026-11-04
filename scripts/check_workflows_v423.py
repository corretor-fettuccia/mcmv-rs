#!/usr/bin/env python3
"""Valida somente workflows indispensáveis para o Core."""
from pathlib import Path
import sys

folder = Path(__file__).resolve().parent.parent / '.github' / 'workflows'
required = {'core-imobiliario.yml', 'sinc-data.yml', 'make-feed-merchantcenter.yml',
            'make-sitemap.yml', 'make-subpage.yml'}
optional = {'gerar-marketplace.yml'}
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
print('OK: cinco workflows essenciais; sexto Meta é opcional.')
