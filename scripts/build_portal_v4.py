#!/usr/bin/env python3
"""Core V4: API pública -> JSON completo -> páginas estáticas -> feed Google derivado.

Sem dependências externas. SITEMAP_FIXTURE permite testar sem acessar rede.
NÃO publica se a API estiver vazia/inválida. Dados não existentes não são inventados.
"""
import csv
import html
import io
import json
import os
import re
import sys
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
CFG_FILE = ROOT / 'portal-config.json'
G = 'http://base.google.com/ns/1.0'
SM = 'http://www.sitemaps.org/schemas/sitemap/0.9'
ET.register_namespace('g', G)
ET.register_namespace('', SM)


def settings():
    conf = json.loads(CFG_FILE.read_text(encoding='utf-8'))
    site = conf['site_url'].strip().rstrip('/') + '/'
    if not valid_url(site):
        raise ValueError('site_url inválida em portal-config.json')
    conf['site_url'] = site
    return conf


def valid_url(url):
    if not isinstance(url, str) or not url or any(c.isspace() for c in url):
        return False
    try:
        p = urlsplit(url)
        return p.scheme == 'https' and p.hostname is not None and not p.username and not p.password and p.port in (None, 443)
    except (ValueError, TypeError):
        return False


def text(value, limit=10000):
    return re.sub(r'\s+', ' ', str(value if value is not None else '')).strip()[:limit]


def full_text(value,limit=40000):
    s=str(value if value is not None else '').replace('\r\n','\n').replace('\r','\n')
    s=re.sub(r'[ \t]+',' ',s)
    s=re.sub(r'\n{3,}','\n\n',s)
    return s.strip()[:limit]


def number(value):
    if value is None or str(value).strip() == '' or isinstance(value, bool):
        return None
    try:
        n = float(value)
        if not 0 <= n < 1e13 or n != n: return None
        return int(n) if n.is_integer() else n
    except (ValueError, TypeError): return None


def attributes(value):
    if isinstance(value, list):
        seq = value
    else:
        raw = str(value or '').strip()
        if raw.startswith('['):
            try:
                parsed=json.loads(raw)
                seq=parsed if isinstance(parsed,list) else raw.split(',')
            except ValueError:
                seq=raw.split(',')
        else:
            seq=raw.split(',')
    out, used = [], set()
    for value in seq:
        s = text(value, 120)
        key = ''.join(c for c in s.casefold() if c.isalnum())
        if key and key not in used:out.append(s);used.add(key)
    return out[:100]


def gallery(value, main_image):
    if isinstance(value, list): seq = value
    else:
        try:
            seq = json.loads(value) if value else []
            if not isinstance(seq, list): seq = []
        except (ValueError, TypeError): seq = str(value or '').splitlines()
    urls = [main_image] + seq
    return list(dict.fromkeys(u for u in urls if valid_url(u)))[:60]


def get_payload():
    fixture = os.environ.get('PORTAL_FIXTURE') or os.environ.get('SITEMAP_FIXTURE')
    if fixture:
        data = json.loads(Path(fixture).read_text(encoding='utf-8'))
    else:
        uri = os.environ.get('VITRINE_API_URL','').strip()
        if not valid_url(uri): raise RuntimeError('Configure a variável VITRINE_API_URL no GitHub Actions (não publique a URL no JavaScript da vitrine).')
        with urlopen(Request(uri, headers={'User-Agent': 'CorePortalV4/1.0','Accept':'application/json'}),timeout=45) as response:
            raw = response.read(8_000_001)
        if len(raw) > 8_000_000: raise RuntimeError('API retornou mais que 8MB')
        data = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(data, dict) or data.get('ok') is not True or not isinstance(data.get('items'), list):
        raise RuntimeError('API inválida/legada. Instale a API pública V4.1.6 e configure VITRINE_API_URL com a URL /exec da implantação atualizada. A saída anterior foi preservada.')
    if data.get('schemaVersion') != 4 or data.get('sourceContract') != 'core-imobiliario-v4':
        raise RuntimeError('CONTRATO ANTIGO: a API pública não retornou schemaVersion=4 e sourceContract=core-imobiliario-v4. Publique nova versão do Web App público e ajuste VITRINE_API_URL no GitHub. Não publicar catálogo incompleto.')
    for rownum, entry in enumerate(data['items'], start=1):
        if not isinstance(entry, dict) or not all(k in entry for k in ('attributes', 'description', 'gallery', 'state')):
            raise RuntimeError(f'CONTRATO INCOMPLETO no imóvel {rownum}: API não disponibilizou attributes, description, gallery ou state. Verifique implantação pública V4.1.6.')
        if not isinstance(entry['attributes'], list) or not isinstance(entry['gallery'], list) or not isinstance(entry['description'], str):
            raise RuntimeError(f'TIPOS INVÁLIDOS no imóvel {rownum}: attributes e gallery devem ser listas, description deve ser texto.')
    if not data['items'] and not (data.get('snapshotComplete') is True and data.get('publishedRows') == 0 and isinstance(data.get('totalRows'), int)):
        raise RuntimeError('API vazia sem confirmação de snapshot completo: saída anterior preservada')
    return data


def convert_record(raw, site):
    if not isinstance(raw, dict):return None
    uid = text(raw.get('id'), 120)
    url = text(raw.get('url'), 2000)
    name = text(raw.get('name'), 180)
    main_image = text(raw.get('image'), 2000)
    if not uid or not name or not valid_url(url):raise ValueError('ID, nome e URL de landing page são obrigatórios')
    if not re.fullmatch('[A-Za-z0-9_-]{2,120}', uid):raise ValueError('ID inválido para diretório seguro: '+uid)
    if not valid_url(main_image):raise ValueError('Imagem principal ausente/inválida: '+uid)
    min_price, max_price = number(raw.get('minimum')), number(raw.get('maximum'))
    if min_price is not None and max_price is not None and max_price < min_price:raise ValueError('Preço máximo menor que o mínimo: '+uid)
    fields = {k: number(raw.get(k)) for k in ['bedrooms','suites','bathrooms','parking','privateArea','totalArea','lotArea']}
    description = full_text(raw.get('description'), 40000)
    highlight = text(raw.get('highlight'), 2000)
    # Dados legados do V3 podem não ter descrição completa; preservar sem inventar.
    full = description or highlight
    out = {
        'id':uid,'url':url,'pageUrl':site+'imoveis/'+uid+'/',
        'name':name,'highlight':highlight,'description':full,
        'descriptionSource':'DESCRICAO_COMPLETA' if description else 'OG_DESCRIPTION (legado)',
        'image':main_image,'gallery':gallery(raw.get('gallery'),main_image),
        'attributes':attributes(raw.get('attributes') or raw.get('atributos') or raw.get('ATRIBUTOS') or raw.get('beneficios')),
        'propertyType':text(raw.get('propertyType'),80),'brand':text(raw.get('brand'),140),
        'condition':('used' if text(raw.get('state'),60).casefold()=='usado' else (text(raw.get('condition'),30) or ('new' if text(raw.get('state'),60) in ['Em construção','Pronto para morar'] else ''))),
        'googleEnabled':raw.get('googleEnabled') is True or str(raw.get('googleEnabled','')).upper()=='SIM',
        'googleAvailability':text(raw.get('googleAvailability'),30),
        'merchantId':text(raw.get('merchantId'),80) or uid,
        'seoTitle':text(raw.get('seoTitle'),140),
        'region':text(raw.get('region'),100),'city':text(raw.get('city'),100),
        'neighborhood':text(raw.get('neighborhood'),100),'address':text(raw.get('address'),220),
        'uf':text(raw.get('uf'),2),'state':text(raw.get('state'),100),
        'minimum':min_price,'maximum':max_price,
        'campaign':text(raw.get('campaign'),40), 'campaignText':text(raw.get('campaignText'),140),
        'campaignStart':text(raw.get('campaignStart'),10),'campaignEnd':text(raw.get('campaignEnd'),10),
        'order':number(raw.get('order')) or 0, **fields}
    return out


def normalize(payload, site):
    input_with_attrs=sum(bool(attributes(i['attributes'])) for i in payload['items'])
    all_items = [convert_record(i,site) for i in payload['items']]
    all_items = [i for i in all_items if i]
    output_with_attrs=sum(bool(i['attributes']) for i in all_items)
    print(f'AUDITORIA ATRIBUTOS: API= {input_with_attrs} imóveis com atributos; catálogo= {output_with_attrs} imóveis com atributos.',flush=True)
    if input_with_attrs and output_with_attrs==0:
        raise RuntimeError('A API retornou atributos, mas o catálogo não os recebeu: não publicar snapshot incompleto.')
    # Snapshot completo e vazio é válido (todos imóveis inativados);
    # proteção contra queda abrupta permanece em main().
    identifiers = [i['id'] for i in all_items]
    if len(set(identifiers)) != len(identifiers): raise RuntimeError('IDs repetidos na API')
    return sorted(all_items,key=lambda i:(i['order'],i['name'].casefold(),i['id']))


def catalog_json(items, payload, conf):
    # items: contrato principal da vitrine; empreendimentos: compatibilidade de leitores antigos.
    return {'schemaVersion':4,'sourceContract':'core-imobiliario-v4','nome':conf.get('name','Portal Imobiliário'),'tipo':'portal_imobiliario',
            'url_principal':conf['site_url'],'url_pesquisa':conf['site_url'],
            'config':payload.get('config',{}),'snapshotComplete':payload.get('snapshotComplete') is True,
            'items':items,'empreendimentos':items,
            'total_empreendimentos':len(items),'filtros':{'atributos': sorted({a for i in items for a in i['attributes']},key=str.casefold)},
            'feeds':{'google_merchant_xml':conf['site_url']+'merchant-produtos.xml','google_ads_csv':conf['site_url']+'google-ads-imoveis.csv'}}


def h(v):return html.escape(str(v or ''),quote=True)


def render_page(i,conf):
    site=conf['site_url']
    title=i['seoTitle'] or i['name']+' | '+conf.get('name','Portal Imobiliário')
    desc=(i['highlight'] or i['description'])[:155]
    location=', '.join(filter(None,[i['neighborhood'],i['city'],i['uf']]))
    gallery_html=''.join(f'<figure><img src="{h(url)}" loading="lazy" alt="{h(i["name"])} — foto {n}"></figure>' for n,url in enumerate(i['gallery'],1))
    metrics=[('Dormitórios','bedrooms'),('Suítes','suites'),('Banheiros','bathrooms'),('Vagas','parking'),('Área privativa (m²)','privateArea'),('Área total (m²)','totalArea'),('Terreno (m²)','lotArea')]
    stats=''.join(f'<div><dt>{h(label)}</dt><dd>{h(i[k])}</dd></div>' for label,k in metrics if i[k] is not None)
    features=''.join('<li>'+h(a)+'</li>' for a in i['attributes'])
    price=f'R$ {i["minimum"]:,.2f}'.replace(',','X').replace('.',',').replace('X','.') if i['minimum'] is not None else 'Consulte os valores'
    about={'@context':'https://schema.org','@type':'WebPage','name':title,'description':desc,
           'url':i['pageUrl'],'image':i['image'],'mainEntity':{'@type':'Place','name':i['name'],
           'address':{'@type':'PostalAddress','streetAddress':i['address'],'addressLocality':i['city'],
                      'addressRegion':i['uf'],'addressCountry':'BR'}}}
    ld=json.dumps(about,ensure_ascii=False).replace('<','\\u003c')
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{h(title)}</title><meta name="description" content="{h(desc)}">
<link rel="canonical" href="{h(i['pageUrl'])}"><meta property="og:type" content="website">
<meta property="og:title" content="{h(title)}"><meta property="og:description" content="{h(desc)}">
<meta property="og:url" content="{h(i['pageUrl'])}"><meta property="og:image" content="{h(i['image'])}">
<script type="application/ld+json">{ld}</script>
<style>body{{margin:0;background:#f6f8f9;color:#1c3343;font:16px/1.6 system-ui,-apple-system,Arial,sans-serif}}
header{{background:#173d56;color:white;padding:20px max(4vw,18px)}}header a{{color:white}}main{{max-width:1050px;margin:36px auto;padding:0 20px}}
h1{{font-size:clamp(28px,5vw,45px);line-height:1.16}}.muted{{color:#5c7380}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}}
figure{{margin:0}}figure img{{width:100%;height:260px;object-fit:cover;border-radius:12px}}
.panel{{background:white;border-radius:16px;padding:24px;margin:20px 0;border:1px solid #dde7eb}}
dt{{color:#657e8a;font-size:13px}}dd{{margin:0;font-size:20px;font-weight:700}}
dl{{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:18px}}
.actions{{display:flex;gap:12px;flex-wrap:wrap}}.button{{background:#0d7b80;color:white;text-decoration:none;padding:13px 18px;border-radius:8px;font-weight:700}}
.secondary{{background:#173d56}}li{{margin:4px 0}}.description{{white-space:pre-wrap;overflow-wrap:anywhere}}
</style></head><body><header><a href="{h(site)}">{h(conf.get('name','Portal Imobiliário'))} · Voltar à busca</a></header>
<main><p class="muted">{h(location)} · {h(i['state'])}</p><h1>{h(i['name'])}</h1>
<p class="muted">{h(i['highlight'])}</p><div class="grid" aria-label="Galeria de fotos">{gallery_html}</div>
<section class="panel"><h2>Características do imóvel</h2><dl>{stats}</dl>
<h2>Benefícios e diferenciais</h2><ul>{features or '<li>Características a confirmar</li>'}</ul></section>
<section class="panel"><h2>Descrição completa</h2><div class="description">{h(i['description'])}</div></section>
<section class="panel"><h2>{h(price)}</h2><p>{h(location)}</p><div class="actions"><a class="button" href="{h(i['url'])}" target="_blank" rel="noopener noreferrer">Conhecer o empreendimento</a><a class="button secondary" href="{h(site)}">Voltar ao catálogo</a></div>
<p class="muted">Preços, imagens, condições e disponibilidade devem ser confirmados com o anunciante.</p></section></main></body></html>'''


def sitemap(items,site):
    urlset=ET.Element('{%s}urlset'%SM)
    urls=[site]+[i['pageUrl'] for i in items]+[i['url'] for i in items]
    for u in dict.fromkeys(urls): ET.SubElement(ET.SubElement(urlset,'{%s}url'%SM),'{%s}loc'%SM).text=u
    ET.indent(urlset,space='  ')
    return b'<?xml version="1.0" encoding="utf-8"?>\n'+ET.tostring(urlset,encoding='utf-8')+b'\n'


def make_ads(items):
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=['Listing ID','Listing name','Final URL','Image URL','City name','Description','Price','Property type','Listing type','Contextual keywords','Address'],lineterminator='\n')
    writer.writeheader()
    for i in items:
        writer.writerow({'Listing ID':i['id'],'Listing name':i['name'][:25], 'Final URL':i['pageUrl'],
            'Image URL':i['image'],'City name':i['city'][:25],'Description':i['highlight'][:25],
            'Price':f'{i["minimum"]:.2f} BRL' if i['minimum'] is not None else '',
            'Property type':i['propertyType'] or 'Other','Listing type':'For sale',
            'Contextual keywords':'; '.join(i['attributes'][:5]),'Address':', '.join(filter(None,[i['address'],i['city'],i['uf']]))})
    return out.getvalue().encode('utf-8-sig')



def make_llms(items,conf):
    site=conf['site_url']
    lines=[f'# {conf.get("name","Portal Imobiliário")} — catálogo de imóveis', '',
           f'Pesquisa pública: {site}', f'Catálogo JSON público: {site}catalogo.json','',
           '## Imóveis publicados', '']
    for i in items:
        lines.extend(['### '+i['name'],'- Página: '+i['pageUrl'],
                      '- Landing page: '+i['url'], '- Localização: '+', '.join(filter(None,[i['city'],i['uf']])),
                      '- Descrição: '+i['description'][:600], ''])
    lines.extend(['## Transparência','',
                  'Disponibilidade, financiamento e preços devem ser confirmados com o anunciante.',
                  'Portal independente, sem vínculo institucional com CAIXA ou Governo Federal.' if conf.get('segment')=='MCMV' else 'Anúncios de responsabilidade de seus anunciantes.',''])
    return '\n'.join(lines).encode('utf-8')


def make_robots(conf):
    return f'User-agent: *\nAllow: /\n\nSitemap: {conf["site_url"]}sitemap.xml\n'.encode()

def put(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(data,str):data=data.encode('utf-8')
    if path.exists() and path.read_bytes()==data:return False
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(data);tmp.replace(path)
    return True


def main():
    conf=settings();payload=get_payload();items=normalize(payload,conf['site_url'])
    # Guarda de redução abrupta: protege contra API truncada ou filtro errado.
    previous=[]
    if (ROOT/'catalogo.json').exists():
        try:previous=json.loads((ROOT/'catalogo.json').read_text(encoding='utf-8')).get('items',[])
        except (ValueError,TypeError):previous=[]
    if len(previous)>=4 and len(items)<len(previous)*0.6 and os.environ.get('PORTAL_ALLOW_LARGE_REMOVAL')!='1':
        raise RuntimeError('Redução superior a 40% do catálogo: verifique fonte/API antes de publicar (override PORTAL_ALLOW_LARGE_REMOVAL=1)')
    catalog=catalog_json(items,payload,conf)
    from merchant_from_catalog import build as merchant_projection
    outputs={'catalogo.json':(json.dumps(catalog,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode(),
             'sitemap.xml':sitemap(items,conf['site_url']),
             'merchant-produtos.xml':merchant_projection(catalog),
             'google-ads-imoveis.csv':make_ads(items),
             'llms.txt':make_llms(items, conf),
             'robots.txt':make_robots(conf)}
    # Gera tudo em memória ANTES de modificar os arquivos; ID igual -> URL igual.
    pages={i['id']:render_page(i,conf) for i in items}
    # Proteção contra exclusão por resposta incompleta: a geração jamais remove páginas existentes.
    for path,data in outputs.items():
        if data is None:
            print('Preservado (faltam dados comerciais verificados):',path);continue
        print('Atualizado' if put(ROOT/path,data) else 'Sem alterações',path)
    for uid,page in pages.items():
        put(ROOT/'imoveis'/uid/'index.html',page)
    # Despublicação segura: somente páginas anteriormente cadastradas no catálogo
    # e cujo registro deixou de ser público recebem noindex (não são excluídas).
    removed={x.get('id') for x in previous if isinstance(x,dict)}-set(pages)
    for uid in removed:
        if uid and re.fullmatch('[A-Za-z0-9_-]{2,120}',uid):
            old=ROOT/'imoveis'/uid/'index.html'
            if old.exists():
                put(old,'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="robots" content="noindex, follow"><title>Imóvel indisponível</title></head><body><main><h1>Imóvel indisponível</h1><p>Este anúncio não está mais publicado.</p><a href="'+html.escape(conf['site_url'],quote=True)+'">Voltar à busca de imóveis</a></main></body></html>')
    print(f'Core V4: {len(items)} imóveis, {len(catalog["filtros"]["atributos"])} filtros de atributos, {len(pages)} páginas HTML, {len(removed)} retiradas de publicação.')
    # Observação: não remover páginas antigas automaticamente. Desativação requer rotina explícita
    # de revisão/depublicação que preserve histórico e redirecionamentos.


if __name__=='__main__':
    try:main()
    except Exception as e:print('ERRO V4:',e,file=sys.stderr);sys.exit(1)
