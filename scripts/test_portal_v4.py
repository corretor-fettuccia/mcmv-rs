"""Rodar: python scripts/test_portal_v4.py (sem rede, usa diretório temporário)."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parent.parent


def run():
    with TemporaryDirectory(prefix='core-v4-') as work:
        tmp=Path(work)
        shutil.copytree(ROOT,tmp/'site',ignore=shutil.ignore_patterns('.git','__pycache__'))
        site=tmp/'site'
        sample={'ok':True,'schemaVersion':4,'sourceContract':'core-imobiliario-v4','config':{'simuladorAtivo':True,'faixasRenda':[],
           'prazoMeses':420,'fatorRenda':0.30,'jurosAno':0.08,'intervaloPercentual':20},
           'items':[{'id':'TESTE01','name':'Apartamento fictício — somente teste',
            'url':'https://exemplo.com.br/imovel01/','image':'https://exemplo.com.br/foto.webp',
            'description':'Descrição integral de teste.\nSegundo parágrafo.', 'state':'Em construção',
            'highlight':'Destaque de teste','attributes':['Sacada','Jacuzzi'],
            'gallery':['https://exemplo.com.br/foto.webp'],'city':'Canoas',
            'minimum':250000,'brand':'Construtora fictícia para teste','condition':'new',
            'googleEnabled':True,'googleAvailability':'in_stock'}],
            'snapshotComplete':True,'publishedRows':1,'totalRows':1}
        fixture=tmp/'fixture.json';fixture.write_text(json.dumps(sample,ensure_ascii=False),encoding='utf-8')
        env=dict(os.environ,PORTAL_FIXTURE=str(fixture),PORTAL_ALLOW_LARGE_REMOVAL='1')
        script=site/'scripts'/'build_portal_v4.py'
        subprocess.run([sys.executable,str(script)],env=env,check=True)
        subprocess.run([sys.executable,str(site/'scripts'/'validate_portal_v4.py')],check=True)
        doc=json.loads((site/'catalogo.json').read_text(encoding='utf-8'))
        assert doc['items'][0]['description']=='Descrição integral de teste.\nSegundo parágrafo.'
        assert doc['items'][0]['attributes']==['Sacada','Jacuzzi']
        page=site/'imoveis'/'TESTE01'/'index.html'
        assert page.exists() and 'Segundo parágrafo' in page.read_text()
        assert len(ET.parse(site/'merchant-produtos.xml').findall('.//item'))==1
        xml=ET.parse(site/'merchant-produtos.xml')
        item=xml.find('.//item')
        assert item.find('{http://base.google.com/ns/1.0}availability').text == 'in_stock'
        # Se desativar apenas Google, despublica XML sem remover imóvel da vitrine.
        sample['items'][0]['googleEnabled']=False
        fixture.write_text(json.dumps(sample,ensure_ascii=False),encoding='utf-8')
        subprocess.run([sys.executable,str(script)],env=env,check=True)
        assert len(ET.parse(site/'merchant-produtos.xml').findall('.//item'))==0
        assert len(json.loads((site/'catalogo.json').read_text())['items'])==1
        # Se habilitar indisponibilidade comercial, continua no feed como out_of_stock.
        sample['items'][0]['googleEnabled']=True
        sample['items'][0]['googleAvailability']='out_of_stock'
        fixture.write_text(json.dumps(sample,ensure_ascii=False),encoding='utf-8')
        subprocess.run([sys.executable,str(script)],env=env,check=True)
        item=ET.parse(site/'merchant-produtos.xml').find('.//item')
        assert item.find('{http://base.google.com/ns/1.0}availability').text=='out_of_stock'
        # Status do portal: ao inativar, um snapshot vazio verificado retira o imóvel de ambos os canais.
        sample['items']=[];sample['publishedRows']=0
        fixture.write_text(json.dumps(sample,ensure_ascii=False),encoding='utf-8')
        subprocess.run([sys.executable,str(script)],env=env,check=True)
        assert len(json.loads((site/'catalogo.json').read_text())['items'])==0
        assert len(ET.parse(site/'merchant-produtos.xml').findall('.//item'))==0
        inactive=(site/'imoveis'/'TESTE01'/'index.html').read_text()
        assert 'noindex' in inactive
        # Falha não pode substituir saída anterior
        prior=(site/'catalogo.json').read_bytes()
        fixture.write_text('{"ok":true,"items":[]}',encoding='utf-8')
        assert subprocess.run([sys.executable,str(script)],env=env,capture_output=True).returncode!=0
        assert prior==(site/'catalogo.json').read_bytes()
        # A API antiga deve ser rejeitada sem modificar o catálogo anterior.
        sample['items']=[{'id':'TESTE01','name':'Sem atributos','url':'https://exemplo.com.br/imovel01/',
                           'image':'https://exemplo.com.br/foto.webp'}]
        sample['publishedRows']=1
        del sample['schemaVersion']
        fixture.write_text(json.dumps(sample,ensure_ascii=False),encoding='utf-8')
        attempt=subprocess.run([sys.executable,str(script)],env=env,capture_output=True,text=True)
        assert attempt.returncode!=0 and 'CONTRATO ANTIGO' in attempt.stderr,attempt.stderr
        assert prior==(site/'catalogo.json').read_bytes()

        print('TESTES V4.1 PASSARAM (HTML, filtros, Merchant on/off, out_of_stock, desativação, snapshot, falha fechada).')

if __name__=='__main__':run()
