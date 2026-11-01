#!/usr/bin/env python3
"""Compatibilidade: redireciona rotinas antigas para o motor ÚNICO V4.

Nunca gerar catalogo.json, sitemap.xml ou feeds com o contrato V3.
A API pública deve fornecer schemaVersion=4 e items[].attributes.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_portal_v4 import main

if __name__ == '__main__':
    try:
        print('LEGADO REDIRECIONADO: executando Motor V4 completo (atributos, HTML, sitemap e feeds).', flush=True)
        main()
    except Exception as e:
        print('ERRO V4: ' + str(e), file=sys.stderr)
        sys.exit(1)
