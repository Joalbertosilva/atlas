# SQL e métricas

Todas as consultas da API estão em `backend/atlas_api/routes/*.py` com bind params. Abaixo, o significado — não um endpoint de SQL.

## Denominadores

| Métrica | Fórmula | Fonte |
|---|---|---|
| `% comparecimento` | comparecimento / aptos | `agg.turnout_*` |
| `% abstenção` | abstenções / aptos | idem |
| `% válidos` (majoritário) | votos válidos da opção / `qt_total_votos_validos` | detalhe |
| `% válidos` (proporcional) | idem (válidos = nominais válidos + legenda válidos) | detalhe |
| `% nominais` | votos válidos da candidatura / `qt_votos_nominais_validos` | só cargos 6/7/8 |
| margem | (1º − 2º) / válidos do município | janela `rank()` |

Branco e nulo **não** entram no denominador de `% válidos`. Anulado sub judice não entra em `qt_votos_validos`.

Nominais convertidos à legenda (`QT_VOTOS_NOM_CONVR_LEG_VALIDOS`) estão no detalhe e na reconciliação de válidos; não viram linha de candidatura.

## Ranking

`rank()` só sobre `kind=candidatura`, ordenado por `qt_votos_validos`. `DS_SIT_TOT_TURNO` é atributo, não resultado do rank.

## Líder municipal e empate

`rank()` por votos válidos; `row_number()` desempata por número só para escolher o rótulo do 1º. `tie=true` quando mais de uma candidatura compartilha o máximo.

## Senador

`choices_per_voter=2` quando `core.seat.qt_vaga=2`. Não use `qt_votos` como número de pessoas.

## Exterior

`sg_uf='ZZ'` em `agg.turnout_state` / `result_state` da disputa `sg_ue=BR`. O summary nacional soma todas as UFs (inclui ZZ) e ainda devolve `exterior` à parte.

## Seção

`fact.vote_section` não tem destinação (válido vs anulado). A UI avisa. Totalização oficial = munzona.

## EXPLAIN

Medido no host em 2026-10-11 (não é SLA):

- Import AC seção (~242 mil linhas): nested loop desligado → ~2 s de INSERT (com nestloop o planner estimava 1 linha).
- Ranking nacional Presidente após agregados: agregação em `agg.result_state` (dezenas de linhas), não em `fact.vote_munzona`.
