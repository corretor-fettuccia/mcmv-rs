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
    old_count = 0
    if old_file.exists():
        try:
            old = json.loads(old_file.read_text(encoding='utf-8'))
            old_count = len(old.get('items', old.get('empreendimentos', [])))
        except (ValueError, TypeError):
            raise RuntimeError('Catálogo existente inválido: corrija-o antes de sincronizar.')
    # Confirmação explícita e contagens coerentes permitem mudanças de status,
    # edição e inativação sem impedir a atualização de registros já publicados.
    catalog = catalog_json(items, payload, conf)
    contents = (json.dumps(catalog, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    changed = put(old_file, contents)
    print(f'[sinc-data] API: {total} registros, {published} publicados; '
          f'anterior: {old_count}; atual: {len(items)}; '
          f'com atributos: {sum(bool(x["attributes"]) for x in items)}; '
          f'arquivo: {"atualizado" if changed else "inalterado"}.', flush=True)

if __name__ == '__main__':
    try: run()
    except Exception as exc:
        print('[sinc-data] ERRO:', exc, file=sys.stderr)
        sys.exit(1)
