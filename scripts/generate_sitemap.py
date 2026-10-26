#!/usr/bin/env python3
"""Atualiza sitemap.xml com as URLs devolvidas pela API PUBLICA da vitrine MCMV-RS.

A chamada reproduz app.js: GET {VITRINE_API_URL}?callback=__portalSitemap
Resposta esperada: __portalSitemap({"ok":true,"config":...,"items":[{"url":"https://..."}]});
"""
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / 'config.js'
OUTPUT = ROOT / 'sitemap.xml'
HOME = 'https://mcmv-rs.com.br/'
CALLBACK = '__portalSitemap'
NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
ET.register_namespace('', NS)


def endpoint():
    configured = os.environ.get('VITRINE_API_URL')
    if not configured:
        if not CONFIG.exists():
            raise RuntimeError('Nao encontrei config.js na raiz do repositorio.')
        match = re.search(r'window\s*\.\s*VITRINE_API_URL\s*=\s*[\'\"]([^\'\"]+)[\'\"]', CONFIG.read_text(encoding='utf-8'))
        if not match:
            raise RuntimeError('config.js nao contem window.VITRINE_API_URL.')
        configured = match.group(1)
    u = urlsplit(configured.strip())
    if u.scheme != 'https' or u.hostname != 'script.google.com' or not re.fullmatch(r'/macros/s/[^/]+/exec', u.path):
        raise RuntimeError('Endereco da API nao e um endpoint HTTPS do Apps Script /exec.')
    q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k.lower() != 'callback']
    q.append(('callback', CALLBACK))
    return urlunsplit((u.scheme, u.netloc, u.path, urlencode(q), ''))


def extract_payload(raw):
    text = raw.lstrip('\ufeff').strip()
    if text.startswith(")]}'"):
        text = text.split('\n', 1)[-1].strip()
    if text.lstrip().lower().startswith(('<!doctype html', '<html')):
        raise RuntimeError('API retornou HTML, nao JSONP. Verifique implantacao /exec, acesso publico (Qualquer pessoa) e login Google.')
    m = re.fullmatch(r'\s*' + re.escape(CALLBACK) + r'\s*\(\s*(.*?)\s*\)\s*;?\s*', text, flags=re.S)
    if m:
        text = m.group(1)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        print('Inicio da resposta recebida (diagnostico):', repr(text[:220]), file=sys.stderr)
        raise RuntimeError('Resposta da API nao e JSON/JSONP valido: ' + str(exc)) from exc
    if not isinstance(obj, dict):
        raise RuntimeError('Resposta deveria ser objeto JSON.')
    if obj.get('ok') is not True:
        raise RuntimeError('API retornou erro: ' + str(obj.get('error') or obj.get('message') or 'ok != true'))
    if not isinstance(obj.get('items'), list):
        raise RuntimeError('API nao retornou a lista items. Chaves: ' + ', '.join(obj.keys()))
    return obj['items']


def fetch_items():
    fixture = os.environ.get('SITEMAP_FIXTURE')
    if fixture:
        print('Modo teste: lendo SITEMAP_FIXTURE')
        return extract_payload(Path(fixture).read_text(encoding='utf-8'))
    url = endpoint()
    print('Consultando a API configurada no config.js via JSONP...')
    print('Endpoint:', urlsplit(url)._replace(query='').geturl())
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; MCMV-RS-Sitemap/1.0)', 'Accept': '*/*'})
    try:
        with urlopen(req, timeout=40) as response:
            body = response.read(5_000_001)
            print('HTTP:', response.status, '| Content-Type:', response.headers.get('Content-Type', '?'))
            print('Destino do redirecionamento:', urlsplit(response.url).hostname)
    except HTTPError as exc:
        raise RuntimeError(f'API HTTP {exc.code}. Confira implantacao e permissoes de acesso do Apps Script.') from exc
    except URLError as exc:
        raise RuntimeError(f'Falha de conexao com a API: {exc.reason}') from exc
    if len(body) > 5_000_000:
        raise RuntimeError('Resposta da API ultrapassou 5 MB.')
    return extract_payload(body.decode('utf-8-sig', errors='replace'))


def clean_url(url):
    if not isinstance(url, str):
        return None
    url = url.strip()
    if any(ch.isspace() for ch in url):
        return None
    try:
        u = urlsplit(url)
        if u.scheme != 'https' or not u.hostname or u.username or u.password or u.port not in (None, 443):
            return None
        params = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('gclid', 'fbclid')]
        return urlunsplit(('https', u.netloc.lower(), u.path or '/', urlencode(params), ''))
    except ValueError:
        return None


def main():
    items = fetch_items()
    print('Empreendimentos recebidos da API:', len(items))
    if not items:
        raise RuntimeError('Lista items vazia. Sitemap anterior preservado.')
    urls = {HOME}
    skipped = 0
    for entry in items:
        if not isinstance(entry, dict) or entry.get('indexar') is False or entry.get('index') is False or entry.get('noindex') is True:
            skipped += 1
            continue
        url = clean_url(entry.get('canonicalUrl') or entry.get('url'))
        if url:
            urls.add(url)
        else:
            skipped += 1
    if len(urls) == 1:
        raise RuntimeError(f'Nenhuma URL externa valida encontrada nos {len(items)} registros; ignorados {skipped}. Sitemap preservado. Verifique campo url da API.')
    root = ET.Element(f'{{{NS}}}urlset')
    for url in [HOME] + sorted(urls - {HOME}):
        row = ET.SubElement(root, f'{{{NS}}}url')
        ET.SubElement(row, f'{{{NS}}}loc').text = url
    ET.indent(root, space='  ')
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode') + '\n'
    if OUTPUT.exists() and OUTPUT.read_text(encoding='utf-8') == xml:
        print('Sem alteracoes no sitemap:', len(urls), 'URLs.')
        return
    OUTPUT.write_text(xml, encoding='utf-8')
    print('sitemap.xml atualizado:', len(urls), 'URLs. Registros ignorados:', skipped)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERRO:', exc, file=sys.stderr)
        sys.exit(1)
