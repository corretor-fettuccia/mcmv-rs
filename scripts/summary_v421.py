#!/usr/bin/env python3
"""Resumo legível com links completos no GitHub Actions / Step summary."""
import json
import os
from core_lib import ROOT

catalog = json.loads((ROOT/'catalogo.json').read_text(encoding='utf-8'))
items = catalog.get('items', [])
attrs = catalog.get('atributos_disponiveis', [])
lines = ['## Core Imobiliário V4.2.1 — arquivos gerados', '',
         f'- Imóveis publicados: **{len(items)}**',
         f'- Filtros por atributos: **{len(attrs)}**',
         f'- Subpáginas geradas: **{len(items)}**',
         f'- Feed Google: `{catalog.get("feeds",{}).get("google_merchant_xml","")}`',
         f'- Sitemap: `{catalog.get("url_principal","")}sitemap.xml`', '',
         '### Páginas dos imóveis', '']
for item in items[:50]:
    lines.append(f'- [{item["name"]}]({item["pageUrl"]}) — {len(item.get("attributes", []))} atributos')
if len(items)>50:lines.append(f'- ... mais {len(items)-50} imóveis')
message='\n'.join(lines)+'\n'
print(message, flush=True)
path=os.environ.get('GITHUB_STEP_SUMMARY')
if path:
    with open(path,'a',encoding='utf-8') as f:f.write(message)
