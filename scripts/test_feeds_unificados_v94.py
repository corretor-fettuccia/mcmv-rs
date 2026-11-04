#!/usr/bin/env python3
"""V9.4: motor unico Merchant+Marketplace, sitemap com imagens, contrato dos XMLs e workflows. Sem rede."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import stage_pages_v421
import validate_marketplace_v8
import validate_xml_v94 as V
import verify_public_v94
from gerar_marketplace import compile_xml
from merchant_from_catalog import build as merchant_build
from test_integracao_feeds_v6 import fixture

BASE = Path(__file__).resolve().parent.parent
SITE = 'https://teste.example.com/'
WF = BASE / '.github' / 'workflows'


def row(uid, **over):
    base = {'id': uid, 'url': f'https://lp.example.com/{uid}/', 'image': f'https://img.example.com/{uid}/capa.webp',
            'name': f'Imóvel {uid}', 'description': 'Descrição completa.', 'highlight': 'Resumo',
            'gallery': [f'https://img.example.com/{uid}/capa.webp', f'https://img.example.com/{uid}/sala.webp',
                        f'https://img.example.com/{uid}/sala.webp', f'https://img.example.com/{uid}/a&b.webp'],
            'attributes': ['Sacada'], 'state': 'Em construção', 'minimum': 250000, 'maximum': 300000,
            'brand': 'Construtora Exemplo', 'condition': 'new', 'merchantId': uid, 'googleEnabled': True,
            'googleAvailability': 'in_stock', 'address': 'Rua Modelo, 100', 'city': 'Canoas', 'uf': 'RS'}
    base.update(over)
    return base


class Workspace:
    """Copia temporaria do projeto + API de mentira; roda os motores como no GitHub Actions."""
    def __init__(self, items):
        self.tmp = tempfile.TemporaryDirectory(prefix='v94-')
        self.root = Path(self.tmp.name)
        shutil.copytree(BASE / 'scripts', self.root / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        (self.root / 'portal-config.json').write_text(json.dumps({'name': 'Portal Teste', 'site_url': SITE}), encoding='utf-8')
        self.set_items(items)

    def set_items(self, items):
        payload = {'ok': True, 'schemaVersion': 4, 'sourceContract': 'core-imobiliario-v4', 'snapshotComplete': True,
                   'totalRows': len(items), 'publishedRows': len(items), 'items': items}
        (self.root / 'api.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')

    def run(self, script, *args):
        env = dict(os.environ, PORTAL_FIXTURE=str(self.root / 'api.json'))
        return subprocess.run([sys.executable, str(self.root / 'scripts' / script), *args], cwd=self.root,
                              env=env, capture_output=True, text=True)

    def ok(self, script, *args):
        result = self.run(script, *args)
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    def close(self):
        self.tmp.cleanup()


class MotorUnicoDeFeeds(unittest.TestCase):
    def tearDown(self):
        getattr(self, 'ws', None) and self.ws.close()

    def test_uma_execucao_gera_os_dois_feeds_e_preserva_o_merchant(self):
        self.ws = ws = Workspace([row('a1'), row('b2', googleEnabled=False)])
        ws.ok('sinc-data.py')
        result = ws.ok('make-feed-merchantcenter.py')
        catalog = json.loads((ws.root / 'catalogo.json').read_text(encoding='utf-8'))
        # Merchant: mesmos bytes que o gerador original produziria para o mesmo catálogo
        self.assertEqual((ws.root / 'merchant-produtos.xml').read_bytes(), merchant_build(catalog))
        meta = (ws.root / 'marketplace-produtos.xml').read_bytes()
        listings = ET.fromstring(meta).findall('listing')
        self.assertEqual([x.findtext('home_listing_id') for x in listings], ['a1', 'b2'])  # Meta independe do flag Google
        self.assertEqual([u.text for u in listings[0].findall('image/url')],
                         ['https://img.example.com/a1/capa.webp', 'https://img.example.com/a1/sala.webp',
                          'https://img.example.com/a1/a&b.webp'])  # principal + galeria, sem repetir, URLs públicas
        self.assertNotIn(b'data:', meta)
        self.assertNotIn(b';base64', meta)
        self.assertIn('GERADO merchant-produtos.xml', result.stdout)
        self.assertIn('GERADO marketplace-produtos.xml', result.stdout)
        with contextlib.redirect_stdout(io.StringIO()):
            V.run(ws.root, 'feeds')  # contrato

    def test_falha_do_marketplace_nao_grava_nenhum_feed(self):
        self.ws = ws = Workspace([row('a1', address='', city='')])
        ws.ok('sinc-data.py')
        (ws.root / 'merchant-produtos.xml').write_text('anterior', encoding='utf-8')
        result = ws.run('make-feed-merchantcenter.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Marketplace (Meta) não gerado', result.stderr)
        self.assertEqual((ws.root / 'merchant-produtos.xml').read_text(encoding='utf-8'), 'anterior')
        self.assertFalse((ws.root / 'marketplace-produtos.xml').exists())

    def test_indicadores_de_publicacao_de_cada_canal(self):
        # marketplaceEnabled vindo da API (texto NAO) atravessa o catálogo e retira só o Meta
        self.ws = ws = Workspace([row('a1', googleEnabled=False), row('b2', marketplaceEnabled='NAO')])
        ws.ok('sinc-data.py')
        result = ws.ok('make-feed-merchantcenter.py')
        google = ET.parse(ws.root / 'merchant-produtos.xml').findall('./channel/item')
        meta = ET.parse(ws.root / 'marketplace-produtos.xml').findall('listing')
        self.assertEqual([i.findtext('{http://base.google.com/ns/1.0}id') for i in google], ['b2'])
        self.assertEqual([i.findtext('home_listing_id') for i in meta], ['a1'])
        self.assertIn('excluiu b2', result.stdout)

    def test_catalogo_ausente_falha(self):
        self.ws = ws = Workspace([row('a1')])
        result = ws.run('make-feed-merchantcenter.py')
        self.assertNotEqual(result.returncode, 0)


class SitemapComImagens(unittest.TestCase):
    def tearDown(self):
        self.ws.close()

    def test_pagina_principal_imoveis_e_imagens_sem_repeticao(self):
        self.ws = ws = Workspace([row('a1'), row('b2')])
        ws.ok('sinc-data.py')
        ws.ok('make-sitemap.py')
        data = (ws.root / 'sitemap.xml').read_bytes()
        self.assertTrue(data.startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn(b'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"', data)
        self.assertIn(b'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"', data)
        self.assertIn(b'a&amp;b.webp', data)  # & escapado
        items = json.loads((ws.root / 'catalogo.json').read_text(encoding='utf-8'))['items']
        pages = V.check_sitemap(data, SITE, items)
        self.assertEqual(list(pages), [SITE, SITE + 'imoveis/a1/', SITE + 'imoveis/b2/'])
        self.assertEqual(pages[SITE], [])
        self.assertEqual(pages[SITE + 'imoveis/a1/'], ['https://img.example.com/a1/capa.webp',
                         'https://img.example.com/a1/sala.webp', 'https://img.example.com/a1/a&b.webp'])
        self.assertNotIn('b2', ''.join(pages[SITE + 'imoveis/a1/']))  # imagem de um imóvel não vaza para outro

    def test_imovel_desativado_sai_do_sitemap(self):
        self.ws = ws = Workspace([row('a1'), row('b2')])
        ws.ok('sinc-data.py')
        ws.ok('make-sitemap.py')
        ws.set_items([row('a1')])  # b2 deixou de ser publicado na planilha
        ws.ok('sinc-data.py')
        ws.ok('make-sitemap.py')
        text = (ws.root / 'sitemap.xml').read_text(encoding='utf-8')
        self.assertIn('/imoveis/a1/', text)
        self.assertNotIn('b2', text)

    def test_catalogo_vazio_gera_sitemap_so_com_a_principal(self):
        self.ws = ws = Workspace([])
        ws.ok('sinc-data.py')
        ws.ok('make-sitemap.py')
        self.assertEqual(list(V.check_sitemap((ws.root / 'sitemap.xml').read_bytes(), SITE, [])), [SITE])


class ContratoDosXml(unittest.TestCase):
    def setUp(self):
        self.catalog = fixture()
        self.meta = compile_xml(self.catalog)[0]
        self.google = merchant_build(self.catalog)

    def bad(self, check, data, old, new, *extra):
        with self.assertRaises(ValueError):
            check(data.replace(old, new), *extra)

    def test_feeds_validos(self):
        self.assertEqual(V.check_merchant(self.google), ['merchant-01'])
        self.assertEqual(list(V.check_marketplace(self.meta, self.catalog['items'])), ['teste-01'])

    def test_merchant_sem_itens_e_valido_mas_rss_quebrado_nao(self):
        with contextlib.redirect_stdout(io.StringIO()):
            empty = merchant_build({**self.catalog, 'items': []})
        self.assertEqual(V.check_merchant(empty), [])
        self.bad(V.check_merchant, self.google, b'<rss ', b'<feed ')
        self.bad(V.check_merchant, self.google, b'250000.00 BRL', b'250000 BRL')
        self.bad(V.check_merchant, self.google, b'in_stock', b'instock')
        self.bad(V.check_merchant, self.google, b'https://exemplo.com/imovel', b'http://exemplo.com/imovel')
        with self.assertRaises(ValueError):
            V.check_merchant(self.google[:-40])  # XML truncado

    def test_merchant_id_repetido(self):
        root = ET.fromstring(self.google)
        root.find('channel').append(root.find('./channel/item'))
        with self.assertRaises(ValueError):
            V.check_merchant(ET.tostring(root))

    def test_marketplace_campos_obrigatorios_e_formatos(self):
        for old, new in [(b'<availability>for_sale', b'<availability>in_stock'),
                         (b'250000.00 BRL', b'0.00 BRL'),
                         (b'<home_listing_id>teste-01</home_listing_id>', b''),
                         (b'name="city"', b'name="cidade"'),
                         (b'<url>https://exemplo.com/principal.webp</url>', b'<url>data:image/png;base64,AAAA</url>'),
                         (b'https://exemplo.com/segunda.webp', b'https://exemplo.com/principal.webp'),  # imagem repetida
                         (b'<listings>', b'<lista>'),
                         (b'rel="self"', b'rel="x"')]:
            with self.subTest(new=new):
                self.bad(V.check_marketplace, self.meta, old, new)

    def test_marketplace_vazio_ou_divergente_do_catalogo(self):
        with self.assertRaises(ValueError):
            V.check_marketplace(b'<listings><title>x</title><link rel="self" href="https://a.com/marketplace-produtos.xml"/></listings>')
        changed = json.loads(json.dumps(self.catalog['items']))
        changed[0]['gallery'].append('https://exemplo.com/terceira.webp')  # catálogo mais novo que o XML
        with self.assertRaises(ValueError):
            V.check_marketplace(self.meta, changed)

    def sitemap(self, extra=''):
        item = self.catalog['items'][0]
        return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
                '<url><loc>https://mcmv-rs.com.br/</loc></url>\n'
                f'<url><loc>{item["pageUrl"]}</loc>'
                + ''.join(f'<image:image><image:loc>{u}</image:loc></image:image>' for u in item['gallery']) + extra
                + '</url>\n</urlset>\n').encode()

    def test_sitemap_valido_e_defeitos(self):
        site = 'https://mcmv-rs.com.br/'
        V.check_sitemap(self.sitemap(), site, self.catalog['items'])
        dup_image = '<image:image><image:loc>https://exemplo.com/principal.webp</image:loc></image:image>'
        for label, data in [('imagem repetida', self.sitemap(dup_image)),
                            ('sem namespace image', self.sitemap().replace(b'xmlns:image=', b'xmlns:img=')),
                            ('url repetida', self.sitemap().replace(b'</urlset>', b'<url><loc>https://mcmv-rs.com.br/</loc></url></urlset>')),
                            ('imagem http', self.sitemap().replace(b'https://exemplo.com/segunda', b'http://exemplo.com/segunda')),
                            ('principal fora do topo', self.sitemap().replace(b'<url><loc>https://mcmv-rs.com.br/</loc></url>\n', b'')),
                            ('sem declaração', self.sitemap().replace(b'<?xml version="1.0" encoding="UTF-8"?>\n', b''))]:
            with self.subTest(label), self.assertRaises(ValueError):
                V.check_sitemap(data, site, self.catalog['items'])

    def test_sitemap_com_pagina_fora_do_catalogo(self):
        with self.assertRaises(ValueError):
            V.check_sitemap(self.sitemap(), 'https://mcmv-rs.com.br/', [])  # catálogo sem o imóvel: página desativada


class EstruturaDosWorkflows(unittest.TestCase):
    def read(self, name):
        return (WF / name).read_text(encoding='utf-8')

    def test_motor_02_gera_dois_feeds_valida_e_publica_um_artefato(self):
        feeds = self.read('make-feed-merchantcenter.yml')
        self.assertEqual(feeds.count('scripts/make-feed-merchantcenter.py'), 1)  # um único gerador
        self.assertLess(feeds.index('make-feed-merchantcenter.py'), feeds.index('validate_xml_v94.py --check feeds'))
        self.assertLess(feeds.index('validate_xml_v94.py --check feeds'), feeds.index('upload-artifact'))
        for name in ('merchant-produtos.xml', 'marketplace-produtos.xml'):
            self.assertIn('            ' + name, feeds)
        self.assertIn('name: core-v4-feeds', feeds)
        self.assertIn('if-no-files-found: error', feeds)

    def test_core_e_o_unico_orquestrador_na_ordem_do_contrato(self):
        core = self.read('core-imobiliario.yml')
        order = ['  sinc_data:', '  merchant:', '  sitemap:', '  subpage:', '  preparar:', '  publicar:', '  verificar_publicacao:']
        positions = [core.index(x) for x in order]
        self.assertEqual(positions, sorted(positions))
        for needs in ('needs: sinc_data', 'needs: merchant', 'needs: sitemap', 'needs: subpage', 'needs: preparar', 'needs: publicar'):
            self.assertIn(needs, core)
        self.assertIn('name: core-v4-feeds', core)
        self.assertNotIn('gerar_marketplace.py', core)  # nada de gerar Meta fora do motor 02
        self.assertNotIn('gerar-marketplace.yml', core)
        prep = core[core.index('  preparar:'):core.index('  publicar:')]
        self.assertLess(prep.index('validate_xml_v94.py --check all'), prep.index('stage_pages_v421.py'))
        self.assertLess(prep.index('stage_pages_v421.py'), prep.index('validate_xml_v94.py --root _site'))
        self.assertLess(prep.index('validate_xml_v94.py --root _site'), prep.index('upload-pages-artifact'))
        self.assertIn('unittest test_feeds_unificados_v94', prep)  # testes de regressão fazem parte do portão
        self.assertNotIn('unittest discover', prep)  # testes obsoletos esquecidos no repositório não podem barrar o deploy
        self.assertIn('auditar_obsoletos_v942.py', prep)
        self.assertIn('verify_public_v94.py', core)

    def test_pacote_nao_traz_workflow_meta_separado(self):
        self.assertFalse((WF / 'gerar-marketplace.yml').exists())
        self.assertEqual(sorted(p.name for p in WF.glob('*.yml')),
                         ['core-imobiliario.yml', 'make-feed-merchantcenter.yml', 'make-sitemap.yml', 'make-subpage.yml', 'sinc-data.yml'])

    def test_sitemap_valida_logo_apos_gerar(self):
        self.assertIn('validate_xml_v94.py --check sitemap', self.read('make-sitemap.yml'))


class StagingConfereOsFeeds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        doc = fixture()
        self.google = merchant_build(doc)
        (self.root / 'catalogo.json').write_text(json.dumps(doc), encoding='utf-8')
        (self.root / 'merchant-produtos.xml').write_bytes(self.google)
        (self.root / 'marketplace-produtos.xml').write_bytes(compile_xml(doc)[0])
        (self.root / 'sitemap.xml').write_text('<urlset/>', encoding='utf-8')
        (self.root / 'index.html').write_text('<h1>Portal</h1>', encoding='utf-8')
        self.patches = [patch.object(stage_pages_v421, 'ROOT', self.root), patch.object(stage_pages_v421, 'DEST', self.root / '_site'),
                        patch.object(validate_marketplace_v8, 'ROOT', self.root)]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def test_inclui_os_tres_xmls_e_registra_no_log(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            stage_pages_v421.run()
        for name in ('merchant-produtos.xml', 'marketplace-produtos.xml', 'sitemap.xml'):
            self.assertTrue((self.root / '_site' / name).is_file())
            self.assertIn(f'INCLUIDO no artefato: {name}', out.getvalue())

    def test_marketplace_ausente_workflow_antigo_e_regerado_na_montagem(self):
        (self.root / 'marketplace-produtos.xml').unlink()  # Core antigo: só o Merchant chegou
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            stage_pages_v421.run()
        self.assertIn('FEED META GERADO', out.getvalue())
        self.assertEqual(len(ET.parse(self.root / '_site' / 'marketplace-produtos.xml').findall('listing')), 1)
        self.assertEqual((self.root / '_site' / 'merchant-produtos.xml').read_bytes(), self.google)  # Merchant idêntico

    def test_marketplace_ausente_e_nao_gerado_bloqueia_sem_tocar_no_site_anterior(self):
        (self.root / 'marketplace-produtos.xml').unlink()
        doc = fixture(); doc['items'][0]['marketplaceEnabled'] = False  # nenhum imóvel elegível
        (self.root / 'catalogo.json').write_text(json.dumps(doc), encoding='utf-8')
        (self.root / '_site').mkdir()
        (self.root / '_site' / 'index.html').write_text('versao anterior', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'Nao foi possivel gerar Marketplace'):
            stage_pages_v421.run()
        self.assertEqual((self.root / '_site' / 'index.html').read_text(encoding='utf-8'), 'versao anterior')

    def test_marketplace_estruturalmente_invalido_bloqueia(self):
        (self.root / 'marketplace-produtos.xml').write_text('<listings/>', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'Marketplace invalido'):
            stage_pages_v421.run()
        self.assertFalse((self.root / '_site').exists())

    def test_sitemap_ausente_bloqueia(self):
        (self.root / 'sitemap.xml').unlink()
        with self.assertRaisesRegex(RuntimeError, 'ausente: sitemap.xml'):
            stage_pages_v421.run()


class VerificacaoPublica(unittest.TestCase):
    """verify_public_v94 sem rede: o 'dominio' e uma pasta local."""
    def setUp(self):
        self.ws = Workspace([row('a1')])
        for script in ('sinc-data.py', 'make-feed-merchantcenter.py', 'make-sitemap.py'):
            self.ws.ok(script)
        self.site = self.ws.root

    def tearDown(self):
        self.ws.close()

    def serve(self, base):
        return patch.object(verify_public_v94, 'get', lambda url: (self.site / url[len(base):]).read_bytes())

    def test_tres_arquivos_publicos_dentro_do_contrato(self):
        with self.serve(SITE):
            self.assertEqual(verify_public_v94.verify(SITE), (1, 1, 2))

    def test_arquivo_publico_fora_do_contrato_reprova(self):
        (self.site / 'marketplace-produtos.xml').write_text('<listings/>', encoding='utf-8')
        with self.serve(SITE), self.assertRaises(ValueError):
            verify_public_v94.verify(SITE)

    def test_arquivo_publico_ausente_reprova(self):
        (self.site / 'sitemap.xml').unlink()
        with self.serve(SITE), self.assertRaises(OSError):
            verify_public_v94.verify(SITE)


class TestesDoCoreIgnoramObsoletos(unittest.TestCase):
    """Reproduz o repositório do usuário: testes de V9.2/V9.3 esquecidos na pasta scripts."""
    @unittest.skipIf(os.environ.get('V94_SEM_RECURSAO'), 'evita o teste chamar a si mesmo')
    def test_comando_do_workflow_passa_com_testes_obsoletos_presentes(self):
        env = dict(os.environ, V94_SEM_RECURSAO='1')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(BASE / 'scripts', root / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(WF.parent, root / '.github')
            for name in ('portal-config.json',):
                shutil.copy2(BASE / name, root / name)
            (root / 'scripts' / 'test_motores_v94.py').write_text(
                'import unittest\nclass T(unittest.TestCase):\n    def test_velho(self): self.fail("obsoleto")\n', encoding='utf-8')
            audit = subprocess.run([sys.executable, str(root / 'scripts' / 'auditar_obsoletos_v942.py')], capture_output=True, text=True)
            self.assertEqual(audit.returncode, 0)
            self.assertIn('test_motores_v94.py', audit.stdout)
            run = subprocess.run([sys.executable, '-m', 'unittest', 'test_feeds_unificados_v94', 'test_integracao_core_v8',
                                  'test_integracao_feeds_v6', 'test_gerar_marketplace'],
                                 cwd=root / 'scripts', capture_output=True, text=True, env=env)
            self.assertEqual(run.returncode, 0, run.stderr[-800:])
            discover = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'scripts', '-p', 'test_*.py'],
                                      cwd=root, capture_output=True, text=True, env=env)
            self.assertNotEqual(discover.returncode, 0)  # confirma que o discover seria barrado pelo arquivo velho


if __name__ == '__main__':
    unittest.main()
