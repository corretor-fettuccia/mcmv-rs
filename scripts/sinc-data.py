#!/usr/bin/env python3
"""Motor 1: API pública V4 -> catalogo.json. Nenhuma outra saída é gravada."""
import json
import os
import sys
from pathlib import Path
from core_lib import ROOT, settings, get_payload, normalize, catalog_json, put


def run():
    conf = settings()
    payload = get_payload()
    rows = payload['items']
    total, published = payload.get('totalRows'), payload.get('publishedRows')
    if (payload.get('snapshotComplete') is not True or type(total) is not int or
        type(published) is not int or total < 0 or published < 0 or
        published > total or published != len(rows)):
        raise RuntimeError('Snapshot incompleto/inconsistente. Catálogo anterior preservado.')
    items = normalize(payload, conf['site_url'])
    if len(items) != published:
        raise RuntimeError('A normalização perdeu imóveis: publicação interrompida.')
    old_file = ROOT / 'catalogo.json'
    old_count = None
    if old_file.is_file():
        try:
            previous = json.loads(old_file.read_text(encoding='utf-8-sig'))
            if isinstance(previous, dict):
                old_items = previous.get('items', previous.get('empreendimentos', []))
                if isinstance(old_items, list):
                    old_count = len(old_items)
        except (ValueError, UnicodeError, TypeError):
            pass
    if old_count is None:
        print('[sinc-data] Catálogo anterior ausente, vazio ou inválido: '
              'reconstruindo exclusivamente com o snapshot confirmado da API V4.', flush=True)
    # A API já foi validada como snapshot completo. O arquivo antigo não define
    # quais imóveis publicar, nem impede a reconstrução quando estiver vazio.
    catalog = catalog_json(items, payload, conf)
    contents = (json.dumps(catalog, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    changed = put(old_file, contents, force=True)
    print(f'[sinc-data] API: {total} registros, {published} publicados; '
          f'anterior: {old_count if old_count is not None else "indisponível"}; atual: {len(items)}; '
          f'com atributos: {sum(bool(x["attributes"]) for x in items)}; '
          f'arquivo: reconstruído pela API (escrita atômica).', flush=True)

if __name__ == '__main__':
    try: run()
    except Exception as exc:
        print('[sinc-data] ERRO:', exc, file=sys.stderr)
        sys.exit(1)
