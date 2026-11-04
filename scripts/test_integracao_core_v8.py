"""Regressões V8: orquestração, artefatos e preservação do feed Google."""
import json
import tempfile
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from gerar_marketplace import compile_xml
from merchant_from_catalog import build as merchant_build
import stage_pages_v421
import validate_marketplace_v8
from test_integracao_feeds_v6 import fixture

BASE = Path(__file__).resolve().parent.parent


class TestCoreV8(unittest.TestCase):
    def test_chain_downloads_same_snapshot_and_both_feeds(self):
        core = (BASE / '.github/workflows/core-imobiliario.yml').read_text(encoding='utf-8')
        meta = (BASE / '.github/workflows/gerar-marketplace.yml').read_text(encoding='utf-8')
        self.assertLess(core.index('  merchant:'), core.index('  marketplace:'))
        self.assertLess(core.index('  marketplace:'), core.index('  sitemap:'))
        self.assertIn('needs: merchant', core)
        self.assertIn('needs: marketplace', core)
        self.assertIn('name: core-v4-marketplace', core)
        self.assertIn('needs: subpage', core)
        self.assertIn('python -u scripts/validate_marketplace_v8.py', core)
        self.assertIn('workflow_call:', meta)
        self.assertIn('name: core-v4-catalogo', meta)
        self.assertIn('name: core-v4-marketplace', meta)
        self.assertIn('--source catalogo.json', meta)
        self.assertNotIn('git push', meta)

    def test_both_feeds_use_same_catalog_and_enter_pages(self):
        source = fixture()
        google = merchant_build(source)
        meta, _ = compile_xml(source)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'catalogo.json').write_text(json.dumps(source), encoding='utf8')
            (root / 'merchant-produtos.xml').write_bytes(google)
            (root / 'marketplace-produtos.xml').write_bytes(meta)
            (root / 'index.html').write_text('<h1>teste</h1>', encoding='utf8')
            with patch.object(validate_marketplace_v8, 'ROOT', root):
                validate_marketplace_v8.run()
            with patch.object(stage_pages_v421, 'ROOT', root), patch.object(stage_pages_v421, 'DEST', root / '_site'):
                stage_pages_v421.run()
            self.assertEqual((root / '_site/merchant-produtos.xml').read_bytes(), google)
            self.assertEqual((root / '_site/marketplace-produtos.xml').read_bytes(), meta)
            self.assertEqual(ET.fromstring(google).find('./channel/item') is not None, True)
            self.assertEqual(ET.fromstring(meta).find('listing') is not None, True)

    def test_validator_rejects_stale_meta_from_previous_catalog(self):
        snapshot = fixture()
        meta, _ = compile_xml(snapshot)
        snapshot['items'][0]['name'] = 'Novo nome'
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'catalogo.json').write_text(json.dumps(snapshot), encoding='utf8')
            (root / 'marketplace-produtos.xml').write_bytes(meta)
            with patch.object(validate_marketplace_v8, 'ROOT', root):
                with self.assertRaises(ValueError):
                    validate_marketplace_v8.run()


if __name__ == '__main__':
    unittest.main()
