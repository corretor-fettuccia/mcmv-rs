#!/usr/bin/env python3
"""V9.4: regressão integral dos dois feeds, sitemap de imagens e publicação Pages.

Executar: python3 -m unittest discover -s scripts -p 'test_*.py'
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from merchant_from_catalog import build as build_merchant
from gerar_marketplace import compile_xml
from test_pipeline_v420 import record

HERE = Path(__file__).resolve().parents[1]
SM = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
IM = '{http://www.google.com/schemas/sitemap-image/1.1}'


class MotoresV94(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mcmv-v94-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(HERE / 'scripts', self.root / 'scripts',
                        ignore=shutil.ignore_patterns('__pycache__'))
        for filename in ('index.html', 'app.js', 'config.js', 'CNAME'):
            shutil.copy2(HERE / filename, self.root / filename)
        (self.root / 'portal-config.json').write_text(json.dumps({
            'name': 'MCMV-RS', 'site_url': 'https://portal.example.com/'
        }), encoding='utf-8')
        first = record('empreendimento_01', ['Piscina', 'Sacada'], True)
        first['gallery'] = [first['image'],
                            'https://fotos.example.com/ambiente?a=1&b=2.webp',
                            'https://fotos.example.com/ambiente?a=1&b=2.webp',
                            'file:///etc/passwd']
        second = record('empreendimento_02', ['Rooftop'], False)
        second['gallery'] = [second['image'], 'https://fotos.example.com/rooftop.webp']
        self.payload = {
            'ok': True, 'schemaVersion': 4, 'sourceContract': 'core-imobiliario-v4',
            'snapshotComplete': True, 'totalRows': 2, 'publishedRows': 2,
            'items': [first, second]
        }
        self.source = self.root / 'api-fixture.json'

    def cmd(self, script):
        env = {**os.environ, 'PORTAL_FIXTURE': str(self.source)}
        result = subprocess.run([sys.executable, str(self.root/'scripts'/script)],
                                cwd=self.root, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f'{script}: {result.stdout}\n{result.stderr}')
        return result.stdout

    def build(self):
        self.source.write_text(json.dumps(self.payload, ensure_ascii=False), encoding='utf-8')
        for engine in ('sinc-data.py', 'make-feed-merchantcenter.py',
                       'make-sitemap.py', 'make-subpage.py',
                       'validate_marketplace_v8.py', 'validate_portal_v420.py',
                       'stage_pages_v421.py', 'validate_pages_v421.py'):
            self.cmd(engine)
        return json.loads((self.root/'catalogo.json').read_text(encoding='utf-8'))

    def test_um_motor_gera_e_publica_ambos_feeds_junto_com_sitemap(self):
        catalog = self.build()
        feed_google = (self.root/'merchant-produtos.xml').read_bytes()
        feed_meta = (self.root/'marketplace-produtos.xml').read_bytes()
        self.assertEqual(feed_google, build_merchant(catalog))  # Merchant sem mudanças
        self.assertEqual(feed_meta, compile_xml(catalog)[0])
        self.assertEqual(len(ET.fromstring(feed_google).findall('./channel/item')), 1)
        self.assertEqual(len(ET.fromstring(feed_meta).findall('listing')), 2)
        for filename in ('catalogo.json', 'merchant-produtos.xml',
                         'marketplace-produtos.xml', 'sitemap.xml', 'robots.txt'):
            self.assertEqual((self.root/filename).read_bytes(),
                             (self.root/'_site'/filename).read_bytes(), filename)
        root = ET.parse(self.root/'_site/sitemap.xml').getroot()
        self.assertEqual(len(root.findall(SM+'url')), 3)
        self.assertEqual([node.findtext(SM+'loc') for node in root.findall(SM+'url')],
                         ['https://portal.example.com/'] + [x['pageUrl'] for x in catalog['items']])
        first_page = root.findall(SM+'url')[1]
        self.assertEqual([x.text for x in first_page.findall(IM+'image/'+IM+'loc')],
                         [catalog['items'][0]['image'], 'https://fotos.example.com/ambiente?a=1&b=2.webp'])
        self.assertEqual(len(root.findall(IM+'image')), 0)  # imagens somente dentro das URLs
        self.assertIn('Sitemap: https://portal.example.com/sitemap.xml',
                      (self.root/'_site/robots.txt').read_text())

    def test_inativacao_remove_pagina_e_imagens_do_sitemap_e_ambos_feeds(self):
        self.build()
        self.payload['items'] = [self.payload['items'][0]]
        self.payload['publishedRows'] = 1
        catalog = self.build()
        self.assertEqual(len(ET.fromstring((self.root/'marketplace-produtos.xml').read_bytes()).findall('listing')), 1)
        urls = [x.text for x in ET.parse(self.root/'_site/sitemap.xml').findall('.//'+SM+'loc')]
        self.assertNotIn('https://portal.example.com/imoveis/empreendimento_02/', urls)
        self.assertNotIn('rooftop.webp', (self.root/'_site/sitemap.xml').read_text(encoding='utf-8'))
        self.assertEqual(len(catalog['items']), 1)

    def test_sem_imovel_meta_elegivel_ainda_gera_xml_sem_inventar_ofertas(self):
        self.payload['items'][0]['marketplaceEnabled'] = False
        self.payload['items'][1]['marketplaceEnabled'] = False
        catalog = self.build()
        self.assertEqual(len(ET.fromstring((self.root/'_site/marketplace-produtos.xml').read_bytes()).findall('listing')), 0)
        self.assertEqual((self.root/'_site/merchant-produtos.xml').read_bytes(), build_merchant(catalog))

    def test_workflow_merchant_entrega_ambos_no_mesmo_artefato(self):
        workflow = (HERE/'.github/workflows/make-feed-merchantcenter.yml').read_text(encoding='utf-8')
        core = (HERE/'.github/workflows/core-imobiliario.yml').read_text(encoding='utf-8')
        self.assertIn('python -u scripts/make-feed-merchantcenter.py', workflow)
        self.assertIn('merchant-produtos.xml\n            marketplace-produtos.xml', workflow)
        self.assertIn('name: core-v4-merchant', workflow)
        self.assertIn('2/4 Gerar feeds Merchant + Marketplace', core)
        self.assertNotIn('python -u scripts/gerar_marketplace.py', core)
        self.assertIn('test -s _site/marketplace-produtos.xml', core)
        self.assertIn('test -s _site/sitemap.xml', core)


if __name__ == '__main__':
    unittest.main()
