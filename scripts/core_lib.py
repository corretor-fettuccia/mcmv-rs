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
import unicodedata
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from datetime import datetime, timezone
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


def attribute_key(value):
    """Chave igual à da vitrine: sem diferença entre acentos e caixa."""
    value = text(value, 120)
    value = unicodedata.normalize('NFD', value)
    return ''.join(char for char in value if not ('\u0300' <= char <= '\u036f')).lower()


def attribute_label(value):
    """Padroniza exibição: 'PISCINA' -> 'Piscina', '02 dormitórios' -> '02 Dormitórios'.

    Maiúscula inicial refere-se à primeira LETRA, não ao primeiro caractere:
    números iniciais são preservados. Restante em caixa baixa, sem alterar acentos.
    """
    label = unicodedata.normalize('NFC', text(value, 120)).lower()
    for i, char in enumerate(label):
        if char.isalpha():
            return label[:i] + char.upper() + label[i + 1:]
    return ''


def _accent_count(value):
    """Na variação equivalente, prefere o rótulo com acentuação existente."""
    return sum(unicodedata.combining(c) for c in unicodedata.normalize('NFD', value))


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
        s = attribute_label(value)
        key = attribute_key(s)
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
        # A cada execução, consulta a implantação /exec atual e ignora caches HTTP
        # intermediários. Não depende da versão anterior do catalogo.json.
        parsed = urlsplit(uri)
        params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                  if k != '_core_refresh']
        params.append(('_core_refresh', str(int(datetime.now(timezone.utc).timestamp() * 1000))))
        fresh_uri = urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                               urlencode(params), parsed.fragment))
        with urlopen(Request(fresh_uri, headers={
            'User-Agent': 'CorePortalV4/1.0', 'Accept': 'application/json',
            'Cache-Control': 'no-cache', 'Pragma': 'no-cache',
        }), timeout=45) as response:
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
        # Marketplace (Meta) só sai do feed por recusa explícita; ausente = publicado.
        'marketplaceEnabled':text(raw.get('marketplaceEnabled','SIM'),10).upper() not in ('FALSE','NAO','NÃO','NO','0'),
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
    # Unifica grafias equivalentes ENTRE imóveis (ex.: 'Agua quente' e
    # 'Água quente'), preferindo o rótulo acentuado quando disponível.
    preferred = {}
    for item in all_items:
        for attr in item['attributes']:
            key = attribute_key(attr)
            if key not in preferred or _accent_count(attr) > _accent_count(preferred[key]):
                preferred[key] = attr
    for item in all_items:
        item['attributes'] = [preferred[attribute_key(attr)] for attr in item['attributes']]
    # Snapshot completo e vazio é válido (todos imóveis inativados).
    identifiers = [i['id'] for i in all_items]
    if len(set(identifiers)) != len(identifiers): raise RuntimeError('IDs repetidos na API')
    return sorted(all_items,key=lambda i:(i['order'],i['name'].casefold(),i['id']))


def catalog_json(items, payload, conf):
    """Catálogo V4 público, incluindo projeção legada com ATRIBUTOS.

    A vitrine usa items[].attributes; leitores legados e agentes podem usar
    empreendimentos[].atributos. Ambas vêm do mesmo registro da API V4.
    """
    # O cadastro pode conter grafias distintas para o mesmo benefício.
    # A vitrine normaliza acentos e maiúsculas: fazer o mesmo aqui evita
    # 26 nomes no JSON vs. 25 filtros reais e falhas na validação do Pages.
    by_key = {}
    for item in items:
        for attr in item['attributes']:
            by_key.setdefault(attribute_key(attr), attr)
    available = sorted(by_key.values(), key=str.casefold)
    legacy = []
    for item in items:
        legacy.append({
            'id': item['id'],
            'nome': item['name'],
            'descricao': item['highlight'] or item['description'],
            'descricao_completa': item['description'],
            'atributos': item['attributes'],
            'galeria': item['gallery'],
            'dormitorios': item['bedrooms'],
            'suites': item['suites'],
            'banheiros': item['bathrooms'],
            'vagas': item['parking'],
            'area_privativa': item['privateArea'],
            'area_total': item['totalArea'],
            'area_terreno': item['lotArea'],
            'tipo_imovel': item['propertyType'],
            'marca': item['brand'],
            'cidade': item['city'],
            'bairro': item['neighborhood'],
            'regiao': item['region'],
            'uf': item['uf'],
            'endereco': item['address'],
            'situacao': item['state'],
            'valor_minimo': item['minimum'],
            'valor_maximo': item['maximum'],
            'imagem': item['image'],
            'url_empreendimento': item['url'],
            'url_detalhes': item['pageUrl'],
            'url_busca': conf['site_url']
        })
    return {
        'schemaVersion': 4,
        'sourceContract': 'core-imobiliario-v4',
        'nome': conf.get('name', 'Portal Imobiliário'),
        'tipo': 'portal_imobiliario',
        'url_principal': conf['site_url'],
        'url_pesquisa': conf['site_url'],
        'config': payload.get('config', {}),
        'snapshotComplete': payload.get('snapshotComplete') is True,
        'total_empreendimentos': len(items),
        'items': items,
        'empreendimentos': legacy,
        'filtros': {
            'campos': ['regiao', 'cidade', 'bairro', 'nome_do_empreendimento', 'situacao', 'renda_familiar', 'atributos'],
            'atributos': available
        },
        'atributos_disponiveis': available,
        'feeds': {
            'google_merchant_xml': conf['site_url'] + 'merchant-produtos.xml',
            'google_ads_csv': conf['site_url'] + 'google-ads-imoveis.csv',
            'meta_marketplace_xml': conf['site_url'] + 'marketplace-produtos.xml',
            'sitemap_xml': conf['site_url'] + 'sitemap.xml'
        }
    }


def put(path, data, force=False):
    """Escrita atômica. force=True recria inclusive um catálogo vazio/antigo."""
    path.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(data,str):data=data.encode('utf-8')
    if not force and path.exists() and path.read_bytes()==data:return False
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(data);tmp.replace(path)
    return True

