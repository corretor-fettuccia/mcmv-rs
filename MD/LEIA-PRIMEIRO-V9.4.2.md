# MCMV-RS V9.4.2 — Core não é barrado por testes de pacotes anteriores

## Erro corrigido

No Actions, o passo "Testes de regressao" rodou **54 testes** (a V9.4 tem 45) e 7 falharam. Os extras eram arquivos de teste de pacotes anteriores que ficaram no repositório (subir um ZIP por cima **não apaga** arquivos): `scripts/test_marketplace_core_v92.py`, `scripts/test_marketplace_fallback_v93.py` e `scripts/test_motores_v94.py`. Eles validam comportamento antigo (por exemplo, o artefato `core-v4-merchant`) e falham por definição. O fallback do Marketplace funcionou normalmente no log; só os testes velhos reprovaram.

## Correção

- O Core passa a rodar **só os testes da V9.4, por nome** (`test_feeds_unificados_v94`, `test_integracao_core_v8`, `test_integracao_feeds_v6`, `test_gerar_marketplace`), em vez de `unittest discover`, que roda tudo o que encontrar na pasta.
- Novo `scripts/auditar_obsoletos_v942.py`: lista, como aviso (não falha), os arquivos obsoletos que ainda estiverem no repositório.
- Teste novo reproduz o seu repositório: coloca um teste velho e falhando em `scripts/`, confirma que o comando do Core passa e que o `discover` antigo falharia.

## Limpeza recomendada (opcional, o Core agora as ignora)

Apague do repositório, se existirem:

- `scripts/test_marketplace_core_v92.py`
- `scripts/test_marketplace_fallback_v93.py`
- `scripts/test_motores_v94.py`
- `.github/workflows/gerar-marketplace.yml`

## Testes locais

```bash
cd scripts
python3 -m unittest test_feeds_unificados_v94 test_integracao_core_v8 test_integracao_feeds_v6 test_gerar_marketplace
```

Não use `unittest discover` em um repositório que recebeu pacotes antigos por cima. O restante (instalação, sequência do Core, contrato) segue o `LEIA-PRIMEIRO-V9.4.md` e o `MD/CONTRATO-FEEDS-V9.4.md`.
