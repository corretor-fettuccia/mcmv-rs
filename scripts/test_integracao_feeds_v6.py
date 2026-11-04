"""Regressão V6: duas saídas independentes derivadas do mesmo catálogo."""
import tempfile
import shutil
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from gerar_marketplace import compile_xml
from merchant_from_catalog import build as build_merchant, G
import stage_pages_v421


def fixture():
    return {
        'schemaVersion': 4,
        'sourceContract': 'core-imobiliario-v4',
        'snapshotComplete': True,
        'total_empreendimentos': 1,
        'nome': 'MCMV-RS',
        'url_principal': 'https://mcmv-rs.com.br/',
        'items': [{
            'id': 'teste-01', 'merchantId': 'merchant-01',
            'name': 'Apartamento de teste', 'highlight': '2 dormitórios',
            'description': 'Apartamento com sacada e churrasqueira',
            'city': 'Canoas', 'uf': 'RS', 'address': 'Rua Exemplo, 100',
            'image': 'https://exemplo.com/principal.webp',
            'gallery': ['https://exemplo.com/principal.webp',
                        'https://exemplo.com/segunda.webp'],
            'pageUrl': 'https://mcmv-rs.com.br/imoveis/teste-01/',
            'url': 'https://exemplo.com/imovel', 'minimum': 250000,
            'googleEnabled': True, 'googleAvailability': 'in_stock',
            'brand': 'Construtora teste', 'condition': 'new',
        }],
    }


class IntegracaoFeedsV6(unittest.TestCase):
    def test_google_e_meta_geram_xmls_diferentes_sem_dependencia(self):
        catalog = fixture()
        google_before = build_merchant(catalog)
        meta_xml, stats = compile_xml(catalog)
        self.assertEqual(stats['incluidos'], 1)
        self.assertEqual(ET.fromstring(google_before).findtext(
            f'./channel/item/{{{G}}}id'), 'merchant-01')
        self.assertEqual(ET.fromstring(meta_xml).findtext(
            'listing/home_listing_id'), 'teste-01')
        self.assertEqual(len(ET.fromstring(meta_xml).findall('listing/image/url')), 2)
        self.assertEqual(build_merchant(catalog), google_before)

    def test_meta_desativado_nao_afeta_google(self):
        catalog = fixture()
        catalog['items'][0]['marketplaceEnabled'] = False
        google_xml = build_merchant(catalog)
        self.assertEqual(len(ET.fromstring(google_xml).findall('./channel/item')), 1)
        with self.assertRaises(ValueError):
            compile_xml(catalog)

    def test_google_desativado_nao_afeta_meta(self):
        catalog = fixture()
        catalog['items'][0]['googleEnabled'] = False
        google_xml = build_merchant(catalog)
        self.assertEqual(len(ET.fromstring(google_xml).findall('./channel/item')), 0)
        meta_xml, _ = compile_xml(catalog)
        self.assertEqual(len(ET.fromstring(meta_xml).findall('listing')), 1)

    def test_core_nao_exige_workflow_marketplace(self):
        scripts = Path(__file__).resolve().parent
        src = scripts.parent / '.github' / 'workflows'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dst = root / '.github' / 'workflows'
            dst.mkdir(parents=True)
            (root / 'scripts').mkdir()
            for workflow in ('core-imobiliario.yml', 'sinc-data.yml',
                             'make-feed-merchantcenter.yml', 'make-sitemap.yml',
                             'make-subpage.yml'):
                shutil.copy2(src / workflow, dst / workflow)
            for audit in ('auditar_workflows_v425.py', 'check_workflows_v423.py'):
                shutil.copy2(scripts / audit, root / 'scripts' / audit)
                result = subprocess.run([sys.executable, str(root / 'scripts' / audit)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_publicador_copia_ambos_xmls_sem_alterar_fontes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'index.html').write_text('<h1>Portal</h1>', encoding='utf-8')
            (root/'merchant-produtos.xml').write_bytes(build_merchant(fixture()))
            (root/'marketplace-produtos.xml').write_bytes(compile_xml(fixture())[0])
            output = root/'_site'
            with patch.object(stage_pages_v421, 'ROOT', root),                  patch.object(stage_pages_v421, 'DEST', output):
                stage_pages_v421.run()
            for name in ('merchant-produtos.xml', 'marketplace-produtos.xml'):
                self.assertEqual((output/name).read_bytes(), (root/name).read_bytes())
                ET.parse(output/name)


if __name__ == '__main__':
    unittest.main()
