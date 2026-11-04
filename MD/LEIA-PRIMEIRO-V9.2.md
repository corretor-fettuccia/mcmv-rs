# MCMV-RS V9.2 — Feed Merchant + Marketplace no mesmo Core

## Objetivo
Uma única execução do **Core Imobiliário - Sincronizar e Publicar** deve gerar e publicar obrigatoriamente:

- `merchant-produtos.xml` (Google) — motor e workflow originais preservados.
- `marketplace-produtos.xml` (Meta) — gerado no job **3/5 Gerar XML Marketplace (Meta)**.

A V9.2 mantém a vitrine V9 com carrossel por hover e o restante do projeto V9.1.

## Correção da causa
Na V9.1, o Marketplace era gerado na etapa final de montagem do Pages e uma exceção
`Nenhum item válido` podia se transformar em simples aviso, permitindo a publicação
sem o XML. Na V9.2, ele vira uma etapa própria, recebe o `catalogo.json` do **mesmo run**,
gera um XML validado e salva `core-v4-marketplace` como artefato de Actions.
A montagem final baixa esse artefato, exige os DOIS XMLs e recusa publicar se algum estiver ausente.

## Sequência da publicação

1. `sinc_data` — sincroniza `catalogo.json`, publica artefato `core-v4-catalogo`.
2. `merchant` — roda o processo Google atual e publica `core-v4-merchant`.
3. `marketplace` — lê `core-v4-catalogo`, executa `scripts/gerar_marketplace.py`, valida e publica `core-v4-marketplace`.
4. `sitemap` — processo original.
5. `subpage` — processo original.
6. `preparar` — baixa ambos os XMLs e outros artefatos, valida o catálogo e copia ambos para `_site/`.
7. `publicar` — publica `_site/` no GitHub Pages.

O workflow avulso `.github/workflows/gerar-marketplace.yml` é opcional e **não participa da sequência**.
Mesmo que esse workflow avulso não exista, o Core gera o feed Meta.

## Instalação sem alterar a API/planilha

1. Baixe `MCMV-RS-V9.2-GITHUB-RAIZ.zip` e **descompacte**.
2. Envie o **conteúdo** do ZIP para a raiz do repositório `corretor-fettuccia/mcmv-rs`, mantendo exatamente as pastas `scripts/` e `.github/workflows/` (a pasta `.github` é oculta em alguns gerenciadores).
3. Substitua os arquivos que o GitHub indicar como atualizados. **Não envie o ZIP como arquivo único** e não crie uma subpasta `MCMV-RS-V9.2` dentro do repositório.
4. Confira na branch `main` que `.github/workflows/core-imobiliario.yml` contém o job `marketplace:` e que `scripts/gerar_marketplace.py` está presente.
5. Em Actions, execute **Core Imobiliario - Sincronizar e Publicar → Run workflow** na branch `main`.
6. No histórico da execução, verifique o job **3/5 Gerar XML Marketplace (Meta)**, com `MARKETPLACE_OK` e o artefato **core-v4-marketplace**.
7. Confirme a etapa **6 - Validar e montar site para Pages**, que deve informar `Dois feeds conferidos`.
8. Somente depois de o job **7 - Publicar o site no GitHub Pages** concluir, confira:
    - https://mcmv-rs.com.br/merchant-produtos.xml
    - https://mcmv-rs.com.br/marketplace-produtos.xml

**Importante:** gerar o XML para a Meta não é o mesmo que a Meta aceitar o feed nem que publicar classificados gratuitos automaticamente no Marketplace. O uso comercial depende do caminho aceito pelo Commerce Manager.

## Segurança e rastreabilidade

- O gerador Google, o Apps Script e o catálogo da planilha permanecem inalterados.
- Não há dependências Python adicionais.
- Feed Meta inválido/sem imóveis elegíveis **falha com mensagem explícita** e impede novo deploy incompleto; a versão anterior já publicada no Pages não é sobrescrita.
- Não há geração silenciosa de XML na montagem do Pages nem reaproveitamento de XML antigo.
- O resumo do Actions mostra separadamente Google e Meta e a contagem de anúncios Meta.
- Para reutilizar em outro portal que implemente o contrato JSON V4, ajuste `portal-config.json` e as URLs do catálogo conforme o projeto; a aceitação pelo Commerce Manager deve ser verificada por portal.

## Testes realizados localmente

- `python -m unittest discover -s scripts -p 'test_*.py' -v`
- `python scripts/test_pipeline_v421.py`
- `node scripts/test_vitrine_hover_v9.js`
- `python scripts/auditar_workflows_v425.py`
- `python scripts/check_workflows_v423.py`
- YAML validado como mapeamento e sequência de jobs, XML verificado com parser.

Não foi possível executar GitHub Actions ou fazer deploy remotamente daqui. O deploy precisa ser acionado na sua conta GitHub após o upload.
