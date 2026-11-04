#!/usr/bin/env python3
"""Roda a mesma sequência do GitHub Actions no seu computador (precisa de VITRINE_API_URL ou PORTAL_FIXTURE)."""
import subprocess
import sys
from pathlib import Path

STEPS = [('sync_catalog.py', []), ('build_feeds.py', []), ('build_pages.py', []), ('build_sitemap.py', []),
         ('build_llms.py', []), ('validate.py', ['--check', 'all']), ('stage_site.py', []),
         ('validate.py', ['--root', '_site', '--check', 'site'])]

if __name__ == '__main__':
    here = Path(__file__).resolve().parent
    for n, (script, args) in enumerate(STEPS, 1):
        print(f'\n=== V10 [{n}/{len(STEPS)}] {script} {" ".join(args)} ===', flush=True)
        if subprocess.run([sys.executable, str(here / script), *args], cwd=here.parent).returncode:
            sys.exit(f'Etapa {script} falhou: nada deve ser publicado.')
    print('\nV10: todas as etapas concluídas. O site está em _site/.')
