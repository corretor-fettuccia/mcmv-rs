# Core Imobiliário V4.2.7 — reconstrução do catálogo e atributos padronizados

## O que foi corrigido

1. **Atualização forçada do catálogo**: `sinc-data.py` consulta a API pública **em toda execução**, sem reutilizar `catalogo.json` como fonte. Se o arquivo anterior estiver ausente, vazio, contiver `{}` ou tiver JSON inválido, a sincronização o reconstrói com base no snapshot válido da API, com substituição atômica. Cabeçalhos `no-cache` e parâmetro variável `_core_refresh` evitam respostas HTTP em cache.
2. **Formatação automática dos atributos**: a primeira letra alfabética fica maiúscula e as demais letras ficam minúsculas, inclusive após um prefixo numérico: `piscina` → `Piscina`, `02 dormitórios` → `02 Dormitórios`, `sala DE ESTAR` → `Sala de estar`. `Água quente` mantém o acento. Espaços extras são eliminados.
3. **Deduplicação de filtros**: diferenças de caixa e acentuação não criam múltiplos filtros. Se houver `agua quente` e `Água quente`, prefere-se a grafia acentuada que já exista entre os cadastros. As listas `items[].attributes`, `empreendimentos[].atributos`, `filtros.atributos` e `atributos_disponiveis` ficam consistentes.
4. **Validação preventiva**: o Core interrompe a publicação caso as listas de filtros não coincidam, ou se a API fornecer snapshot incompleto; não publica arquivo vazio por erro da API.

A planilha e o Apps Script **não são alterados**. A padronização ocorre na distribuição pública do catálogo.

## Instalar exclusivamente pelo site do GitHub

No repositório `corretor-fettuccia/mcmv-rs`, branch **main**, substitua ou crie os arquivos extraídos do patch nos caminhos exatos:

- `scripts/core_lib.py`
- `scripts/sinc-data.py`
- `scripts/validate_portal_v420.py`
- `scripts/test_reconstrucao_v427.py`
- `.github/workflows/sinc-data.yml`
- `.github/workflows/core-imobiliario.yml`

**Não envie o ZIP fechado como arquivo do repositório.** Extraia-o e use **Add file → Upload files** nas pastas correspondentes. Faça commit na `main`.

Em **Settings → Secrets and variables → Actions → Variables**, confirme o nome exato `VITRINE_API_URL` com o valor:

`https://script.google.com/macros/s/AKfycbz4WtifpLezYJdLhLGlxe-M5tdcupG9Ttj7QCmWc9QTLbCDebCU99MjB7OvDwbpSjCq/exec`

A variável deve estar na aba **Variables**, pois o YAML utiliza `${{ vars.VITRINE_API_URL }}`. A URL não precisa ser escrita no código. Caso a implantação pública do Apps Script mude no futuro, altere somente essa variável.

Em seguida abra **Actions → Core Imobiliario - Sincronizar e Publicar → Run workflow → main → Run workflow**. O Core executará em ordem:

1. `sinc-data` → recriação de `catalogo.json` a partir da API;
2. `make-feed-merchantcenter` → XML e CSV baseados no novo JSON;
3. `make-sitemap` → sitemap baseado no novo JSON;
4. `make-subpage` → criação/atualização das páginas individuais;
5. validação e publicação direta no GitHub Pages.

A atualização da configuração de workflows também aciona o Core automaticamente na `main`; ainda assim você pode usar **Run workflow** para confirmar o resultado imediatamente.

## Como verificar

No log do job **01 sinc-data**, procure:

`[sinc-data] API: ... ; arquivo: reconstruído pela API (escrita atômica).`

Se o catálogo anterior foi apagado, também aparecerá:

`[sinc-data] Catálogo anterior ausente, vazio ou inválido: reconstruindo ...`

No job **05 - Validar e montar site para Pages**, confira que o teste dos filtros passou e no job **06 - Publicar o site no GitHub Pages** confira o sucesso da implantação.

Páginas públicas após a publicação:

- `https://mcmv-rs.com.br/catalogo.json`
- `https://mcmv-rs.com.br/sitemap.xml`
- `https://mcmv-rs.com.br/imoveis/ID_DO_IMOVEL/`

> **Importante:** nessa arquitetura, o catálogo gerado é publicado no **artefato do GitHub Pages**. Ele **não será gravado automaticamente na branch `main`**, pois a opção anterior de `git push` foi removida. Portanto, ver o arquivo vazio na branch não significa que o catálogo publicado esteja vazio. Verifique a URL pública após a execução do Core. Executar somente `sinc-data` disponibiliza um artefato de teste, mas não publica o site completo.

## Comportamento de segurança

- A API deve retornar `ok: true`, `schemaVersion: 4`, `sourceContract: core-imobiliario-v4`, `snapshotComplete: true` e contagens coerentes.
- Falha de rede, contrato inválido ou snapshot incompleto **bloqueiam a publicação** em vez de substituir o site por um resultado inválido.
- `publishedRows: 0` somente é aceito se vier explicitamente confirmado pela API como snapshot completo.
- Imóveis já cadastrados mantêm seu ID e URL; mudanças de preço, descrição, atributos e imagens são refletidas na próxima execução.

## Arquivos e testes

A execução local de homologação foi realizada com dados fictícios, sem modificar Google Sheets, Apps Script ou o GitHub de produção. O novo teste `scripts/test_reconstrucao_v427.py` cobre arquivo apagado, vazio, corrompido, `{}`, nomes de atributos equivalentes, atualização de imóveis e proteção contra snapshot incompleto.
