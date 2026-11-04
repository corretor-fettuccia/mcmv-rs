#!/usr/bin/env python3
"""Teste de regressão sem rede: 4 anúncios legados -> 2 anúncios V4 com atributos.
Rode: python3 scripts/test_snapshot_v417.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent


def run():
    with tempfile.TemporaryDirectory(prefix='core417-') as tmp:
        root = Path(tmp) / 'portal'
        shutil.copytree(SOURCE, root, ignore=shutil.ignore_patterns('__pycache__'))
        # Simula a produção anterior com 4 anúncios sem atributos.
        legacy = SOURCE.parent / 'testes' / 'catalogo_legado_4_registros.json'
        if legacy.exists(): shutil.copy2(legacy, root / 'catalogo.json')
        items = [
            {'id': 'LINQ-ID-1', 'url': 'https://exemplo.org/linq', 'image': 'https://exemplo.org/share.webp',
             'name': 'Imóvel com sacada', 'description': 'Apartamento com sacada e churrasqueira',
             'highlight': 'Apartamento com sacada', 'attributes': ['Sacada', 'Churrasqueira'],
             'gallery': ['https://exemplo.org/share.webp'], 'state': 'Em construção',
             'minimum': 250000, 'maximum': 350000, 'googleEnabled': True,
             'googleAvailability': 'in_stock', 'brand': 'Construtora exemplo', 'condition': 'new'},
            {'id': 'MEZZANO-ID-2', 'url': 'https://exemplo.org/mezzano', 'image': 'https://exemplo.org/image.webp',
             'name': 'Imóvel com piscina', 'description': 'Apartamento com piscina no rooftop',
             'highlight': 'Apartamento com rooftop', 'attributes': ['Sacada', 'Piscina', 'Rooftop'],
             'gallery': ['https://exemplo.org/image.webp'], 'state': 'Em construção',
             'minimum': 500000, 'maximum': 530000, 'googleEnabled': False,
             'googleAvailability': '', 'brand': 'Construtora exemplo', 'condition': 'new'},
        ]
        payload = {'ok': True, 'schemaVersion': 4, 'sourceContract': 'core-imobiliario-v4',
                   'snapshotComplete': True, 'totalRows': 2, 'publishedRows': 2,
                   'items': items, 'config': {'simuladorAtivo': True, 'faixasRenda': []}}
        fixture = Path(tmp) / 'api.json'
        fixture.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        env = dict(os.environ, PORTAL_FIXTURE=str(fixture))
        build = [sys.executable, str(root / 'scripts' / 'build_portal_v4.py')]
        result = subprocess.run(build, cwd=root, env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        catalog = json.loads((root / 'catalogo.json').read_text(encoding='utf-8'))
        assert len(catalog['items']) == 2, catalog['items']
        assert catalog['filtros']['atributos'] == ['Churrasqueira', 'Piscina', 'Rooftop', 'Sacada']
        assert catalog['empreendimentos'][0]['atributos']==catalog['items'][0]['attributes']
        assert len(catalog['empreendimentos']) == 2
        assert (root / 'imoveis' / 'LINQ-ID-1' / 'index.html').exists()
        assert (root / 'imoveis' / 'MEZZANO-ID-2' / 'index.html').exists()
        assert len(ET.parse(root / 'merchant-produtos.xml').findall('.//item')) == 1
        snapshot = (root / 'catalogo.json').read_bytes()
        payload['publishedRows'] = 1
        fixture.write_text(json.dumps(payload), encoding='utf-8')
        result = subprocess.run(build, cwd=root, env=env, text=True, capture_output=True)
        assert result.returncode != 0 and (root / 'catalogo.json').read_bytes() == snapshot
        print('OK: migração 4->2, atributos, páginas, Merchant e proteção contra snapshot incoerente.')

if __name__ == '__main__':
    run()
