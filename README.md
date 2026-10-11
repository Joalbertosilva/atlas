# Atlas Eleitoral 2026

Painel **independente** de resultados das Eleições Gerais de 2026, com mapas, navegação até a seção e busca online integrada. Os dados vêm do [Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/) e das [Malhas do IBGE](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3). **Não é um site oficial da Justiça Eleitoral.**

Orçamento zero: Docker na sua máquina, sem APIs pagas, sem Kafka/K8s/Airflow.

## O que já roda

- API Flask + PostgreSQL/PostGIS (porta `127.0.0.1:8070`)
- SearXNG próprio (só a API fala com ele) — consulta real testada em 2026-10-11
- CLI `atlas-etl` (descobrir, baixar, importar, retomar, reconciliar, cobertura)
- Carga nacional (munzona, agregados, locais, detalhe de seção, 3 504 pesquisas): publicada. Falta `secao` — ver [docs/STATUS.md](docs/STATUS.md)

## Subir para demonstrar

```bash
cp .env.example .env
chmod 600 .env
# gere POSTGRES_PASSWORD, SEARXNG_SECRET e API_CACHE_SECRET:
python3 -c 'import secrets; print(secrets.token_hex(32))'

docker compose up -d db searxng
# migrations (do host, apontando para a porta publicada):
export DATABASE_URL="postgresql+psycopg://atlas:SUA_SENHA@127.0.0.1:55432/atlas"
.venv/bin/alembic -c migrations/alembic.ini upgrade head

# carga (exemplo: referências + Presidência + um estado)
.venv/bin/atlas-etl import municipio_tse_ibge
.venv/bin/atlas-etl import geometry
.venv/bin/atlas-etl import consulta_vagas
.venv/bin/atlas-etl import consulta_cand --ue BR
.venv/bin/atlas-etl import detalhe_munzona --ue BR
.venv/bin/atlas-etl import munzona_cand --ue BR
.venv/bin/atlas-etl rebuild-aggregates

docker compose up -d --build api
# frontend: npm --prefix frontend run dev   (proxy /api → :8070)
# ou, depois do build da imagem: docker compose up -d frontend
```

Carga nacional: `atlas-etl import-all` (horas; SP sozinho tem milhões de linhas). `atlas-etl resume` retoma recortes pendentes.

## Portas (só localhost)

| Serviço | Porta |
|---|---|
| PostgreSQL/PostGIS | `127.0.0.1:55432` |
| API | `127.0.0.1:8070` |
| Frontend | `127.0.0.1:8088` |
| SearXNG | sem porta publicada |

## Documentação

[Arquitetura](docs/ARCHITECTURE.md) · [Fontes](docs/DATA_SOURCES.md) · [ETL](docs/ETL.md) · [SQL](docs/SQL.md) · [API](docs/API.md) · [Setup](docs/SETUP.md) · [Busca](docs/SEARCH.md) · [LGPD](docs/LGPD.md) · [Metodologia](docs/METHODOLOGY.md) · [Cobertura](docs/COVERAGE.md) · [Status](docs/STATUS.md) · [Demo](docs/DEMO.md)

## Testes

```bash
.venv/bin/pytest -m "not live_search"
cd frontend && npm test -- --run && npm run typecheck && npm run build
```
