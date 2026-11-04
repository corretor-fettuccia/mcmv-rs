#!/usr/bin/env python3
"""Regressão V4.2.7: catálogo vazio, reconstrução forçada e atributos pt-BR."""
import json
import os
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run():
    with tempfile.TemporaryDirectory(prefix='core427-') as directory:
        root = Path(directory)
        shutil.copytree(ROOT / 'scripts', root / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        (root / 'portal-config.json').write_text(json.dumps({
            'name': 'Portal Teste', 'site_url': 'https://portal.exemplo.com.br/'
        }), encoding='utf-8')

        def row(id, attrs):
            return {
                'id': id, 'url': 'https://lp.exemplo.com.br/',
                'image': 'https://lp.exemplo.com.br/share.webp',
                'name': id, 'description': 'Descrição completa',
                'attributes': attrs,
                'gallery': ['https://lp.exemplo.com.br/share.webp'],
                'state': 'Em construção', 'minimum': 250000,
                'brand': 'Construtora Exemplo', 'condition': 'new',
                'googleEnabled': True, 'googleAvailability': 'in_stock',
            }

        payload = {
            'ok': True, 'schemaVersion': 4, 'sourceContract': 'core-imobiliario-v4',
            'snapshotComplete': True, 'totalRows': 2, 'publishedRows': 2,
            'items': [
                row('imovel_1', [
                    'piscina', 'PISCINA', '02 dormitórios', 'sala DE estar',
                    'Água quente', 'PET PLACE', '   Sacada  '
                ]),
                row('imovel_2', [
                    'Piscina', '02 DORMITÓRIOS', 'SALA DE ESTAR',
                    'agua quente', 'Pet place', 'SACADA'
                ]),
            ],
        }
        fixture = root / 'api-fixture.json'
        fixture.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        env = {**os.environ, 'PORTAL_FIXTURE': str(fixture)}
        def sync(expect_success=True):
            result = subprocess.run(
                [sys.executable, str(root / 'scripts' / 'sinc-data.py')],
                cwd=root, env=env, text=True, capture_output=True)
            if expect_success and result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            if not expect_success and not result.returncode:
                raise AssertionError('A API inválida não pode atualizar o catálogo')
            return result

        # Ausente, arquivo vazio, JSON inválido e JSON válido sem dados:
        for content in (None, '', '{inválido', '{}'):
            target = root / 'catalogo.json'
            if content is None:
                target.unlink(missing_ok=True)
            else:
                target.write_text(content, encoding='utf-8')
            sync()
            catalog = json.loads(target.read_text(encoding='utf-8'))
            assert len(catalog['items']) == 2
            assert len(catalog['empreendimentos']) == 2
            assert len(catalog['atributos_disponiveis']) == 6, catalog['atributos_disponiveis']
            assert catalog['atributos_disponiveis'] == [
                '02 Dormitórios', 'Pet place', 'Piscina',
                'Sacada', 'Sala de estar', 'Água quente'
            ], catalog['atributos_disponiveis']
            assert catalog['items'][0]['attributes'] == [
                'Piscina', '02 Dormitórios', 'Sala de estar',
                'Água quente', 'Pet place', 'Sacada'
            ]
            assert catalog['items'][1]['attributes'] == [
                'Piscina', '02 Dormitórios', 'Sala de estar',
                'Água quente', 'Pet place', 'Sacada'
            ]
            assert catalog['empreendimentos'][0]['atributos'] == catalog['items'][0]['attributes']

        # A edição na planilha replica no catálogo, inclusive substituindo o anterior.
        payload['items'][0]['attributes'] = ['jacuzzi', 'PISCINA']
        payload['items'][1]['attributes'] = ['sala de estar']
        fixture.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        sync()
        updated = json.loads((root / 'catalogo.json').read_text(encoding='utf-8'))
        assert updated['atributos_disponiveis'] == ['Jacuzzi', 'Piscina', 'Sala de estar']
        assert updated['items'][0]['attributes'] == ['Jacuzzi', 'Piscina']

        # Snapshot incompleto não deve destruir o último catálogo.
        previous = (root / 'catalogo.json').read_bytes()
        payload['snapshotComplete'] = False
        fixture.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        sync(False)
        assert (root / 'catalogo.json').read_bytes() == previous

    print('OK V4.2.7: catálogo ausente/vazio/corrompido reconstruído; 6 filtros únicos; '
          'maiúscula inicial; atualização; proteção contra API incompleta.')

if __name__ == '__main__':
    run()
