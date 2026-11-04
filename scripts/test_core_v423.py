#!/usr/bin/env python3
"""Teste local offline para a orquestração sequencial, com dois imóveis de exemplo.

Não é executado automaticamente em produção: apenas para homologação do pacote.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent

def run():
    with tempfile.TemporaryDirectory(prefix='core423-') as d:
        root = Path(d)
        shutil.copytree(ROOT / 'scripts', root / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        for name in ['index.html', 'app.js', 'config.js', 'portal-config.json', 'CNAME']:
            shutil.copy2(ROOT / name, root / name)
        def row(id, attrs, google):
            return {'id':id, 'url':'https://exemplo.com.br/'+id+'/',
                    'image':'https://exemplo.com.br/'+id+'.webp', 'name':id,
                    'description':'Descrição completa com informações comerciais.',
                    'gallery':['https://exemplo.com.br/'+id+'.webp'],
                    'attributes':attrs,'state':'Em construção',
                    'minimum':250000,'maximum':300000,'brand':'Construtora Exemplo',
                    'condition':'new','merchantId':id, 'googleEnabled':google,
                    'googleAvailability':'in_stock', 'address':'Rua Modelo, 100', 'city':'Canoas', 'uf':'RS'}
        payload = {'ok':True,'schemaVersion':4, 'sourceContract':'core-imobiliario-v4',
                   'snapshotComplete':True,'totalRows':2,'publishedRows':2,
                   'items':[row('imovel-linq',['Sacada','Churrasqueira','Água quente','2 Dormitórios','Elevador duplo'],True),
                            row('imovel-mezzano',['Sacada','Churrasqueira','Piscina','Rooftop','Elevador duplo'],False)]}
        fixture = root / 'snapshot.json'
        def pipeline():
            fixture.write_text(json.dumps(payload,ensure_ascii=False), encoding='utf-8')
            env = dict(os.environ, PORTAL_FIXTURE=str(fixture))
            for step in ['sinc-data','make-feed-merchantcenter','make-sitemap','make-subpage']:
                subprocess.run([sys.executable,str(root/'scripts'/f'{step}.py')], cwd=root,env=env,check=True,capture_output=True,text=True)
            for step in ['validate_portal_v420','stage_pages_v421','validate_pages_v421']:
                subprocess.run([sys.executable,str(root/'scripts'/f'{step}.py')], cwd=root,env=env,check=True,capture_output=True,text=True)
            subprocess.run([sys.executable,str(root/'scripts'/'validate_xml_v94.py'),'--root',str(root/'_site')], cwd=root,env=env,check=True,capture_output=True,text=True)
        pipeline()
        catalog=json.loads((root/'_site'/'catalogo.json').read_text())
        assert len(catalog['items'])==2
        assert len(catalog['atributos_disponiveis'])==7
        assert len(list((root/'_site'/'imoveis').glob('*/index.html')))==2
        ns={'x':'http://www.sitemaps.org/schemas/sitemap/0.9'}
        assert len(ET.parse(root/'_site'/'sitemap.xml').findall('.//x:loc',ns))==3
        assert len(ET.parse(root/'_site'/'merchant-produtos.xml').findall('./channel/item'))==1
        assert len(ET.parse(root/'_site'/'marketplace-produtos.xml').findall('listing'))==2  # independe do flag Google
        page = root/'_site'/'imoveis'/'imovel-linq'/'index.html'
        assert all(x in page.read_text() for x in ['Acessar página do imóvel','Compartilhar','Água quente'])
        old_url=catalog['items'][0]['pageUrl']
        payload['items'][0]['attributes'].append('Jacuzzi')
        payload['items'][0]['description']='Descrição atualizada com jacuzzi.'
        pipeline()
        updated=json.loads((root/'_site'/'catalogo.json').read_text())
        assert len(updated['atributos_disponiveis'])==8
        assert updated['items'][0]['pageUrl']==old_url
        assert 'Descrição atualizada com jacuzzi.' in page.read_text()
        assert 'Jacuzzi' in page.read_text()
        assert not (root/'_site'/'scripts').exists()
        print('OK: 2 imóveis, 7→8 filtros, feed=1, sitemap=3, atualização de URL e descrição, Pages pronto.')

if __name__ == '__main__':
    run()
