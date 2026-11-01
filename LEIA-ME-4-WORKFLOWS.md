# Core Imobiliário V4.2.2 — Quatro workflows independentes

**O GitHub Actions executa quatro motores distintos e um Core orquestrador.**

| Workflow | Arquivo Python | Entrada | Saída |
|---|---|---|---|
| `sinc-data.yml` | `scripts/sinc-data.py` | API pública V4 (`VITRINE_API_URL`) | `catalogo.json` completo |
| `make-feed-merchantcenter.yml` | `scripts/make-feed-merchantcenter.py` | `catalogo.json` | `merchant-produtos.xml`, `google-ads-imoveis.csv` |
| `make-sitemap.yml` | `scripts/make-sitemap.py` | `catalogo.json` | `sitemap.xml`, `robots.txt`, `llms.txt` |
| `make-subpage.yml` | `scripts/make-subpage.py` | `catalogo.json` | `imoveis/<ID>/index.html` |

`core-imobiliario.yml` **não gera dados diretamente**: usa `jobs.<etapa>.uses` para chamar os 4 workflows na sequência `sinc_data → merchant → sitemap → subpage → preparar_publicacao → publicar`. Cada workflow pode ser acionado individualmente por **Run workflow** para diagnóstico: nesse caso, os motores 2 a 4 leem o `catalogo.json` salvo na branch e geram artefatos de teste, mas não publicam o site. **Para publicar, execute o Core.**

## Instalar diretamente no GitHub (sem terminal ou execução local)

1. No repositório `corretor-fettuccia/mcmv-rs`, atualize o código usando os caminhos do ZIP, especialmente os quatro arquivos `.github/workflows/*.yml` e `core-imobiliario.yml`.
2. **Exclua** os dois workflows legados `.github/workflows/gerar-indexacao.yml` e `.github/workflows/atualizar-sitemap.yml`. Eles podem sobrescrever o catálogo e o sitemap.
3. Em **Settings → Secrets and variables → Actions → Variables**, configure `VITRINE_API_URL` com a URL `/exec` da API pública Apps Script V4.
4. Em **Settings → Actions → General**, permita execução e chamadas de workflows reutilizáveis; em **Workflow permissions**, conceda **Read and write permissions** para o `GITHUB_TOKEN`, necessário para registrar os arquivos gerados na branch.
5. Em **Settings → Pages → Build and deployment**, selecione **Source: GitHub Actions**.
6. Acesse **Actions → Core Imobiliario V4.2.2 | 4 Actions separados → Run workflow**. Espere todos os 6 jobs ficarem verdes.
7. Verifique `https://mcmv-rs.com.br/catalogo.json`, `/sitemap.xml` e as páginas `/imoveis/<ID>/`. A vitrine lê o JSON e cria os botões de atributos dinamicamente a partir de `items[].attributes`.

## Contrato de dados

- **Fonte de verdade:** Google Sheets administrado pelo Apps Script privado; Apps Script público fornece o snapshot V4.
- **JSON público:** preserva `items[].attributes`, `items[].description`, `items[].gallery` e `items[].pageUrl`. O campo `atributos_disponiveis` agrega filtros.
- **Atualizações:** a cada execução completa do Core, páginas existentes são reescritas em caso de alteração; IDs e URLs permanecem permanentes.
- **Desativação:** imóveis inativos não entram no catálogo nem no sitemap; HTML antigo recebe `noindex` (via `make-subpage`).
- **Merchant:** somente os imóveis elegíveis e habilitados para Google entram no XML; o XML não é a base do portal. Elegibilidade de imóveis no Merchant Center depende das políticas do Google.
- **Falha:** se qualquer etapa falhar, o job final de Pages não roda e o site anterior permanece disponível.

## Teste de independência

Você verá, na aba Actions, **cinco workflows**: quatro motores autônomos e um Core central. Os quatro motores têm scripts Python individuais, e o Core apenas os coordena via `needs` e artefatos do GitHub Actions. Não é necessário `scripts/core.py` para executar no GitHub.
