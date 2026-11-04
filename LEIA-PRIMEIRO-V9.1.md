# MCMV-RS V9.1 — correção de deploy e feeds (auditoria Ponytail)

## O que foi corrigido

O `gerar-marketplace.yml` estava presente no ZIP original da V9, mas ausente do checkout de produção. As duas auditorias exigiam o arquivo e encerravam o Core com `exit code 1` antes da montagem do GitHub Pages.

A V9.1 **não exige mais o sexto workflow para publicar o Marketplace**. O `stage_pages_v421.py`, que já é chamado no job `preparar` do Core, agora:

1. Lê o mesmo `catalogo.json` recebido do sincronizador nesta execução.
2. Gera `marketplace-produtos.xml` a partir da galeria, endereços e preços existentes.
3. Valida o XML usando `validate_marketplace_v8.py`.
4. Inclui o XML no artefato `_site/` que será publicado junto com `merchant-produtos.xml`.

O feed Merchant **continua sendo gerado por `make-feed-merchantcenter.yml`**, sem alteração de sua lógica. `gerar-marketplace.yml` permanece disponível como workflow **opcional de geração avulsa**, caso o arquivo `.github` seja enviado corretamente; o Core não depende mais dele.

Se nenhum imóvel for elegível para Meta, o feed Meta antigo é descartado do novo artefato e o Core continua publicando o Merchant e o portal. É registrado um `::warning::` no log. Erros de contrato/snapshot continuam sendo propagados para não publicar dados incorretos.

## Instalação

**GitHub direto:** use `MCMV-RS-V9.1-GITHUB-RAIZ.zip`. Descompacte e envie os arquivos **dentro** do ZIP para a raiz do repositório. Não envie a pasta `GIT-PAGE` como subpasta.

Os diretórios que começam por ponto (`.github/`) podem ficar ocultos no gerenciador de arquivos. Confirme que `.github/workflows/core-imobiliario.yml` está no caminho exato. A V9.1 funciona **mesmo sem** o arquivo opcional `.github/workflows/gerar-marketplace.yml`; não ignore os arquivos da pasta `scripts/`.

**Backup completo:** use `MCMV-RS-V9.1-PROJETO-COMPLETO.zip`, que conserva a organização original: `GIT-PAGE/`, `GOOGLE.APPSCRIPT/` e `DOCUMENTACAO-HISTORICA/`. Apenas `GIT-PAGE/` deve ser enviado ao repositório GitHub; os Apps Scripts não devem ser arrastados para a raiz do GitHub Pages.

Depois: **Actions → Core Imobiliario - Sincronizar e Publicar → Run workflow (main)**. A publicação ocorre somente se o job final de Pages concluir. A criação de um feed XML não implica aceitação automática em catálogo/Marketplace da Meta.

## Arquivos modificados

- `.github/workflows/core-imobiliario.yml`: volta à sequência dos quatro motores essenciais; não referencia workflow Meta avulso.
- `scripts/auditar_workflows_v425.py`: exige só os cinco workflows essenciais (Core + 4); valida o opcional se presente.
- `scripts/check_workflows_v423.py`: mesmo contrato, sem bloquear pela ausência do sexto.
- `scripts/stage_pages_v421.py`: gera e valida Meta usando o catálogo recebido nesta execução.
- `scripts/validate_pages_v421.py`: exige Meta somente se houver imóveis elegíveis; protege contra XML obsoleto.
- `scripts/test_integracao_core_v8.py`, `scripts/test_integracao_feeds_v6.py`, `scripts/test_core_v423.py`: testes adaptados ao Core sem dependência do sexto workflow.

**Não modificados:** `scripts/make-feed-merchantcenter.py`, `scripts/merchant_from_catalog.py`, `scripts/gerar_marketplace.py`, `scripts/sinc-data.py`, `app.js`, `index.html`, os Apps Scripts, os outros quatro motores/workflows essenciais, sitemap e geração de subpáginas.

## Testes locais

- 18 testes unitários de integração/Meta: OK
- Teste de reconstrução do Core (`python scripts/test_core_v423.py`): OK
- Auditorias com 6 workflows e simulando ausência do sexto: OK
- Omissão de um dos 5 workflows essenciais: rejeitada corretamente
- `node scripts/test_vitrine_hover_v9.js`: OK
- YAML verificado com PyYAML, sem erros de parse
- `python -m compileall -q scripts`: OK

Não houve deploy no GitHub nem homologação da Meta neste ambiente. Os testes de catálogo da vitrine que dependem de `catalogo.json` real precisam de um fixture na raiz (o ZIP não inclui o catálogo de produção, por segurança).
