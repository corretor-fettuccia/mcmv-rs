#!/usr/bin/env python3
"""Interrompe o Core se workflows antigos de publicação continuarem no checkout."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
p = root / '.github' / 'workflows'
conflicts = [
    'sinc-data.yml', 'make-feed-merchantcenter.yml', 'make-sitemap.yml',
    'make-subpage.yml', 'gerar-indexacao.yml', 'atualizar-sitemap.yml',
    'gerar-sitemap.yml', 'gerar-llms.yml',
]
present = [name for name in conflicts if (p / name).exists()]
if present:
    print('::error::Workflows antigos encontrados em .github/workflows/: ' + ', '.join(present))
    print('Exclua-os no GitHub e mantenha somente core-imobiliario.yml para a geração/publicação.')
    sys.exit(1)
print('OK: nenhum workflow legado de geração detectado.')
