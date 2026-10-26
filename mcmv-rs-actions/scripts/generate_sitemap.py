#!/usr/bin/env python3
"""Gera sitemap.xml a partir da API publica JSONP da vitrine MCMV-RS."""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config.js'
OUTPUT = ROOT / 'sitemap.xml'
HOME = 'https://mcmv-rs.com.br/'
NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
ET.register_namespace('', NS)


def api_url():
    if os.environ.get('VITRINE_API_URL'):
        url = os.environ['VITRINE_API_URL']
    else:
        match = re.search(r'window\.VITRINE_API_URL\s*=\s*[\'\"](https://[^\'\"]+)[\'\"]', CONFIG.read_text(encoding='utf-8'))
        if not match:
            raise ValueError('API nao encontrada em config.js')
        url = match.group(1)
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or parts.hostname != 'script.google.com' or not re.fullmatch(r'/macros/s/[^/]+/exec', parts.path):
        raise ValueError('URL da API invalida')
    return url


def load_items():
    if os.environ.get('SITEMAP_FIXTURE'):
        raw = Path(os.environ['SITEMAP_FIXTURE']).read_text(encoding='utf-8')
    else:
        url = api_url()
        query = urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query, keep_blank_values=True)
        query = [(k, v) for k, v in query if k.lower() != 'callback']
        query.append(('callback', '__sitemapGithubActions'))
        parts = urllib.parse.urlsplit(url)
        url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), ''))
        req = urllib.request.Request(url, headers={'User-Agent':'MCMV-RS-Sitemap/1.0', 'Accept':'application/javascript, application/json'})
        with urllib.request.urlopen(req, timeout=35) as response:
            raw = response.read(5_000_001).decode('utf-8-sig')
        if len(raw) > 5_000_000:
            raise ValueError('Resposta maior do que 5 MB')
    raw = raw.strip().rstrip(';').strip()
    if raw.startswith('__sitemapGithubActions(') and raw.endswith(')'):
        raw = raw[len('__sitemapGithubActions('):-1]
    # Se houver login do Google ou callback de outro nome, falhar sem sobrescrever o sitemap.
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get('ok') is not True or not isinstance(payload.get('items'), list):
        raise ValueError('API nao retornou {ok:true, items:[...]}')
    return payload['items']


def canonical_url(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    try:
        parts = urllib.parse.urlsplit(value)
        if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
                or parts.port not in (None, 443) or any(ch.isspace() for ch in value)):
            return None
        # Retira fragmentos e parametros de rastreamento; mantem caminhos e querys nao promocionais.
        qs = [(key, val) for key, val in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
              if not key.lower().startswith('utm_') and key.lower() not in ('gclid','fbclid')]
        return urllib.parse.urlunsplit(('https', parts.netloc.lower(), parts.path or '/', urllib.parse.urlencode(qs), ''))
    except ValueError:
        return None


def main():
    items = load_items()
    if not items:
        raise ValueError('Catalogo vazio; sitemap existente preservado')
    urls = {HOME}
    skipped = 0
    for item in items:
        if not isinstance(item, dict):
            skipped += 1
            continue
        # Campo opcional: se admin incluir indexar:false ou noindex:true, respeitar.
        if item.get('indexar') is False or item.get('index') is False or item.get('noindex') is True:
            skipped += 1
            continue
        url = canonical_url(item.get('canonicalUrl') or item.get('url'))
        if url:
            urls.add(url)
        else:
            skipped += 1
    if len(urls) == 1:
        raise ValueError('Nenhuma landing page valida; sitemap existente preservado')
    if len(urls) > 50000:
        raise ValueError('Mais de 50 mil URLs: dividir em sitemaps')
    root = ET.Element(f'{{{NS}}}urlset')
    for url in [HOME] + sorted(urls - {HOME}):
        row = ET.SubElement(root, f'{{{NS}}}url')
        ET.SubElement(row, f'{{{NS}}}loc').text = url
    ET.indent(root, space='  ')
    result = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode') + '\n'
    if len(result.encode('utf-8')) > 50_000_000:
        raise ValueError('Sitemap maior que 50MB')
    if OUTPUT.exists() and OUTPUT.read_text(encoding='utf-8') == result:
        print(f'Sitemap sem alteracoes: {len(urls)} URLs, {skipped} ignoradas')
        return
    OUTPUT.write_text(result, encoding='utf-8')
    print(f'Sitemap atualizado: {len(urls)} URLs, {skipped} ignoradas')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERRO: {exc}', file=sys.stderr)
        sys.exit(1)
