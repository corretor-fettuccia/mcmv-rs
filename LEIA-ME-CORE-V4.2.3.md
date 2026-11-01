# Core Imobiliário V4.2.3 — instalação simplificada (GitHub Actions)

O portal usa **um único workflow** (`.github/workflows/core-imobiliario.yml`) e **quatro scripts Python independentes**. O workflow roda no GitHub, constrói os arquivos e publica no GitHub Pages **sem realizar commit automático** na branch `main`.

## Os quatro motores

| Ordem | Arquivo | Entrada | Saída |
|---|---|---|---|
| 1 | `scripts/sinc-data.py` | API pública Apps Script V4 | `catalogo.json` completo |
| 2 | `scripts/make-feed-merchantcenter.py` | `catalogo.json` | `merchant-produtos.xml` e `google-ads-imoveis.csv` |
| 3 | `scripts/make-sitemap.py` | `catalogo.json` | `sitemap.xml`, `robots.txt` e `llms.txt` |
| 4 | `scripts/make-subpage.py` | `catalogo.json` | `imoveis/<ID>/index.html` |

O GitHub Actions para na primeira falha; só publica se testes e validações passarem. Os quatro scripts podem ser executados separadamente em ambiente de desenvolvimento, mas há **apenas um workflow de produção**.

## Instalação **no próprio GitHub** (sem terminal)

1. Faça backup da branch principal. Suba o conteúdo do ZIP completo para a **raiz** do repositório `corretor-fettuccia/mcmv-rs` (mantendo as pastas `scripts/` e `.github/workflows/`). Para uma atualização pequena, use o ZIP patch.
2. Em `.github/workflows/` **mantenha apenas** `core-imobiliario.yml` entre os workflows que geram o portal. **Exclua** `sinc-data.yml`, `make-feed-merchantcenter.yml`, `make-sitemap.yml`, `make-subpage.yml` anteriores e quaisquer workflows legados que também escrevam `catalogo.json`, `sitemap.xml`, `merchant-produtos.xml` ou implantem o Pages (por exemplo `gerar-indexacao.yml`, `atualizar-sitemap.yml`).
3. Em **Settings → Secrets and variables → Actions → Variables → New repository variable**, crie ou confirme `VITRINE_API_URL` apontando para a implantação `/exec` da API pública V4 (não o ID do projeto).
4. Em **Settings → Pages → Build and deployment**, selecione **Source: GitHub Actions**. Confirme também seu domínio personalizado. O arquivo `CNAME` já está no projeto.
5. Em **Actions → Core Imobiliário V4.2.3 | Sincronizar e publicar**, clique em **Run workflow**, escolhendo a branch `main`.
6. Verifique se os jobs `gerar` e `publicar` ficaram verdes. Dentro de `gerar`, veja as quatro etapas nomeadas `1/4` a `4/4`. A URL publicada aparece no job `publicar`.
7. Confira as URLs `https://mcmv-rs.com.br/catalogo.json`, `https://mcmv-rs.com.br/sitemap.xml`, `https://mcmv-rs.com.br/merchant-produtos.xml` e as subpáginas `/imoveis/<ID>/`.

### Permissões — configuração mínima

O workflow possui `contents: read` durante a geração, e `pages: write` + `id-token: write` **somente no job de publicação**. Não é preciso habilitar `Read and write permissions` no **Settings → Actions → General**; a configuração padrão de leitura basta, desde que nenhuma política do repositório/organização bloqueie a execução.

### O que é atualizado

- **Imóvel novo:** aparece no JSON, ganha sua subpágina e entra no sitemap.
- **Imóvel alterado:** a subpágina é **recriada no mesmo ID e mesma URL** com os campos novos (preço, características, descrição, galeria, status da obra, etc.).
- **Imóvel desativado:** deixa de constar no JSON e no sitemap; no deploy por artefato, a página pode deixar de existir (**404**) se não houver histórico anterior na origem. Não há preservação obrigatória de páginas antigas na branch, pois não há commits automáticos.
- **Publicação Google desativada:** o imóvel permanece no portal, mas não aparece no XML do Merchant.
- **Atributos:** `items[].attributes` e `atributos_disponiveis` são publicados a partir da API. A vitrine gera as opções de filtros automaticamente. O motor falha se a API não retornar o contrato V4 esperado.

### Atenção: arquivos gerados não aparecem no repositório

O novo modelo publica os arquivos gerados **no site do GitHub Pages**, via artefato (`_site`). `catalogo.json`, `sitemap.xml` e `imoveis/` podem ficar desatualizados ou ausentes no navegador de arquivos da branch `main`, e **isso é esperado**; a versão pública correta é a publicada no domínio após o Actions. **Não configure nenhuma outra rotina para fazer commit desses arquivos**, pois isso criaria concorrência.

### Diagnóstico

- Falha em `1/4 sinc-data`: conferir `VITRINE_API_URL` e a implantação da API pública; o snapshot deve conter `schemaVersion:4`, `sourceContract:core-imobiliario-v4` e `items[].attributes`.
- Falha em `2/4`: verificar campos do Merchant no catálogo, e erros do gerador.
- Falha em `3/4`: verificar `site_url` em `portal-config.json` e os IDs dos imóveis.
- Falha em `4/4`: verificar IDs seguros, URLs e dados de imagens.
- Falha em validação: nada será publicado, protegendo o último site publicado.
- Falha no job `publicar`: confira **Settings → Pages → Source: GitHub Actions**, permissões `pages:write/id-token:write` e restrições do ambiente `github-pages`.

### Arquivos mantidos

`index.html`, `app.js`, `config.js`, `CNAME`, `portal-config.json`, imagens e estilos existentes são preservados. Os serviços privados do Google Apps Script e a planilha não são modificados por este pacote. Mudanças na planilha chegam à publicação na próxima sincronização; agendamento diário às 07:17 UTC (04:17 de Brasília quando UTC−3).

**Pré-requisitos:** os arquivos do pacote devem estar efetivamente no GitHub e a variável `VITRINE_API_URL` configurada. Não foi feito deploy na sua conta.

## Verificação automática de workflows conflitantes

A etapa `scripts/check_workflows_v423.py` bloqueia o Core se os quatro workflows individuais anteriores ou os workflows legados de indexação ainda existirem em `.github/workflows/`. Isso evita publicar uma versão nova enquanto scripts antigos continuam ativos. Exclua esses arquivos **antes de executar** o Core V4.2.3. Outros workflows não relacionados ao portal podem continuar normalmente.

## Testes locais incluídos

`test_pipeline_v420.py`, `test_pipeline_v421.py` e `test_core_v423.py` rodam automaticamente antes de consultar a API. O novo teste verifica dois imóveis, 7 filtros, 1 item no XML, 3 URLs no sitemap e a atualização de um imóvel mantendo a mesma URL.
