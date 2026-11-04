#!/usr/bin/env python3
"""Motor 2 (V9.4, unificado): catalogo.json -> merchant-produtos.xml + marketplace-produtos.xml.

Uma unica rotina (feeds_v94.run), um unico catalogo, sem chamada a API.
"""
import sys
from feeds_v94 import run

if __name__ == '__main__':
    try: run()
    except Exception as exc:
        print('[make-feed-merchantcenter] ERRO:', exc, file=sys.stderr)
        sys.exit(1)
