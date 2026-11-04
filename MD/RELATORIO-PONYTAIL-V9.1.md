# Relatório Ponytail — MCMV-RS V9.1

## O que este repositório faz
O Core sincroniza o catálogo imobiliário com a API pública, prepara o feed Google Merchant, sitemap, páginas individuais e publica o site no GitHub Pages. A mudança auditada é a geração do feed Meta durante a montagem do site. Carga esperada: uma execução agendada do Core por dia, mais acionamentos manuais; leitura de catálogo pequeno.

## Deve corrigir

1. **A auditoria bloqueia a publicação por um sexto workflow inexistente** (`scripts/auditar_workflows_v425.py`, `scripts/check_workflows_v423.py`).
   - **O que acontece:** o pacote inclui `gerar-marketplace.yml`, mas se o diretório oculto `.github` não for enviado, o checkout só tem os workflows anteriores.
   - **Problema:** as auditorias interrompem o job `preparar` antes do Pages e impedem inclusive o feed Merchant já gerado.
   - **Correção:** cinco workflows obrigatórios, sexto opcional. Um essencial ausente ainda interrompe o job.
   - **Se ignorar:** erro `AUSENTE: .../.github/workflows/gerar-marketplace.yml` persiste.

2. **Meta não era construído pelo Core antigo** (`scripts/stage_pages_v421.py`).
   - **O que acontece:** o Core antigo recebe o catálogo e o Merchant, mas não recebe nem gera XML Meta.
   - **Problema:** copiar apenas os arquivos visíveis do ZIP não publica o feed Meta.
   - **Correção:** gerar Meta usando o catálogo fresco na montagem do Pages, com validação e inclusão na mesma publicação.
   - **Se ignorar:** `/marketplace-produtos.xml` segue ausente mesmo se o Merchant funcionar.

## Convém corrigir

3. **Testes assumiam o sexto workflow como obrigatório** (`scripts/test_integracao_feeds_v6.py`, `scripts/test_integracao_core_v8.py`).
   - **O que acontece:** removendo o workflow, um teste anterior validava exatamente a falha que derruba a produção.
   - **Problema:** os testes não detectavam o caso real, Core sem workflow Meta no checkout.
   - **Correção:** teste de ausência do opcional, rejeição de ausência do essencial, criação automática dos dois XMLs e descarte de XML antigo.
   - **Se ignorar:** regressão da dependência poderia retornar no próximo release.

## Veredito
Corrigido e testado localmente; nenhuma dependência nova. O Core produz o Merchant como antes e constrói o Meta na montagem. A ausência do workflow Meta avulso não impede o Pages.

## Não verificado
Execução real do GitHub Actions e aceitação efetiva pela Meta; URLs de imagens remotas não foram baixadas. Aplicação de alterações no GitHub é responsabilidade da instalação do pacote.
