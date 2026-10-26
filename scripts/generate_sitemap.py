#!/usr/bin/env python3
"""Gera sitemap da vitrine a partir do JSONP publico do Google Apps Script.
Execute na raiz do repositorio: python scripts/generate_sitemap.py
"""
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
HOME = 'https://mcmv-rs.com.br/'
OUTPUT = ROOT / 'sitemap.xml'
CONFIG = ROOT / 'config.js'
NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
ET.register_namespace('', NS)
CALLBACK = '__portalVitrine_' + str(int(time.time() * 1000)) + '_' + str(secrets.randbelow(100000))


def get_api_url():
    configured = os.getenv('VITRINE_API_URL', '').strip()
    if not configured:
        if not CONFIG.is_file():
            raise RuntimeError('config.js nao encontrado na raiz.')
        config = CONFIG.read_text(encoding='utf-8')
        match = re.search(r'window\s*\.\s*VITRINE_API_URL\s*=\s*[\'\"]([^\'\"]+)', config)
        if not match:
            raise RuntimeError('Nao encontrei window.VITRINE_API_URL em config.js')
        configured = match.group(1)
    uri = urlsplit(configured)
    if uri.scheme != 'https' or uri.hostname != 'script.google.com' or not re.fullmatch(r'/macros/s/[^/]+/exec', uri.path):
        raise RuntimeError('URL da API nao e endpoint Apps Script HTTPS /exec')
    query = [(k, v) for k, v in parse_qsl(uri.query) if k.lower() != 'callback']
    query.append(('callback', CALLBACK))
    return urlunsplit((uri.scheme, uri.netloc, uri.path, urlencode(query), ''))


def unpack(body):
    text = body.strip().lstrip('\ufeff').strip()
    if text.startswith(")]}'"):
        text = text.partition('\n')[2].strip()
    if text.lower().startswith(('<html', '<!doctype html')):
        raise RuntimeError('Apps Script retornou HTML/login, em vez do catalogo')
    matcher = re.fullmatch(r'\s*' + re.escape(CALLBACK) + r'\s*\(\s*(.*?)\s*\)\s*;?\s*', text, re.S)
    if matcher:
        text = matcher.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError('Resposta inesperada da API. Inicio: ' + repr(text[:160])) from exc
    if not isinstance(data, dict):
        raise RuntimeError('API retornou JSON que nao e objeto')
    if data.get('ok') is not True:
        raise RuntimeError('API retornou erro: ' + str(data.get('error') or data.get('message') or 'ok != true'))
    items = data.get('items')
    if not isinstance(items, list):
        raise RuntimeError('API nao entregou items como lista. Campos: ' + ', '.join(data))
    return items


def fetch():
    fixture = os.getenv('SITEMAP_FIXTURE')
    if fixture:
        print('TESTE: usando arquivo local', flush=True)
        return unpack(Path(fixture).read_text(encoding='utf-8'))
    url = get_api_url()
    print('Consultando Apps Script:', urlsplit(url).netloc + urlsplit(url).path, flush=True)
    print('Callback:', CALLBACK, flush=True)
    req = Request(url, headers={'Accept': '*/*', 'User-Agent': 'Mozilla/5.0 (compatible; MCMV-RS-Sitemap/2.0)'})
    try:
        with urlopen(req, timeout=45) as response:
            body = response.read(5_000_001)
            print('HTTP:', response.status, '| tipo:', response.headers.get('Content-Type', '?'), flush=True)
    except HTTPError as exc:
        raise RuntimeError('API HTTP ' + str(exc.code)) from exc
    except URLError as exc:
        raise RuntimeError('Falha de conexao com API: ' + str(exc.reason)) from exc
    if len(body) > 5_000_000:
        raise RuntimeError('API devolveu mais de 5 MB')
    return unpack(body.decode('utf-8-sig', errors='replace'))


def normalize_url(value):
    if not isinstance(value, str) or not value.strip() or any(c.isspace() for c in value):
        return None
    try:
        u = urlsplit(value.strip())
        if u.scheme not in ('https', 'http') or not u.hostname or u.username or u.password:
            return None
        if u.port not in (None, 80, 443):
            return None
        pairs = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('gclid', 'fbclid')]
        return urlunsplit((u.scheme, u.netloc.lower(), u.path or '/', urlencode(pairs), ''))
    except ValueError:
        return None


def make_xml(items):
    print('Itens recebidos da API:', len(items), flush=True)
    if not items:
        raise RuntimeError('items vazio; sitemap preservado')
    urls = {HOME}
    invalid = []
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            invalid.append(f'#{i} objeto invalido')
            continue
        if item.get('indexar') is False or item.get('index') is False or item.get('noindex') is True:
            continue
        url = normalize_url(item.get('url') or item.get('canonicalUrl') or item.get('landingPageUrl'))
        if url:
            urls.add(url)
            print(f'  [{i}] {item.get("name", "Empreendimento")} -> {url}', flush=True)
        else:
            invalid.append(f'#{i} {item.get("name", "sem nome")}: URL ausente/invalida; campos={list(item.keys())[:14]}')
    for message in invalid[:15]:
        print('IGNORADO:', message, flush=True)
    if len(urls) <= 1:
        raise RuntimeError('Nenhuma landing page valida na resposta; sitemap anterior preservado')
    root = ET.Element(f'{{{NS}}}urlset')
    for url in [HOME] + sorted(urls - {HOME}):
        ET.SubElement(ET.SubElement(root, f'{{{NS}}}url'), f'{{{NS}}}loc').text = url
    ET.indent(root, space='  ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode') + '\n', len(urls)


def main():
    xml, count = make_xml(fetch())
    if OUTPUT.exists() and OUTPUT.read_text(encoding='utf-8') == xml:
        print('Sem alteracoes:', count, 'URLs', flush=True)
        return
    OUTPUT.write_text(xml, encoding='utf-8')
    print('SUCESSO: sitemap.xml atualizado com', count, 'URLs', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERRO:', exc, file=sys.stderr, flush=True)
        sys.exit(1)
