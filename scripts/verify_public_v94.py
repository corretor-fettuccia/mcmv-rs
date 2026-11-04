#!/usr/bin/env python3
"""Pos-deploy: busca os 3 XMLs nos enderecos publicos e aplica o contrato V9.4.

Tenta de novo porque o CDN do GitHub Pages pode demorar a refletir o deploy.
Uso: verify_public_v94.py [URL_BASE]
"""
import json
import sys
import time
from urllib.request import Request, urlopen
from core_lib import settings
from validate_xml_v94 import check_merchant, check_marketplace, check_sitemap

TRIES, WAIT = 8, 30  # shortcut: ~4 min de espera total; aumentar se o CDN demorar mais


def get(url):
    req = Request(f'{url}?v={int(time.time())}', headers={'User-Agent': 'MCMV-RS-Verify/9.4', 'Cache-Control': 'no-cache'})
    with urlopen(req, timeout=30) as response:
        if response.status != 200:
            raise ValueError(f'HTTP {response.status}')
        return response.read(60 * 1024 * 1024)


def verify(base):
    items = json.loads(get(base + 'catalogo.json').decode('utf-8-sig'))['items']
    merchant = check_merchant(get(base + 'merchant-produtos.xml'))
    meta = check_marketplace(get(base + 'marketplace-produtos.xml'), items)
    pages = check_sitemap(get(base + 'sitemap.xml'), base, items)
    return len(merchant), len(meta), len(pages)


if __name__ == '__main__':
    base = (sys.argv[1] if len(sys.argv) > 1 else settings()['site_url']).rstrip('/') + '/'
    for attempt in range(1, TRIES + 1):
        try:
            merchant, meta, pages = verify(base)
            print(f'[publico V9.4] OK {base}merchant-produtos.xml ({merchant} itens)')
            print(f'[publico V9.4] OK {base}marketplace-produtos.xml ({meta} anúncios)')
            print(f'[publico V9.4] OK {base}sitemap.xml ({pages} URLs)')
            sys.exit(0)
        except Exception as exc:  # rede, HTTP ou contrato: todos reprovam a tentativa
            print(f'[publico V9.4] tentativa {attempt}/{TRIES}: {exc}', flush=True)
            if attempt < TRIES:
                time.sleep(WAIT)
    print('::error::Arquivos públicos ausentes ou fora do contrato após o deploy', file=sys.stderr)
    sys.exit(1)
