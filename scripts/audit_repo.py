#!/usr/bin/env python3
"""Avisa (nunca falha) sobre arquivos de versões anteriores que o upload por ZIP não apaga.

Um upload não remove nada do repositório: scripts, testes e workflows antigos continuam lá e podem
confundir. Este aviso lista o que pode ser apagado. Nada disso entra no site (stage_site.py usa lista de permissão).
"""
from pathlib import Path
from core_lib import ROOT

SCRIPTS = {'core_lib.py', 'sync_catalog.py', 'merchant.py', 'marketplace.py', 'build_feeds.py', 'build_pages.py',
           'build_sitemap.py', 'build_llms.py', 'validate.py', 'stage_site.py', 'verify_public.py', 'audit_repo.py',
           'run_local.py', 'test_core.py', 'test_vitrine_hover.js', 'test_vitrine_catalogo.js'}
WORKFLOWS = {'core-imobiliario.yml'}


def obsolete(root=ROOT):
    root = Path(root)
    found = [f'scripts/{p.name}' for p in sorted((root / 'scripts').glob('*')) if p.is_file() and p.name not in SCRIPTS]
    found += [f'.github/workflows/{p.name}' for p in sorted((root / '.github' / 'workflows').glob('*')) if p.is_file() and p.name not in WORKFLOWS]
    return found


if __name__ == '__main__':
    old = obsolete()
    for name in old:
        print(f'::warning::Arquivo de versão anterior no repositório (pode apagar): {name}')
    print(f'[audit] {len(old)} arquivo(s) antigo(s) fora da V10; nenhum afeta o site publicado.')
