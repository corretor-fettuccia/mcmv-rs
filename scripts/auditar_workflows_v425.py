#!/usr/bin/env python3
"""Confere os workflows obrigatorios. V9.4: o Marketplace nasce no motor 02; gerar-marketplace.yml e legado tolerado."""
from pathlib import Path
import sys

wf = Path(__file__).resolve().parents[1] / '.github' / 'workflows'
essential = ('sinc-data.yml', 'make-feed-merchantcenter.yml', 'make-sitemap.yml',
             'make-subpage.yml', 'core-imobiliario.yml')
optional = 'gerar-marketplace.yml'  # legado V9.3: pode existir em repositorios antigos; o Core nao o usa e pode ser apagado
errors = []
for name in essential + ((optional,) if (wf / optional).is_file() else ()):
    path = wf / name
    if not path.is_file():
        errors.append(f'AUSENTE: {path}')
        continue
    content = path.read_text(encoding='utf-8')
    if 'workflow_dispatch:' not in content:
        errors.append(f'SEM RUN WORKFLOW: {name}')
    if (name in essential[:4] or name == optional) and 'workflow_call:' not in content:
        errors.append(f'SEM WORKFLOW_CALL: {name}')
    print(f'OK {path.relative_to(wf.parent.parent)}')
extras = sorted(({path.name for path in wf.glob('*.yml')} |
                 {path.name for path in wf.glob('*.yaml')})
                 - set((*essential, optional)))
if extras:
    errors.append('WORKFLOWS EXTRA: ' + ', '.join(extras))
if errors:
    for error in errors:
        print('::error::' + error)
    sys.exit(1)
print('OK: cinco workflows essenciais (V9.4). Marketplace e gerado no motor 02 junto com o Merchant; gerar-marketplace.yml e legado opcional.')
