#!/usr/bin/env python3
"""Testes da V10 (sem rede): leitura da API, catálogo, feeds, páginas, sitemap, llms, validação, montagem e workflow.

Cada teste roda os scripts reais numa cópia temporária do projeto, com uma API de mentira (PORTAL_FIXTURE),
exatamente como o GitHub Actions os executa.
"""
import hashlib
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
import site_files
import stage_site
import validate as V
import verify_public

BASE = Path(__file__).resolve().parent.parent
SITE = 'https://teste.example.com/'
WORKFLOW = BASE / '.github' / 'workflows' / 'core-imobiliario.yml'
G = '{http://base.google.com/ns/1.0}'
WEBP = b'RIFF\x24\x00\x00\x00WEBPVP8 ' + b'0' * 64
PNG = b'\x89PNG\r\n\x1a\n' + b'0' * 64
JPG = b'\xff\xd8\xff\xe0' + b'0' * 64


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
        self.images = self.root / 'imagens-fixture'
        self.images.mkdir()
        self.set_api(payload if payload is not None else api(items if items is not None else [row('a1'), row('b2')]))

    def set_api(self, payload):
        (self.root / 'api.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        for item in payload.get('items', []):  # toda imagem do catálogo "existe" na internet de mentira
            for url in [item.get('image')] + list(item.get('gallery', [])):
                self.serve(url, PNG if str(url).endswith('.png') else JPG if str(url).endswith('.jpg') else WEBP)

    def serve(self, url, data):
        (self.images / hashlib.sha1(url.encode()).hexdigest()).write_bytes(data)

    def offline(self, url):
        (self.images / hashlib.sha1(url.encode()).hexdigest()).unlink(missing_ok=True)

    def run(self, script, *args, **env):
        e = dict(os.environ, PORTAL_FIXTURE=str(self.root / 'api.json'), IMAGENS_FIXTURE=str(self.images), **env)
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
        meta = [i.findtext(G + 'id') for i in ET.parse(ws.root / 'marketplace-produtos.xml').findall('./channel/item')]
        self.assertEqual(google, ['b2', 'c3'])
        self.assertEqual(meta, ['a1', 'c3'])
        self.assertIn('1/2 GERADO merchant-produtos.xml', result.stdout)
        self.assertIn('2/2 GERADO marketplace-produtos.xml', result.stdout)
        self.assertIn('Merchant não inclui a1', result.stdout)
        self.assertIn('Marketplace não inclui b2', result.stdout)
        self.assertTrue((ws.root / 'google-ads-imoveis.csv').is_file())
        self.assertEqual(ws.validate('feeds').returncode, 0)

    def test_meta_e_catalogo_de_produtos_rss_com_o_vocabulario_da_meta(self):
        ws = self.workspace([row('a1')])
        ws.build()
        meta = ws.read('marketplace-produtos.xml')
        root = ET.fromstring(meta.encode())
        self.assertEqual((root.tag, root.get('version')), ('rss', '2.0'))  # <listings> a Meta recusa: "formato XML errado"
        self.assertNotIn('<listings', meta)
        self.assertIn('xmlns:g="http://base.google.com/ns/1.0"', meta)
        self.assertEqual(root.find('./channel/{http://www.w3.org/2005/Atom}link').get('href'), SITE + 'marketplace-produtos.xml')
        item = root.find('./channel/item')
        values = {k: item.findtext(G + k) for k in ('id', 'availability', 'condition', 'price', 'link', 'brand', 'title')}
        self.assertEqual(values, {'id': 'a1', 'availability': 'in stock', 'condition': 'new', 'price': '250000.00 BRL',
                                  'link': SITE + 'imoveis/a1/', 'brand': 'Construtora Exemplo', 'title': 'Imóvel a1'})
        self.assertEqual(item.findtext(G + 'description'), 'Descrição completa. Segundo parágrafo.')

    def test_meta_usa_imagens_publicas_sem_repeticao_e_sem_base64(self):
        ws = self.workspace([row('a1')])
        ws.build()
        meta = ws.read('marketplace-produtos.xml')
        item = ET.fromstring(meta.encode()).find('./channel/item')
        self.assertEqual(item.findtext(G + 'image_link'), 'https://img.example.com/a1/capa.webp')
        self.assertEqual([u.text for u in item.findall('additional_image_link')],
                         ['https://img.example.com/a1/sala.webp', 'https://img.example.com/a1/a&b.webp'])
        self.assertNotIn('data:', meta)
        self.assertNotIn('base64', meta)

    def test_meta_limita_a_20_imagens_extras_e_traduz_disponibilidade(self):
        galeria = [f'https://img.example.com/a1/{n:02d}.webp' for n in range(30)]
        ws = self.workspace([row('a1', gallery=galeria, googleAvailability='out_of_stock', condition='used')])
        ws.build()
        item = ET.fromstring(ws.read('marketplace-produtos.xml').encode()).find('./channel/item')
        self.assertEqual(len(item.findall('additional_image_link')), 20)
        self.assertEqual((item.findtext(G + 'availability'), item.findtext(G + 'condition')), ('out of stock', 'used'))

    def test_meta_corta_descricao_e_titulo_nos_limites_da_meta(self):
        ws = self.workspace([row('a1', description='palavra ' * 3000, name='T' * 300)])
        ws.build()
        item = ET.fromstring(ws.read('marketplace-produtos.xml').encode()).find('./channel/item')
        self.assertEqual(len(item.findtext(G + 'description')), 9999)
        self.assertLessEqual(len(item.findtext(G + 'title')), 200)
        self.assertEqual(ws.validate('feeds').returncode, 0)

    def test_meta_so_aceita_condicao_do_vocabulario_da_meta(self):
        ws = self.workspace([row('a1', condition='danificado'), row('b2', condition='refurbished'), row('c3', condition='used')])
        ws.ok('sync_catalog.py')
        result = ws.ok('build_feeds.py')
        meta = [i.findtext(G + 'id') for i in ET.parse(ws.root / 'marketplace-produtos.xml').findall('./channel/item')]
        self.assertEqual(meta, ['b2', 'c3'])
        self.assertIn('Marketplace não inclui a1', result.stdout)
        self.assertEqual(ws.validate('feeds').returncode, 0)

    def test_falha_do_marketplace_nao_grava_nenhum_feed(self):
        ws = self.workspace([row('a1', brand='')])
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
    def test_paginas_trazem_as_imagens_baixadas_e_so_imoveis_ativos(self):
        ws = self.workspace([row('a1'), row('b2')])
        ws.build()
        folder = ws.root / 'imoveis' / 'a1'
        fotos = sorted(p.name for p in folder.iterdir() if p.name != 'index.html')
        self.assertEqual(len(fotos), 3)  # capa, sala e a&b (a repetida some)
        self.assertTrue(all(site_files.LOCAL_NAME.fullmatch(n) for n in fotos))
        page = ws.read('imoveis/a1/index.html')
        for nome in fotos:
            self.assertIn(f'<img src="{nome}"', page)
        self.assertNotIn('img.example.com', page)  # nenhuma imagem remota quando todas baixaram
        self.assertIn(f'<meta property="og:image" content="{SITE}imoveis/a1/{fotos[0]}">', page)
        self.assertIn('rel="canonical" href="' + SITE + 'imoveis/a1/"', page)
        self.assertNotIn('noindex', page)
        # b2 sai da planilha: a pasta gerada pelo Core (página + imagens) some; pasta alheia permanece
        (ws.root / 'imoveis' / 'manual').mkdir()
        (ws.root / 'imoveis' / 'manual' / 'notas.txt').write_text('meu', encoding='utf-8')
        ws.set_api(api([row('a1')]))
        ws.ok('sync_catalog.py')
        result = ws.ok('build_pages.py')
        self.assertFalse((ws.root / 'imoveis' / 'b2').exists())
        self.assertTrue((ws.root / 'imoveis' / 'manual' / 'notas.txt').exists())
        self.assertIn("pastas removidas: 1 ['b2']", result.stdout)
    def test_sitemap_principal_primeiro_imagens_hospedadas_e_namespaces(self):
        ws = self.workspace([row('a1'), row('b2')])
        ws.build()
        data = ws.read('sitemap.xml')
        self.assertTrue(data.startswith('<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn('xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"', data)
        found = V.check_sitemap(data.encode(), SITE, ws.catalog()['items'])
        self.assertEqual(list(found), [SITE, SITE + 'imoveis/a1/', SITE + 'imoveis/b2/'])
        imagens = found[SITE + 'imoveis/a1/']
        self.assertEqual(len(imagens), 3)
        self.assertTrue(all(i.startswith(SITE + 'imoveis/a1/') for i in imagens))  # cópias hospedadas no próprio domínio
        capa = (ws.root / 'imoveis' / 'a1' / imagens[0].rsplit('/', 1)[1])
        self.assertEqual(capa.read_bytes(), WEBP)
        self.assertIn('Sitemap: ' + SITE + 'sitemap.xml', ws.read('robots.txt'))

    def test_sitemap_le_as_paginas_construidas_nao_o_catalogo(self):
        ws = self.workspace([row('a1')])
        ws.build()
        page = ws.root / 'imoveis' / 'a1' / 'index.html'
        html_text = page.read_text(encoding='utf-8')
        figura = re.search(r'<figure>.*?</figure>\n?', html_text, re.S).group(0)
        page.write_text(html_text.replace(figura, '', 1), encoding='utf-8')  # a página passa a ter 2 imagens
        ws.ok('build_sitemap.py')
        self.assertEqual(ws.read('sitemap.xml').count('<image:loc>'), 2)

    def test_sitemap_sem_pagina_construida_falha(self):
        ws = self.workspace([row('a1'), row('b2')])
        ws.build()
        shutil.rmtree(ws.root / 'imoveis' / 'b2')
        result = ws.run('build_sitemap.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('página não construída para b2', result.stderr)
    def test_llms_combina_sitemap_e_catalogo_no_formato_llms_txt(self):
        ws = self.workspace([row('a1', minimum=250000, maximum=300000), row('b2')])
        ws.build()
        llms = ws.read('llms.txt')
        linhas = llms.splitlines()
        self.assertTrue(linhas[0].startswith('# Portal Teste'))
        self.assertTrue(linhas[2].startswith('> Catálogo de 2 empreendimento(s)'))
        self.assertIn('em Canoas', linhas[2])
        for titulo in ('## Empreendimentos', '## Dados e feeds', '## Optional'):
            self.assertIn(titulo, linhas)
        for uid in ('a1', 'b2'):
            self.assertIn(f'- [Imóvel {uid}]({SITE}imoveis/{uid}/): Resumo', llms)  # link da página (sitemap) + resumo (catálogo)
        self.assertIn('A partir de R$ 250.000 até R$ 300.000', llms)
        self.assertIn('Atributos: Piscina, Sacada', llms)
        self.assertIn('Imagens: 3 (principal: ' + SITE + 'imoveis/a1/', llms)  # contagem e capa vêm do sitemap
        for nome in ('catalogo.json', 'sitemap.xml', 'merchant-produtos.xml', 'marketplace-produtos.xml'):
            self.assertIn(f']({SITE}{nome})', llms)
        self.assertIn('(https://lp.example.com/a1/)', llms)  # landing page do empreendedor, em Optional

    def test_llms_falha_se_sitemap_e_catalogo_divergem(self):
        ws = self.workspace([row('a1'), row('b2')])
        ws.build()
        sitemap = ws.read('sitemap.xml')
        (ws.root / 'sitemap.xml').write_text(re.sub(r'  <url>\n    <loc>[^<]*imoveis/b2/</loc>.*?</url>\n', '', sitemap, flags=re.S), encoding='utf-8')
        result = ws.run('build_llms.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('sitemap e catálogo divergem', result.stderr)

class ImagensBaixadas(Base):
    def test_baixa_lista_e_nomeia_pelo_conteudo(self):
        ws = self.workspace([row('a1', image='https://img.example.com/a1/capa.webp', gallery=['https://img.example.com/a1/capa.webp', 'https://img.example.com/a1/planta.webp'])])
        ws.serve('https://img.example.com/a1/planta.webp', PNG)  # a extensão da URL mente: vale o conteúdo
        ws.ok('sync_catalog.py')
        result = ws.ok('build_pages.py')
        nomes = sorted(p.name for p in (ws.root / 'imoveis' / 'a1').iterdir() if p.name != 'index.html')
        self.assertEqual([n.rsplit('.', 1)[1] for n in nomes], ['webp', 'png'])
        self.assertIn('imoveis/a1/: 2 imagens (baixadas 2, já existentes 0, remotas 0)', result.stdout)
        for nome in nomes:  # listagem de ./imoveis/
            self.assertIn(f'imoveis/a1/{nome}', result.stdout)

    def test_imagem_que_falha_volta_ao_endereco_original_e_o_sitemap_escapa(self):
        ws = self.workspace([row('a1')])
        ws.offline('https://img.example.com/a1/a&b.webp')
        ws.ok('sync_catalog.py')
        result = ws.ok('build_pages.py')
        self.assertIn('::warning::imagem não baixada', result.stdout)
        self.assertIn('a&b.webp', result.stdout)
        self.assertIn('remotas 1', result.stdout)
        page = ws.read('imoveis/a1/index.html')
        self.assertIn('<img src="https://img.example.com/a1/a&amp;b.webp"', page)
        ws.ok('build_sitemap.py')
        self.assertIn('https://img.example.com/a1/a&amp;b.webp', ws.read('sitemap.xml'))
        ws.ok('build_feeds.py')
        ws.ok('build_llms.py')
        self.assertEqual(ws.validate('all').returncode, 0)  # imagem remota aceita só se for o endereço do catálogo

    def test_erro_4xx_nao_se_repete_e_falha_de_rede_tenta_duas_vezes(self):
        url = 'https://img.example.com/a1/capa.webp'
        with mock.patch.object(site_files, '_download', side_effect=site_files.NotFound('HTTP 404')) as baixar:
            with self.assertRaises(OSError):
                site_files.fetch_image(url)
        self.assertEqual(baixar.call_count, 1)
        with mock.patch.object(site_files.time, 'sleep'), \
                mock.patch.object(site_files, '_download', side_effect=[OSError('rede caiu'), WEBP]) as baixar:
            self.assertEqual(site_files.fetch_image(url), (WEBP, 'webp'))
        self.assertEqual(baixar.call_count, 2)
        with mock.patch.object(site_files.time, 'sleep'), \
                mock.patch.object(site_files, '_download', side_effect=OSError('rede caiu')) as baixar:
            with self.assertRaises(OSError):
                site_files.fetch_image(url)
        self.assertEqual(baixar.call_count, 2)

    def test_html_ou_arquivo_grande_demais_nao_viram_imagem(self):
        ws = self.workspace([row('a1')])
        ws.serve('https://img.example.com/a1/sala.webp', b'<html>404 amigavel</html>')
        ws.serve('https://img.example.com/a1/a&b.webp', WEBP + b'0' * site_files.MAX_BYTES)
        ws.ok('sync_catalog.py')
        result = ws.ok('build_pages.py')
        self.assertIn('o conteúdo não é uma imagem', result.stdout)
        self.assertIn('maior que 10 MB', result.stdout)
        self.assertIn('baixadas 1, já existentes 0, remotas 2', result.stdout)

    def test_reaproveita_arquivos_e_apaga_imagens_de_galerias_antigas(self):
        ws = self.workspace([row('a1')])
        ws.ok('sync_catalog.py')
        ws.ok('build_pages.py')
        for arquivo in ws.images.iterdir():  # sem "internet": tudo vem do que já foi baixado
            arquivo.unlink()
        again = ws.ok('build_pages.py')
        self.assertIn('baixadas 0, já existentes 3, remotas 0', again.stdout)
        antes = {p.name for p in (ws.root / 'imoveis' / 'a1').iterdir()}
        ws.set_api(api([row('a1', gallery=['https://img.example.com/a1/capa.webp', 'https://img.example.com/a1/nova.webp'])]))
        ws.ok('sync_catalog.py')
        ws.ok('build_pages.py')
        depois = {p.name for p in (ws.root / 'imoveis' / 'a1').iterdir()}
        self.assertEqual(len(depois), 3)  # index.html + capa (reaproveitada) + nova
        self.assertEqual(len(antes & depois), 2)  # as imagens que saíram da galeria foram apagadas

    def test_enderecos_nao_permitidos(self):
        for url in ('http://img.example.com/x.webp', 'https://127.0.0.1/x.webp', 'https://10.0.0.5/x.webp', 'https://localhost/x.webp',
                    'https://user:senha@img.example.com/x.webp', 'data:image/png;base64,AAAA', 'https://semponto/x.webp'):
            with self.subTest(url):
                self.assertFalse(site_files.safe_url(url))
        self.assertTrue(site_files.safe_url('https://img.example.com/x.webp'))
        self.assertTrue(site_files.safe_url('https://8.8.8.8/x.webp'))

    def test_tipo_pela_assinatura_do_arquivo(self):
        self.assertEqual([site_files.kind(x) for x in (JPG, PNG, WEBP, b'GIF89a....', b'\x00\x00\x00\x1cftypavif....', b'<svg>', b'<html>', b'')],
                         ['jpg', 'png', 'webp', 'gif', 'avif', None, None, None])


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

    def test_marketplace_vocabulario_da_meta(self):
        self.edit('marketplace-produtos.xml', '<g:availability>in stock</g:availability>', '<g:availability>in_stock</g:availability>')
        self.falha('feeds', 'fora do vocabulário da Meta')

    def test_marketplace_mais_de_20_imagens_extras(self):
        extras = ''.join(f'<additional_image_link>https://img.example.com/a1/x{n}.webp</additional_image_link>' for n in range(20))
        self.edit('marketplace-produtos.xml', '<g:brand>Construtora Exemplo</g:brand>', extras + '<g:brand>Construtora Exemplo</g:brand>')
        self.falha('feeds', 'mais de 20 additional_image_link')

    def test_marketplace_descricao_grande_demais(self):
        self.edit('marketplace-produtos.xml', '<g:description>Descrição completa. Segundo parágrafo.</g:description>',
                  '<g:description>' + 'x' * 10000 + '</g:description>')
        self.falha('feeds', 'mais de 9999 caracteres')

    def test_marketplace_sem_link_para_si_mesmo(self):
        self.edit('marketplace-produtos.xml', 'rel="self"', 'rel="outro"')
        self.falha('feeds', 'atom:link')

    def test_marketplace_vazio_ou_ausente(self):
        (self.ws.root / 'marketplace-produtos.xml').write_text('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>x</title><atom:link rel="self" href="https://a.com/marketplace-produtos.xml"/></channel></rss>', encoding='utf-8')
        self.falha('feeds', 'nenhum <item>')
        (self.ws.root / 'marketplace-produtos.xml').unlink()
        self.falha('feeds', 'marketplace-produtos.xml')

    def test_marketplace_divergente_do_catalogo(self):
        self.edit('marketplace-produtos.xml', '<g:id>b2</g:id>', '<g:id>zz</g:id>')
        self.falha('feeds', 'divergem do catálogo')

    def test_marketplace_malformado(self):
        (self.ws.root / 'marketplace-produtos.xml').write_text('<rss><channel><item>', encoding='utf-8')
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
        self.edit('llms.txt', '](' + SITE + 'imoveis/b2/)', '](removido)')
        self.falha('sitemap', 'llms.txt')
    def test_pagina_ausente_noindex_ou_sem_imagem(self):
        self.edit('imoveis/a1/index.html', '<link rel="canonical"', '<link rel="x"')
        self.falha('pages', 'canonical')
        self.ws.build()
        self.edit('imoveis/a1/index.html', '<meta charset="utf-8">', '<meta charset="utf-8"><meta name="robots" content="noindex">')
        self.falha('pages', 'noindex')
        self.ws.build()
        foto = next(p for p in (self.ws.root / 'imoveis' / 'a1').iterdir() if p.name != 'index.html')
        foto.write_bytes(b'<html>erro</html>')
        self.falha('pages', 'imagem local ausente ou inválida')
        foto.unlink()
        self.falha('pages', 'imagem local ausente ou inválida')
        self.ws.build()
        page = self.ws.root / 'imoveis' / 'a1' / 'index.html'
        page.write_text(re.sub(r'<figure>.*?</figure>\n?', '', page.read_text(encoding='utf-8'), count=1, flags=re.S), encoding='utf-8')
        self.falha('pages', 'galeria do catálogo')
        shutil.rmtree(self.ws.root / 'imoveis' / 'a1')
        self.falha('pages', 'página ausente')

    def test_sitemap_com_imagem_diferente_da_pagina(self):
        sitemap = self.ws.read('sitemap.xml')
        nome = re.search(r'imoveis/a1/(\d\d-[0-9a-f]{8}\.webp)', sitemap).group(1)
        self.edit('sitemap.xml', nome, '99-deadbeef.webp')
        self.falha('sitemap', 'divergem da página construída')
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
        (ws.root / 'imoveis' / 'a1' / 'rascunho.psd').write_text('x', encoding='utf-8')  # dentro da pasta do imóvel, mas a página não usa
        (ws.root / '.github').mkdir(exist_ok=True)
        ws.ok('stage_site.py')
        site = ws.root / '_site'
        publicados = sorted(p.relative_to(site).as_posix() for p in site.rglob('*') if p.is_file())
        fotos = [f'imoveis/{u}/{p.name}' for u in ('a1', 'b2') for p in (ws.root / 'imoveis' / u).iterdir() if site_files.LOCAL_NAME.fullmatch(p.name)]
        self.assertEqual(len(fotos), 6)
        self.assertEqual(publicados, sorted([
            '.nojekyll', 'CNAME', 'app.js', 'catalogo.json', 'config.js', 'google-ads-imoveis.csv', 'hero-mcmv-rs.png',
            'icon.jpeg', 'imoveis/a1/index.html', 'imoveis/b2/index.html', 'index.html', 'llms.txt',
            'marketplace-produtos.xml', 'merchant-produtos.xml', 'robots.txt', 'sitemap.xml'] + fotos))
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

    def test_imagem_usada_pela_pagina_e_ausente_falha_sem_tocar_no_site_anterior(self):
        ws = self.workspace()
        ws.build()
        ws.ok('stage_site.py')
        (ws.root / '_site' / 'marca.txt').write_text('publicado antes', encoding='utf-8')
        foto = next(p for p in (ws.root / 'imoveis' / 'a1').iterdir() if p.name != 'index.html')
        foto.unlink()
        result = ws.run('stage_site.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('imagem usada pela página ausente', result.stderr)
        self.assertEqual((ws.root / '_site' / 'marca.txt').read_text(encoding='utf-8'), 'publicado antes')

    def test_site_maior_que_o_limite_do_pages_nao_e_montado(self):
        ws = self.workspace()
        ws.build()
        (ws.root / '_site').mkdir()
        (ws.root / '_site' / 'marca.txt').write_text('publicado antes', encoding='utf-8')
        with mock.patch.object(stage_site, 'MAX_SITE_BYTES', 100), self.assertRaisesRegex(RuntimeError, 'limite'):
            stage_site.run(ws.root)
        self.assertEqual((ws.root / '_site' / 'marca.txt').read_text(encoding='utf-8'), 'publicado antes')
        self.assertFalse((ws.root / '_site.tmp').exists())

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
            self.assertEqual(verify_public.verify(SITE), (2, 2, 3, 2))  # 2 imóveis com imagem hospedada abrindo

    def test_verificacao_publica_reprova_imagem_que_nao_e_imagem(self):
        ws = self.workspace()
        ws.build()
        ws.ok('stage_site.py')
        site = ws.root / '_site'

        def get(url):
            data = (site / url[len(SITE):]).read_bytes()
            return b'<html>404</html>' if re.search(r'\d\d-[0-9a-f]{8}\.webp$', url) else data

        with mock.patch.object(verify_public, 'get', get), self.assertRaisesRegex(ValueError, 'não respondeu uma imagem'):
            verify_public.verify(SITE)
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

    def test_audit_cobre_os_modulos_importados_pelos_scripts_da_v10(self):
        locais = {n[:-3] for n in audit_repo.SCRIPTS if n.endswith('.py')}
        for nome in sorted(audit_repo.SCRIPTS):
            if not nome.endswith('.py'):
                continue
            codigo = (BASE / 'scripts' / nome).read_text(encoding='utf-8')
            for modulo in re.findall(r'^(?:from|import) ([a-z_]+)', codigo, re.M):
                if (BASE / 'scripts' / f'{modulo}.py').is_file():
                    self.assertIn(modulo, locais, f'{nome} importa {modulo}.py, que o audit trataria como antigo')

    def test_audit_nao_aponta_como_antigo_nenhum_script_que_o_workflow_usa(self):
        usados = set(re.findall(r'scripts/([A-Za-z_]+\.py)', WORKFLOW.read_text(encoding='utf-8')))
        usados |= set(re.findall(r'node (?:scripts/)?(test_[a-z_]+\.js)', WORKFLOW.read_text(encoding='utf-8')))
        usados |= {'test_core.py'}
        self.assertEqual(usados - audit_repo.SCRIPTS, set())


if __name__ == '__main__':
    unittest.main()
