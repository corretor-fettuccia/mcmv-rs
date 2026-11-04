#!/usr/bin/env python3
"""Testes da V10 (sem rede): leitura da API, catálogo, feeds, páginas, sitemap, llms, validação, montagem e workflow.

Cada teste roda os scripts reais numa cópia temporária do projeto, com uma API de mentira (PORTAL_FIXTURE),
exatamente como o GitHub Actions os executa.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_repo
import core_lib
import validate as V
import verify_public

BASE = Path(__file__).resolve().parent.parent
SITE = 'https://teste.example.com/'
WORKFLOW = BASE / '.github' / 'workflows' / 'core-imobiliario.yml'
G = '{http://base.google.com/ns/1.0}'


def row(uid, **over):
    """Registro como a API pública do Apps Script o entrega."""
    base = {'id': uid, 'url': f'https://lp.example.com/{uid}/', 'image': f'https://img.example.com/{uid}/capa.webp',
            'name': f'Imóvel {uid}', 'description': 'Descrição completa.\n\nSegundo parágrafo.', 'highlight': 'Resumo',
            'gallery': [f'https://img.example.com/{uid}/capa.webp', f'https://img.example.com/{uid}/sala.webp',
                        f'https://img.example.com/{uid}/sala.webp', f'https://img.example.com/{uid}/a&b.webp'],
            'attributes': ['PISCINA', 'Sacada'], 'state': 'Em construção', 'minimum': 250000, 'maximum': 300000,
            'brand': 'Construtora Exemplo', 'condition': 'new', 'merchantId': '', 'googleEnabled': True,
            'googleAvailability': 'in_stock', 'address': 'Rua Modelo, 100', 'city': 'Canoas', 'uf': 'RS',
            'neighborhood': 'Centro', 'region': 'Metropolitana', 'propertyType': 'Apartamento', 'bedrooms': 2,
            'bathrooms': 1, 'privateArea': 47, 'order': 0}
    base.update(over)
    return base


def api(items, **over):
    payload = {'ok': True, 'schemaVersion': 4, 'sourceContract': 'core-imobiliario-v4', 'snapshotComplete': True,
               'totalRows': len(items), 'publishedRows': len(items), 'config': {'titulo': 'Teste'}, 'items': items}
    payload.update(over)
    return payload


class Workspace:
    def __init__(self, items=None, payload=None):
        self.tmp = tempfile.TemporaryDirectory(prefix='v10-')
        self.root = Path(self.tmp.name)
        shutil.copytree(BASE / 'scripts', self.root / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('index.html', 'app.js', 'config.js', 'hero-mcmv-rs.png', 'icon.jpeg', 'CNAME'):
            shutil.copy2(BASE / name, self.root / name)
        (self.root / 'portal-config.json').write_text(json.dumps({'name': 'Portal Teste', 'site_url': SITE}), encoding='utf-8')
        self.set_api(payload if payload is not None else api(items if items is not None else [row('a1'), row('b2')]))

    def set_api(self, payload):
        (self.root / 'api.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')

    def run(self, script, *args, **env):
        e = dict(os.environ, PORTAL_FIXTURE=str(self.root / 'api.json'), **env)
        return subprocess.run([sys.executable, str(self.root / 'scripts' / script), *args], cwd=self.root,
                              env=e, capture_output=True, text=True)

    def ok(self, script, *args, **env):
        result = self.run(script, *args, **env)
        assert result.returncode == 0, f'{script} falhou:\n{result.stdout}\n{result.stderr}'
        return result

    def build(self):
        for script in ('sync_catalog.py', 'build_feeds.py', 'build_pages.py', 'build_sitemap.py', 'build_llms.py'):
            self.ok(script)

    def read(self, name):
        return (self.root / name).read_text(encoding='utf-8')

    def catalog(self):
        return json.loads(self.read('catalogo.json'))

    def validate(self, check='all', root=None):
        return self.run('validate.py', '--root', str(root or self.root), '--check', check)

    def close(self):
        self.tmp.cleanup()


class Base(unittest.TestCase):
    def workspace(self, *a, **k):
        ws = Workspace(*a, **k)
        self.addCleanup(ws.close)
        return ws


class LeituraDaApi(Base):
    def test_gera_catalogo_com_os_quatro_enderecos_publicos_e_atributos_padronizados(self):
        ws = self.workspace()
        result = ws.ok('sync_catalog.py')
        c = ws.catalog()
        self.assertEqual([i['id'] for i in c['items']], ['a1', 'b2'])
        self.assertEqual(c['items'][0]['attributes'], ['Piscina', 'Sacada'])
        self.assertEqual(c['items'][0]['merchantId'], 'a1')  # API vazia -> usa o id
        self.assertEqual(c['items'][0]['pageUrl'], SITE + 'imoveis/a1/')
        self.assertEqual(c['feeds'], {'google_merchant_xml': SITE + 'merchant-produtos.xml', 'google_ads_csv': SITE + 'google-ads-imoveis.csv',
                                      'meta_marketplace_xml': SITE + 'marketplace-produtos.xml', 'sitemap_xml': SITE + 'sitemap.xml'})
        self.assertIn('2 imóveis ativos', result.stdout)

    def test_registra_novos_atualizados_e_removidos_em_relacao_ao_catalogo_publicado(self):
        ws = self.workspace([row('a1'), row('b2'), row('c3')])
        ws.ok('sync_catalog.py')
        anterior = ws.root / 'anterior.json'
        shutil.copy2(ws.root / 'catalogo.json', anterior)
        ws.set_api(api([row('a1'), row('b2', name='Nome novo'), row('d4')]))
        result = ws.ok('sync_catalog.py', CATALOGO_ANTERIOR=str(anterior))
        self.assertIn("Novos: 1 ['d4']", result.stdout)
        self.assertIn("Atualizados: 1 ['b2']", result.stdout)
        self.assertIn("Removidos: 1 ['c3']", result.stdout)
        self.assertEqual([i['id'] for i in ws.catalog()['items']], ['a1', 'd4', 'b2'])  # c3 saiu; ordem do catálogo é por nome

    def test_sem_catalogo_anterior_tudo_e_novo(self):
        ws = self.workspace()
        result = ws.ok('sync_catalog.py', CATALOGO_ANTERIOR=str(ws.root / 'nao-existe.json'))
        self.assertIn("Novos: 2", result.stdout)

    def test_respostas_invalidas_da_api_nao_gravam_catalogo(self):
        casos = {
            'ok falso': api([row('a1')], ok=False, error='planilha'),
            'contrato antigo': api([row('a1')], schemaVersion=3),
            'snapshot incompleto': api([row('a1')], snapshotComplete=False),
            'publicados diferente de itens': api([row('a1')], publishedRows=3, totalRows=3),
            'sem attributes': api([{k: v for k, v in row('a1').items() if k != 'attributes'}]),
            'imagem http': api([row('a1', image='http://img.example.com/x.webp')]),
            'imagem base64': api([row('a1', image='data:image/png;base64,AAAA')]),
            'id repetido': api([row('a1'), row('a1')]),
            'id inseguro': api([row('../x')]),
            'preço invertido': api([row('a1', minimum=5, maximum=1)]),
        }
        for nome, payload in casos.items():
            with self.subTest(nome):
                ws = self.workspace(payload=payload)
                (ws.root / 'catalogo.json').write_text('{"anterior": true}', encoding='utf-8')
                result = ws.run('sync_catalog.py')
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertEqual(ws.read('catalogo.json'), '{"anterior": true}')

    def test_variavel_ausente_ou_invalida_falha_com_mensagem_clara(self):
        env = {k: v for k, v in os.environ.items() if k not in ('PORTAL_FIXTURE', 'VITRINE_API_URL')}
        for value in ('', 'http://script.google.com/macros/s/x/exec', 'nao-e-url'):
            with self.subTest(value), mock.patch.dict(os.environ, env, clear=True), mock.patch.dict(os.environ, {'VITRINE_API_URL': value}):
                with self.assertRaisesRegex(RuntimeError, 'VITRINE_API_URL'):
                    core_lib.get_payload()

    def test_le_a_url_da_variavel_com_parametro_de_tempo_e_tenta_de_novo(self):
        url = 'https://script.google.com/macros/s/ABC/exec'
        pedidos = []

        class Resp:
            def __init__(self, data): self.data = data
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self, n): return self.data

        respostas = [OSError('503'), Resp(json.dumps(api([row('a1')])).encode())]

        def fake(req, timeout):
            pedidos.append(req.full_url)
            r = respostas.pop(0)
            if isinstance(r, Exception): raise r
            return r

        env = {k: v for k, v in os.environ.items() if k != 'PORTAL_FIXTURE'}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.dict(os.environ, {'VITRINE_API_URL': url}), \
                mock.patch.object(core_lib, 'urlopen', fake), mock.patch.object(core_lib.time, 'sleep'):
            data = core_lib.get_payload()
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(len(pedidos), 2)  # 1ª tentativa falhou, 2ª funcionou
        self.assertTrue(pedidos[0].startswith(url + '?_core_refresh='))

    def test_lista_vazia_com_snapshot_completo_e_valida(self):
        ws = self.workspace(payload=api([]))
        ws.ok('sync_catalog.py')
        self.assertEqual(ws.catalog()['items'], [])


class Feeds(Base):
    def test_uma_execucao_gera_os_dois_feeds_com_elegibilidade_propria(self):
        ws = self.workspace([row('a1', googleEnabled=False), row('b2', marketplaceEnabled='NAO'), row('c3')])
        ws.ok('sync_catalog.py')
        result = ws.ok('build_feeds.py')
        google = [i.findtext(G + 'id') for i in ET.parse(ws.root / 'merchant-produtos.xml').findall('./channel/item')]
        meta = [i.findtext('home_listing_id') for i in ET.parse(ws.root / 'marketplace-produtos.xml').findall('listing')]
        self.assertEqual(google, ['b2', 'c3'])
        self.assertEqual(meta, ['a1', 'c3'])
        self.assertIn('1/2 GERADO merchant-produtos.xml', result.stdout)
        self.assertIn('2/2 GERADO marketplace-produtos.xml', result.stdout)
        self.assertIn('Merchant não inclui a1', result.stdout)
        self.assertIn('Marketplace não inclui b2', result.stdout)
        self.assertTrue((ws.root / 'google-ads-imoveis.csv').is_file())
        self.assertEqual(ws.validate('feeds').returncode, 0)

    def test_marketplace_usa_imagens_publicas_sem_repeticao_e_sem_base64(self):
        ws = self.workspace([row('a1')])
        ws.build()
        meta = ws.read('marketplace-produtos.xml')
        listing = ET.fromstring(meta.encode()).find('listing')
        self.assertEqual([u.text for u in listing.findall('image/url')],
                         ['https://img.example.com/a1/capa.webp', 'https://img.example.com/a1/sala.webp', 'https://img.example.com/a1/a&b.webp'])
        self.assertEqual(listing.findtext('availability'), 'for_sale')
        self.assertEqual(listing.findtext('price'), '250000.00 BRL')
        self.assertNotIn('data:', meta)
        self.assertNotIn('base64', meta)

    def test_falha_do_marketplace_nao_grava_nenhum_feed(self):
        ws = self.workspace([row('a1', address='', city='')])
        ws.ok('sync_catalog.py')
        (ws.root / 'merchant-produtos.xml').write_text('anterior', encoding='utf-8')
        result = ws.run('build_feeds.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Marketplace (Meta) não gerado', result.stderr)
        self.assertEqual(ws.read('merchant-produtos.xml'), 'anterior')
        self.assertFalse((ws.root / 'marketplace-produtos.xml').exists())

    def test_merchant_com_zero_elegiveis_e_rss_valido(self):
        ws = self.workspace([row('a1', googleEnabled=False)])
        ws.ok('sync_catalog.py')
        ws.ok('build_feeds.py')
        self.assertEqual(ET.parse(ws.root / 'merchant-produtos.xml').findall('./channel/item'), [])
        self.assertEqual(ws.validate('feeds').returncode, 0)

    def test_segunda_execucao_nao_altera_nada(self):
        ws = self.workspace()
        ws.build()
        again = ws.ok('build_feeds.py')
        self.assertEqual(again.stdout.count('inalterado'), 2)


class PaginasSitemapELlms(Base):
    def test_paginas_trazem_todas_as_imagens_e_so_imoveis_ativos(self):
        ws = self.workspace([row('a1'), row('b2')])
        ws.build()
        page = ws.read('imoveis/a1/index.html')
        for url in ws.catalog()['items'][0]['gallery']:
            self.assertIn(url.replace('&', '&amp;'), page)
        self.assertIn('rel="canonical" href="' + SITE + 'imoveis/a1/"', page)
        self.assertNotIn('noindex', page)
        # b2 sai da planilha: a pasta gerada pelo Core some; pasta alheia permanece
        (ws.root / 'imoveis' / 'manual').mkdir()
        (ws.root / 'imoveis' / 'manual' / 'notas.txt').write_text('meu', encoding='utf-8')
        ws.set_api(api([row('a1')]))
        ws.ok('sync_catalog.py')
        result = ws.ok('build_pages.py')
        self.assertFalse((ws.root / 'imoveis' / 'b2').exists())
        self.assertTrue((ws.root / 'imoveis' / 'manual' / 'notas.txt').exists())
        self.assertIn("removidas do diretório: 1 ['b2']", result.stdout)

    def test_sitemap_principal_primeiro_imagens_namespaces_e_escape(self):
        ws = self.workspace([row('a1'), row('b2')])
        ws.build()
        data = ws.read('sitemap.xml')
        self.assertTrue(data.startswith('<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn('xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"', data)
        self.assertIn('a&amp;b.webp', data)
        found = V.check_sitemap(data.encode(), SITE, ws.catalog()['items'])
        self.assertEqual(list(found), [SITE, SITE + 'imoveis/a1/', SITE + 'imoveis/b2/'])
        self.assertEqual(found[SITE + 'imoveis/a1/'][0], 'https://img.example.com/a1/capa.webp')
        self.assertEqual(len(found[SITE + 'imoveis/a1/']), 3)  # repetida some
        self.assertIn('Sitemap: ' + SITE + 'sitemap.xml', ws.read('robots.txt'))

    def test_llms_lista_todos_os_imoveis_do_catalogo(self):
        ws = self.workspace([row('a1'), row('b2')])
        ws.build()
        llms = ws.read('llms.txt')
        for uid in ('a1', 'b2'):
            self.assertIn(SITE + f'imoveis/{uid}/', llms)
        self.assertIn(SITE + 'catalogo.json', llms)


class Validacao(Base):
    def setUp(self):
        self.ws = self.workspace([row('a1'), row('b2')])
        self.ws.build()
        self.assertEqual(self.ws.validate().returncode, 0)

    def edit(self, name, old, new):
        path = self.ws.root / name
        text = path.read_text(encoding='utf-8')
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding='utf-8')

    def falha(self, check='all', fragment=''):
        result = self.ws.validate(check)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(fragment, result.stderr)

    def test_merchant(self):
        self.edit('merchant-produtos.xml', '250000.00 BRL', '0.00 BRL')
        self.falha('feeds', 'preço inválido')

    def test_marketplace_imagem_base64(self):
        self.edit('marketplace-produtos.xml', 'https://img.example.com/a1/capa.webp', 'data:image/png;base64,AAAA')
        self.falha('feeds', 'URL inválida')

    def test_marketplace_vazio_ou_ausente(self):
        (self.ws.root / 'marketplace-produtos.xml').write_text('<listings><title>x</title><link rel="self" href="https://a.com/marketplace-produtos.xml"/></listings>', encoding='utf-8')
        self.falha('feeds', 'nenhum <listing>')
        (self.ws.root / 'marketplace-produtos.xml').unlink()
        self.falha('feeds', 'marketplace-produtos.xml')

    def test_marketplace_divergente_do_catalogo(self):
        self.edit('marketplace-produtos.xml', '<home_listing_id>b2</home_listing_id>', '<home_listing_id>zz</home_listing_id>')
        self.falha('feeds', 'divergem do catálogo')

    def test_marketplace_malformado(self):
        (self.ws.root / 'marketplace-produtos.xml').write_text('<listings><listing>', encoding='utf-8')
        self.falha('feeds', 'malformado')

    def test_sitemap_url_inexistente_no_catalogo(self):
        self.edit('sitemap.xml', '</urlset>', f'  <url>\n    <loc>{SITE}imoveis/fantasma/</loc>\n  </url>\n</urlset>')
        self.falha('sitemap', 'divergem do catálogo')

    def test_sitemap_url_repetida_e_home_fora_do_topo(self):
        self.edit('sitemap.xml', '</urlset>', f'  <url>\n    <loc>{SITE}imoveis/a1/</loc>\n  </url>\n</urlset>')
        self.falha('sitemap', 'repetida')

    def test_sitemap_sem_namespace_de_imagem(self):
        self.edit('sitemap.xml', ' xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"', '')
        self.falha('sitemap', 'namespace')

    def test_robots_e_llms(self):
        self.edit('robots.txt', 'Sitemap:', 'Mapa:')
        self.falha('sitemap', 'robots.txt')

    def test_llms_sem_imovel(self):
        self.edit('llms.txt', SITE + 'imoveis/b2/', 'removido')
        self.falha('sitemap', 'llms.txt')

    def test_pagina_ausente_noindex_ou_sem_imagem(self):
        self.edit('imoveis/a1/index.html', '<link rel="canonical"', '<link rel="x"')
        self.falha('pages', 'incompleta')
        self.ws.build()
        self.edit('imoveis/a1/index.html', '<meta charset="utf-8">', '<meta charset="utf-8"><meta name="robots" content="noindex">')
        self.falha('pages', 'noindex')
        self.ws.build()
        self.edit('imoveis/a1/index.html', 'https://img.example.com/a1/sala.webp', 'https://img.example.com/a1/outra.webp')
        self.falha('pages', 'galeria')
        shutil.rmtree(self.ws.root / 'imoveis' / 'a1')
        self.falha('pages', 'página ausente')

    def test_catalogo_nao_declara_o_marketplace(self):
        c = self.ws.catalog()
        del c['feeds']['meta_marketplace_xml']
        (self.ws.root / 'catalogo.json').write_text(json.dumps(c), encoding='utf-8')
        self.falha('catalog', 'meta_marketplace_xml')

    def test_catalogo_incompleto_ou_antigo(self):
        c = self.ws.catalog()
        c['snapshotComplete'] = False
        (self.ws.root / 'catalogo.json').write_text(json.dumps(c), encoding='utf-8')
        self.falha('all', 'contrato')


class MontagemDoSite(Base):
    def test_lista_de_permissao_nao_leva_codigo_documentos_nem_arquivos_antigos(self):
        ws = self.workspace()
        ws.build()
        (ws.root / 'LEIA-PRIMEIRO-V9.md').write_text('x', encoding='utf-8')
        (ws.root / 'catalogo-teste.json').write_text('{}', encoding='utf-8')
        (ws.root / 'imoveis' / 'orfao').mkdir()
        (ws.root / 'imoveis' / 'orfao' / 'index.html').write_text('x', encoding='utf-8')
        (ws.root / '.github').mkdir(exist_ok=True)
        ws.ok('stage_site.py')
        site = ws.root / '_site'
        publicados = sorted(p.relative_to(site).as_posix() for p in site.rglob('*') if p.is_file())
        self.assertEqual(publicados, sorted([
            '.nojekyll', 'CNAME', 'app.js', 'catalogo.json', 'config.js', 'google-ads-imoveis.csv', 'hero-mcmv-rs.png',
            'icon.jpeg', 'imoveis/a1/index.html', 'imoveis/b2/index.html', 'index.html', 'llms.txt',
            'marketplace-produtos.xml', 'merchant-produtos.xml', 'robots.txt', 'sitemap.xml']))
        self.assertEqual(ws.validate('site', site).returncode, 0)

    def test_arquivo_obrigatorio_ausente_falha_sem_tocar_no_site_anterior(self):
        ws = self.workspace()
        ws.build()
        ws.ok('stage_site.py')
        (ws.root / '_site' / 'marca.txt').write_text('publicado antes', encoding='utf-8')
        (ws.root / 'marketplace-produtos.xml').unlink()
        result = ws.run('stage_site.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('marketplace-produtos.xml', result.stderr)
        self.assertEqual((ws.root / '_site' / 'marca.txt').read_text(encoding='utf-8'), 'publicado antes')

    def test_site_montado_sem_um_dos_tres_xmls_reprova(self):
        ws = self.workspace()
        ws.build()
        ws.ok('stage_site.py')
        (ws.root / '_site' / 'sitemap.xml').unlink()
        result = ws.validate('site', ws.root / '_site')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('sitemap.xml', result.stderr)

    def test_sequencia_local_completa(self):
        ws = self.workspace()
        result = ws.ok('run_local.py')
        self.assertIn('todas as etapas concluídas', result.stdout)
        self.assertTrue((ws.root / '_site' / 'marketplace-produtos.xml').is_file())


class PublicacaoEWorkflow(Base):
    def test_verificacao_publica_aprova_os_arquivos_publicados(self):
        ws = self.workspace()
        ws.build()
        ws.ok('stage_site.py')
        site = ws.root / '_site'
        with mock.patch.object(verify_public, 'get', lambda url: (site / url[len(SITE):]).read_bytes()):
            self.assertEqual(verify_public.verify(SITE), (2, 2, 3))

    def test_verificacao_publica_reprova_marketplace_ausente(self):
        ws = self.workspace()
        ws.build()
        ws.ok('stage_site.py')
        site = ws.root / '_site'

        def get(url):
            name = url[len(SITE):]
            if name == 'marketplace-produtos.xml':
                raise ValueError('HTTP 404')
            return (site / name).read_bytes()

        with mock.patch.object(verify_public, 'get', get), self.assertRaisesRegex(ValueError, '404'):
            verify_public.verify(SITE)

    def test_workflow_unico_na_ordem_certa_e_usando_a_variavel(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertNotIn('uses: ./.github/workflows', text)  # sem workflows encadeados: nada para ficar desatualizado
        self.assertIn('VITRINE_API_URL: ${{ vars.VITRINE_API_URL || secrets.VITRINE_API_URL }}', text)
        order = ['sync_catalog.py', 'build_feeds.py', 'build_pages.py', 'build_sitemap.py', 'build_llms.py',
                 'validate.py --check all', 'stage_site.py', 'validate.py --root _site --check site',
                 'upload-pages-artifact', 'deploy-pages', 'verify_public.py']
        positions = [text.index(item) for item in order]
        self.assertEqual(positions, sorted(positions), 'etapas fora de ordem')
        self.assertLess(text.index('unittest test_core'), text.index('sync_catalog.py'))  # testes antes de publicar
        self.assertIn('path: _site', text)
        self.assertIn('needs: construir', text)
        self.assertIn('needs: publicar', text)
        self.assertIn("cron: '17 7 * * *'", text)
        for script in set(re.findall(r'scripts/([A-Za-z_]+\.py)', text)):
            self.assertTrue((BASE / 'scripts' / script).is_file(), script)
        for script in set(re.findall(r'node (?:scripts/)?(test_[a-z_]+\.js)', text)):
            self.assertTrue((BASE / 'scripts' / script).is_file(), script)

    def test_aviso_de_arquivos_antigos(self):
        with tempfile.TemporaryDirectory() as tmp:  # árvore própria: o resultado não depende do que há no repositório real
            root = Path(tmp)
            (root / 'scripts').mkdir()
            (root / '.github' / 'workflows').mkdir(parents=True)
            for name in ('core_lib.py', 'validate.py', 'feeds_v94.py'):
                (root / 'scripts' / name).write_text('x', encoding='utf-8')
            for name in ('core-imobiliario.yml', 'make-sitemap.yml'):
                (root / '.github' / 'workflows' / name).write_text('x', encoding='utf-8')
            self.assertEqual(audit_repo.obsolete(root), ['scripts/feeds_v94.py', '.github/workflows/make-sitemap.yml'])

    def test_audit_nao_aponta_como_antigo_nenhum_script_que_o_workflow_usa(self):
        usados = set(re.findall(r'scripts/([A-Za-z_]+\.py)', WORKFLOW.read_text(encoding='utf-8')))
        usados |= set(re.findall(r'node (?:scripts/)?(test_[a-z_]+\.js)', WORKFLOW.read_text(encoding='utf-8')))
        usados |= {'test_core.py'}
        self.assertEqual(usados - audit_repo.SCRIPTS, set())


if __name__ == '__main__':
    unittest.main()
