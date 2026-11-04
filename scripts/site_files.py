#!/usr/bin/env python3
"""Arquivos do site: imagens baixadas para imoveis/{id}/ e leitura das páginas já construídas.

- O tipo da imagem vem da assinatura binária (não do cabeçalho HTTP): página de erro em HTML nunca vira "imagem".
- IMAGENS_FIXTURE=<pasta> troca a rede por arquivos locais (teste), como PORTAL_FIXTURE faz com a API.
"""
import hashlib
import ipaddress
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from core_lib import valid_url

MAX_BYTES = 10 * 1024 * 1024
LOCAL_NAME = re.compile(r'\d{2}-[0-9a-f]{8}\.(?:webp|jpg|png|gif|avif)')


def kind(data):
    """Extensão pela assinatura binária, ou None se não for uma imagem aceita (jpg, png, gif, webp, avif)."""
    if data[:3] == b'\xff\xd8\xff':
        return 'jpg'
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'webp'
    if data[4:8] == b'ftyp' and data[8:12] in (b'avif', b'avis'):
        return 'avif'
    return None


def safe_url(url):
    """https público: sem credenciais e sem endereço IP privado/local (a rede do runner não é alvo)."""
    if not valid_url(url):
        return False
    host = urlsplit(url).hostname
    # shortcut: DNS que aponte para IP interno não é checado; as URLs vêm da planilha do próprio dono.
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return host.lower() != 'localhost' and '.' in host


def local_name(index, url, ext):
    return f'{index:02d}-{hashlib.sha1(url.encode()).hexdigest()[:8]}.{ext}'


class NotFound(OSError):
    code = 404  # erro 4xx não se repete


def _download(url):
    fixture = os.environ.get('IMAGENS_FIXTURE')
    if fixture:
        path = Path(fixture) / hashlib.sha1(url.encode()).hexdigest()
        if not path.is_file():
            raise NotFound('HTTP 404 (fixture)')
        return path.read_bytes()
    req = Request(url, headers={'User-Agent': 'MCMV-RS-Core/10', 'Accept': 'image/*'})
    with urlopen(req, timeout=30) as response:
        data = response.read(MAX_BYTES + 1)
    return data


def fetch_image(url):
    """(bytes, extensão) ou levanta ValueError/OSError com o motivo. Duas tentativas."""
    if not safe_url(url):
        raise ValueError('endereço não permitido')
    for attempt in (1, 2):
        try:
            data = _download(url)
            break
        except OSError as exc:
            if attempt == 2 or 400 <= getattr(exc, 'code', 0) < 500:
                raise
            time.sleep(2)
    if len(data) > MAX_BYTES:
        raise ValueError(f'maior que {MAX_BYTES // 1024 // 1024} MB')
    ext = kind(data)
    if not ext:
        raise ValueError('o conteúdo não é uma imagem (jpg, png, gif, webp ou avif)')
    return data, ext


def fetch_all(urls, workers=8):
    """Resultados na mesma ordem das URLs: (bytes, ext) ou o texto do erro."""
    def one(url):
        try:
            return fetch_image(url)
        except (OSError, ValueError) as exc:
            return str(exc)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, urls))


class _Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical = None
        self.images = []
        self._figure = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'link' and a.get('rel') == 'canonical':
            self.canonical = a.get('href')
        elif tag == 'figure':
            self._figure += 1
        elif tag == 'img' and self._figure and a.get('src'):
            self.images.append(a['src'])

    def handle_endtag(self, tag):
        if tag == 'figure':
            self._figure -= 1


def read_page(path):
    """(URL canônica, [src das imagens da galeria, na ordem]) de uma página gerada por build_pages.py."""
    parser = _Page()
    parser.feed(Path(path).read_text(encoding='utf-8'))
    return parser.canonical, parser.images


def absolute(page_url, src):
    return urljoin(page_url, src)
