#!/usr/bin/env python3
"""V9.4.2: avisa (sem falhar) sobre arquivos de pacotes anteriores que o upload por cima nao apaga."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
OBSOLETE = ('scripts/test_marketplace_core_v92.py', 'scripts/test_marketplace_fallback_v93.py',
            'scripts/test_motores_v94.py', '.github/workflows/gerar-marketplace.yml')
found = [name for name in OBSOLETE if (root / name).exists()]
for name in found:
    print(f'::warning::Arquivo obsoleto no repositorio (pode apagar): {name}')
print(f'[obsoletos V9.4.2] {len(found)} arquivo(s) obsoleto(s); ignorados pelo Core, que roda so os testes V9.4 por nome.')
