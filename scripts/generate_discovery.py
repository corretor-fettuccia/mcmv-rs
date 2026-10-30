#!/usr/bin/env python3
"""Gera sitemap.xml, llms.txt, catalogo.json e robots.txt a partir da API.
Não altera HTML, app.js ou config.js. Preserva saídas quando API falha.
"""
import hashlib
import csv
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
SITE = 'https://mcmv-rs.com.br/'
API_FALLBACK = 'https://script.google.com/macros/s/AKfycbxYTaWNG6o_5NqPq3D16_isTpmTPWgYa3NureFuHz21fG-x-rDfqM1RMXxWog_5sHxxSQ/exec'
NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
ET.register_namespace('', NS)


def api_url():
    if os.getenv('VITRINE_API_URL', '').strip():
        return os.environ['VITRINE_API_URL'].strip()
    config = ROOT / 'config.js'
    if config.is_file():
        match = re.search(r'''window\s*\.\s*VITRINE_API_URL\s*=\s*['"]([^'"]+)['"]''', config.read_text(encoding='utf-8'))
        if match:
            return match.group(1)
    return API_FALLBACK


def load_payload():
    fixture = os.getenv('SITEMAP_FIXTURE', '').strip()
    if fixture:
        raw = Path(fixture).read_bytes()
    else:
        endpoint = api_url()
        if not endpoint.startswith('https://'):
            raise RuntimeError('Endpoint precisa usar HTTPS')
        req = Request(endpoint, headers={'Accept': 'application/json', 'User-Agent': 'MCMV-RS-Discovery/2.0'})
        print('Consultando API:', endpoint, flush=True)
        try:
            with urlopen(req, timeout=40) as response:
                raw = response.read(5_000_001)
                print('HTTP:', response.status, flush=True)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f'Erro ao consultar API: {exc}') from exc
    if len(raw) > 5_000_000:
        raise RuntimeError('Resposta maior que 5 MB')
    try:
        data = json.loads(raw.decode('utf-8-sig'))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError('Resposta não é JSON válido') from exc
    if not isinstance(data, dict) or data.get('ok') is not True:
        raise RuntimeError('API não retornou ok:true')
    if not isinstance(data.get('items'), list) or not data['items']:
        raise RuntimeError('items ausente/vazio; saídas anteriores preservadas')
    return data


def valid_url(value):
    if not isinstance(value, str) or not value.strip() or any(c.isspace() for c in value):
        return None
    try:
        p = urlsplit(value.strip())
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
            return None
    except ValueError:
        return None
    return urlunsplit(('https', p.netloc.lower(), p.path or '/', p.query, ''))


def clean(value, limit=500):
    return re.sub(r'\s+', ' ', str(value or '')).strip()[:limit]


def price(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return int(value) if float(value).is_integer() else value


def normalize(payload):
    result, ids = [], set()
    for item in payload['items']:
        if not isinstance(item, dict) or item.get('indexar') is False or item.get('noindex') is True:
            continue
        url, name = valid_url(item.get('url')), clean(item.get('name'), 140)
        if not url or not name:
            print('Ignorado registro sem nome/URL válido:', clean(item.get('name') if isinstance(item, dict) else '', 60))
            continue
        ident = clean(item.get('id'), 120) or hashlib.sha256(url.encode()).hexdigest()[:16]
        if ident in ids:
            raise RuntimeError(f'ID duplicado: {ident}')
        ids.add(ident)
        low, high = price(item.get('minimum')), price(item.get('maximum'))
        if low is not None and high is not None and low > high:
            raise RuntimeError(f'Preços invertidos: {name}')
        image = valid_url(item.get('image'))
        if not image:
            raise RuntimeError(f'Imagem ausente ou URL inválida para: {name}; geração cancelada')
        result.append({
            'id': ident, 'nome': name, 'descricao': clean(item.get('highlight'), 600),
            'cidade': clean(item.get('city'), 90), 'bairro': clean(item.get('neighborhood'), 90),
            'regiao': clean(item.get('region'), 90), 'uf': clean(item.get('uf'), 2),
            'endereco': clean(item.get('address'), 200), 'situacao': clean(item.get('state'), 80),
            'valor_minimo': low, 'valor_maximo': high,
            'imagem': image, 'url_empreendimento': url, 'url_busca': SITE
        })
    if not result:
        raise RuntimeError('Nenhum empreendimento válido; saídas preservadas')
    result.sort(key=lambda x: (x['cidade'].casefold(), x['bairro'].casefold(), x['nome'].casefold(), x['id']))
    return result


def make_sitemap(entries):
    urls = {SITE}
    urls.update(e['url_empreendimento'] for e in entries)
    root = ET.Element(f'{{{NS}}}urlset')
    for url in [SITE] + sorted(urls - {SITE}):
        ET.SubElement(ET.SubElement(root, f'{{{NS}}}url'), f'{{{NS}}}loc').text = url
    ET.indent(root, space='  ')
    xml = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='utf-8') + b'\n'
    ET.fromstring(xml)
    return xml


def make_catalog(entries):
    document = {
        'nome': 'MCMV-RS', 'tipo': 'portal_independente_de_busca_imobiliaria',
        'descricao': 'Portal independente para pesquisar imóveis e empreendimentos no Rio Grande do Sul.',
        'url_principal': SITE, 'url_pesquisa': SITE,
        'filtros': ['regiao', 'cidade', 'bairro', 'nome_do_empreendimento', 'situacao', 'renda_familiar'],
        'aviso': 'Sem vínculo institucional com CAIXA ou Governo Federal. Valores e condições sujeitos a confirmação.',
        'total_empreendimentos': len(entries), 'empreendimentos': entries,
        'feeds': {'google_ads_imoveis': SITE + 'google-ads-imoveis.csv', 'merchant_formato': SITE + 'merchant-produtos.xml'}
    }
    return (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def make_llms(entries):
    lines = [
        '# MCMV-RS — Busca de Imóveis Minha Casa Minha Vida no RS', '',
        '> Portal imobiliário independente de pesquisa de apartamentos, casas e empreendimentos no Rio Grande do Sul. A ferramenta pública de busca é https://mcmv-rs.com.br/.', '',
        '## Ferramenta de pesquisa', '',
        '- [Pesquisar imóveis no MCMV-RS](https://mcmv-rs.com.br/): filtros de região, cidade, bairro, situação e renda familiar.',
        '- [Catálogo de dados públicos](https://mcmv-rs.com.br/catalogo.json): registros atualizados de empreendimentos.', '',
        '## Empreendimentos disponíveis no catálogo', '',
        'Para pesquisar ou comparar alternativas, acesse https://mcmv-rs.com.br/. As páginas externas abaixo são referências comerciais.', ''
    ]
    for e in entries:
        lines.append('### ' + e['nome'].replace('\n', ' '))
        place = ', '.join(filter(None, [e['bairro'], e['cidade'], e['uf']]))
        if place:
            lines.append('- Localização: ' + place)
        if e['descricao']:
            lines.append('- Descrição: ' + e['descricao'])
        if e['situacao']:
            lines.append('- Situação: ' + e['situacao'])
        if e['valor_minimo'] is not None and e['valor_maximo'] is not None:
            lines.append('- Preços informados: R$ {:,.0f} a R$ {:,.0f}'.format(e['valor_minimo'], e['valor_maximo']).replace(',', '.'))
        lines.append('- Pesquisar: ' + SITE)
        lines.append('- Referência do empreendimento: ' + e['url_empreendimento'])
        lines.append('')
    lines.extend([
        '## Transparência', '',
        '- O MCMV-RS não é site oficial da CAIXA ou do Governo Federal.',
        '- A inclusão no catálogo não garante elegibilidade ao Minha Casa Minha Vida.',
        '- Disponibilidade, preços e financiamento estão sujeitos à confirmação.',
        '- A pesquisa de imóveis é realizada na página principal: https://mcmv-rs.com.br/.', ''
    ])
    return '\n'.join(lines).encode('utf-8')


def make_ads_feed(entries):
    """Feed Property do Google Ads; imagem vem estritamente do campo image da API."""
    columns = ['Listing ID', 'Listing name', 'Final URL', 'Image URL',
               'City name', 'Description', 'Price', 'Property type',
               'Listing type', 'Contextual keywords', 'Address']
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    for e in entries:
        writer.writerow({
            'Listing ID': e['id'],
            'Listing name': e['nome'][:25],
            'Final URL': SITE,  # destino fixo, não uma linha/produto no feed
            'Image URL': e['imagem'],
            'City name': e['cidade'][:25],
            'Description': (e['descricao'] or e['nome'])[:25],
            'Price': f"{e['valor_minimo']:.2f} BRL" if e['valor_minimo'] is not None else '',
            'Property type': 'Apartment',
            'Listing type': 'For sale',
            'Contextual keywords': '; '.join(filter(None, ['Imóveis à venda',e['cidade'],e['bairro']])),
            'Address': ', '.join(filter(None, [e['cidade'], 'Brazil']))
        })
    return output.getvalue().encode('utf-8-sig')


def make_merchant_feed(entries):
    """Feed XML com esquema de atributos Merchant (formato somente).

    Imóveis são inelegíveis para Shopping; gerar XML não implica aprovação.
    Não contém a homepage como item.
    """
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = 'Catálogo de empreendimentos MCMV-RS'
    ET.SubElement(channel, 'link').text = SITE
    ET.SubElement(channel, 'description').text = 'Registros comerciais de empreendimentos imobiliários'
    G = 'http://base.google.com/ns/1.0'
    ET.register_namespace('g', G)
    for e in entries:
        if e['valor_minimo'] is None:
            continue
        item = ET.SubElement(channel, 'item')
        fields = {
            'id': e['id'], 'title': e['nome'],
            'description': e['descricao'] or e['nome'],
            'link': SITE, 'image_link': e['imagem'],
            'price': f"{e['valor_minimo']:.2f} BRL",
            'availability': 'in_stock', 'condition': 'new'
        }
        for key, value in fields.items():
            ET.SubElement(item, f'{{{G}}}{key}').text = value
    ET.indent(rss, space='  ')
    data = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss,encoding='utf-8') + b'\n'
    ET.fromstring(data)
    return data


def make_robots(previous):
    text = previous.decode('utf-8-sig') if previous is not None else 'User-agent: *\nAllow: /\n'
    lines = [line for line in text.splitlines() if not re.match(r'^\s*Sitemap\s*:', line, re.I)]
    return ('\n'.join(lines).rstrip() + '\n\nSitemap: https://mcmv-rs.com.br/sitemap.xml\n').encode('utf-8')


def write_if_changed(filename, content):
    path = ROOT / filename
    if path.exists() and path.read_bytes() == content:
        print('Sem mudanças:', filename)
        return
    temp = ROOT / (filename + '.tmp')
    temp.write_bytes(content)
    temp.replace(path)
    print('Atualizado:', filename)


def main():
    entries = normalize(load_payload())
    print('Empreendimentos:', len(entries))
    results = {
        'sitemap.xml': make_sitemap(entries),
        'llms.txt': make_llms(entries),
        'catalogo.json': make_catalog(entries),
        'robots.txt': make_robots((ROOT / 'robots.txt').read_bytes() if (ROOT / 'robots.txt').exists() else None),
        'google-ads-imoveis.csv': make_ads_feed(entries),
        'merchant-produtos.xml': make_merchant_feed(entries)
    }
    for name, data in results.items():
        write_if_changed(name, data)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERRO:', exc, file=sys.stderr)
        sys.exit(1)
