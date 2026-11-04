#!/usr/bin/env python3
"""Diagnóstico offline do catálogo e da vitrine: não altera arquivos."""
import json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
cat=json.loads((root/'catalogo.json').read_text(encoding='utf-8'))
items=cat.get('items',[]) if isinstance(cat.get('items'),list) else []
html=(root/'index.html').read_text(encoding='utf-8')
app=(root/'app.js').read_text(encoding='utf-8')
attrs=sorted({str(a).strip() for x in items for a in (x.get('attributes') if isinstance(x.get('attributes'),list) else []) if str(a).strip()},key=str.casefold)
print('DIAGNÓSTICO VITRINE CORE V4.1.8')
assert cat.get('sourceContract')=='core-imobiliario-v4', 'Catálogo não possui contrato V4: execute o workflow após implantar a API pública atualizada.'
print('Catálogo:',len(items),'imóveis;',len(attrs),'atributos distintos')
print('Atributos:', ', '.join(attrs) if attrs else '(nenhum cadastrado)')
print('HTML instalado:', 'Core V4 compatível' if 'id="attributeFilters"' in html else 'ANTIGO OU INCOMPATÍVEL')
print('Filtro no HTML:', 'SIM' if 'id="attributeFilters"' in html else 'NÃO')
print('Filtro no JavaScript:', 'SIM' if 'function refreshAttributes()' in app else 'NÃO')
if not attrs:
    print('AÇÃO: verificar ATRIBUTOS na planilha dos imóveis ATIVOS, confirmar retorno items[].attributes na API PÚBLICA e executar sincronização GitHub Actions.')
if 'id="attributeFilters"' not in html or 'function refreshAttributes()' not in app:
    raise SystemExit('ERRO: vitrine sem componentes dos filtros. Publique index.html e app.js da mesma versão.')
with open(root/'catalogo.json',encoding='utf-8') as f:
    pass
