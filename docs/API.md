# Contrato da API — Atlas Eleitoral 2026

Base: `http://127.0.0.1:8070/api` (Compose) ou via proxy do frontend em `/api`.
OpenAPI gerado pelo código: `GET /api/openapi.json`; UI: `GET /api/docs`.

Somente leitura. Não existe endpoint de importação, administração ou SQL arbitrário:
importações são feitas pela CLI (`docs/ETL.md`).

## Convenções

- JSON UTF-8. Números de votos são inteiros; percentuais são `number` (0–100) com
  denominador explícito em `meta.denominators` ou no próprio campo.
- Códigos (município TSE, IBGE, zona, seção, número de candidatura) são **strings**.
- Datas ISO 8601. `source_generated_at` = data/hora de geração declarada no arquivo do TSE;
  `imported_at` = data/hora da publicação local.
- Paginação: `page` (≥1, padrão 1) e `page_size` (1–200, padrão 50).

### Envelope de sucesso

```json
{
  "data": [],
  "meta": {
    "scope": {"cd_eleicao": "6257", "nr_turno": 1, "cd_cargo": "1", "sg_uf": null, "cd_municipio": null},
    "source": {"source_generated_at": "2026-10-11T12:32:05", "imported_at": "2026-10-11T19:00:00Z",
               "resources": ["votacao_candidato_munzona_2026_BR"]},
    "coverage": {"status": "completo|parcial|indisponivel", "published_scopes": 1, "expected_scopes": 1, "notes": []},
    "pagination": {"page": 1, "page_size": 50, "total": 12},
    "denominators": {"pct_validos": "qt_total_votos_validos"}
  }
}
```

### Envelope de erro

```json
{"error": {"code": "invalid_parameter", "message": "texto em pt-BR", "details": {}}}
```

Códigos: `invalid_parameter` (400/422), `not_found` (404), `rate_limited` (429),
`upstream_unavailable` (503), `internal_error` (500).

## Parâmetros de recorte comuns

| Parâmetro | Tipo | Observação |
|---|---|---|
| `cargo` | string | `1` Presidente, `3` Governador, `5` Senador, `6` Dep. Federal, `7` Dep. Estadual, `8` Dep. Distrital |
| `turno` | int | `1` (2º turno só quando publicado pelo TSE) |
| `uf` | string | sigla; `ZZ` = exterior (somente Presidente) |
| `municipio` | string | código TSE de 5 dígitos |

A eleição é derivada do cargo (`6257` federal para cargo 1, `6259` estadual para os demais).
Para cargos estaduais `uf` é obrigatório no ranking (não existe disputa nacional de governador).

## Rotas

### `GET /api/health`
`{"status":"ok|degradado","database":"ok|erro","searxng":"ok|erro"}`

### `GET /api/coverage`
`data`: `{ "summary": {...}, "scopes": [{"kind","sg_uf","status","rows","source_generated_at","imported_at","reconciliation_ok"}], "reconciliation": [...], "pending": [texto] }`

### `GET /api/elections`
`data`: `[{"cd_eleicao","ds_eleicao","dt_eleicao","tp_abrangencia","turnos":[1]}]`

### `GET /api/offices`
`data`: `[{"cd_cargo","ds_cargo","system":"majoritario|proporcional","scope":"nacional|estadual","cd_eleicao","turnos":[1],"seats":{"AC":2,...}}]`

### `GET /api/states`
`data`: `[{"sg_uf","nm_uf","cd_uf_ibge","is_exterior"}]`

### `GET /api/municipalities?uf=&q=&page=&page_size=`
`data`: `[{"cd_municipio_tse","cd_municipio_ibge","nm_municipio","sg_uf","is_exterior"}]`
`q` busca por nome sem acento (mín. 2 caracteres).

### `GET /api/candidacies?cargo=&uf=&q=&page=`
`data`: `[{"candidacy_id","sq_candidato","nr_candidato","nm_urna_candidato","nm_candidato","sg_partido","nm_partido","sg_federacao","nm_coligacao","cd_cargo","ds_cargo","sg_ue","ds_situacao_candidatura","rounds":[{"nr_turno","ds_sit_tot_turno","nm_tipo_destinacao_votos"}]}]`

### `GET /api/results/summary?cargo=&turno=&uf=&municipio=`
Totais do recorte (fonte: `detalhe_votacao_munzona`).
`data`: `{"qt_aptos","qt_comparecimento","qt_abstencoes","qt_votos","qt_total_votos_validos","qt_votos_nominais_validos","qt_total_votos_leg_validos","qt_votos_brancos","qt_total_votos_nulos","qt_total_votos_anul_subjud","qt_total_votos_anulados","qt_total_secoes","pct_comparecimento","pct_abstencao","choices_per_voter","exterior": {...mesmos campos, apenas Presidente/nacional} | null, "dt_ultima_totalizacao"}`
- `pct_comparecimento = qt_comparecimento / qt_aptos`.
- Senador: `qt_votos` = 2 × comparecimento (duas escolhas); `choices_per_voter = 2`.

### `GET /api/results/ranking?cargo=&turno=&uf=&municipio=&kind=&page=&page_size=&format=json|csv`
`kind`: `candidatura` (padrão) | `todas` (inclui legenda, branco, nulo).
`data`: `[{"rank","option_id","kind","nr_votavel","label","candidacy_id","nm_candidato","sg_partido","sg_federacao","qt_votos","qt_votos_validos","pct_validos","pct_nominais","ds_sit_tot_turno","nm_tipo_destinacao_votos","color"}]`
- `pct_validos = qt_votos_validos / qt_total_votos_validos` (válidos incluem legenda nos proporcionais).
- `pct_nominais = qt_votos_validos / qt_votos_nominais_validos` (somente proporcionais; `null` nos majoritários).
- `ds_sit_tot_turno` vem do arquivo oficial; o ranking **não** define eleitos.
- `color`: cor estável por candidatura dentro da disputa (hex).

### `GET /api/results/municipalities?cargo=&turno=&uf=&mode=leader|candidate&option_id=&format=json|csv`
Uma linha por município do recorte (sem geometria).
- `mode=leader`: `{"cd_municipio_tse","cd_municipio_ibge","nm_municipio","sg_uf","is_exterior","leader": {"option_id","label","sg_partido","color","qt_votos_validos","pct_validos"} | null,"second": {...} | null,"tie": bool,"tied_option_ids": [],"margin_votes","margin_pp","qt_total_votos_validos"}`
- `mode=candidate` (requer `option_id`): `{"cd_municipio_tse","cd_municipio_ibge","nm_municipio","sg_uf","is_exterior","qt_votos_validos","pct_validos","qt_total_votos_validos"}`
- `meta.legend`: lista de `{option_id,label,color,municipios}` (modo líder) ou faixas `{min,max}` (modo candidato).
- Sem dados → `leader: null`; empate → `tie: true`, `leader` = primeiro por número, `tied_option_ids` preenchido.

### `GET /api/results/compare?cargo=&turno=&uf=&option_ids=1,2,3`
Até 3 opções **da mesma disputa**. `data`: `{"options":[...ranking rows],"municipalities":[{"cd_municipio_tse","nm_municipio","values":{"<option_id>":{"qt_votos_validos","pct_validos"}}}]}`

### `GET /api/municipalities/{cd_municipio_tse}/zones?cargo=&turno=`
`data`: `[{"nr_zona","qt_aptos","qt_comparecimento","qt_total_votos_validos","qt_votos_brancos","qt_total_votos_nulos","leader":{...}|null,"sections_loaded":int}]`

### `GET /api/municipalities/{cd_municipio_tse}/polling-places?zona=&q=&page=`
`data`: `[{"polling_place_id","nr_zona","nr_local_votacao","nm_local_votacao","ds_tipo_local","ds_endereco","nm_bairro","latitude","longitude","coord_status","qt_secoes","qt_eleitor"}]`
Coordenadas somente quando `coord_status = "valida"`.

### `GET /api/sections?municipio=&zona=&local=&page=`
`municipio` obrigatório. `data`: `[{"section_id","nr_zona","nr_secao","polling_place_id","nm_local_votacao","link_status","ds_tipo_secao_agregada","nr_secao_principal","qt_eleitor_secao"}]`

### `GET /api/sections/{section_id}/results?cargo=&turno=`
`data`: `{"section": {...}, "turnout": {"qt_aptos","qt_comparecimento","qt_abstencoes","qt_votos_nominais","qt_votos_brancos","qt_votos_nulos","qt_votos_legenda","st_secao_instalada","st_secao_anulada","ds_origem_voto"} | null, "results": [{"option_id","kind","nr_votavel","label","sg_partido","qt_votos","color"}]}`
Na seção, `qt_votos` é o total digitado para a opção (o arquivo de seção não distingue válidos de anulados sub judice); `meta.notes` explica.

### `GET /api/map/geometry?level=municipio|uf&uf=`
GeoJSON `FeatureCollection` (sem envelope). `properties`: `{"cd_municipio_ibge","cd_municipio_tse","nm_municipio","sg_uf"}` ou `{"cd_uf_ibge","sg_uf","nm_uf"}`.
Geometrias da API de Malhas IBGE v3 (qualidade mínima). Cache HTTP `max-age=86400`.

### Busca

Todas aceitam `POST` com JSON (usado pelo frontend para não expor a consulta na URL da aplicação)
e `GET` com query string. Corpo/parâmetros: `q` (2–200 caracteres), `page` (1–5),
`uf`, `municipio`, `candidato` (contexto opcional adicionado à consulta).

#### `/api/search/web` e `/api/search/news`
```json
{"data": [{"title","url","domain","snippet","engines":["bing"],"published_at": "ISO|null"}],
 "meta": {"query_sent": "consulta efetivamente enviada", "category": "general|news",
          "providers": [{"engine":"bing","status":"ok|indisponivel","reason":"texto|null","results":7}],
          "cache": {"hit": false, "fetched_at": "ISO", "ttl_seconds": 600},
          "status": "ok|parcial|indisponivel"}}
```

#### `/api/search/polls`
Busca local em `polls.registered_poll`. Filtros extras: `uf`, `cargo` (texto), `empresa`, `de`, `ate`.
`data`: `[{"nr_protocolo_registro","sg_uf","nm_ue","nm_empresa","nm_empresa_fantasia","ds_cargo","dt_registro","dt_inicio_pesquisa","dt_fim_pesquisa","dt_divulgacao","qt_entrevistado","vr_pesquisa","pesqele_url","status":"registro_oficial_encontrado"}]`
Nenhum percentual de intenção de voto é retornado (o cadastro não contém).

#### `/api/search/fact-checks`
`data`: `[{"title","url","domain","publisher","snippet","published_at","status":"possivel_checagem_relacionada|checagem_publicada_identificada","rating":null}]`
`meta.status`: `ok | sem_correspondencia_suficiente | fonte_temporariamente_indisponivel`.
Somente domínios da lista `meta.allowed_publishers`. Sem classificação automática de verdadeiro/falso.

#### `GET /api/search/status`
`data`: `{"searxng":"ok|indisponivel","version","engines":[{"name","category","status","last_error"}],"cache_entries","rate_limit_per_minute"}`

Rate limit por IP (em memória, sem persistir IP): `SEARCH_RATE_LIMIT_PER_MINUTE` (padrão 20) → 429.
