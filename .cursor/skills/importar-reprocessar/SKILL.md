---
name: importar-reprocessar
description: Importa ou reprocessa um recorte TSE com staging, validação e publicação transacional.
---

# Importar / reprocessar

## Entrada
- `kind` (`consulta_cand`, `munzona_cand`, `secao`, …) e opcionalmente `--ue`.

## Passos
1. `atlas-etl download --kind … --ue …` (retomável, concorrência ≤ 2).
2. `atlas-etl import <kind> --ue XX` — COPY em chunks → valida → publica numa transação.
3. Falha: recorte anterior permanece; `meta.import_run.status=failed`.
4. Mesmo CRC+tamanho+membro = `skipped_duplicate`. `--force` substitui o recorte.
5. Depois de munzona: `atlas-etl rebuild-aggregates`. Não some seção com munzona.

## Saída
- JSON por recorte (`status`, `rows`) e `atlas-etl coverage -v`.

## Verificação
- Reexecutar o mesmo import deve pular. `atlas-etl reconcile` sem divergência no recorte.
---
