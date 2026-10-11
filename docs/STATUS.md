# Status (2026-10-11, após `finish_secao.sh`)

## Concluído e publicado no volume `atlas_pgdata`

| Recorte | Situação |
|---|---|
| TSE–IBGE, vagas, geometria IBGE | publicado |
| `cand` BR + 27 UFs | publicado |
| `munzona_detalhe` / `munzona_cand` / `munzona_partido` BR + 27 UFs | publicado |
| agregados | `result_municipality` 6 216 515 · `result_state` 20 591 |
| `locais` 27 UFs + ZZ | publicado |
| `secao` BR + 27 UFs + ZZ | **29/29** (`secao:SP` 17 043 634 linhas às 20:05 UTC; `secao:ZZ` 0 linhas oficiais) |
| `detalhe_secao` BR + 27 UFs + ZZ | publicado (ZZ oficialmente 0 linhas) |
| `polls:BRASIL` | publicado (3 504 registros) |
| API / SearXNG / frontend (código) | no ar; `GET /api/coverage` → `pending: []` |

Totais da Presidência 1º turno (fonte munzona, conferidos na API e no PDF do TSE):

- Aptos 158 745 502 · comparecimento 125 275 835 · válidos 119 300 788
- nº 22 FLAVIO BOLSONARO 56 104 503 (47,0278%) · nº 13 LULA 53 879 538 (45,1628%) — `DS_SIT_TOT_TURNO` = `2º TURNO`
- Exterior (ZZ) comparecimento 341 766
- `source_generated_at` TSE: 2026-10-11T12:32:05

## Reconciliação (lote 20:15 UTC)

Ok: `validos_opcoes_vs_detalhe`, `votos_digitados_vs_detalhe`, `comparecimento_secao_vs_munzona`, `senador_duas_escolhas`, `relatorio_pdf_presidente`, `municipios_sem_codigo_ibge`.

Ainda divergente (não inventar geometria nem somar os dois grãos):

- `municipios_sem_geometria`: Boa Esperança do Norte (MT, TSE `73709`, IBGE `5101837`) — município no cadastro TSE–IBGE sem polígono na malha IBGE. Entra nos totais, fica fora do mapa.
- `secao_vs_munzona`: 92 recortes de **candidatura** (branco/nulo batem). Presidente: diferença = nulos técnicos do detalhe. Alguns governador/senador têm gap maior (ex. RJ cargo 3). Ranking e dashboard usam munzona, que fecha com o PDF.

Não declarar “seção nacional reconciliada”. Declarar: arquivos `secao:*` publicados; totais oficiais do painel vêm de munzona.

## Fora do escopo agora

- 2º turno: o TSE ainda não publicou os CSVs; o endpoint aceita `turno=2` quando existirem.
- LGPD: responsável/contato só com dado real — não inventar.
- Polimento visual grande da UI: adiado a pedido.

## Como subir de novo (não apague o volume)

```bash
cd /home/joao/Documentos/eleicao2026
./scripts/up_stack.sh
npm --prefix frontend run dev     # http://127.0.0.1:5173/
```

`DATABASE_URL` no container da API: `@db:5432`. `SEARXNG_URL=http://searxng:8080`.
pgAdmin: `127.0.0.1:55432`, user `atlas`, senha `POSTGRES_PASSWORD` do `.env`, database `atlas`.
