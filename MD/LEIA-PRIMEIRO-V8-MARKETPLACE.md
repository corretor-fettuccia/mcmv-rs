# MCMV-RS V8 — Integração do feed Meta dentro do Core

## Alteração principal

O Core executa **cinco motores** sequenciais em um único run:

1. `sinc-data.yml` — consulta Apps Script (`VITRINE_API_URL`), valida e exporta `catalogo.json` (`core-v4-catalogo`).
2. `make-feed-merchantcenter.yml` — gera `merchant-produtos.xml` e `google-ads-imoveis.csv` (`core-v4-merchant`). **Não alterado.**
3. `gerar-marketplace.yml` — em modo `workflow_call`, baixa o **mesmo** `core-v4-catalogo`, executa `gerar_marketplace.py --source catalogo.json` e envia `marketplace-produtos.xml` + `marketplace-relatorio.json` (`core-v4-marketplace`).
4. `make-sitemap.yml` — gera `sitemap.xml`, `robots.txt`, `llms.txt` (`core-v4-sitemap`).
5. `make-subpage.yml` — gera `imoveis/{id}/index.html` (`core-v4-subpages`).

O job `preparar` recebe todos os artefatos, valida ambos os XMLs, monta `_site/` e o job `publicar` faz **um único deploy** para GitHub Pages.

## Instalação segura

- Use **MCMV-RS-V8-GITHUB-RAIZ.zip** para atualizar o repositório GitHub. Extraia, entre no conteúdo e preserve `.github/` e `scripts/` na raiz do repositório; não envie apenas o ZIP.
- O pacote não contém `catalogo.json` vazio nem XMLs antigos de produção. **Não apague o arquivo público em operação por causa disso:** o GitHub Actions monta o site com os artefatos novos em cada execução.
- Não é necessário editar `VITRINE_API_URL` se já está funcionando. Não exige novos segredos ou dependências.
- GitHub → Actions → **Core Imobiliario - Sincronizar e Publicar** → **Run workflow** (`main`).
- Confirme os jobs `1/5` a `5/5`, `5 - Validar e montar site para Pages` e `6 - Publicar o site no GitHub Pages`.
- Confira `https://mcmv-rs.com.br/merchant-produtos.xml` e `https://mcmv-rs.com.br/marketplace-produtos.xml` depois do deploy.

## Workflow Meta avulso / agendamento

O `gerar-marketplace.yml` ainda permite execução manual e agendamento **00h10 (UTC 03:10)**. Essas execuções **somente geram o artefato de teste** do feed no GitHub Actions; **não escrevem na branch nem publicam no domínio**. O Core mantém seu horário original e publica ambos os feeds juntos a partir da mesma sincronização.

## Falhas e preservação dos feeds

O Core publica de forma atômica. Se o Marketplace falhar, **o Core não fará um deploy parcial**; os feeds públicos anteriores permanecem ativos. O motor Google original não foi modificado. Se nenhum imóvel for elegível para a Meta, a execução retorna erro explícito e preserva o site anterior.

O conteúdo XML usa URLs HTTPS das fotografias existentes, sem Base64. Anúncios representam empreendimentos com preço mínimo cadastrado; não afirmam disponibilidade de uma unidade individual. A aceitação do feed pelo Commerce Manager e a possibilidade de anúncios orgânicos no Marketplace dependem da Meta e não são verificáveis apenas por testes locais.

## Testes locais, sem rede

`python3 -m unittest discover -s scripts -p 'test_gerar_marketplace.py' -v`

`python3 -m unittest discover -s scripts -p 'test_integracao_*.py' -v`

`python3 scripts/auditar_workflows_v425.py`

`python3 scripts/check_workflows_v423.py`
