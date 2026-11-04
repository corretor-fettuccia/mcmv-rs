#!/usr/bin/env python3
"""Motor 2: um catálogo -> Merchant XML, Marketplace XML e CSV de anúncios."""
import json
import csv
import io
import sys
from core_lib import ROOT, put
from merchant_from_catalog import build
from gerar_marketplace import compile_xml


def run():
    catalog = json.loads((ROOT / 'catalogo.json').read_text(encoding='utf-8'))
    if catalog.get('schemaVersion') != 4 or catalog.get('sourceContract') != 'core-imobiliario-v4':
        raise RuntimeError('Catálogo V4 obrigatório; execute sinc-data primeiro.')
    # O Merchant continua utilizando exatamente o mesmo gerador de antes.
    content = build(catalog)  # RSS válido mesmo com zero imóveis elegíveis
    meta_content, meta_report = compile_xml(catalog)
    updated = put(ROOT / 'merchant-produtos.xml', content)
    meta_updated = put(ROOT / 'marketplace-produtos.xml', meta_content)
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
    put(ROOT / 'google-ads-imoveis.csv', out.getvalue().encode('utf-8-sig'))
    print('[FEEDS V9.4] Merchant:', 'atualizado' if updated else 'inalterado',
          '; Marketplace:', 'atualizado' if meta_updated else 'inalterado',
          f'; Meta incluídos={meta_report["incluidos"]}, excluídos={len(meta_report["excluidos"])}', flush=True)
    if meta_report['excluidos']:
        for skipped in meta_report['excluidos']:
            print(f'[FEEDS V9.4] Meta ignorado {skipped["id"]}: {skipped["motivo"]}', flush=True)

if __name__ == '__main__':
    try: run()
    except Exception as exc:
        print('[make-feed-merchantcenter] ERRO:', exc, file=sys.stderr)
        sys.exit(1)
