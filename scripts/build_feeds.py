#!/usr/bin/env python3
"""Etapa 2: UMA rotina gera os dois feeds a partir do mesmo catalogo.json.

  merchant-produtos.xml     Google Merchant (RSS g:)
  marketplace-produtos.xml  Meta, catálogo de produtos (RSS g:)
  google-ads-imoveis.csv    auxiliar do Google Ads

Os dois XMLs são montados em memória e só então gravados: se o Marketplace falhar, nada é gravado.
"""
import csv
import io
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from core_lib import ROOT, load_catalog, put
from merchant import build as build_merchant
from marketplace import compile_xml

CSV_FIELDS = ['Listing ID', 'Listing name', 'Final URL', 'Image URL', 'City name', 'Description',
              'Price', 'Property type', 'Listing type', 'Contextual keywords', 'Address']


def ads_csv(catalog):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_FIELDS, lineterminator='\n')
    writer.writeheader()
    for i in catalog['items']:
        writer.writerow({
            'Listing ID': i['id'], 'Listing name': i['name'][:25], 'Final URL': i['pageUrl'], 'Image URL': i['image'],
            'City name': i.get('city', '')[:25], 'Description': (i.get('highlight') or i.get('description') or '')[:25],
            'Price': f"{float(i['minimum']):.2f} BRL" if i.get('minimum') is not None else '',
            'Property type': i.get('propertyType') or 'Other', 'Listing type': 'For sale',
            'Contextual keywords': '; '.join(i.get('attributes', [])[:5]),
            'Address': ', '.join(v for v in (i.get('address'), i.get('city'), i.get('uf')) if v)})
    return out.getvalue().encode('utf-8-sig')


def run(root=ROOT):
    root = Path(root)
    catalog = load_catalog(root)
    merchant, merchant_skipped = build_merchant(catalog)
    try:
        meta, report = compile_xml(catalog)
    except ValueError as exc:
        # shortcut: Marketplace vazio não é publicado (todos os imóveis desligados bloqueiam o deploy). Mudar se for preciso retirar tudo de uma vez.
        raise RuntimeError(f'Marketplace (Meta) não gerado: {exc}') from exc
    state = lambda changed: 'atualizado' if changed else 'inalterado'
    count = len(ET.fromstring(merchant).findall('./channel/item'))
    print(f'[feeds] 1/2 GERADO merchant-produtos.xml: {count} itens, {len(merchant)} bytes, '
          f'{state(put(root / "merchant-produtos.xml", merchant))}', flush=True)
    for ident, reason in merchant_skipped:
        print(f'[feeds] Merchant não inclui {ident}: {reason}', flush=True)
    print(f'[feeds] 2/2 GERADO marketplace-produtos.xml: {report["incluidos"]} anúncios de {report["recebidos"]}, '
          f'{len(meta)} bytes, {state(put(root / "marketplace-produtos.xml", meta))}', flush=True)
    for skipped in report['excluidos']:
        print(f'[feeds] Marketplace não inclui {skipped["id"]}: {skipped["motivo"]}', flush=True)
    put(root / 'google-ads-imoveis.csv', ads_csv(catalog))


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        print('::error::build_feeds:', exc, file=sys.stderr)
        sys.exit(1)
