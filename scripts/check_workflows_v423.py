#!/usr/bin/env python3
"""Valida a presença dos cinco Workflows da V4.2.4 e a ausência de publicadores legados."""
from pathlib import Path
import sys
p=Path(__file__).resolve().parent.parent/'.github'/'workflows'
allowed={'core-imobiliario.yml','sinc-data.yml','make-feed-merchantcenter.yml','make-sitemap.yml','make-subpage.yml'}
existing={x.name for x in p.glob('*.yml')} | {x.name for x in p.glob('*.yaml')}
missing=allowed-existing
unknown=existing-allowed
if missing or unknown:
    if missing: print('::error::Workflows obrigatórios ausentes:',', '.join(sorted(missing)))
    if unknown: print('::error::Exclua workflows antigos/duplicados:',', '.join(sorted(unknown)))
    sys.exit(1)
for filename in sorted(allowed):
    content=(p/filename).read_text(encoding='utf-8')
    if 'workflow_dispatch:' not in content:
        print('::error::Falta workflow_dispatch em', filename)
        sys.exit(1)
print('OK: 5 workflows (.github/workflows), todos com workflow_dispatch; nenhum fluxo legado.')
