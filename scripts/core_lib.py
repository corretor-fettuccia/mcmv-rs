#!/usr/bin/env python3
"""Núcleo comum da V10: API pública do Apps Script -> catalogo.json (fonte única).

Sem dependências externas. Dado ausente não é inventado. Nenhum motor consulta a API,
a planilha ou as landing pages: todos leem o catalogo.json gerado por sync_catalog.py.
"""
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = 'core-imobiliario-v4'  # contrato da API pública; a V10 não exige mudar o Apps Script


def settings():
    conf = json.loads((ROOT / 'portal-config.json').read_text(encoding='utf-8'))
    site = conf['site_url'].strip().rstrip('/') + '/'
    if not valid_url(site):
        raise ValueError('site_url inválida em portal-config.json')
    conf['site_url'] = site
    return conf


def valid_url(url):
    """https público, sem espaços, credenciais ou porta (barra data:/base64 e http)."""
    if not isinstance(url, str) or not url or any(c.isspace() for c in url):
        return False
    try:
        p = urlsplit(url)
        return p.scheme == 'https' and p.hostname is not None and not p.username and not p.password and p.port in (None, 443)
    except (ValueError, TypeError):
        return False


def text(value, limit=10000):
    return re.sub(r'\s+', ' ', str(value if value is not None else '')).strip()[:limit]


def full_text(value, limit=40000):
    s = str(value if value is not None else '').replace('\r\n', '\n').replace('\r', '\n')
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()[:limit]


def number(value):
    if value is None or str(value).strip() == '' or isinstance(value, bool):
        return None
    try:
        n = float(value)
        if not 0 <= n < 1e13 or n != n:
            return None
        return int(n) if n.is_integer() else n
    except (ValueError, TypeError):
        return None


def attribute_key(value):
    """Chave igual à da vitrine: sem diferença entre acentos e caixa."""
    value = unicodedata.normalize('NFD', text(value, 120))
    return ''.join(c for c in value if not ('̀' <= c <= 'ͯ')).lower()


def attribute_label(value):
    """Padroniza a exibição: 'PISCINA' -> 'Piscina', '02 dormitórios' -> '02 Dormitórios' (primeira LETRA)."""
    label = unicodedata.normalize('NFC', text(value, 120)).lower()
    for i, char in enumerate(label):
        if char.isalpha():
            return label[:i] + char.upper() + label[i + 1:]
    return ''


def _accent_count(value):
    return sum(unicodedata.combining(c) for c in unicodedata.normalize('NFD', value))


def attributes(value):
    if isinstance(value, list):
        seq = value
    else:
        raw = str(value or '').strip()
        seq = raw.split(',')
        if raw.startswith('['):
            try:
                parsed = json.loads(raw)
                seq = parsed if isinstance(parsed, list) else seq
            except ValueError:
                pass
    out, used = [], set()
    for value in seq:
        label = attribute_label(value)
        key = attribute_key(label)
        if key and key not in used:
            out.append(label)
            used.add(key)
    return out[:100]


def gallery(value, main_image):
    """Imagem principal primeiro; só https; sem repetição; até 60."""
    if isinstance(value, list):
        seq = value
    else:
        try:
            seq = json.loads(value) if value else []
            seq = seq if isinstance(seq, list) else []
        except (ValueError, TypeError):
            seq = str(value or '').splitlines()
    return list(dict.fromkeys(u for u in [main_image] + seq if valid_url(u)))[:60]


def _fetch(url):
    # shortcut: 3 tentativas com espera fixa; o Apps Script às vezes responde 5xx isolado. Aumentar se for frequente.
    last = None
    for attempt in range(1, 4):
        try:
            req = Request(url, headers={'User-Agent': 'MCMV-RS-Core/10', 'Accept': 'application/json',
                                        'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
            with urlopen(req, timeout=45) as response:
                raw = response.read(8_000_001)
            if len(raw) > 8_000_000:
                raise RuntimeError('API retornou mais que 8MB')
            return json.loads(raw.decode('utf-8-sig'))
        except (OSError, ValueError) as exc:
            last = exc
            print(f'[api] tentativa {attempt}/3 falhou: {exc}', flush=True)
            if attempt < 3:
                time.sleep(5 * attempt)
    raise RuntimeError(f'API do Apps Script inacessível ou fora do JSON: {last}')


def get_payload():
    """Lê a API pública (VITRINE_API_URL) ou, em teste, o arquivo PORTAL_FIXTURE. Valida o contrato."""
    fixture = os.environ.get('PORTAL_FIXTURE')
    if fixture:
        data = json.loads(Path(fixture).read_text(encoding='utf-8-sig'))
    else:
        uri = os.environ.get('VITRINE_API_URL', '').strip()
        if not valid_url(uri):
            raise RuntimeError('Configure VITRINE_API_URL (URL /exec https do Apps Script) em Settings > Secrets and variables > Actions.')
        parsed = urlsplit(uri)  # parâmetro de tempo: ignora caches intermediários, sempre o estado atual da planilha
        params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != '_core_refresh']
        params.append(('_core_refresh', str(int(datetime.now(timezone.utc).timestamp() * 1000))))
        data = _fetch(urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(params), parsed.fragment)))
    if not isinstance(data, dict) or data.get('ok') is not True or not isinstance(data.get('items'), list):
        raise RuntimeError(f'API inválida: esperado ok=true e items[]; recebido erro={str(data.get("error", ""))[:120] if isinstance(data, dict) else type(data).__name__}')
    if data.get('schemaVersion') != 4 or data.get('sourceContract') != CONTRACT:
        raise RuntimeError(f'Contrato da API diferente do esperado (schemaVersion 4 / {CONTRACT}). Publique nova versão do Web App.')
    for n, entry in enumerate(data['items'], start=1):
        if not isinstance(entry, dict) or not all(k in entry for k in ('attributes', 'description', 'gallery', 'state')):
            raise RuntimeError(f'Imóvel {n} sem attributes, description, gallery ou state: implantação da API desatualizada.')
        if not isinstance(entry['attributes'], list) or not isinstance(entry['gallery'], list) or not isinstance(entry['description'], str):
            raise RuntimeError(f'Imóvel {n}: attributes e gallery devem ser listas e description, texto.')
    total, published = data.get('totalRows'), data.get('publishedRows')
    if (data.get('snapshotComplete') is not True or type(total) is not int or type(published) is not int
            or total < 0 or published < 0 or published > total or published != len(data['items'])):
        raise RuntimeError('Snapshot da API incompleto ou inconsistente: nada é publicado.')
    return data


def convert_record(raw, site):
    uid = text(raw.get('id'), 120)
    url = text(raw.get('url'), 2000)
    name = text(raw.get('name'), 180)
    main_image = text(raw.get('image'), 2000)
    if not uid or not name or not valid_url(url):
        raise ValueError(f'ID, nome e URL https da landing page são obrigatórios (id={uid or "?"})')
    if not re.fullmatch('[A-Za-z0-9_-]{2,120}', uid):
        raise ValueError('ID inválido para diretório seguro: ' + uid)
    if not valid_url(main_image):
        raise ValueError('Imagem principal ausente/inválida: ' + uid)
    low, high = number(raw.get('minimum')), number(raw.get('maximum'))
    if low is not None and high is not None and high < low:
        raise ValueError('Preço máximo menor que o mínimo: ' + uid)
    description = full_text(raw.get('description'), 40000)
    highlight = text(raw.get('highlight'), 2000)
    state = text(raw.get('state'), 100)
    return {
        'id': uid, 'url': url, 'pageUrl': site + 'imoveis/' + uid + '/',
        'name': name, 'highlight': highlight, 'description': description or highlight,
        'descriptionSource': 'DESCRICAO_COMPLETA' if description else 'OG_DESCRIPTION',
        'image': main_image, 'gallery': gallery(raw.get('gallery'), main_image),
        'attributes': attributes(raw.get('attributes')),
        'propertyType': text(raw.get('propertyType'), 80), 'brand': text(raw.get('brand'), 140),
        'condition': 'used' if state.casefold() == 'usado' else (
            text(raw.get('condition'), 30) or ('new' if state in ('Em construção', 'Pronto para morar') else '')),
        'googleEnabled': raw.get('googleEnabled') is True or str(raw.get('googleEnabled', '')).upper() == 'SIM',
        'googleAvailability': text(raw.get('googleAvailability'), 30),
        # Marketplace (Meta): só sai do feed por recusa explícita; ausente = publicado.
        'marketplaceEnabled': text(raw.get('marketplaceEnabled', 'SIM'), 10).upper() not in ('FALSE', 'NAO', 'NÃO', 'NO', '0'),
        'merchantId': text(raw.get('merchantId'), 80) or uid,
        'seoTitle': text(raw.get('seoTitle'), 140),
        'region': text(raw.get('region'), 100), 'city': text(raw.get('city'), 100),
        'neighborhood': text(raw.get('neighborhood'), 100), 'address': text(raw.get('address'), 220),
        'uf': text(raw.get('uf'), 2), 'state': state,
        'minimum': low, 'maximum': high,
        'campaign': text(raw.get('campaign'), 40), 'campaignText': text(raw.get('campaignText'), 140),
        'campaignStart': text(raw.get('campaignStart'), 10), 'campaignEnd': text(raw.get('campaignEnd'), 10),
        'order': number(raw.get('order')) or 0,
        **{k: number(raw.get(k)) for k in ('bedrooms', 'suites', 'bathrooms', 'parking', 'privateArea', 'totalArea', 'lotArea')}}


def normalize(payload, site):
    """Converte todos os imóveis (um inválido derruba a publicação) e unifica grafias de atributos."""
    items = [convert_record(i, site) for i in payload['items']]
    if sum(bool(attributes(i['attributes'])) for i in payload['items']) and not any(i['attributes'] for i in items):
        raise RuntimeError('A API enviou atributos, mas o catálogo não os recebeu.')
    preferred = {}
    for item in items:
        for attr in item['attributes']:
            key = attribute_key(attr)
            if key not in preferred or _accent_count(attr) > _accent_count(preferred[key]):
                preferred[key] = attr
    for item in items:
        item['attributes'] = [preferred[attribute_key(a)] for a in item['attributes']]
    ids = [i['id'] for i in items]
    if len(set(ids)) != len(ids):
        raise RuntimeError('IDs repetidos na API')
    return sorted(items, key=lambda i: (i['order'], i['name'].casefold(), i['id']))


def catalog_json(items, payload, conf):
    """Catálogo público: items[] (vitrine, feeds, páginas) + empreendimentos[] (leitores legados e agentes)."""
    available = sorted({attribute_key(a): a for i in items for a in i['attributes']}.values(), key=str.casefold)
    legacy = [{
        'id': i['id'], 'nome': i['name'], 'descricao': i['highlight'] or i['description'],
        'descricao_completa': i['description'], 'atributos': i['attributes'], 'galeria': i['gallery'],
        'dormitorios': i['bedrooms'], 'suites': i['suites'], 'banheiros': i['bathrooms'], 'vagas': i['parking'],
        'area_privativa': i['privateArea'], 'area_total': i['totalArea'], 'area_terreno': i['lotArea'],
        'tipo_imovel': i['propertyType'], 'marca': i['brand'], 'cidade': i['city'], 'bairro': i['neighborhood'],
        'regiao': i['region'], 'uf': i['uf'], 'endereco': i['address'], 'situacao': i['state'],
        'valor_minimo': i['minimum'], 'valor_maximo': i['maximum'], 'imagem': i['image'],
        'url_empreendimento': i['url'], 'url_detalhes': i['pageUrl'], 'url_busca': conf['site_url']} for i in items]
    site = conf['site_url']
    return {
        'schemaVersion': 4, 'sourceContract': CONTRACT,
        'nome': conf.get('name', 'Portal Imobiliário'), 'tipo': 'portal_imobiliario',
        'url_principal': site, 'url_pesquisa': site,
        'config': payload.get('config', {}), 'snapshotComplete': True,
        'total_empreendimentos': len(items), 'items': items, 'empreendimentos': legacy,
        'filtros': {'campos': ['regiao', 'cidade', 'bairro', 'nome_do_empreendimento', 'situacao', 'renda_familiar', 'atributos'],
                    'atributos': available},
        'atributos_disponiveis': available,
        'feeds': {'google_merchant_xml': site + 'merchant-produtos.xml', 'google_ads_csv': site + 'google-ads-imoveis.csv',
                  'meta_marketplace_xml': site + 'marketplace-produtos.xml', 'sitemap_xml': site + 'sitemap.xml'}}


def load_catalog(root=ROOT):
    """Lê o catalogo.json local e confere o contrato; é a única entrada dos demais motores."""
    path = Path(root) / 'catalogo.json'
    if not path.is_file():
        raise RuntimeError('catalogo.json ausente: execute sync_catalog.py antes.')
    catalog = json.loads(path.read_text(encoding='utf-8'))
    if (catalog.get('schemaVersion') != 4 or catalog.get('sourceContract') != CONTRACT
            or catalog.get('snapshotComplete') is not True or not isinstance(catalog.get('items'), list)
            or catalog.get('total_empreendimentos') != len(catalog['items'])):
        raise RuntimeError('catalogo.json fora do contrato V4 / snapshot completo.')
    return catalog


def diff_catalogs(old_items, new_items):
    """(novos, alterados, removidos) por id, comparando o conteúdo completo de cada imóvel."""
    old = {i.get('id'): i for i in old_items if isinstance(i, dict)}
    new = {i['id']: i for i in new_items}
    return ([i for i in new if i not in old],
            [i for i in new if i in old and old[i] != new[i]],
            [i for i in old if i not in new])


def put(path, data):
    """Escrita atômica; devolve True se o conteúdo mudou."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode('utf-8')
    if path.exists() and path.read_bytes() == data:
        return False
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_bytes(data)
    tmp.replace(path)
    return True
