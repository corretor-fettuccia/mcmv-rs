#!/usr/bin/env python3
"""Valida staging Pages a partir dos quatro motores com fixture sem rede."""
import json
import os
import subprocess
import shutil
import sys
import tempfile
from pathlib import Path

SOURCE=Path(__file__).resolve().parent.parent

def run():
    # Testes de V4.2 garantem mudancas e inativacoes; aqui testamos o ARTEFATO de deploy.
    with tempfile.TemporaryDirectory(prefix='test-v421-') as d:
        root=Path(d)
        shutil.copytree(SOURCE/'scripts',root/'scripts',ignore=shutil.ignore_patterns('__pycache__'))
        (root/'portal-config.json').write_text(json.dumps({'name':'Portal Teste','site_url':'https://teste.example.com/'}),encoding='utf-8')
        for source in ['index.html','app.js','config.js']:
            shutil.copy2(SOURCE/source,root/source)
        (root/'CNAME').write_text('teste.example.com\n')
        row={'id':'imovel_1','url':'https://imovel.example.com/','image':'https://imovel.example.com/foto.webp',
             'name':'Imóvel teste','description':'Descrição completa, sacada e jacuzzi.','highlight':'Resumo',
             'gallery':['https://imovel.example.com/foto.webp'], 'attributes':['Sacada','Jacuzzi'],
             'state':'Em construção','minimum':250000,'maximum':280000,'brand':'Construtora Exemplo',
             'condition':'new','merchantId':'imovel_1','googleEnabled':True,'googleAvailability':'in_stock', 'address':'Rua Modelo, 100', 'city':'Canoas', 'uf':'RS'}
        fixture=root/'api-fixture.json'
        fixture.write_text(json.dumps({'ok':True,'schemaVersion':4,'sourceContract':'core-imobiliario-v4',
                                       'snapshotComplete':True,'totalRows':1,'publishedRows':1,'items':[row]}),encoding='utf-8')
        env={**os.environ,'PORTAL_FIXTURE':str(fixture)}
        for engine in ('sinc-data','make-feed-merchantcenter','make-sitemap','make-subpage'):
            subprocess.run([sys.executable,str(root/'scripts'/f'{engine}.py')],env=env,cwd=root,check=True,stdout=subprocess.DEVNULL)
        assert (root/'marketplace-produtos.xml').is_file()  # V9.4: gerado pelo motor 02
        subprocess.run([sys.executable,str(root/'scripts'/'stage_pages_v421.py')],env=env,cwd=root,check=True,stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable,str(root/'scripts'/'validate_pages_v421.py')],env=env,cwd=root,check=True,stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable,str(root/'scripts'/'validate_xml_v94.py'),'--root',str(root/'_site')],env=env,cwd=root,check=True,stdout=subprocess.DEVNULL)
        page=root/'_site'/'imoveis'/'imovel_1'/'index.html'
        assert 'Jacuzzi' in page.read_text(encoding='utf-8')
        assert 'Compartilhar' in page.read_text(encoding='utf-8')
        assert not (root/'_site'/'scripts').exists()
        assert not (root/'_site'/'.github').exists()
        assert not (root/'_site'/'api-fixture.json').is_file()  # fixture never deployed
        assert (root/'_site'/'catalogo.json').exists()
        assert (root/'_site'/'sitemap.xml').exists()
        subprocess.run(['node',str(root/'scripts'/'test_vitrine_catalogo_v420.js')],cwd=root,check=True,stdout=subprocess.DEVNULL)
    print('TESTE V4.2.1 OK: geracao sequencial, subpage, artefato Pages e validacao.')

if __name__=='__main__':
    run()
