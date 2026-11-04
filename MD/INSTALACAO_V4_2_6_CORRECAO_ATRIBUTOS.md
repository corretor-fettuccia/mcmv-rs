# V4.2.6 — Correção do erro 25 !== 26 no GitHub Actions

## Diagnóstico

O gerador `scripts/core_lib.py` contabilizava as opções de atributos pelo texto literal. A vitrine, em `app.js`, agrupa os atributos ignorando diferenças de maiúsculas e acentos. Por exemplo, `Água quente` e `AGUA QUENTE` são uma única opção visível. Dessa forma, o teste `scripts/test_vitrine_catalogo_v420.js` comparava 25 opções exibidas com 26 textos distintos, interrompendo o job **5 - Validar e montar site para Pages**.

## Correção

- `scripts/core_lib.py`: adota a normalização usada na vitrine e passa a gerar `atributos_disponiveis` e `filtros.atributos` sem duplicatas equivalentes. Mantém as características originais em `items[].attributes` e as URLs/IDs dos imóveis.
- `scripts/test_vitrine_catalogo_v420.js`: compara a contagem normalizada com os filtros exibidos, verifica a coerência da lista pública e contém teste para variações de grafia/acentuação.

Não é necessário alterar os Apps Scripts, a planilha, os quatro motores independentes, o workflow Core ou o layout do portal.

## Instalação pelo navegador do GitHub (sem terminal)

1. Descompacte o ZIP.
2. Acesse https://github.com/corretor-fettuccia/mcmv-rs e selecione a branch `main`.
3. Abra `scripts/core_lib.py` e substitua seu conteúdo pelo arquivo de mesmo caminho do patch. Salve com **Commit changes**.
4. Repita em `scripts/test_vitrine_catalogo_v420.js`.
5. Vá em **Actions → Core Imobiliario - Sincronizar e Publicar → Run workflow**, selecionando `main`.
6. Espere os jobs **5 - Validar e montar site para Pages** e **6 - Publicar o site no GitHub Pages** passarem.

**Não envie o ZIP fechado para dentro do repositório.** Envie os arquivos extraídos, nos caminhos `scripts/`.

## Resultado esperado

No exemplo com 3 imóveis, 26 textos literais e 25 valores normalizados:

- `VALIDADO: catálogo=3 imóveis; páginas=3; sitemap=4 URLs; feed=3; atributos=25.`
- `OK V4.2.6: CTAs internos, filtros e contagens normalizados, grafias equivalentes, catálogo, HTTP 404.`

O número exato pode variar conforme as atualizações da sua planilha. A diferença de grafia não bloqueará mais a publicação. Se aparecer **outro erro**, o novo log indicará qual validação falhou.

## Testes realizados

- Teste integrado local usando 3 imóveis, com 26 textos diferentes e 25 filtros reais: passou.
- Scripts Python e JavaScript com sintaxe válida: passaram.
- Testes existentes do pipeline, geração/atualização das páginas, sitemap e feed: passaram.

Nenhuma alteração foi aplicada diretamente na sua conta GitHub.
