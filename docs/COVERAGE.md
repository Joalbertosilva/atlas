# Cobertura

**Objetivo:** todos os municípios, cargos e seções dos arquivos oficiais de 2026.

**Carregado agora:** veja `atlas-etl coverage -v` e `GET /api/coverage`. Este arquivo descreve regras, não um número estático.

## Regras de anúncio

- “Nacional” no dashboard da Presidência = disputa `sg_ue=BR` com munzona BR publicado + agregados reconstruídos.
- UF “completa” para cargos estaduais = `munzona_cand`, `munzona_detalhe` e `munzona_partido` daquela UF.
- Seções: só afirmar depois de `secao:<UE>` publicado e `secao_vs_munzona` ok.
- Locais: só `link_status=confirmado` conta como local identificado. O restante aparece como “Local não identificado na base”.
- Município sem código IBGE: entra em totais, não no mapa.
- `votacao_secao_2026_ZZ.zip` sem linhas: exterior da Presidência vem de `secao:BR` / munzona BR (`SG_UF=ZZ`).

## Pendências típicas durante a carga

SP e MG são os recortes mais lentos (milhões de linhas nominais). `import-all` e `resume` são a via oficial — não rode dois ETLs no mesmo banco.
