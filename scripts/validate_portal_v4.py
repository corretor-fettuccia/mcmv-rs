import json
import xml.etree.ElementTree as ET
from pathlib import Path
root=Path(__file__).resolve().parent.parent
cat=json.loads((root/'catalogo.json').read_text(encoding='utf-8'))
items=cat['items']
assert cat['total_empreendimentos']==len(items)
assert items or cat.get('snapshotComplete') is True, 'Catálogo vazio sem confirmação' 
assert len({i['id'] for i in items})==len(items)
assert cat['schemaVersion']==4
assert cat.get('sourceContract')=='core-imobiliario-v4', 'Catálogo sem contrato de origem V4'
found=sorted({a for i in items for a in i.get('attributes',[])},key=str.casefold)
assert cat.get('filtros',{}).get('atributos')==found, 'Filtros divergentes dos atributos dos imóveis'
idx=(root/'index.html').read_text(encoding='utf-8')
app=(root/'app.js').read_text(encoding='utf-8')
assert 'id="attributeArea"' in idx and 'id="attributeFilters"' in idx, 'Filtro ausente no HTML da vitrine'
assert 'app.js?v=4.1.6' in idx and 'function refreshAttributes()' in app, 'Versão do JavaScript da vitrine incompatível'
if not found:
    print('AVISO: catálogo publicado não contém atributos. A seção deve indicar 0 até os imóveis serem atualizados.')
links=set()
for x in items:
    assert x['id'] and x['name'] and x['description'] and x['image']
    assert isinstance(x['attributes'],list) and isinstance(x['gallery'],list)
    page=root/'imoveis'/x['id']/'index.html'
    assert page.is_file(),f'HTML ausente: {page}'
    assert '<link rel="canonical"' in page.read_text(encoding='utf-8')
    links.add(x['pageUrl'])
sm='{http://www.sitemaps.org/schemas/sitemap/0.9}'
urls={e.text for e in ET.parse(root/'sitemap.xml').getroot().findall(f'{sm}url/{sm}loc')}
assert links<=urls, 'Sitemap sem todos os imóveis'
ET.parse(root/'merchant-produtos.xml')
print('OK:',len(items),'imóveis,',len(links),'páginas HTML indexáveis, XML válido')
