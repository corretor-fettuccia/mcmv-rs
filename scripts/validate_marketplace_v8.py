#!/usr/bin/env python3
"""Confere o feed Meta gerado a partir do catálogo da mesma execução do Core."""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from gerar_marketplace import compile_xml
from core_lib import ROOT


def run():
    catalog = json.loads((ROOT / 'catalogo.json').read_text(encoding='utf-8'))
    expected_xml, report = compile_xml(catalog)
    path = ROOT / 'marketplace-produtos.xml'
    actual = path.read_bytes()
    root = ET.fromstring(actual)
    if root.tag != 'listings':
        raise ValueError('Raiz XML Meta incorreta')
    expected_listings = ET.fromstring(expected_xml).findall('listing')
    actual_listings = root.findall('listing')
    expected_ids = [row.findtext('home_listing_id') for row in expected_listings]
    actual_ids = [row.findtext('home_listing_id') for row in actual_listings]
    if actual_ids != expected_ids:
        raise ValueError('Feed Marketplace diverge do catálogo sincronizado nesta execução')
    if len(actual_ids) != report['incluidos']:
        raise ValueError('Feed Marketplace não corresponde à contagem de elegíveis do catálogo')
    for atual, esperado in zip(actual_listings, expected_listings):
        if ET.tostring(atual, encoding='utf-8') != ET.tostring(esperado, encoding='utf-8'):
            raise ValueError('Dados do Marketplace divergem do catálogo sincronizado')
    for listing in root.findall('listing'):
        for key in ('name', 'description', 'price', 'availability', 'url'):
            if not listing.findtext(key):
                raise ValueError('Campo obrigatório ausente no anúncio: ' + key)
        if listing.find('address') is None or not listing.findall('image/url'):
            raise ValueError('Anúncio sem endereço ou imagens')
    print(f'[Meta V9.4] OK: {len(actual_ids)} anúncios, {len(report["excluidos"])} excluídos.')


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        print('::error::Validação Marketplace V8:', exc, file=sys.stderr)
        sys.exit(1)
