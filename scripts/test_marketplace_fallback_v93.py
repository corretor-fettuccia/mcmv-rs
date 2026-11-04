#!/usr/bin/env python3
"""Garante que o Core legado (etapa 5) publica os dois feeds sem workflow Meta."""
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
        self.patches = [patch.object(stage_pages_v421, 'ROOT', self.root),
                        patch.object(stage_pages_v421, 'DEST', self.root/'_site'),
                        patch.object(validate_marketplace_v8, 'ROOT', self.root)]
        for obj in self.patches: obj.start()

    def tearDown(self):
        for obj in reversed(self.patches): obj.stop()
        self.tmp.cleanup()

    def test_sem_feed_meta_preexistente_cria_e_publica(self):
        self.assertFalse((self.root/'marketplace-produtos.xml').exists())
        stage_pages_v421.run()
        a=self.root/'_site'
        self.assertEqual((a/'merchant-produtos.xml').read_bytes(), self.merchant)
        feed=ET.parse(a/'marketplace-produtos.xml').getroot()
        self.assertEqual(feed.tag,'listings')
        self.assertEqual(len(feed.findall('listing')),1)
        self.assertFalse((a/'scripts').exists())

    def test_feed_meta_obsoleto_e_regerado_e_google_intacto(self):
        (self.root/'marketplace-produtos.xml').write_text('<feed>antigo</feed>', encoding='utf-8')
        stage_pages_v421.run()
        self.assertEqual(ET.parse(self.root/'_site/marketplace-produtos.xml').getroot().tag, 'listings')
        self.assertEqual((self.root/'merchant-produtos.xml').read_bytes(), self.merchant)

    def test_falha_catalogo_nao_apaga_site_previamente_publicado(self):
        (self.root/'_site').mkdir()
        (self.root/'_site/index.html').write_text('versao anterior',encoding='utf-8')
        doc=fixture()
        doc['items'][0]['minimum']=None
        (self.root/'catalogo.json').write_text(json.dumps(doc),encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'Nao foi possivel gerar Marketplace'):
            stage_pages_v421.run()
        self.assertEqual((self.root/'_site/index.html').read_text(), 'versao anterior')
        self.assertEqual((self.root/'merchant-produtos.xml').read_bytes(), self.merchant)

if __name__=='__main__':unittest.main()
