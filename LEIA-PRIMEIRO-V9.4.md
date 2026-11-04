# MCMV-RS V9.4 — feeds Merchant + Marketplace e sitemap de imagens

## Objetivo

**Um único bloco de geração** no segundo job do Core recebe o mesmo `catalogo.json` da sincronização e produz, em conjunto:

- `merchant-produtos.xml` — usa o gerador Google existente (`merchant_from_catalog.build`), sem mudar seu formato;
- `marketplace-produtos.xml` — usa `gerar_marketplace.compile_xml`, sem segunda execução do Core;
- `google-ads-imoveis.csv` — mantém a saída já existente.

O workflow `.github/workflows/make-feed-merchantcenter.yml` envia **os três arquivos no mesmo artefato**, `core-v4-merchant`. A etapa 5 do Core apenas recebe, valida e monta o `_site`. Nenhum feed é gerado dentro da montagem do Pages.

O outro motor, `.github/workflows/make-sitemap.yml`, recebe **o mesmo catálogo** e gera `sitemap.xml`, `robots.txt` e `llms.txt`. O sitemap contém a URL canônica da vitrine e cada URL `/imoveis/{ID}/`, com as fotos válidas e sem repetição em `image:image` / `image:loc`. Não adiciona URLs de páginas em domínios de terceiros como páginas canônicas do portal. Não inventa datas de modificação (`lastmod`).

## Instalação correta

1. Faça backup da branch `main` antes de atualizar.
2. Para o repositório GitHub, utilize o ZIP **`MCMV-RS-V9.4-GITHUB-RAIZ.zip`**. Descompacte. Os diretórios `.github/` e `scripts/` precisam ficar **diretamente na raiz do repositório**, nunca dentro de uma pasta `MCMV-RS-V9.4/`.
3. Envie todas as alterações para `main` e confirme que estes arquivos foram substituídos no GitHub: `.github/workflows/core-imobiliario.yml`, `.github/workflows/make-feed-merchantcenter.yml`, `scripts/make-feed-merchantcenter.py`, `scripts/make-sitemap.py` e `scripts/stage_pages_v421.py`.
4. Em `Actions → Core Imobiliario - Sincronizar e Publicar`, use **Run workflow** em `main`. **Não use Re-run jobs num run antigo**: ele utiliza o commit anterior.
5. No job **`2/4 Gerar feeds Merchant + Marketplace`**, procure `[FEEDS V9.4] Merchant:` e `Marketplace:`. O artefato `core-v4-merchant` deve conter ambos os XMLs.
6. No job **`3/4 make-sitemap`**, confirme `[make-sitemap V9.4] ... fotos`. No job **`5 - Validar e montar site para Pages`**, confira `[FEEDS V9.4] Dois XMLs + sitemap presentes no _site`.
7. Depois de o job `6 - Publicar o site no GitHub Pages` concluir com sucesso, confira `https://mcmv-rs.com.br/merchant-produtos.xml`, `https://mcmv-rs.com.br/marketplace-produtos.xml`, `https://mcmv-rs.com.br/sitemap.xml`.

## Garantias e limites

- Para um snapshot V4 **válido e completo**, ambos os arquivos XML são produzidos e enviados no **mesmo artefato**. Se algum não existir ou não corresponder ao catálogo, a publicação falha explicitamente; o pipeline não afirma sucesso sem ele.
- O Marketplace não descarta os imóveis quando `googleEnabled=false`; são elegibilidades independentes. Se `marketplaceEnabled=false` chegar pela API, a desativação será preservada no catálogo.
- Sem imóveis Meta elegíveis, ainda é gerado XML sintaticamente válido com zero `<listing>`; não se inventa imóvel nem preço. A aceitação de um feed vazio depende da Meta.
- A aceitação/importação do XML no Commerce Manager da Meta **não foi homologada**; geração e publicação técnica não garantem publicidade gratuita no Marketplace.
- Arquivos gerados **não são commits em `main`**. Estão no artefato GitHub Pages e só ficam acessíveis na URL pública após o deploy.
- O sitemap de imagens pode referenciar fotos hospedadas em outros domínios. A indexação dessas imagens depende dos controles e requisitos do Google, inclusive verificação de domínios aplicáveis.

## Testes locais

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/test_core_v423.py
python3 scripts/test_pipeline_v420.py
python3 scripts/test_pipeline_v421.py
python3 scripts/auditar_workflows_v425.py
python3 scripts/check_workflows_v423.py
node scripts/test_vitrine_hover_v9.js
```

Os testes não substituem o deploy no GitHub. A execução local não altera o site em produção.
