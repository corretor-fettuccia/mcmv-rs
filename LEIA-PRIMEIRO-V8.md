# MCMV-RS V8 — GitHub (raiz do repositório)

## Instalar a versão 8

Este ZIP contém o conteúdo que deve ficar **diretamente na raiz** do repositório GitHub `mcmv-rs`, incluindo a pasta oculta `.github/workflows/`. NÃO envie o ZIP fechado como arquivo; extraia-o e preserve os caminhos, inclusive `.github`.

- Faça backup da branch atual antes de substituir arquivos.
- Envie o conteúdo extraído para `main` (não para dentro de outra pasta chamada `mcmv-rs`).
- Confirme que existem os seis arquivos em `.github/workflows/`, especialmente `gerar-marketplace.yml`.
- Em GitHub → Actions → `Core Imobiliario - Sincronizar e Publicar` → Run workflow → `main`.
- Acompanhe os jobs `1/5 sinc-data`, `2/5 make-feed-merchantcenter`, `3/5 gerar-marketplace`, `4/5 make-sitemap`, `5/5 make-subpage`, `5 - Validar e montar site para Pages`, `6 - Publicar o site no GitHub Pages`.
- Depois do deploy, acesse `https://mcmv-rs.com.br/merchant-produtos.xml` e `https://mcmv-rs.com.br/marketplace-produtos.xml`.

**Importante:** não acompanha `catalogo.json` de teste nem XMLs antigos de produção. O Core busca o catálogo da API configurada em `VITRINE_API_URL` e gera os dois feeds em cada publicação. O workflow Meta pode ser executado separadamente, porém o botão avulso gera somente um artefato para download; para disponibilizar na URL pública, execute o Core. A agenda avulsa `03:10 UTC` = `00h10` em Brasília, mas o horário não é garantido pelo agendador do GitHub.

O Merchant permanece no mesmo gerador `scripts/make-feed-merchantcenter.py`, sem alterações. Ambos os feeds são empacotados no mesmo artefato do Pages e publicados juntos; se qualquer gerador falhar, o site anterior permanece ativo, em vez de um deploy parcial.

Documentação detalhada: `MD/LEIA-PRIMEIRO-V8-MARKETPLACE.md`.

Este pacote implementa a **geração e publicação do feed**, não o envio de anúncios classificados orgânicos ao Facebook Marketplace nem uma homologação feita no Commerce Manager da Meta.
