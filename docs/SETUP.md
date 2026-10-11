# Setup

## Máquina

Testado em Linux, 8 vCPU, ~7 GiB RAM, Docker 29, Compose v5, Python 3.14, Node 24. PostgreSQL local/Supabase já ocupam 5432 e 54321–54327 — por isso o banco do Atlas usa **55432**.

Não apague volumes Docker para “consertar” erro. RAM é o limite da carga de SP: o ETL lê em chunks (`ATLAS_CHUNK_ROWS=250000`).

## Primeira subida

```bash
cd /home/joao/Documentos/eleicao2026
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e etl

cp .env.example .env && chmod 600 .env
# edite senhas/segredos (32 bytes hex)

docker compose up -d db searxng
export DATABASE_URL="postgresql+psycopg://atlas:SENHA@127.0.0.1:55432/atlas"
alembic -c migrations/alembic.ini upgrade head   # revisões 0001–0003
```

## Desenvolvimento da API no host

```bash
export DATABASE_URL=...55432/atlas
export SEARXNG_URL=http://127.0.0.1:8070   # NÃO: o SearXNG não tem porta publicada
```

Para falar com o SearXNG a partir do host: `docker compose exec searxng wget -q -O - 'http://127.0.0.1:8080/search?q=TSE&format=json'`.

A API no Compose usa sempre `http://searxng:8080` e `db:5432` (não o DATABASE_URL reescrito para localhost).

```bash
docker compose up -d --build api
curl -sS http://127.0.0.1:8070/api/health
```

## pgAdmin 4 (acessar o banco do Atlas)

O `POSTGRES_USER=atlas` do `.env` **não é** o usuário do PostgreSQL que você instalou no notebook. São dois bancos:

| | PostgreSQL do notebook | Atlas (Docker) |
|---|---|---|
| Porta | `5432` | **`127.0.0.1:55432`** |
| Usuário | o seu (pgAdmin atual) | `atlas` (veja `.env`) |
| Senha | a sua | `POSTGRES_PASSWORD` no `.env` |
| Database | o seu | `atlas` |

Não troque o user do `.env` para o seu nome: o container cria o role `atlas` e a API/ETL usam isso.

No pgAdmin: **Register → Server** →

- Host: `127.0.0.1`
- Port: `55432`
- Username: `atlas`
- Password: a linha `POSTGRES_PASSWORD=` do arquivo `/home/joao/Documentos/eleicao2026/.env`
- Database: `atlas`

O Docker precisa estar no ar (`docker compose up -d db`). Esquemas: `core`, `fact`, `agg`, `meta`, `polls`.

## Frontend em desenvolvimento

```bash
cd frontend
npm ci
npm run dev    # Vite em :5173, proxy /api → :8070
```

## ETL

```bash
export ATLAS_DOWNLOAD_DIR=$PWD/data/downloads
atlas-etl discover
atlas-etl download --kind consulta_vagas
atlas-etl inspect consulta_vagas_2026
atlas-etl import-all          # nacional
atlas-etl resume              # pendências
atlas-etl coverage -v
atlas-etl reconcile
```

Dentro do Compose: `docker compose --profile etl run --rm etl coverage -v`.

## Retomar (Docker caiu / sessão isolada)

Não apague o volume `atlas_pgdata`. Não rode um segundo `import-all`.

```bash
./scripts/up_stack.sh         # db + searxng + api
./scripts/resume_load.sh      # só se ainda houver recorte pendente; não inicia segundo ETL
npm --prefix frontend run dev
```

Carga nacional de 2026-10-11: cand, munzona, agregados, locais, `secao` 29/29, detalhe_secao e 3 504 pesquisas. Não rode `import-all` de novo no mesmo volume.
