#!/usr/bin/env python3
"""Regressões: feed gerado no motor 2, montagem nunca reescreve o XML."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from test_integracao_feeds_v6 import fixture
from merchant_from_catalog import build
import stage_pages_v421
import validate_marketplace_v8

class FallbackV93(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        doc = fixture()
        (self.root/'catalogo.json').write_text(json.dumps(doc), encoding='utf-8')
        self.merchant = build(doc)
        (self.root/'merchant-produtos.xml').write_bytes(self.merchant)
        (self.root/'index.html').write_text('<h1>Portal</h1>', encoding='utf-8')
        (self.root/'sitemap.xml').write_text('<urlset/>', encoding='utf-8')
        (self.root/'robots.txt').write_text('User-agent: *', encoding='utf-8')
        (self.root/'llms.txt').write_text('Portal', encoding='utf-8')
        self.patches = [patch.object(stage_pages_v421, 'ROOT', self.root),
                        patch.object(stage_pages_v421, 'DEST', self.root/'_site'),
                        patch.object(validate_marketplace_v8, 'ROOT', self.root)]
        for obj in self.patches: obj.start()

    def tearDown(self):
        for obj in reversed(self.patches): obj.stop()
        self.tmp.cleanup()

    def test_sem_feed_meta_preexistente_falha_explicitamente(self):
        self.assertFalse((self.root/'marketplace-produtos.xml').exists())
        with self.assertRaisesRegex(RuntimeError, 'marketplace-produtos.xml'):
            stage_pages_v421.run()
        self.assertFalse((self.root/'_site').exists())
        self.assertEqual((self.root/'merchant-produtos.xml').read_bytes(), self.merchant)

    def test_feed_meta_obsoleto_e_rejeitado_e_google_intacto(self):
        (self.root/'marketplace-produtos.xml').write_text('<feed>antigo</feed>', encoding='utf-8')
        with self.assertRaises(Exception):
            stage_pages_v421.run()
        self.assertEqual((self.root/'merchant-produtos.xml').read_bytes(), self.merchant)
        self.assertFalse((self.root/'_site').exists())

    def test_falha_catalogo_nao_apaga_site_previamente_publicado(self):
        (self.root/'_site').mkdir()
        (self.root/'_site/index.html').write_text('versao anterior',encoding='utf-8')
        doc=fixture()
        doc['items'][0]['minimum']=None
        (self.root/'catalogo.json').write_text(json.dumps(doc),encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'marketplace-produtos.xml'):
            stage_pages_v421.run()
        self.assertEqual((self.root/'_site/index.html').read_text(), 'versao anterior')
        self.assertEqual((self.root/'merchant-produtos.xml').read_bytes(), self.merchant)

if __name__=='__main__':unittest.main()
