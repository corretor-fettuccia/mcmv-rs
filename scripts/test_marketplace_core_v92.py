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
    def test_marketplace_job_is_required(self):
        workflow=(ROOT/'.github/workflows/core-imobiliario.yml').read_text(encoding='utf-8')
        for fragment in ('  marketplace:', 'needs: merchant', 'needs: marketplace',
                         'name: core-v4-marketplace', 'python -u scripts/gerar_marketplace.py',
                         'python -u scripts/validate_marketplace_v8.py'):
            self.assertIn(fragment, workflow)
        self.assertEqual(workflow.count('name: core-v4-marketplace'), 2)

    def test_staging_does_not_generate_feed_or_skip_missing(self):
        src=(ROOT/'scripts/stage_pages_v421.py').read_text(encoding='utf-8')
        self.assertNotIn('compile_xml(', src)
        self.assertNotIn('unlink(missing_ok=True)', src)
        self.assertIn('marketplace-produtos.xml', src)
        self.assertIn('validate_marketplace()', src)

    def test_missing_meta_blocks_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            local=Path(tmp)
            shutil.copytree(ROOT/'scripts',local/'scripts')
            (local/'catalogo.json').write_text('{}',encoding='utf-8')
            (local/'merchant-produtos.xml').write_text('<rss/>',encoding='utf-8')
            proc=subprocess.run([sys.executable, str(local/'scripts/stage_pages_v421.py')],
                                cwd=local,capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn('marketplace-produtos.xml',proc.stderr)
            self.assertFalse((local/'_site').exists())

if __name__=='__main__': unittest.main()
