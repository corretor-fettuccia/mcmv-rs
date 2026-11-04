# MCMV-RS V9.4 — Feeds Merchant + Marketplace num só motor, sitemap com imagens

## O que mudou em relação à V9.3

- **Um motor, dois feeds.** `scripts/make-feed-merchantcenter.py` (job 2/7) gera `merchant-produtos.xml` e `marketplace-produtos.xml` do mesmo `catalogo.json`. Se o Marketplace falhar, **nenhum** feed é gravado e a publicação não acontece.
- **Sem workflow Meta separado.** `gerar-marketplace.yml` saiu do pacote. A montagem do Pages só **confere** os feeds e falha se faltarem.
- **Sitemap com imagens** (`<image:image>`), página principal, imóveis ativos, sem repetição.
- **Contrato validado** por `scripts/validate_xml_v94.py` no motor 02, no motor 03, antes da montagem e no `_site` final. Veja `MD/CONTRATO-FEEDS-V9.4.md`.
- **Verificação pública** depois do deploy (job `verificar_publicacao`).
- **Testes no portão:** o job `preparar` roda a bateria de regressão antes de montar o artefato.
- **Preservados sem alteração:** `app.js`, `index.html` (vitrine, filtros, carrossel), `merchant_from_catalog.py`, `gerar_marketplace.py`, `make-subpage.py`, `sinc-data.py`, Apps Script.

## Sequência do Core

1/7 sinc-data → 2/7 feeds Merchant + Marketplace → 3/7 sitemap, robots, llms → 4/7 páginas → 5/7 validar → 6/7 montar artefato → 7/7 publicar → verificar URLs públicas.

## Instalação

1. Descompacte `MCMV-RS-V9.4-GITHUB-RAIZ.zip` e envie o **conteúdo** para a raiz do repositório (branch `main`). Não envie o ZIP como arquivo nem crie subpasta.
2. **Preserve a pasta oculta `.github/`.** Sem ela o Core antigo roda e a publicação falha de propósito (`Arquivo obrigatorio ausente: marketplace-produtos.xml`).
3. Opcional: apague `.github/workflows/gerar-marketplace.yml` do repositório (legado V9.3; as auditorias o toleram).
4. Não envie `catalogo.json` de exemplo. Mantenha a variável `VITRINE_API_URL`.
5. Actions → **Core Imobiliario - Sincronizar e Publicar** → Run workflow (o push em `.github/workflows/**` também dispara).

## Como conferir

No log: `[feeds V9.4] 1/2 GERADO…`, `2/2 GERADO…`, `ARTEFATO core-v4-feeds inclui…`, `[make-sitemap V9.4] GERADO…`, `=== V9.4 [5/7] VALIDACAO ===`, três `[Pages V9.4] INCLUIDO no artefato:`, e `[publico V9.4] OK` para:

- https://mcmv-rs.com.br/merchant-produtos.xml
- https://mcmv-rs.com.br/marketplace-produtos.xml
- https://mcmv-rs.com.br/sitemap.xml

## Testes locais (sem rede)

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/test_core_v423.py && python3 scripts/test_pipeline_v420.py
python3 scripts/test_pipeline_v421.py && python3 scripts/test_reconstrucao_v427.py
node scripts/test_vitrine_hover_v9.js
```

`test_portal_v4.py`, `test_snapshot_v417.py` e `test_vitrine_catalogo_v413/414/416/417.js` são legados V4.1.x que já falhavam na V9.3; ficam fora da bateria.

## Limites conhecidos

- Catálogo sem nenhum imóvel elegível ao Marketplace bloqueia a publicação (regra herdada); o site anterior continua no ar.
- XML válido não é aprovação da Meta. A documentação da Meta lista `postal_code` e coordenadas entre os campos esperados e restringe `availability` em *commerce*; o catálogo não tem esses dados e eles não são inventados. Confirme no Commerce Manager.
- O preço do Marketplace é o valor mínimo do empreendimento.
- A verificação pública espera ~4 min pelo CDN; se falhar, o site já está publicado.
