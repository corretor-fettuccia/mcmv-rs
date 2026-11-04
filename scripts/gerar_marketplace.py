#!/usr/bin/env python3
"""Compila feed de imóveis Meta a partir do catálogo MCMV-RS, sem dependências externas."""
import argparse
import json
import logging
import os
import re
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse, urljoin

DEFAULT_SOURCE = 'https://mcmv-rs.com.br/catalogo.json'
DEFAULT_OUTPUT = 'marketplace-produtos.xml'
FEED_PUBLIC_URL = 'https://mcmv-rs.com.br/marketplace-produtos.xml'
# Evita multiplicar itens pelas duas representações de dados no schema v4.
REQUIRED_CONTRACT = 'core-imobiliario-v4'
MAX_IMAGES = 20

def valid_https_url(value):
    if not isinstance(value, str):
        return False
    v = urlparse(value.strip())
    return v.scheme == 'https' and bool(v.netloc) and not any(c.isspace() for c in value)

def get_json(source):
    if source.startswith(('https://','http://')):
        if not source.startswith('https://'):
            raise ValueError('A fonte remota precisa usar HTTPS')
        req = urllib.request.Request(source,headers={'User-Agent':'MCMV-RS-MarketplaceFeed/1.0','Accept':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as resp:
            raw = resp.read(8_000_001)
            if len(raw)>8_000_000:
                raise ValueError('Catálogo excede 8 MB')
        return json.loads(raw.decode('utf-8-sig'))
    return json.loads(Path(source).read_text(encoding='utf-8-sig'))

def check_contract(doc):
    if not isinstance(doc,dict):
        raise ValueError('O catálogo não é um objeto JSON')
    if doc.get('schemaVersion') != 4 or doc.get('sourceContract') != REQUIRED_CONTRACT:
        raise ValueError('Contrato inesperado: exigido core-imobiliario-v4 / schemaVersion 4')
    if doc.get('snapshotComplete') is not True:
        raise ValueError('Snapshot incompleto: arquivo existente preservado')
    items = doc.get('items')
    if not isinstance(items,list) or not items:
        raise ValueError('Lista items vazia: arquivo existente preservado')
    total = doc.get('total_empreendimentos')
    if type(total) is not int or total != len(items):
        raise ValueError(f'Contagem inconsistente: total_empreendimentos={total}, items={len(items)}')
    ids=[x.get('id') for x in items if isinstance(x,dict)]
    if len(ids)!=len(items) or any(not str(x or '').strip() for x in ids) or len(set(ids))!=len(ids):
        raise ValueError('IDs ausentes ou duplicados: arquivo existente preservado')
    return items

def text_value(value, limit=5000):
    s = re.sub(r'\s+', ' ', str(value or '')).strip()
    return ''.join(ch for ch in s if ch in '\t\n\r' or ord(ch)>=32)[:limit]

def money(value):
    if isinstance(value,bool) or value is None:
        return None
    try:
        d=Decimal(str(value))
        if not d.is_finite() or d<=0:
            return None
        return f'{d:.2f} BRL'
    except (InvalidOperation,ValueError):
        return None

def distinct_images(item):
    candidates=[]
    first=item.get('image')
    if isinstance(first,str): candidates.append(first)
    if isinstance(item.get('gallery'),list): candidates.extend(item['gallery'])
    seen=set(); result=[]
    for value in candidates:
        if not valid_https_url(value): continue
        url=value.strip()
        if url in seen: continue
        seen.add(url); result.append(url)
        if len(result)>=MAX_IMAGES: break
    return result

def optional_int(value):
    if type(value) is int and value>=0: return str(value)
    return None

def make_listing(item):
    ident=text_value(item.get('id'),100)
    name=text_value(item.get('name'),150)
    city=text_value(item.get('city'),150)
    region=text_value(item.get('uf'),20)
    address=text_value(item.get('address'),240)
    url=item.get('pageUrl') if valid_https_url(item.get('pageUrl')) else item.get('url')
    price=money(item.get('minimum'))
    images=distinct_images(item)
    if item.get('marketplaceEnabled') is False:
        return None, 'publicação Meta desativada explicitamente'
    if not (ident and name and city and region and address and price and valid_https_url(url) and images):
        return None, 'falta ID, título, cidade, UF, endereço, preço, URL ou imagem'

    node=ET.Element('listing')
    def add(tag,val):
        if val is not None and str(val).strip(): ET.SubElement(node,tag).text=str(val)
    add('home_listing_id',ident)
    add('name',name)
    # Não utilizar "in_stock" como status Meta: são vocabulários diferentes.
    add('availability','for_sale')
    highlight=text_value(item.get('highlight'),1200)
    desc=highlight or text_value(item.get('description'),1200)
    if not desc: desc=name
    add('description',desc)
    addr=ET.SubElement(node,'address',{'format':'simple'})
    def component(n,v):
        if v: ET.SubElement(addr,'component',{'name':n}).text=v
    component('addr1',address)
    component('city',city)
    component('region',region)
    component('country','BR')
    # Ignorar bairro divergente do endereço: sem inferências geográficas.
    neighborhood=text_value(item.get('neighborhood'),150)
    if neighborhood and neighborhood.casefold() in address.casefold(): add('neighborhood',neighborhood)
    for img in images:
        ET.SubElement(ET.SubElement(node,'image'),'url').text=img
    add('listing_type','for_sale_by_agent')
    add('num_beds',optional_int(item.get('bedrooms')))
    add('num_baths',optional_int(item.get('bathrooms')))
    if isinstance(item.get('privateArea'),(int,float)) and item['privateArea']>0:
        add('area_size',str(item['privateArea']))
        add('area_unit','sq_m')
    # price é o valor mínimo do empreendimento. Não é uma unidade individual confirmada.
    add('price',price)
    prop=str(item.get('propertyType') or '').casefold()
    if 'apartamento' in prop: add('property_type','apartment')
    elif 'casa' in prop: add('property_type','house')
    elif 'terreno' in prop or 'lote' in prop: add('property_type','land')
    add('url',url)
    return node,None

def compile_xml(doc, feed_url=None):
    items=check_contract(doc)
    site_url=doc.get('url_principal')
    if not valid_https_url(feed_url):
        feed_url=urljoin(site_url.rstrip('/')+'/',DEFAULT_OUTPUT) if valid_https_url(site_url) else FEED_PUBLIC_URL
    title=text_value(doc.get('nome'),150) or 'MCMV-RS'
    root=ET.Element('listings')
    ET.SubElement(root,'title').text=f'{title} — Empreendimentos'
    ET.SubElement(root,'link',{'rel':'self','href':feed_url})
    included=0; excluded=[]
    for item in items:
        listing,reason=make_listing(item)
        if listing is not None:
            root.append(listing); included+=1
        else:
            excluded.append({'id':str(item.get('id','?')),'motivo':reason})
    if included == 0:
        raise ValueError('Nenhum item válido: arquivo existente preservado')
    ET.indent(root,space='  ')
    content=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    ET.fromstring(content)
    return content,{'recebidos':len(items),'incluidos':included,'excluidos':excluded}

def atomic_write(path,content):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=f'.{path.name}.',suffix='.tmp',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as fh: fh.write(content)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def main(argv=None):
    parser=argparse.ArgumentParser(description='Gerar feed XML de imóveis Meta a partir do MCMV-RS')
    parser.add_argument('--source',default=DEFAULT_SOURCE)
    parser.add_argument('--output',default=DEFAULT_OUTPUT)
    parser.add_argument('--report',default=None)
    parser.add_argument('--feed-url',default=None,help='URL pública do arquivo XML (opcional)')
    args=parser.parse_args(argv)
    try:
        content,report=compile_xml(get_json(args.source),feed_url=args.feed_url)
        if args.report:
            atomic_write(args.report,json.dumps(report,ensure_ascii=False,indent=2).encode('utf-8'))
        atomic_write(args.output,content)
        logging.info('Criado %s: %d incluídos, %d excluídos',args.output,report['incluidos'],len(report['excluidos']))
        for skipped in report['excluidos']:
            logging.warning('Excluído %s: %s',skipped['id'],skipped['motivo'])
        return 0
    except Exception as exc:
        logging.error('Falha segura; feed anterior não alterado: %s',exc)
        return 1

if __name__=='__main__':
    logging.basicConfig(format='%(levelname)s: %(message)s',level=logging.INFO)
    sys.exit(main())
