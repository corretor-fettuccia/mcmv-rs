#!/usr/bin/env python3
"""Rotina unica V9.4: catalogo.json -> merchant-produtos.xml + marketplace-produtos.xml.

Chamada pelo motor 02 (make-feed-merchantcenter.py) e, como rede de seguranca, pela montagem do Pages.
Os dois XMLs sao montados em memoria antes de qualquer gravacao: se o Marketplace falhar, nada e gravado.
"""
import json
import csv
import io
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from core_lib import ROOT, put
from merchant_from_catalog import build
from gerar_marketplace import compile_xml


def run(root=ROOT):
    root = Path(root)
    catalog = json.loads((root / 'catalogo.json').read_text(encoding='utf-8'))
    if catalog.get('schemaVersion') != 4 or catalog.get('sourceContract') != 'core-imobiliario-v4':
        raise RuntimeError('Catálogo V4 obrigatório; execute sinc-data primeiro.')
    merchant = build(catalog)  # RSS válido mesmo com zero imóveis elegíveis
    try:
        meta, report = compile_xml(catalog)
    except ValueError as exc:  # sem Marketplace não há publicação (V9.4)
        # shortcut: Meta vazio não é publicado (todos os imóveis desligados bloqueiam o deploy); mudar se for preciso retirar tudo de uma vez.
        raise RuntimeError(f'Marketplace (Meta) não gerado: {exc}') from exc
    # Compatibilidade com o feed de anúncios em CSV, também derivado do catálogo.
    out = io.StringIO()
    fields = ['Listing ID','Listing name','Final URL','Image URL','City name','Description',
              'Price','Property type','Listing type','Contextual keywords','Address']
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for item in catalog['items']:
        writer.writerow({'Listing ID':item['id'],'Listing name':item['name'][:25],
            'Final URL':item['pageUrl'],'Image URL':item['image'],
            'City name':item.get('city','')[:25],
            'Description':(item.get('highlight') or item.get('description') or '')[:25],
            'Price': f"{float(item['minimum']):.2f} BRL" if item.get('minimum') is not None else '',
            'Property type':item.get('propertyType') or 'Other','Listing type':'For sale',
            'Contextual keywords':'; '.join(item.get('attributes',[])[:5]),
            'Address':', '.join(v for v in [item.get('address'),item.get('city'),item.get('uf')] if v)})
    # Gravação somente depois de os dois feeds estarem prontos.
    state = lambda changed: 'atualizado' if changed else 'inalterado'
    merchant_items = len(ET.fromstring(merchant).findall('./channel/item'))
    print(f'[feeds V9.4] 1/2 GERADO merchant-produtos.xml: {merchant_items} itens, {len(merchant)} bytes, '
          f'{state(put(root / "merchant-produtos.xml", merchant))}', flush=True)
    put(root / 'google-ads-imoveis.csv', out.getvalue().encode('utf-8-sig'))
    print(f'[feeds V9.4] 2/2 GERADO marketplace-produtos.xml: {report["incluidos"]} anúncios de '
          f'{report["recebidos"]}, {len(meta)} bytes, {state(put(root / "marketplace-produtos.xml", meta))}', flush=True)
    for skipped in report['excluidos']:
        print(f'[feeds V9.4] Marketplace excluiu {skipped["id"]}: {skipped["motivo"]}', flush=True)
    put(root / 'marketplace-relatorio.json', json.dumps(report, ensure_ascii=False, indent=2) + '\n')
