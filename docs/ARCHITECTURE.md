# Arquitetura

```
navegador ──► frontend (Vite/nginx) ──► /api ──► Flask (gunicorn, 1 worker / 8 threads)
                                                    │
                                                    ├─► PostgreSQL 17 + PostGIS (volume atlas_pgdata)
                                                    └─► SearXNG (rede interna) ──► duckduckgo/bing/…
ETL (CLI no host ou serviço compose profile=etl) ──► mesmo banco
```

## Camadas de dados

| Schema | Função |
|---|---|
| `meta` | recursos, importações, publicações, reconciliação |
| `staging` | tabelas UNLOGGED por `run_<id>_<kind>`, DROP após publicar |
| `core` | eleição, cargo, município, candidatura, opção de voto, seção, local, geometria |
| `fact` | `vote_munzona`, `turnout_munzona`, `vote_section` (partição por UE), `turnout_section` |
| `agg` | município/UF reconstruídos **só** a partir de munzona |
| `polls` | cadastro oficial de pesquisas |
| `app` | cache HMAC de busca |

Agregados e API de ranking/mapa leem `agg.*`. Seção é navegação e reconciliação, nunca somada aos agregados.

## Rede

Compose cria a rede `backend`. API e ETL resolvem `db` e `searxng`. Portas só em `127.0.0.1`. SearXNG sem publish.

## Por que 1 processo na API

Rate limit e cache de geometria GeoJSON ficam em memória. Vários workers gunicorn quebrariam o limite por IP e o cache.
