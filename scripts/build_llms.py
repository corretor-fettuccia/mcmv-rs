#!/usr/bin/env python3
"""Etapa 5: sitemap.xml + catalogo.json -> llms.txt (descoberta para agentes de IA, formato llmstxt.org).

Estrutura: H1 com o nome, resumo em citação, depois seções de links. Cada imóvel é um link para a sua página
(a URL vem do sitemap, os dados do catálogo). Sitemap e catálogo divergentes interrompem a publicação.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from core_lib import ROOT, settings, put, load_catalog

SM = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
IMG = '{http://www.google.com/schemas/sitemap-image/1.1}'


def real(value):
    return 'R$ ' + f'{value:,.0f}'.replace(',', '.')


def sitemap_pages(root):
    """{URL da página: [URLs das imagens]} lido do sitemap.xml já gerado."""
    path = Path(root) / 'sitemap.xml'
    if not path.is_file():
        raise RuntimeError('sitemap.xml ausente: execute build_sitemap.py antes')
    return {(u.findtext(SM + 'loc') or '').strip(): [(i.findtext(IMG + 'loc') or '').strip() for i in u.findall(IMG + 'image')]
            for u in ET.parse(path).getroot().findall(SM + 'url')}


def run(root=ROOT):
    root = Path(root)
    conf = settings()
    site = conf['site_url']
    catalog = load_catalog(root)
    pages = sitemap_pages(root)
    items = catalog['items']
    wanted = {i['pageUrl'] for i in items}
    if set(pages) - {site} != wanted:
        raise RuntimeError(f'sitemap e catálogo divergem: só no sitemap {sorted(set(pages) - {site} - wanted)}, '
                           f'só no catálogo {sorted(wanted - set(pages))}')
    title = (catalog.get('config') or {}).get('titulo') or conf.get('name', 'Portal Imobiliário')
    cities = sorted({i['city'] for i in items if i.get('city')})
    lines = [f'# {conf.get("name", "Portal Imobiliário")} — {title}', '',
             f'> Catálogo de {len(items)} empreendimento(s) imobiliário(s) publicado(s) em {site}'
             + (f', em {", ".join(cities)}' if cities else '') + '. Preços e condições sujeitos a confirmação com o anunciante.', '',
             '## Empreendimentos', '']
    for i in items:
        images = pages[i['pageUrl']]
        place = ', '.join(v for v in (i.get('neighborhood'), i.get('city'), i.get('uf')) if v)
        facts = [f'Local: {place}'] if place else []
        if i.get('minimum'):
            facts.append('A partir de ' + real(i['minimum']) + (f' até {real(i["maximum"])}' if i.get('maximum') and i['maximum'] != i['minimum'] else ''))
        if i.get('bedrooms') is not None:
            facts.append(f'Dormitórios: {i["bedrooms"]}')
        if i.get('state'):
            facts.append(f'Situação: {i["state"]}')
        summary = (i.get('highlight') or i.get('description') or '')[:240]
        lines.append(f'- [{i["name"]}]({i["pageUrl"]})' + (f': {summary}' if summary else ''))
        if facts:
            lines.append('  - ' + '. '.join(facts))
        if i.get('attributes'):
            lines.append('  - Atributos: ' + ', '.join(i['attributes'][:12]))
        lines.append(f'  - Imagens: {len(images)} (principal: {images[0]})')
    lines += ['', '## Dados e feeds', '',
              f'- [Catálogo completo (JSON)]({site}catalogo.json): todos os campos de cada empreendimento',
              f'- [Sitemap]({site}sitemap.xml): páginas e imagens',
              f'- [Feed Google Merchant]({site}merchant-produtos.xml)',
              f'- [Feed Meta Marketplace]({site}marketplace-produtos.xml)', '',
              '## Optional', '']
    lines += [f'- [{i["name"]} — site do empreendimento]({i["url"]})' for i in items]
    put(root / 'llms.txt', '\n'.join(lines) + '\n')
    print(f'[llms] GERADO llms.txt: {len(items)} imóveis (sitemap e catálogo conferem), {sum(len(v) for v in pages.values())} imagens no sitemap.', flush=True)


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        print('::error::build_llms:', exc, file=sys.stderr)
        sys.exit(1)
