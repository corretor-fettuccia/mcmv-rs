# MCMV-RS V10

Planilha Google → API do Apps Script → **um único workflow** no GitHub Actions → site no GitHub Pages.
O visitante só lê arquivos estáticos; a API nunca é chamada pelo navegador.

## Instalar
1. Suba o conteúdo desta pasta na **raiz** do repositório (branch `main`).
2. Em **Settings → Secrets and variables → Actions** mantenha `VITRINE_API_URL` com a URL `/exec` do Apps Script
   (aba *Variables*; a aba *Secrets* também é aceita).
3. Em **Settings → Pages**, a origem deve ser **GitHub Actions**.
4. Apague do repositório o que o log do passo "Avisar sobre arquivos de versoes anteriores" listar. O upload de ZIP não
   remove nada, e os arquivos antigos só atrapalham a leitura. Eles **nunca** vão para o site: a montagem usa lista de permissão.
5. Rode **Actions → Core Imobiliario → Run workflow**. Depois disso roda sozinho às 07:17 UTC (04:17 em Brasília), a cada push em `main` e quando você mandar.

Não suba `catalogo.json`, XMLs nem `imoveis/`: são gerados a cada execução (`.gitignore` já os ignora).

## O fluxo (`.github/workflows/core-imobiliario.yml`)
| # | Passo | Script | Saída |
|---|---|---|---|
| – | Testes sem rede | `test_core.py`, `test_vitrine_*.js` | bloqueiam a publicação se falharem |
| 1 | Lê a API (estado atual da planilha) e registra **novos / atualizados / removidos** | `sync_catalog.py` | `catalogo.json` |
| 2 | Feeds Google e Meta, **mesma rotina** | `build_feeds.py` | `merchant-produtos.xml`, `marketplace-produtos.xml`, `google-ads-imoveis.csv` |
| 3 | Páginas individuais com todas as imagens | `build_pages.py` | `imoveis/{id}/index.html` |
| 4 | Sitemap com imagens e robots | `build_sitemap.py` | `sitemap.xml`, `robots.txt` |
| 5 | Descoberta para IA | `build_llms.py` | `llms.txt` |
| 6 | Validação independente dos geradores | `validate.py --check all` | falha = não publica |
| 7–8 | Monta e valida `_site` | `stage_site.py`, `validate.py --check site` | artefato do Pages |
| – | Publica e confere as URLs públicas | `deploy-pages`, `verify_public.py` | `https://mcmv-rs.com.br/{merchant-produtos,marketplace-produtos,sitemap}.xml` |

Tudo que vem depois do passo 1 lê só o `catalogo.json`. Para rodar no seu computador: `VITRINE_API_URL=… python scripts/run_local.py`.

## Contrato dos feeds
- **Merchant** (RSS 2.0, `g:`): entra o imóvel com `googleEnabled`, disponibilidade `in_stock`/`out_of_stock`, marca, condição, preço mínimo, imagem, URL e descrição. `g:price` = `250000.00 BRL`.
- **Marketplace** (Meta `<listings>`): entra o imóvel com id, nome, cidade, UF, endereço, preço mínimo, URL e imagem https, exceto `marketplaceEnabled` = `false/NAO`. A API atual não envia esse campo, então **todos** entram. `availability = for_sale`, `image/url` de 1 a 20 (principal + galeria, sem repetição, nunca Base64), `price` = valor mínimo do empreendimento.
- Cada feed tem a sua elegibilidade; os dois podem listar imóveis diferentes. Imóvel que falta dado fica fora e o motivo vai para o log. Nada é inventado.
- **Sitemap**: página principal primeiro, depois só imóveis ativos (`/imoveis/{id}/`), cada um com `image:image` (https, sem repetição); sem `lastmod`, pois a planilha não tem esse dado.

## Logs
`[sync]`, `[feeds] 1/2 GERADO …`, `[feeds] 2/2 GERADO …`, `[pages]`, `[sitemap]`, `[llms]`, `[validate] OK …`, `[site] INCLUÍDO no artefato: …`, `[publico] OK <url>`.

## Limites conhecidos
- Marketplace sem nenhum imóvel elegível **bloqueia o deploy** (`shortcut:` em `build_feeds.py`). Se todos os imóveis forem desativados, o site antigo continua no ar até alguém religar um.
- O Meta pede mais que o catálogo traz (CEP, latitude/longitude): não são inventados. Se a Meta recusar anúncios por isso, as colunas precisam existir na planilha.
- Imóveis são categoria restrita no Google Merchant: feed válido não garante aprovação.
- O passo final espera até ~4 minutos o CDN do Pages refletir o deploy.
