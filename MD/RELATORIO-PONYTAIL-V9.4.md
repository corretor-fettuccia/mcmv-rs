# Auditoria Ponytail V9.4 — fluxos de publicação

**Escopo:** entrada de catálogo (API Google Apps Script V4), normalização, saída dos dois XMLs, sitemap de imagens, artefatos de workflow e publicação GitHub Pages. Volume presumido: dezenas a centenas de imóveis, execução agendada de um único Core.

## Falhas corrigidas

1. **Dois lugares gerando o Marketplace:** o feed não era produzido no job do Merchant, mas apenas depois, no job Pages. Isso permitia falhas por falta de artefato e obscurecia o ponto de erro. Agora os dois XMLs saem de `scripts/make-feed-merchantcenter.py` e entram em `core-v4-merchant`.
2. **Mapa sem imagens:** `scripts/make-sitemap.py` gerava apenas `<loc>` das páginas. Agora adiciona fotos em `image:image/image:loc` por página, com URLs HTTPS válidas e sem duplicatas, e mantém `robots.txt` coerente com o domínio.
3. **Desativação Meta descartada:** `core_lib.convert_record` não preservava `marketplaceEnabled`, tornando inócua uma eventual desativação na API. Agora o campo é preservado e é independente de `googleEnabled`.
4. **Nenhum item Meta gerava falha:** se não houvesse elegíveis, o Marketplace falhava após o Merchant ter sido gerado. Agora o feed vazio representa fielmente o catálogo, sem inventar ofertas.
5. **Resumo do Core incorreto:** exibia versão antiga e marcava feed Meta vazio como arquivo ausente. Atualizado.

## Auditoria de regressão

- O gerador de conteúdo XML Google em `merchant_from_catalog.py` não foi modificado.
- O carrossel V9 `app.js` e `index.html` não foram modificados.
- Scripts `sinc-data.py`, `make-subpage.py` e seus workflows foram preservados.
- Os testes agora verificam o mesmo artefato com os dois XMLs, a montagem sem regeneração silenciosa, a rejeição de XML Meta desatualizado, a presença de URLs e imagens no sitemap, e a exclusão de URLs de imóveis inativos.

## Limites desta auditoria

Não houve execução na conta GitHub nem importação autenticada no Commerce Manager. O XML foi validado sintaticamente em testes locais. Não se afirmou homologação de publicação automática na Meta.
