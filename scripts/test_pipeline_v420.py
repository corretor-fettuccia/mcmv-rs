#!/usr/bin/env python3
"""Teste autocontido de pipeline, edição, desativação e idempotência. Sem rede."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

SOURCE = Path(__file__).resolve().parent.parent


def record(uid, attrs, merchant=True):
    return {
        'id':uid,'url':f'https://exemplo.com.br/{uid}/', 'image':f'https://exemplo.com.br/{uid}/share.webp',
        'name':f'Imóvel {uid}', 'highlight':'Resumo da oferta',
        'description':'Descrição completa do imóvel\nCom sacada e garagem.\nContato na landing page.',
        'attributes':attrs,
        'gallery':[f'https://exemplo.com.br/{uid}/share.webp',f'https://exemplo.com.br/{uid}/foto.webp'],
        'propertyType':'apartamento','brand':'Construtora Exemplo','condition':'new',
        'merchantId':uid,'seoTitle':f'Apartamento {uid}',
        'googleEnabled':merchant,'googleAvailability':'in_stock',
        'bedrooms':2,'suites':1,'bathrooms':2,'parking':1,'privateArea':63,
        'totalArea':None,'lotArea':None,'region':'Metropolitana RS','city':'Canoas',
        'neighborhood':'Centro','address':'Rua Exemplo, 123','uf':'RS',
        'state':'Em construção','minimum':250000,'maximum':350000,'campaign':'',
        'campaignText':'','campaignStart':'','campaignEnd':'','order':0}


def exercise(root,fixture):
    env=os.environ.copy()
    env['PORTAL_FIXTURE']=str(fixture)
    env.pop('VITRINE_API_URL',None)
    cmd=[sys.executable,str(root/'scripts'/'core.py')]
    subprocess.run(cmd,cwd=root,env=env,check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(root/'scripts'/'validate_portal_v420.py')],cwd=root,env=env,check=True,stdout=subprocess.DEVNULL)


def run():
    with tempfile.TemporaryDirectory(prefix='core-v420-test-') as temp:
        root=Path(temp)
        shutil.copytree(SOURCE/'scripts',root/'scripts',ignore=shutil.ignore_patterns('__pycache__'))
        (root/'portal-config.json').write_text(json.dumps({'name':'Portal Teste','site_url':'https://teste.example.com/'}),encoding='utf-8')
        fixture=root/'api.json'
        records=[record('imovel_001',['Sacada','Jacuzzi']),record('imovel_002',['Sacada','Piscina'],False)]
        data={'ok':True,'schemaVersion':4,'sourceContract':'core-imobiliario-v4','snapshotComplete':True,
              'totalRows':2,'publishedRows':2,'config':{},'items':records}
        fixture.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        exercise(root,fixture)
        catalog=json.loads((root/'catalogo.json').read_text(encoding='utf-8'))
        assert catalog['filtros']['atributos']==['Jacuzzi','Piscina','Sacada']
        page=root/'imoveis'/'imovel_001'/'index.html'
        source=page.read_text(encoding='utf-8')
        assert 'Descrição completa do imóvel' in source and 'Compartilhar' in source
        assert 'Acessar página do imóvel' in source and 'foto.webp' in source
        assert 'https://teste.example.com/imoveis/imovel_001/' in source
        assert len(ET.parse(root/'merchant-produtos.xml').find('channel').findall('item'))==1
        before={x: (root/x).read_bytes() for x in ['catalogo.json','sitemap.xml','merchant-produtos.xml','imoveis/imovel_001/index.html']}
        exercise(root,fixture)
        assert all((root/x).read_bytes()==content for x,content in before.items()),'Segunda execução deve ser idempotente'
        # Edição de imóvel já existente + um imóvel desativado e exclusão do feed.
        data['items']=[record('imovel_001',['Elevador duplo','Sacada'],False)]
        data['items'][0]['description']='Nova descrição atualizada pela planilha.'
        data['items'][0]['minimum']=270000
        data['publishedRows']=1
        fixture.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        exercise(root,fixture)
        assert 'Nova descrição atualizada pela planilha.' in page.read_text(encoding='utf-8')
        assert '270.000,00' in page.read_text(encoding='utf-8')
        stale=(root/'imoveis'/'imovel_002'/'index.html').read_text(encoding='utf-8')
        assert 'noindex,follow' in stale and 'Imóvel indisponível' in stale
        assert 'imovel_002' not in (root/'sitemap.xml').read_text(encoding='utf-8')
        assert len(ET.parse(root/'merchant-produtos.xml').find('channel').findall('item'))==0
        # Falha da API não pode substituir o catálogo válido.
        previous=(root/'catalogo.json').read_bytes()
        data['snapshotComplete']=False
        fixture.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        result=subprocess.run([sys.executable,str(root/'scripts'/'core.py')],cwd=root,env={**os.environ,'PORTAL_FIXTURE':str(fixture)},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        assert result.returncode!=0 and (root/'catalogo.json').read_bytes()==previous
    print('TESTES V4.2 OK: catálogo, atributos, feed, sitemap, HTML, compartilhar, atualização, inativação e falha da API.')

if __name__=='__main__':
    run()
