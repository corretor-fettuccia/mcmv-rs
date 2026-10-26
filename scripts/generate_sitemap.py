#!/usr/bin/env python3
"""Gera sitemap.xml usando diretamente a API JSON pública da vitrine MCMV-RS.

Contrato esperado: {"ok": true, "items": [{"name": "...", "url": "https://..."}, ...]}
Não altera o arquivo se ocorrer erro de API ou nenhuma URL for encontrada.
"""
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
SITE = 'https://mcmv-rs.com.br/'
API_FALLBACK = 'https://script.google.com/macros/s/AKfycbxYTaWNG6o_5NqPq3D16_isTpmTPWgYa3NureFuHz21fG-x-rDfqM1RMXxWog_5sHxxSQ/exec'
NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
ET.register_namespace('', NS)


def api_url():
    override = os.getenv('VITRINE_API_URL', '').strip()
    if override:
        return override
    path = ROOT / 'config.js'
    if path.exists():
        match = re.search(r'window\s*\.\s*VITRINE_API_URL\s*=\s*[\'\"]([^\'\"]+)', path.read_text(encoding='utf-8'))
        if match:
            return match.group(1)
    return API_FALLBACK


def load_items():
    fixture = os.getenv('SITEMAP_FIXTURE', '').strip()  # para teste local sem rede
    if fixture:
        payload = json.loads(Path(fixture).read_text(encoding='utf-8'))
    else:
        url = api_url()
        print('Consultando API JSON:', url, flush=True)
        req = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'MCMV-RS-Sitemap/1.0'})
        try:
            with urlopen(req, timeout=40) as response:
                raw = response.read(5_000_001)
                print('HTTP:', response.status, '| Content-Type:', response.headers.get('Content-Type'), flush=True)
        except (HTTPError, URLError) as exc:
            raise RuntimeError(f'Falha ao consultar API: {exc}') from exc
        if len(raw) > 5_000_000:
            raise RuntimeError('Resposta excede 5 MB')
        try:
            payload = json.loads(raw.decode('utf-8-sig'))
        except (ValueError, UnicodeDecodeError) as exc:
            raise RuntimeError('A resposta da API não é JSON válido') from exc
    if not isinstance(payload, dict) or payload.get('ok') is not True:
        raise RuntimeError(f'API não retornou ok:true. Resposta: {str(payload)[:250]}')
    items = payload.get('items')
    if not isinstance(items, list) or not items:
        raise RuntimeError('items[] não existe ou veio vazio; sitemap antigo preservado')
    print('Imóveis recebidos:', len(items), flush=True)
    return items


def valid_url(value):
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if any(char.isspace() for char in value):
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
            return None
    except ValueError:
        return None
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or '/', parts.query, ''))


def main():
    items = load_items()
    urls = {SITE}
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get('indexar') is False or item.get('noindex') is True:
            continue
        url = valid_url(item.get('url'))
        if url:
            urls.add(url)
            print(' +', item.get('name', '(sem nome)'), '=>', url, flush=True)
        else:
            print(' ! URL inválida:', item.get('name', '(sem nome)'), flush=True)
    if len(urls) == 1:
        raise RuntimeError('Nenhuma landing page válida recebida; sitemap antigo preservado')
    root = ET.Element(f'{{{NS}}}urlset')
    for url in [SITE] + sorted(urls - {SITE}):
        ET.SubElement(ET.SubElement(root, f'{{{NS}}}url'), f'{{{NS}}}loc').text = url
    ET.indent(root, space='  ')
    content = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='utf-8') + b'\n'
    ET.fromstring(content)
    target = ROOT / 'sitemap.xml'
    if target.exists() and target.read_bytes() == content:
        print('Sem mudanças:', len(urls), 'URLs', flush=True)
    else:
        temp = ROOT / 'sitemap.xml.tmp'
        temp.write_bytes(content)
        temp.replace(target)
        print('SUCESSO:', len(urls), 'URLs escritas em sitemap.xml', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERRO:', exc, file=sys.stderr, flush=True)
        sys.exit(1)
