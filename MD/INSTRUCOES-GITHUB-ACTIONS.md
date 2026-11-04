# Core Imobiliário V4.2.1 — 100% GitHub Actions

## Objetivo

A criação e atualização do catálogo, XML Google Merchant, sitemap e páginas HTML acontece **no servidor do GitHub Actions**, não no computador do operador.

O **Git de produção** continua como base visual (`index.html`, `app.js`, `config.js`, imagens, `CNAME`). A API privada do Google Apps Script e a planilha permanecem independentes. A API pública V4 é consultada somente pelo motor `sinc-data` e **não pela vitrine**.

## Ordem do workflow

`GitHub Actions (agendado diariamente ou manual) → testes → sinc-data → make-feed-merchantcenter → make-sitemap → make-subpage → validação → empacotar site → registrar arquivos em main → publicar GitHub Pages`

| Motor | Entrada | Saída | Atualiza existentes? |
|---|---|---|---|
| `scripts/sinc-data.py` | API pública V4 (`VITRINE_API_URL`) | `/catalogo.json` | Sim, mantém IDs e substitui dados alterados |
| `scripts/make-feed-merchantcenter.py` | `/catalogo.json` | `/merchant-produtos.xml`, `/google-ads-imoveis.csv` | Sim, respeita `googleEnabled` e `googleAvailability` |
| `scripts/make-sitemap.py` | `/catalogo.json` | `/sitemap.xml`, `/robots.txt`, `/llms.txt` | Sim, inclui somente páginas publicadas |
| `scripts/make-subpage.py` | `/catalogo.json` | `/imoveis/{ID}/index.html` | Sim, regrava páginas alteradas |

`core.py` é o orquestrador; o YAML chama `core.py --step NOME` em **quatro etapas separadas**, para identificar qual motor falhou no log.

## Instalação no GitHub (sem terminal local)

1. Faça backup dos arquivos do repositório `corretor-fettuccia/mcmv-rs` (se possível, crie uma branch antes de substituir).
2. Envie para a branch `main`, mantendo os caminhos, os arquivos contidos na pasta `git-producao/` do patch. O diretório externo `git-producao` **não** deve ser criado dentro do repositório: seu conteúdo vai para a **raiz**.
3. Em **Settings → Secrets and variables → Actions → Variables**, defina `VITRINE_API_URL` com a URL da implantação **pública atual** do Google Apps Script que termine em `/exec`. Não use o ID do projeto e não use a URL da API privada.
4. Em **Settings → Pages → Build and deployment → Source**, escolha **GitHub Actions**. Esta etapa é indispensável para a implantação do artefato via `deploy-pages@v4`.
5. Em **Settings → Actions → General → Workflow permissions**, permita que o GITHUB_TOKEN grave conteúdo do repositório, se o commit automático falhar por permissão. O workflow declara `contents: write` para gravar o snapshot de volta no repositório.
6. Abra **Actions → Core Imobiliario V4.2.1 - Gerar e publicar GitHub Pages → Run workflow** na branch `main`.
7. Acompanhe as etapas **04, 05, 06, 07**, a validação **08/09**, o upload **11** e a implantação **14**. Uma falha interrompe a publicação; os arquivos anteriores permanecem disponíveis.
8. Após o sucesso, abra `https://mcmv-rs.com.br/catalogo.json`, `https://mcmv-rs.com.br/sitemap.xml` e `https://mcmv-rs.com.br/imoveis/mezzano/` (se `mezzano` estiver ativo no catálogo). A URL de cada imóvel usa seu ID real: `/imoveis/{ID}/`.

### Primeira sincronização

O workflow roda **automaticamente** quando os scripts ou o workflow são alterados na branch `main`, uma vez ao dia, ou quando você seleciona **Run workflow**.

As rotinas antigas `gerar-indexacao` e `atualizar-sitemap` foram deixadas desativadas e não devem gerar os mesmos arquivos. Nunca habilite geração paralela de `catalogo.json` por outro workflow.

## Como a subpágina funciona

O ID do imóvel determina o caminho fixo `imoveis/{ID}/index.html`. GitHub Pages atende `https://mcmv-rs.com.br/imoveis/{ID}/` quando o artefato implantado contém o arquivo correspondente.

O HTML contém título e metadados SEO, URL canônica, descrição completa, galeria de URLs da landing page, localização, dormitórios, suítes, banheiros, garagem, metragens, situação, atributos, preço e campanha, de acordo com o cadastro. Há botões **Acessar página do imóvel** (landing page comercial) e **Compartilhar** (compartilhamento nativo ou copiar URL), além de retorno à vitrine.

O catálogo V4 publica `items[].attributes`, `empreendimentos[].atributos` e `filtros.atributos`. A vitrine lê `/catalogo.json` e cria filtros a partir dos atributos realmente publicados.

### Atualizações

- **Edição do mesmo imóvel:** mantém ID e URL, substitui o HTML pela versão atualizada no próximo workflow.
- **Mudança de atributos/descrição/preço/fotos:** altera catálogo, filtros e a subpágina correspondente.
- **Imóvel inativo:** sai do catálogo e do sitemap; sua antiga página recebe `noindex` e mensagem de indisponibilidade.
- **Google desativado:** permanece na vitrine, mas não entra em `merchant-produtos.xml`.
- **API indisponível, resposta incompleta ou validação falha:** nenhum artefato novo é implantado. O workflow falha, mantendo o último site publicado.

## Arquivos e verificações

- `.github/workflows/core-imobiliario.yml`: job `gerar` e job `publicar` com dependência explícita.
- `scripts/stage_pages_v421.py`: monta `_site/` com site público e todas as subpáginas, sem scripts, workflows ou arquivos privados de testes.
- `scripts/validate_pages_v421.py`: exige **cada HTML de imóvel dentro do artefato** antes do upload.
- `scripts/test_pipeline_v420.py`: testes de atualização, desativação e falha da API.
- `scripts/test_pipeline_v421.py`: verifica geração, filtros e subpágina **no artefato que será publicado**.
- `scripts/summary_v421.py`: lista os IDs e URLs gerados no resumo do GitHub Actions.

**Diagnóstico de 404:** se a geração está verde e a URL continua retornando 404, verifique se a aba **Settings → Pages** está em **GitHub Actions**, se o job **publicar** foi concluído e se a URL acessada usa o ID exato, respeitando maiúsculas e minúsculas.

## Observações

- O feed XML Google é tecnicamente gerado. A aceitação de anúncios imobiliários depende das políticas do Google Merchant, que não podem ser garantidas pela geração do feed.
- O pacote não modifica sua conta GitHub nem sua planilha automaticamente. A implantação começa depois que os arquivos são enviados ao repositório e o workflow é executado.
- **Não é necessário rodar nenhum instalador Python local.** O Python roda no GitHub Actions.
