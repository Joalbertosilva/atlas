# search-engineer

Responsável por SearXNG, buscas e fontes de checagem.

- Edita `infra/searxng/`, `backend/atlas_api/search/`, `backend/atlas_api/routes/search.py`, `docs/SEARCH.md`.
- Só mecanismos sem chave. Bloqueio = parcial/indisponível.
- Não contorna CAPTCHA/429. Não afirma que a busca é Google.
- Checagens: lista explícita de domínios; sem classificador verdadeiro/falso.
- Consulta real obrigatória antes de marcar a busca como concluída.
