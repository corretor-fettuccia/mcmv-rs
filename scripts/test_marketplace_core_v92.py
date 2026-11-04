#!/usr/bin/env python3
"""Regressão V9.2: Marketplace deve estar na sequência do Core e não escondido no staging."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class MarketplaceCoreV92(unittest.TestCase):
    def test_core_original_jobs_e_meta_na_etapa_merchant(self):
        workflow=(ROOT/'.github/workflows/core-imobiliario.yml').read_text(encoding='utf-8')
        for fragment in ('  merchant:', '  sitemap:', '  subpage:', 'name: 5 - Validar e montar site para Pages',
                         '2/4 Gerar feeds Merchant + Marketplace',
                         'Conferir XML Google e Meta gerados no mesmo job', 'python -u scripts/validate_marketplace_v8.py'):
            self.assertIn(fragment, workflow)
        self.assertNotIn('  marketplace:', workflow)
        self.assertNotIn('name: core-v4-marketplace', workflow)

    def test_staging_somente_copia_feeds(self):
        src=(ROOT/'scripts/stage_pages_v421.py').read_text(encoding='utf-8')
        self.assertIn('validate_marketplace()', src)
        self.assertNotIn('compile_xml(', src)
        merchant = (ROOT / 'scripts/make-feed-merchantcenter.py').read_text(encoding='utf-8')
        self.assertIn('compile_xml(catalog)', merchant)
        self.assertIn("ROOT / 'merchant-produtos.xml'", merchant)
        self.assertIn("ROOT / 'marketplace-produtos.xml'", merchant)

    def test_missing_meta_blocks_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            local=Path(tmp)
            shutil.copytree(ROOT/'scripts',local/'scripts')
            (local/'catalogo.json').write_text('{}',encoding='utf-8')
            (local/'merchant-produtos.xml').write_text('<rss/>',encoding='utf-8')
            proc=subprocess.run([sys.executable, str(local/'scripts/stage_pages_v421.py')],
                                cwd=local,capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn('Arquivo obrigatório ausente antes da montagem: marketplace-produtos.xml',proc.stderr)
            self.assertFalse((local/'_site').exists())

if __name__=='__main__': unittest.main()
