"""Camada 1: consulta arquivo merchant.md; camada 2: serializa Merchant RSS.
Sem dependências externas. Não altera a página de origem nem o catálogo Ads.
"""
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlsplit

G = 'http://base.google.com/ns/1.0'
ET.register_namespace('g', G)
FIELDS = ('id','title','description','availability','condition','price','image_link','link','brand')
ROOT = Path(__file__).resolve().parent.parent
SITE = 'https://mcmv-rs.com.br/'
MD_NAME = os.getenv('MERCHANT_MD_NAME', 'merchant.md')


def url_ok(u):
    try:
        p=urlsplit(u)
        return p.scheme=='https' and bool(p.hostname) and not p.username and not p.password and not any(c.isspace() for c in u)
    except (TypeError,ValueError): return False


def parse_md(raw):
    """Aceita front matter simples chave: valor; description: | com continuação recuada."""
    text=raw.lstrip('\ufeff').replace('\r\n','\n')
    if not text.startswith('---\n'):
        raise ValueError('Esperado YAML front matter no início (---)')
    blocks=text.split('\n---\n',1)
    if len(blocks)!=2: raise ValueError('Fechamento do front matter ausente')
    lines=blocks[0][4:].splitlines()
    data={}; key=None; multiline=False
    for line in lines:
        if multiline and (line.startswith('  ') or not line.strip()):
            data[key]+=('\n' if data[key] else '')+line.strip()
            continue
        multiline=False
        if not line.strip() or line.lstrip().startswith('#'): continue
        if ':' not in line: raise ValueError('Linha inválida: '+line[:100])
        k,v=line.split(':',1); k=k.strip();v=v.strip()
        if k not in FIELDS and k!='enabled': continue
        if k in data: raise ValueError('Campo duplicado: '+k)
        if v=='|': data[k]='';key=k;multiline=True
        else: data[k]=v.strip('"\'')
    return data


def read_md(url):
    """Fixture local opcional para testes, caso contrário HTTPS público."""
    fixtures=os.getenv('MERCHANT_MD_FIXTURES','')
    if fixtures:
        candidate=Path(fixtures)/ (urlsplit(url).hostname+'.md')
        if candidate.exists(): return parse_md(candidate.read_text(encoding='utf-8'))
    md_url=urljoin(url.rstrip('/')+'/',MD_NAME)
    if not url_ok(md_url): raise ValueError('URL insegura')
    req=Request(md_url,headers={'User-Agent':'MCMV-RS-Feed/4.0','Accept':'text/markdown,text/plain'})
    with urlopen(req,timeout=12) as r:
        if r.status!=200: raise ValueError('HTTP '+str(r.status))
        payload=r.read(200_001)
        if len(payload)>200_000: raise ValueError('Markdown muito grande')
        return parse_md(payload.decode('utf-8-sig'))


def normalize_doc(data, source_url):
    if str(data.get('enabled','true')).lower()=='false': return None
    obj={k:re.sub(r'\s+',' ',str(data.get(k,'')).strip()) for k in FIELDS}
    # ID persistente: prioridade arquivo MD. Se ausente, determinístico por URL.
    # Evita UTC novo a cada execução; o UTC deve ser gerado pelo produtor do MD.
    if not obj['id']:
        obj['id']='IMB'+hashlib.sha256(source_url.encode()).hexdigest()[:20].upper()
    if not obj['link']: obj['link']=source_url
    if not obj['title'] or not obj['description'] or not obj['brand']:
        raise ValueError('title/description/brand obrigatórios, sem valores presumidos')
    if obj['availability'] not in ('in_stock','out_of_stock','preorder','backorder'):
        raise ValueError('availability inválido')
    if obj['condition'] not in ('new','used','refurbished'):
        raise ValueError('condition inválido')
    if not re.fullmatch(r'\d+(?:\.\d{2}) BRL',obj['price']):
        raise ValueError('price deve ser 250000.00 BRL')
    if not url_ok(obj['image_link']) or not url_ok(obj['link']):
        raise ValueError('link e image_link devem ser URLs HTTPS completas')
    if urlsplit(obj['link']).hostname != urlsplit(source_url).hostname:
        raise ValueError('link não corresponde ao host da landing page')
    if len(obj['id'])>50: raise ValueError('ID muito longo')
    return obj


def prev_feed(path):
    if not path.exists():return {}
    try:
        root=ET.parse(path).getroot(); result={}
        for item in root.findall('./channel/item'):
            obj={k:(item.findtext('{%s}%s'%(G,k)) or '') for k in FIELDS}
            if obj['link'] and url_ok(obj['link']) and obj['brand']:
                result[urlsplit(obj['link']).hostname]=obj
        return result
    except ET.ParseError: return {}


def make_feed(items):
    rss=ET.Element('rss',{'version':'2.0'}); channel=ET.SubElement(rss,'channel')
    for k,v in [('title','Catálogo de empreendimentos MCMV-RS'),('link',SITE),('description','Registros comerciais de empreendimentos imobiliários')]:
        ET.SubElement(channel,k).text=v
    for obj in sorted(items,key=lambda x:x['id']):
        item=ET.SubElement(channel,'item')
        for k in FIELDS: ET.SubElement(item,'{%s}%s'%(G,k)).text=obj[k]
    ET.indent(rss,space='  ')
    data=b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(rss,encoding='utf-8')+b'\n'
    ET.fromstring(data)
    return data


def build(entries, old_path):
    """Falha isolada: retém registro anterior válido; ausência inédita: não inventa."""
    previous=prev_feed(old_path); output=[]; errors=[]
    for e in entries:
        url=e['url_empreendimento']; host=urlsplit(url).hostname
        try:
            obj=normalize_doc(read_md(url),url)
            if obj is not None:output.append(obj)
        except Exception as exc:
            errors.append(f'{host}: {exc}')
            if host in previous: output.append(previous[host])
    ids=[o['id'] for o in output]
    if len(set(ids))!=len(ids):raise RuntimeError('IDs Merchant duplicados')
    if errors:
        print('AVISOS MD (não removem registros históricos):\n'+'\n'.join(errors))
    if not output:
        # XML antigo sem g:brand não pode ser convertido sem dado verdadeiro.
        # Preserva arquivo anterior em vez de publicar XML vazio.
        if old_path.exists():
            print('Nenhum Markdown válido; XML anterior preservado.')
            return None
        print('Nenhum Markdown válido; XML ainda não será gerado.')
        return None
    # Se algum registro falhar sem anterior, evita apagar dados anteriores por truncamento.
    if errors and old_path.exists():
        prev_count=len(ET.parse(old_path).getroot().findall('./channel/item'))
        if len(output)<prev_count:
            print('Cobertura menor que o feed existente; XML anterior preservado.')
            return None
    return make_feed(output)
