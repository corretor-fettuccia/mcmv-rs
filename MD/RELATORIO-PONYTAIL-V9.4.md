# Relatório Ponytail — MCMV-RS V9.4

## O que este repositório faz
O Core sincroniza o catálogo com a API do Apps Script, gera feeds Google e Meta, sitemap e páginas, e publica no GitHub Pages. Carga: uma execução diária mais manuais, catálogo pequeno.

## Corrigido
1. **O feed Meta nascia por três caminhos** (workflow avulso, passo na montagem, fallback no staging). Agora um só gerador, no motor 02; a montagem só confere.
2. **`marketplaceEnabled` nunca chegava ao catálogo** (`core_lib.py`): uma linha o repassa (ausente = publicado).
3. **A validação do Marketplace comparava o gerador com ele mesmo.** `validate_xml_v94.py` valida o contrato por fora do gerador.
4. **Ninguém verificava o domínio.** Job `verificar_publicacao` (`verify_public_v94.py`).
5. **Dois testes defendiam o comportamento antigo**: removidos; 25 testes novos em `test_feeds_unificados_v94.py`. Mutação: 9 defeitos plantados (sitemap sem imagens, namespace removido, home removida, marketplace não gravado, falha engolida, indicador ignorado, staging sem exigir feeds, artefato sem marketplace, Core baixando artefato antigo), todos pegos.

## Não corrigido (de propósito)
- Testes legados V4.1.x já quebrados na V9.3.
- Catálogo sem imóvel elegível bloqueia o deploy. `shortcut: Meta vazio não é publicado, mudar se for preciso retirar tudo de uma vez.`
- `postal_code`, latitude e longitude: o catálogo não tem, não inventados.

## Veredito
Pronto para instalar. Nenhuma dependência nova. `merchant_from_catalog.py`, `gerar_marketplace.py`, `app.js`, `index.html` e o Apps Script estão byte a byte iguais à V9.3.

## Não verificado
Execução real no GitHub Actions e no domínio; aceitação pela Meta e Google; download das imagens remotas.
