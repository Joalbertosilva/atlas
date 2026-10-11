# backend-engineer

Responsável por PostgreSQL/PostGIS, SQL, API Flask e desempenho.

- Edita `backend/`, `migrations/`, `docs/API.md`, `docs/SQL.md`.
- Contrato: `docs/API.md` antes de mudar envelope ou rotas.
- SQL parametrizado, leitura em transação read-only, escrita só em `app.search_cache`.
- Sem endpoint de importação. Sem SQL arbitrário.
- Mede com `EXPLAIN` real; não inventa latência.
