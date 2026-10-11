# Segurança

- Segredos só em `.env` (modo 600), fora do Git. `.env.example` sem valores reais.
- Compose: API/ETL montam `DATABASE_URL` com host `db`, não com o URL do host.
- Engine de leitura: `default_transaction_read_only=on`, `hide_parameters=true`, timeout 20s.
- Escrita só em `app.search_cache`.
- SearXNG: `limiter=false` (não é público), `public_instance=false`, `formats: [html, json]`.
- `safe_url` rejeita não-HTTP(S), userinfo e javascript. Sem fetcher de páginas no caminho atual (sem SSRF).
- CSV de exportação prefixa `' ` em células que começam com `= + - @`.
- Imagens Docker com digest. Sem credenciais na imagem.
- Healthcheck da API: HTTP 503 se o banco cair (não mascara degradado como 200).
