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
        self.assertLess(core.index('  merchant:'), core.index('  sitemap:'))
        self.assertLess(core.index('  sitemap:'), core.index('  subpage:'))
        self.assertIn('needs: merchant', core)
        self.assertIn('2/4 Gerar feeds Merchant + Marketplace', core)
        merchant = (BASE/'.github/workflows/make-feed-merchantcenter.yml').read_text(encoding='utf-8')
        self.assertIn('marketplace-produtos.xml', merchant)
        self.assertIn('merchant-produtos.xml', merchant)
        self.assertNotIn('uses: ./.github/workflows/gerar-marketplace.yml', core)
        self.assertIn('needs: subpage', core)
        self.assertIn('scripts/stage_pages_v421.py', core)
        self.assertIn('name: core-v4-catalogo', core)
        self.assertNotIn('name: core-v4-marketplace', core)
        self.assertNotIn('git push', core)

    def test_both_feeds_use_same_catalog_and_enter_pages(self):
        source = fixture()
        google = merchant_build(source)
        meta, _ = compile_xml(source)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'catalogo.json').write_text(json.dumps(source), encoding='utf8')
            (root / 'merchant-produtos.xml').write_bytes(google)
            # Meta ja gerado na etapa preparar, staging verifica e recria quando necessario.
            (root / 'marketplace-produtos.xml').write_bytes(meta)
            (root / 'index.html').write_text('<h1>teste</h1>', encoding='utf8')
            (root / 'sitemap.xml').write_text('<urlset/>', encoding='utf8')
            (root / 'robots.txt').write_text('User-agent: *', encoding='utf8')
            (root / 'llms.txt').write_text('Portal', encoding='utf8')
            with patch.object(stage_pages_v421, 'ROOT', root), patch.object(stage_pages_v421, 'DEST', root / '_site'), patch.object(validate_marketplace_v8, 'ROOT', root):
                stage_pages_v421.run()
            self.assertEqual((root / '_site/merchant-produtos.xml').read_bytes(), google)
            self.assertEqual((root / '_site/marketplace-produtos.xml').read_bytes(), meta)
            self.assertEqual(ET.fromstring(google).find('./channel/item') is not None, True)
            self.assertEqual(ET.fromstring(meta).find('listing') is not None, True)

    def test_meta_invalido_bloqueia_deploy_mas_preserva_merchant(self):
        source = fixture()
        source['items'][0]['marketplaceEnabled'] = False
        google = merchant_build(source)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'catalogo.json').write_text(json.dumps(source), encoding='utf8')
            (root / 'merchant-produtos.xml').write_bytes(google)
            (root / 'marketplace-produtos.xml').write_text('antigo', encoding='utf8')
            with patch.object(stage_pages_v421, 'ROOT', root), patch.object(stage_pages_v421, 'DEST', root / '_site'), patch.object(validate_marketplace_v8, 'ROOT', root):
                with self.assertRaises(RuntimeError):
                    stage_pages_v421.run()
            self.assertEqual((root / 'merchant-produtos.xml').read_bytes(), google)
            self.assertFalse((root / '_site').exists())

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
