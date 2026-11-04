#!/usr/bin/env python3
"""Resumo legível com links completos no GitHub Actions / Step summary."""
import json
import os
from xml.etree import ElementTree as ET
from core_lib import ROOT

catalog = json.loads((ROOT/'catalogo.json').read_text(encoding='utf-8'))
items = catalog.get('items', [])
attrs = catalog.get('atributos_disponiveis', [])
feed_meta = ROOT / 'marketplace-produtos.xml'
feed_google = ROOT / 'merchant-produtos.xml'
meta_count = len(ET.parse(feed_meta).getroot().findall('listing')) if feed_meta.exists() else 0
lines = ['## Core Imobiliário V9.4 — arquivos gerados', '',
         f'- Imóveis publicados: **{len(items)}**',
         f'- Filtros por atributos: **{len(attrs)}**',
         f'- Subpáginas geradas: **{len(items)}**',
         f'- Feed Google Merchant: **{"OK" if feed_google.is_file() else "AUSENTE"}** — `{catalog.get("url_principal","")}merchant-produtos.xml`',
         f'- Feed Meta Marketplace: **{"OK" if meta_count else "AUSENTE"}**, {meta_count} anúncios — `{catalog.get("url_principal","")}marketplace-produtos.xml`',
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
