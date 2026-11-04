# MCMV-RS V9 — Vitrine com carrossel por hover

## Instalação (projeto completo)

O arquivo `MCMV-RS-V9-GITHUB-RAIZ.zip` é o pacote destinado à raiz de `corretor-fettuccia/mcmv-rs`.
Extraia-o antes de enviar. Os arquivos `.github/workflows/` são pastas ocultas e devem permanecer no caminho original.
Não envie o ZIP fechado como um único arquivo nem crie uma pasta extra dentro da raiz do repositório.

Após atualizar o GitHub, execute manualmente **Actions → Core Imobiliario - Sincronizar e Publicar → Run workflow (main)**, ou aguarde a execução agendada. O workflow faz deploy no GitHub Pages; alterações em `app.js`/`index.html` por si só não acionam o Core por push, pois sua regra de push monitora `.github/workflows/**`.

## Alteração da V9

Apenas os arquivos `app.js` e `index.html` foram modificados em relação à V8 de origem. O teste `scripts/test_vitrine_hover_v9.js` foi acrescentado.

- O card mostra a imagem principal por padrão.
- Ao passar o mouse sobre o card (hover), inicia-se a segunda foto e, em seguida, o carrossel avança a cada 1,5 segundo, tal como no Imoplace.
- Ao retirar o mouse, a primeira foto retorna; o comportamento também é ativado por foco de teclado.
- No mobile, a primeira imagem permanece estática, pois não há hover de mouse. Com preferência por movimento reduzido, a galeria também fica estática.
- Cada card usa no máximo 5 URLs públicas, deduplicadas, de `items[].image` e `items[].gallery` do catálogo V4. O formato dos dados não muda.
- Cards de foto única não iniciam rotação. Cards sem imagens utilizam a arte ilustrativa existente.
- Filtros reconstroem a vitrine e interrompem temporizadores anteriores; ao renderizar novamente, todos os cards começam pela primeira foto.
- Indicadores de foto e pequenos marcadores são mostrados quando há mais de uma imagem.
- Não baixa, transforma, grava nem publica fotos em Base64; usa as URLs existentes.

## Preservação

Os workflows, scripts Python de sincronização, os dois geradores de feed (`merchant-produtos.xml` e `marketplace-produtos.xml`), o Core, os Apps Scripts e demais arquivos da V8 permanecem sem alterações. O novo efeito é exclusivo da interface da vitrine.

## Testes executados

- Navegador Chromium (Playwright, fixture local interceptada): hover imediato, troca após 1,5 segundo, retorno ao sair, re-render por filtro, fallback, foto única, reduced motion, mobile sem overflow, sem erros JavaScript.
- `node scripts/test_vitrine_hover_v9.js`: teste independente do carrossel.
- Regressões existentes da vitrine: `test_vitrine_catalogo_v420.js`, `test_vitrine_catalogo_v417.js`, `test_vitrine_catalogo_v416.js` com um `catalogo.json` de teste temporário, removido do pacote.
- 17 testes Python de integração da V8 (feeds, Core, validação e geração para Pages) aprovados.

O pacote NÃO contém `catalogo.json` de produção nem feeds pré-gerados. O Core produz esses artefatos com a fonte real ao executar no GitHub.
