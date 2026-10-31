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
