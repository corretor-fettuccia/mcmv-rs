# Core Imobiliário V4.2.5 — Ativar os Workflows pelo site do GitHub

## O que foi auditado

O pacote anterior já possuía **cinco arquivos YAML** com gatilho de execução manual. O botão `Run workflow` **não depende de executar Python** e **não é ativado por upload de um arquivo ZIP**.

De acordo com a documentação oficial do GitHub, o workflow só é oferecido na aba Actions quando o `.yml` está na pasta **`.github/workflows/` da branch padrão** e define `workflow_dispatch`. O pacote V4.2.5 explicita esse evento nos cinco YAML e adiciona um gatilho `push` no **Core** para que um commit que altere `.github/workflows/` também gere uma primeira execução de diagnóstico na aba Actions.

**Importante:** não foi possível ler a listagem real de `.github/workflows` na conta do proprietário com os recursos públicos disponíveis aqui. Logo, não é possível afirmar que os YAML estejam implantados na sua `main`.

## 1. Confirme se os arquivos estão no repositório

Abra https://github.com/corretor-fettuccia/mcmv-rs/tree/main/.github/workflows

A pasta deve exibir **exatamente** estes cinco arquivos:

- `core-imobiliario.yml`
- `sinc-data.yml`
- `make-feed-merchantcenter.yml`
- `make-sitemap.yml`
- `make-subpage.yml`

**Se não aparecem nessa pasta, esta é a razão pela qual a aba Actions não oferece os workflows.**

### Como instalar somente pelo navegador

1. Baixe e **extraia** o ZIP do patch no computador. **Não envie o arquivo ZIP diretamente ao repositório**: GitHub não extrai ZIP automaticamente.
2. No GitHub, abra **Code**, branch **main**, pasta `.github/workflows`.
3. Para cada YAML, use **Add file → Upload files** nessa pasta (ou edite o arquivo correspondente). Faça commit **diretamente na `main`**. O arquivo precisa aparecer com o caminho `.github/workflows/NOME.yml`.
4. Envie também os arquivos `scripts/` do pacote para a pasta `scripts/` na mesma branch, preservando seus nomes.
5. Remova somente antigos `.yml` que geram os mesmos arquivos para evitar concorrência. Não apague o código PHP/HTML nem os dados de produção.
6. Abra https://github.com/corretor-fettuccia/mcmv-rs/actions e atualize a página.
7. No menu à esquerda selecione **Core Imobiliario - Sincronizar e Publicar** e clique **Run workflow → main → Run workflow**.

**Observação:** se o botão não aparecer, confira se sua conta está com permissão de escrita e se a seção `Settings → Actions → General` não tem Actions desativado. Se o workflow estiver marcado como desativado, abra-o e clique **Enable workflow**. Se os arquivos estiverem apenas numa branch de teste, será preciso integrá-los à branch padrão.

## 2. A configuração do site, uma vez que o workflow esteja visível

- `Settings → Secrets and variables → Actions → Variables`: `VITRINE_API_URL` com a URL da **implantação pública Apps Script `/exec`** (não o ID do projeto).
- `Settings → Pages → Build and deployment → Source`: **GitHub Actions**.
- O `core-imobiliario.yml` é o único publicador Pages; os outros quatro executam individualmente e disponibilizam seus arquivos nos **Artifacts** da execução.
- Não é necessário configurar `contents: write` nem token pessoal. O job de implantação define `pages: write` e `id-token: write`.

## 3. O que significa cada workflow

| Arquivo | Execução manual | Resultado |
|---|---|---|
| `sinc-data.yml` | Sim | Snapshot `catalogo.json` com atributos |
| `make-feed-merchantcenter.yml` | Sim | XML/CSV derivados do catálogo |
| `make-sitemap.yml` | Sim | Sitemap, robots e llms |
| `make-subpage.yml` | Sim | HTML individual com galeria, atributos, contato e compartilhar |
| `core-imobiliario.yml` | Sim | Executa os quatro na ordem, valida e publica o site |

O Core também tem `schedule` diário e `push` restrito a alterações nos arquivos de workflow na `main`. Não há `git push` automático. Arquivos gerados vão para o **artefato do GitHub Pages**, não para a branch.

## 4. Se o botão continuar ausente

Verifique **na ordem**:

1. Está visualizando o repositório **`corretor-fettuccia/mcmv-rs`** e a branch **`main`**?
2. Existem os cinco arquivos **soltos dentro de `.github/workflows/`** (não em subpasta do ZIP ou como `.zip`)?
3. Os arquivos foram **commitados**, ou apenas enviados para uma proposta de Pull Request?
4. A aba **Actions** está habilitada em Settings?
5. O workflow foi desativado manualmente? (botão **Enable workflow**.)
6. Sua conta possui permissão de gravação? Sem ela, você não vê a ação manual de executar.

O problema **não é** a variável `VITRINE_API_URL` nem o conteúdo de `catalogo.json`: essas condições são verificadas **depois que o workflow inicia**, não ao exibir o botão.

## 5. Testes locais incluídos

- Sintaxe YAML e eventos nos cinco arquivos.
- `python scripts/auditar_workflows_v425.py` (é executado pelo Core no GitHub, não precisa rodar localmente).
- Testes offline dos scripts Python de catálogo, atributos, HTML, sitemap, feed e atualização do mesmo imóvel.

Sem acesso autenticado à aba Actions da sua conta, esta validação não confirma a instalação real. O primeiro critério de aceite é **ver os cinco Workflows listados na barra lateral**; o segundo é conseguir executar manualmente o Core.
