> **HISTÓRICO V6.** Para instalar a versão atual, leia `LEIA-PRIMEIRO-V8-MARKETPLACE.md`.

# MCMV-RS V6 corrigida — Feed Marketplace + Feed Merchant

## O que mudou

A estrutura original foi preservada: `GIT-PAGE/` contém o site GitHub Pages e
`GOOGLE.APPSCRIPT/` contém os Apps Scripts, **que não devem ir para o repositório público**.

Foram corrigidos somente dois auditores do Core. O Core exige os mesmos cinco
workflows de sempre, mas **não exige mais** `gerar-marketplace.yml` para publicar.
Se o sexto workflow existir, será validado. Isso resolve a falha
`AUSENTE: .github/workflows/gerar-marketplace.yml` que bloqueou o passo 5 do Core.
O arquivo solto `.github/workflows/a` (um byte) foi retirado.

A geração do Google Merchant **não foi alterada**:
`scripts/make-feed-merchantcenter.py`,
`scripts/merchant_from_catalog.py`,
`.github/workflows/make-feed-merchantcenter.yml` e
`.github/workflows/core-imobiliario.yml` permanecem exatamente como foram enviados.

## Instalar na raiz certa do GitHub

**Importante:** `.github/workflows/` precisa existir na raiz do repositório GitHub,
e NÃO dentro de `GIT-PAGE/`, `mcmv-rs-v6/` ou qualquer outra subpasta.

Use o arquivo separado `MCMV-RS-V6-GITHUB-RAIZ.zip`: extraia e envie **seu
conteúdo** para a raiz da branch `main`, preservando pastas e substituindo
apenas os arquivos homônimos. O ZIP GitHub-RAIZ não contém Apps Script privado.
O pacote completo serve de backup e para reutilização dos dois projetos.

**Proteção dos dados em produção:** o `catalogo.json` da V6 recebida contém
apenas um byte (não é JSON válido). Por isso, o ZIP `GITHUB-RAIZ` **não inclui**
este arquivo nem os demais resultados gerados por automação (`merchant-produtos.xml`,
`google-ads-imoveis.csv`, `imoveis/`, `llms.txt` e `robots.txt`). Os arquivos
existentes no repositório não serão sobrescritos por versões antigas.
O Core já reconstrói e publica o catálogo, o feed Merchant e as páginas
no próprio GitHub Actions. O script Marketplace consulta o JSON **público**
e não depende do arquivo vazio incluído no backup da V6 recebida.

Confira na aba Code se estes arquivos existem nos caminhos **exatos**:

- `.github/workflows/core-imobiliario.yml`
- `.github/workflows/gerar-marketplace.yml`
- `.github/workflows/make-feed-merchantcenter.yml`
- `scripts/gerar_marketplace.py`
- `scripts/make-feed-merchantcenter.py`

## Gerar e publicar

1. Em **Actions** rode `Gerar Marketplace Produtos` manualmente na branch `main`.
   O trabalho roda sozinho todos os dias à **00h10 de Brasília** (`10 3 * * *` UTC).
2. O Marketplace lê `https://mcmv-rs.com.br/catalogo.json` (ou a variável
   `MARKETPLACE_CATALOG_URL` para reutilizar em outro projeto) e escreve apenas
   `marketplace-produtos.xml` na raiz da branch. É um catálogo de imóveis
   com preço de referência e URLs de até 20 imagens. Não usa Base64.
3. **Na publicação normal do Core**, o estágio Pages inclui esse XML que
   estava na branch junto do novo `merchant-produtos.xml` gerado pelo Core.
4. Verifique as duas URLs após o Core publicar:
   - `https://mcmv-rs.com.br/marketplace-produtos.xml`
   - `https://mcmv-rs.com.br/merchant-produtos.xml`

A geração separada do Marketplace não força um deploy próprio: assim, **não
interfere na rotina de publicação do Core**. O XML novo vai ao domínio apenas
na próxima publicação normal do Core. GitHub Actions pode atrasar agendamentos.

## Testes locais sem rede

Executar dentro da pasta `GIT-PAGE`:

```bash
python3 -m unittest discover -s scripts -p 'test_gerar_marketplace.py' -v
python3 -m unittest discover -s scripts -p 'test_integracao_feeds_v6.py' -v
python3 scripts/auditar_workflows_v425.py
python3 scripts/check_workflows_v423.py
```

## Alcance da integração Meta

O XML segue o modelo de **Home Listings** para alimentar um catálogo imobiliário
no Commerce Manager (anúncios dinâmicos). É preciso configurar a importação
agendada e consultar o diagnóstico retornado pela Meta; publicar classificados
gratuitos automaticamente no Facebook Marketplace é outra operação não oferecida
por este workflow.
