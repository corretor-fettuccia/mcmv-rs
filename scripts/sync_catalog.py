#!/usr/bin/env python3
"""Etapa 1: API pública do Apps Script (VITRINE_API_URL) -> catalogo.json.

Lê o estado atual da planilha a cada execução, valida o snapshot e grava o catálogo local.
Compara com o catálogo já publicado só para registrar no log o que é novo, alterado ou removido.
"""
import json
import os
import sys
from urllib.request import Request, urlopen
from core_lib import ROOT, settings, get_payload, normalize, catalog_json, put, diff_catalogs


def previous_items(conf):
    """Itens do catálogo anterior (arquivo CATALOGO_ANTERIOR ou o publicado no site). Só informativo."""
    source = os.environ.get('CATALOGO_ANTERIOR') or ('' if os.environ.get('PORTAL_FIXTURE') else conf['site_url'] + 'catalogo.json')
    if not source:
        return None
    try:
        if source.startswith('https://'):
            with urlopen(Request(source, headers={'User-Agent': 'MCMV-RS-Core/10', 'Cache-Control': 'no-cache'}), timeout=20) as r:
                data = json.loads(r.read(8_000_001).decode('utf-8-sig'))
        else:
            data = json.loads(open(source, encoding='utf-8-sig').read())
        items = data.get('items')
        return items if isinstance(items, list) else None
    except (OSError, ValueError):  # primeira publicação, domínio fora do ar ou JSON antigo: não impede a sincronização
        return None


def run():
    conf = settings()
    payload = get_payload()
    items = normalize(payload, conf['site_url'])
    catalog = catalog_json(items, payload, conf)
    changed = put(ROOT / 'catalogo.json', json.dumps(catalog, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(f'[sync] API lida: {payload["totalRows"]} linhas, {len(items)} imóveis ativos; '
          f'{sum(bool(i["attributes"]) for i in items)} com atributos; catalogo.json '
          f'{"gravado" if changed else "idêntico ao arquivo local"}.', flush=True)
    old = previous_items(conf)
    if old is None:
        print('[sync] Catálogo publicado indisponível: todos os imóveis tratados como novos.', flush=True)
        added, edited, removed = [i['id'] for i in items], [], []
    else:
        added, edited, removed = diff_catalogs(old, items)
    print(f'[sync] Novos: {len(added)} {added} | Atualizados: {len(edited)} {edited} | Removidos: {len(removed)} {removed}', flush=True)


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        print('::error::sync_catalog:', exc, file=sys.stderr)
        sys.exit(1)
