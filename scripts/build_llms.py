#!/usr/bin/env python3
"""Etapa 5: catalogo.json -> llms.txt (descoberta para agentes de IA), sempre igual ao catálogo público."""
import sys
from pathlib import Path
from core_lib import ROOT, settings, put, load_catalog


def run(root=ROOT):
    root = Path(root)
    conf = settings()
    site = conf['site_url']
    catalog = load_catalog(root)
    lines = [f'# {conf.get("name", "Portal Imobiliário")} — imóveis', '', f'Portal: {site}', f'Catálogo: {site}catalogo.json',
             f'Sitemap: {site}sitemap.xml', '', '## Imóveis publicados', '']
    for e in catalog['items']:
        lines += [f'### {e["name"]}', f'- Detalhes: {e["pageUrl"]}', f'- Landing page: {e["url"]}', f'- Cidade: {e.get("city", "")}',
                  f'- Atributos: {", ".join(e.get("attributes", []))}', f'- Resumo: {(e.get("description") or "")[:500]}', '']
    lines += ['## Aviso', '', 'Condições sujeitas a confirmação com o anunciante.', '']
    put(root / 'llms.txt', '\n'.join(lines) + '\n')
    print(f'[llms] GERADO llms.txt: {len(catalog["items"])} imóveis.', flush=True)


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        print('::error::build_llms:', exc, file=sys.stderr)
        sys.exit(1)
