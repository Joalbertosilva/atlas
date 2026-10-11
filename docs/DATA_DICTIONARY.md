# Dicionário (campos que persistimos)

Códigos são **texto**. Quantidades são inteiro. `#NULO`/`#NE`/vazio → NULL (`staging.nn`).

## Chaves

| Entidade | Chave |
|---|---|
| Município | `cd_municipio_tse` (5 dígitos). IBGE à parte (`cd_municipio_ibge`, 7 dígitos). |
| Seção | `(cd_municipio_tse, nr_zona, nr_secao)` |
| Local | `(cd_municipio_tse, nr_zona, nr_local_votacao)` — nome não identifica |
| Candidatura | `(cd_eleicao, sq_candidato)` — `nr_candidato` não é único no país |
| Disputa | `(cd_eleicao, nr_turno, cd_cargo, sg_ue)` — `sg_ue=BR` Presidente, UF nos demais |
| Opção de voto | `(cd_eleicao, cd_cargo, sg_ue, kind, nr_votavel, sq_candidato)` |
| Fato munzona | disputa + município + zona + opção + voto em trânsito |
| Fato seção | partição `sg_ue` + seção + disputa + opção |

## Cargos persistidos

`1` Presidente, `3` Governador, `5` Senador, `6` Dep. Federal, `7` Dep. Estadual, `8` Dep. Distrital.

Cargos 2, 4, 9, 10 (vice/suplente) são ignorados no cadastro: não recebem voto próprio nos arquivos de resultado.

## Categorias de voto (`core.vote_option.kind`)

- `candidatura` — `SQ_CANDIDATO` positivo
- `legenda` — número de partido; `SQ` vazio ou negativo
- `branco` — `NR_VOTAVEL=95`
- `nulo` — `NR_VOTAVEL=96` (digitação nula; nulo técnico fica no detalhe, não vira opção)

`qt_votos` = digitados. `qt_votos_validos` = parcela válida (`NM_TIPO_DESTINACAO_VOTOS` / colunas `*_VALIDOS`). Anulado sub judice entra em `qt_votos` e não em `qt_votos_validos`.

## Comparecimento (2026)

Observado no arquivo: `QT_APTOS = QT_COMPARECIMENTO + QT_ABSTENCOES + QT_ELEITORES_SECOES_NAO_INSTALADAS` (seções do exterior não instaladas, etc.). Constraint em `0003_turnout_identity`.

Aptos/comparecimento **repetem em cada cargo**. Agregar só dentro de um `contest_id`.

## Senador

`consulta_vagas`: 2 vagas por UF. `QT_VOTOS` do detalhe ≈ 2 × comparecimento.

## Vínculo seção–local

Comparado `NR_LOCAL_VOTACAO` do cadastro (`eleitorado_local_votacao`, 1º turno) com o do arquivo de votos. Sem casamento por nome.

`link_status`: `confirmado` | `somente_cadastro` | `somente_resultado` | `divergente` | `sem_vinculo`.

Coordenadas: só `coord_status=valida` (faixa Brasil ou ZZ; descarta `-1,-1` e `0,0`). Sem geocodificação.

## Não importado (minimização)

CPF, e-mail, título, nascimento, gênero, raça, instrução, estado civil, ocupação, telefone do local, nome do estatístico da pesquisa (`NM_ESTATISTICO_RESP`).
