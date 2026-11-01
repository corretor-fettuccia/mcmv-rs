# Core Imobiliário V4.2.4 — APENAS GITHUB ACTIONS / WORKFLOWS

## Objetivo

**Nada de terminal, instalador local ou comandos Python no seu computador.**
Uma vez que os arquivos estejam no repositório, todas as operações são feitas em **GitHub → Actions → Workflows → Run workflow**.

## Os cinco Workflows visíveis na aba Actions

| Workflow | Para que serve | Executar individualmente | Publica o site |
| --- | --- | --- | --- |
| `01 sinc-data` | Consulta a API V4 e gera `catalogo.json` completo com `attributes[]` | Sim | Não. Resultado em Artifacts. |
| `02 make-feed-merchantcenter` | Lê catálogo JSON e gera XML/CSV | Sim | Não. Resultado em Artifacts. |
| `03 make-sitemap` | Lê catálogo JSON e gera sitemap, robots e llms | Sim | Não. Resultado em Artifacts. |
| `04 make-subpage` | Lê catálogo JSON e cria/atualiza `/imoveis/ID/index.html` | Sim | Não. Resultado em Artifacts. |
| **`Core Imobiliário`** | Executa os quatro, valida e publica no GitHub Pages | **Sim** | **Sim**. |

Ao executar **um dos três últimos workflows individualmente**, o próprio workflow consulta a API e prepara um catálogo temporário atualizado antes de chamar o script responsável. No Core, isso é feito **uma única vez** no primeiro workflow: os outros recebem o mesmo `catalogo.json` como artefato, sem novas chamadas à API.

Os quatro scripts estão em `scripts/` e não fazem publicação direta. O Core publica um artefato estático via `actions/upload-pages-artifact` e `actions/deploy-pages`. **Não há `git push` automático nem necessidade de `contents: write`.**

## Instalação inicial — somente pelo site do GitHub

1. No repositório `corretor-fettuccia/mcmv-rs`, envie os arquivos do ZIP pelo editor web do GitHub, respeitando a estrutura de pastas. Isso é uma única atualização do código: **não precisa de terminal**.
2. Em `.github/workflows/`, mantenha **somente** os cinco arquivos deste pacote. Exclua os workflows antigos que geravam catálogo, sitemap ou publicavam Pages; eles podem sobrescrever a versão V4.
3. Em `Settings → Secrets and variables → Actions → Variables`, mantenha `VITRINE_API_URL` como a URL `/exec` **atual** da API pública V4.
4. Em `Settings → Pages → Build and deployment`, escolha `Source: GitHub Actions`.
5. Em `Settings → Actions → General`, permita as Actions necessárias. `Workflow permissions` pode ficar em `Read repository contents and packages` — o Core usa permissões específicas de publicação em seu job `publicar`.
6. Abra `Actions → Core Imobiliário | Sincronizar e publicar (4 workflows) → Run workflow` e selecione a branch `main`.
7. Espere seis jobs verdes: **sinc-data → Merchant → sitemap → subpage → preparar → publicar**.

## Verificação

- `https://mcmv-rs.com.br/catalogo.json` — `items[].attributes`, `description`, `gallery` e `pageUrl` completos.
- `https://mcmv-rs.com.br/sitemap.xml` — página principal e todas as subpáginas ativas.
- `https://mcmv-rs.com.br/imoveis/mezzano/` — exemplo de URL individual, desde que `mezzano` esteja publicado na API.
- `https://mcmv-rs.com.br/merchant-produtos.xml` — feed gerado apenas dos imóveis com publicação Google habilitada.

**Importante:** na publicação por artefato Pages, `catalogo.json` e os HTMLs são publicados **no site**, mas não são gravados automaticamente na branch `main`. Para visualizar um resultado isolado, abra a execução do respectivo workflow e baixe o arquivo em **Artifacts**. Para atualizar o portal, execute o **Core**.

## Atualizações e status

Quando o cadastro na planilha muda, na próxima execução do Core os quatro scripts passam a usar o novo snapshot. O ID e `pageUrl` ficam permanentes; descrição, preço, atributos e imagens são reconstruídos. Imóveis desativados não entram no catálogo público/sitemap e não entram no feed Google; páginas de imóveis removidos deixam de constar na nova publicação e no sitemap (caso não exista HTML anterior no checkout, a URL antiga deixa de existir).

## Testes e falhas

Se algum dos quatro motores falhar, os jobs seguintes e a publicação não serão executados. O último site publicado permanece. Nenhum workflow legado pode continuar concorrendo com o Core.
