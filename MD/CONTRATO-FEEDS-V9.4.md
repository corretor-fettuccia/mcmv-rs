# Contrato dos feeds MCMV-RS V9.4

Fonte única: `catalogo.json` (schemaVersion 4, `sourceContract: core-imobiliario-v4`, `snapshotComplete: true`), produzido por `scripts/sinc-data.py` a partir da API pública do Apps Script. Nenhum feed consulta a API, a planilha ou as landing pages. **Dado ausente no catálogo não é inventado: o item sai do feed e o motivo vai para o log.**

Validador: `scripts/validate_xml_v94.py` (estrutura, independente dos geradores).

## 1. `merchant-produtos.xml` — Google Merchant (preservado da V9.3)

RSS 2.0 com namespace `g` = `http://base.google.com/ns/1.0`, UTF-8. Gerador `scripts/merchant_from_catalog.py`, sem alteração (saída idêntica à da V9.3 para o mesmo catálogo; há teste).

| Elemento | Origem no catálogo | Regra |
|---|---|---|
| `g:id` | `merchantId` (ou `id`) | único no arquivo |
| `g:title` | `name` | obrigatório |
| `g:description` | `description` (ou `highlight`) | obrigatório |
| `g:availability` | `googleAvailability` | `in_stock` ou `out_of_stock` |
| `g:condition` | `condition` | `new` ou `used` |
| `g:price` | `minimum` | `250000.00 BRL`, maior que zero |
| `g:image_link` | `image` | https público |
| `g:link` | `url` | https; landing page |
| `g:brand` | `brand` | obrigatório |

Elegibilidade: `googleEnabled = true` e todos os campos presentes. Zero itens elegíveis é válido (RSS vazio retira ofertas antigas). Auxiliar do mesmo motor: `google-ads-imoveis.csv` (inalterado).

## 2. `marketplace-produtos.xml` — Meta (gerado pelo mesmo motor)

Raiz `<listings>` com `<title>` e `<link rel="self" href="…/marketplace-produtos.xml"/>`. Gerador `scripts/gerar_marketplace.py` (`compile_xml`), chamado por `make-feed-merchantcenter.py`, sem alteração.

| Elemento `<listing>` | Origem | Regra |
|---|---|---|
| `home_listing_id` | `id` | obrigatório, único |
| `name` | `name` | obrigatório |
| `availability` | constante `for_sale` | não reaproveita `googleAvailability` (vocabulário do Google) |
| `description` | `highlight`, senão `description`, senão `name` | obrigatório |
| `address format="simple"` | `address`, `city`, `uf`, país `BR` | `addr1`, `city`, `region`, `country` obrigatórios |
| `neighborhood` | `neighborhood` | só se constar no endereço |
| `image/url` (1 a 20) | `image` + `gallery` | https público, sem repetição, principal primeiro; **nunca Base64/`data:`** |
| `listing_type` | constante `for_sale_by_agent` | |
| `num_beds`, `num_baths`, `area_size`/`area_unit` | `bedrooms`, `bathrooms`, `privateArea` | omitidos se ausentes |
| `price` | `minimum` | `250000.00 BRL`, maior que zero; **valor mínimo do empreendimento**, não de unidade |
| `property_type` | `propertyType` | `apartment`, `house`, `land`; omitido se desconhecido |
| `url` | `pageUrl` (senão `url`) | https |

Elegibilidade: `marketplaceEnabled` diferente de `false` e `id`, `name`, `city`, `uf`, `address`, `minimum`, URL e imagem presentes. Independente de `googleEnabled`.

**Falha:** nenhum imóvel elegível ⇒ `Nenhum item válido` e a publicação é interrompida.

**`marketplaceEnabled`:** a API atual não envia o campo. O sincronizador o repassa se vier (`false`, `NAO`, `NÃO`, `NO`, `0` desativam); ausente = publicado. A API não foi alterada.

## 3. `sitemap.xml`

`<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">`, UTF-8.

- Primeira URL: página principal (`site_url`).
- Depois, um `loc` por imóvel ativo: `site_url + imoveis/{id}/`, https, sem repetição.
- Cada imóvel traz `<image:image><image:loc>` (principal + galeria, https, sem repetição na página, até 60; limite Google 1000).
- Imóvel desativado não está no catálogo e sai do sitemap; a validação confirma que cada URL tem `imoveis/{id}/index.html` sem `noindex`.
- Sem `lastmod`/`changefreq`/`priority` (o catálogo não tem esses dados).

## 4. Logs

| Marcador | Etapa |
|---|---|
| `[feeds V9.4] 1/2 GERADO merchant-produtos.xml`, `2/2 GERADO marketplace-produtos.xml` | geração |
| `[feeds V9.4] Marketplace excluiu <id>: <motivo>` | exclusão |
| `[feeds V9.4] ARTEFATO core-v4-feeds inclui <arquivo>` | artefato do Actions |
| `[make-sitemap V9.4] GERADO sitemap.xml` | sitemap |
| `[validate V9.4] OK …` | validação |
| `[V9.4] RECEBIDO <arquivo>`, `[Pages V9.4] INCLUIDO no artefato: <arquivo>` | montagem |
| `[publico V9.4] OK <url>` | verificação pós-deploy |

## 5. Validações

| Onde | Comando | Reprova |
|---|---|---|
| Job 02 | `validate_xml_v94.py --check feeds` | XML malformado; raiz/namespace errados; campo obrigatório ausente; preço fora do formato ou zero; id repetido; URL não https (inclui `data:`); imagem repetida; `availability` fora do contrato; Marketplace vazio; divergência do catálogo |
| Job 03 | `--check sitemap` | declaração/namespace ausentes; URL ou imagem repetida; principal fora do topo; fora do catálogo; `robots.txt` sem `Sitemap:`; `llms.txt` ausente |
| Job 5-6, validação | `validate_portal_v420.py` + `--check all` | tudo acima + páginas inexistentes/`noindex` |
| Job 5-6, montagem | `stage_pages_v421.py`, `validate_pages_v421.py`, `--root _site` | feed ou sitemap ausente (falha **antes** de tocar em `_site`); contrato revalidado no artefato |
| Pós-deploy | `verify_public_v94.py` | URL pública ausente ou fora do contrato (8 tentativas, 30 s) |

## 6. Testes automatizados (`scripts/`, sem rede; rodam no job `preparar` antes de publicar)

| Arquivo | Cobre |
|---|---|
| `test_feeds_unificados_v94.py` (25) | motor único; Merchant idêntico ao original; imagens sem Base64; falha do Marketplace não grava nada; indicadores independentes; sitemap (principal, imagens, namespaces, escape, sem repetição, desativado); casos negativos do contrato; estrutura dos workflows; staging; verificação pública |
| `test_core_v423`, `test_pipeline_v420/v421` | pipeline completo, idempotência, atualização, inativação, artefato |
| `test_integracao_core_v8`, `test_integracao_feeds_v6` | independência Google/Meta, Merchant preservado, auditorias |
| `test_gerar_marketplace`, `test_reconstrucao_v427` | gerador Meta e catálogo (inalterados) |
| `test_vitrine_hover_v9.js`, `test_vitrine_catalogo_v420.js` | vitrine, filtros, carrossel (inalterados) |
