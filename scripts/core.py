#!/usr/bin/env python3
"""Core V8 local: sequencia dos cinco motores. Falha => sem publicação."""
import argparse
import subprocess
import sys

STEPS = [
    ('sinc-data', 'sinc-data.py'),
    ('make-feed-merchantcenter', 'make-feed-merchantcenter.py'),
    ('gerar-marketplace', 'gerar_marketplace.py'),
    ('make-sitemap', 'make-sitemap.py'),
    ('make-subpage', 'make-subpage.py'),
]

def run():
    parser = argparse.ArgumentParser(description='Sincronizador Core Imobiliário V8')
    parser.add_argument('--step', choices=[s[0] for s in STEPS], help='Executar somente um motor')
    args = parser.parse_args()
    from pathlib import Path
    directory = Path(__file__).resolve().parent
    jobs = [s for s in STEPS if not args.step or s[0] == args.step]
    for i, (label, filename) in enumerate(jobs, 1):
        print(f'\n=== CORE V8 [{i}/{len(jobs)}] {label} ===', flush=True)
        command = [sys.executable, str(directory / filename)]
        if label == 'gerar-marketplace':
            command += ['--source', str(directory.parent / 'catalogo.json')]
        result = subprocess.run(command, check=False)
        if result.returncode:
            raise RuntimeError(f'Etapa {label} falhou (exit {result.returncode}); publicação interrompida.')
    print('\nCORE V8: todas as etapas concluídas com sucesso.', flush=True)

if __name__ == '__main__':
    try: run()
    except Exception as exc:
        print('ERRO CORE V8:', exc, file=sys.stderr)
        sys.exit(1)
