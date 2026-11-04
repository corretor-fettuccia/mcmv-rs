#!/usr/bin/env python3
"""Auditoria das rotinas GitHub Actions: não usa pacotes de terceiros."""
from pathlib import Path
import sys
wf=Path(__file__).resolve().parents[1]/'.github'/'workflows'
expect=['sinc-data.yml','make-feed-merchantcenter.yml','make-sitemap.yml','make-subpage.yml','core-imobiliario.yml','gerar-marketplace.yml']
errors=[]
for name in expect:
    f=wf/name
    if not f.is_file(): errors.append(f"AUSENTE: {f}");continue
    s=f.read_text(encoding='utf-8')
    if 'workflow_dispatch:' not in s: errors.append(f"SEM RUN WORKFLOW: {name}")
    if name in ('sinc-data.yml','make-feed-merchantcenter.yml','make-sitemap.yml','make-subpage.yml') and 'workflow_call:' not in s: errors.append(f"SEM WORKFLOW_CALL: {name}")
    print(f"OK {f.relative_to(wf.parent.parent)} (workflow_dispatch)")
extras=sorted({f.name for f in wf.glob('*.yml')} - set(expect))
if extras: errors.append('WORKFLOWS EXTRA: '+ ', '.join(extras))
if errors:
    for msg in errors:print('::error::'+msg)
    sys.exit(1)
print('OK: 5 workflows legados preservados + 1 workflow independente do Marketplace')
