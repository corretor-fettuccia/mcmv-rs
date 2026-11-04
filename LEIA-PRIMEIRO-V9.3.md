# MCMV-RS V9.3 — Correção definitiva do feed Meta no Core legado

## Causa observada

A branch `main` consultada em 04/11/2026 executava o Core de quatro motores, com a etapa `5 - Validar e montar site para Pages`. Nesse Core, `scripts/stage_pages_v421.py` copiava os arquivos sem executar o gerador Meta. Por isso, `marketplace-produtos.xml` não existia no artefato do Pages.

## Correção V9.3

- Preserva o workflow e gerador do **Google Merchant**, sem modificações.
- O Core V9.3 chama `scripts/gerar_marketplace.py` dentro da etapa **5 - Validar e montar site para Pages**, depois de receber o `catalogo.json` e o Merchant da mesma execução.
- **Fallback no `scripts/stage_pages_v421.py`**: ele gera ou regenera `marketplace-produtos.xml` com o catálogo da execução, mesmo quando a branch usa o Core legado de 4 motores e não chama a etapa explícita. Não depende de `gerar-marketplace.yml`.
- Se não for possível criar o Meta, o processo falha **antes de substituir `_site`**, com mensagem clara. O feed Merchant não é alterado.
- A validação final exige o Marketplace dentro de `_site` e correspondente ao catálogo. O HTML e o carrossel da V9 são preservados.

## Instalação — importante

Envie o CONTEÚDO do ZIP `GITHUB-RAIZ` ao repositório `corretor-fettuccia/mcmv-rs`, na branch `main` (não a pasta ZIP como arquivo). Preserve a pasta oculta `.github/`. O arquivo `core-imobiliario.yml` deve substituir o anterior. Confira também se `scripts/stage_pages_v421.py` foi atualizado.

Se `.github` não for enviado por engano, **o script novo de staging ainda gera o feed** durante a etapa 5 do Core antigo, desde que o próprio `scripts/stage_pages_v421.py` seja atualizado.

Não substitua o catálogo ativo por um JSON de exemplo; o ZIP de instalação não contém `catalogo.json`.

**Para verificar a instalação:** abra `scripts/stage_pages_v421.py` no GitHub e procure `FEED META GERADO`. Na execução `Actions → Core Imobiliario → Run workflow` procure `V9.3 OK` ou `FEED META GERADO`. No artefato `_site`, os dois arquivos devem existir. Só após publicar, verifique as URLs `/merchant-produtos.xml` e `/marketplace-produtos.xml`.

## Testes locais (sem rede)

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/test_core_v423.py
python3 scripts/test_pipeline_v421.py
node scripts/test_vitrine_hover_v9.js
```

## Nota sobre Meta

XML gerado não significa que a Meta aprovou o feed no Commerce Manager nem que criou anúncios individuais no Marketplace. Esses processos dependem da integração e das regras da plataforma.

## Notas de homologação

A versão foi testada com catálogos de exemplo V4 (um imóvel válido e cenários de erro). Não foi possível executar o mesmo job na conta GitHub do usuário nem confirmar a publicação ao vivo. O feed Meta requer credenciamento/importação na plataforma, caso desejado.
