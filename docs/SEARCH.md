# Busca online

Instância **própria** SearXNG no Compose. Imagem fixada:

`docker.io/searxng/searxng:2026.10.11-ad46ebd7d@sha256:ddd642cae6eac75412938fd846ddbf440a2df029cfeae8a562b8b205f4e35e25`

JSON habilitado em `infra/searxng/settings.yml`. `secret_key` vem de `SEARXNG_SECRET` (`.env`). Sem porta publicada: só `api` acessa `http://searxng:8080/search`.

## Teste real (2026-10-11)

Consulta `eleições 2026 TSE`, `language=pt-BR`, `format=json`:

| Mecanismo | Resultado |
|---|---|
| duckduckgo | 10 resultados (TSE) |
| bing | 6 resultados |
| mojeek | 10; depois *access denied* em outra chamada |
| wikipedia | 0 (sem erro) |
| google | *access denied* — removido |
| startpage | CAPTCHA — removido |
| brave / brave.news | 429 — removidos |
| google news | *access denied* — removido |
| duckduckgo news | 30 resultados com data |
| bing news | 10 resultados |
| wikinews | 5 resultados |

Habilitados agora: duckduckgo, bing, mojeek, wikipedia, duckduckgo news, wikinews. `bing news` foi desligado (erro de parsing em 2026-10-11). Google é opcional e **não** está ligado. A UI mostra o nome do mecanismo; nunca diz “busca Google”. Se a categoria notícias voltar vazia, o backend (e a UI) tenta a busca geral e marca o resultado como parcial.

Categorias: `general` (web) e `news`. Se um mecanismo cair, o backend devolve `meta.status=parcial` e `providers[].status=indisponivel` com o motivo do SearXNG. Sem stealth, proxy ou quebra de CAPTCHA.

## Backend

- Valida `q` (2–200). Timeout `SEARCH_TIMEOUT_SECONDS` (8). Rate limit por hash de IP em memória.
- Sanitiza título/trecho (nh3, sem tags). Dedup por URL. Datas só se o mecanismo mandar ISO válido.
- Cache HMAC em `app.search_cache` (`SEARCH_CACHE_TTL_SECONDS=600`). Acerto de cache informa `fetched_at`; não finge resultado “ao vivo”.
- Checagens: filtro de domínio em `backend/atlas_api/search/factcheck.py`. Sem rating automático. Sem leitura de página (evita SSRF/paywall).
- Pesquisas registradas: FTS no PostgreSQL. Sem percentuais (o cadastro não tem).
- Ficha `/evolucao/{protocolo}`: cadastro TSE + cobertura jornalística (POST `/search/polls/{protocolo}/leitura`). Percentuais só quando o trecho cita nome oficial + `%`. No 1º turno, confronto com a urna. 2º turno abre mesmo sem CSV de votos.
- PesqEle: a API devolve a [consulta pública do TSE](https://www.tse.jus.br/eleicoes/pesquisa-eleitorais/consulta-as-pesquisas-registradas) + o protocolo na ficha. O detalhe `detalhar.xhtml` exige sessão no sistema; fetch desacompanhado recebe *Access Denied* da Akamai. Não inventamos querystring de protocolo.

## UI

`/pesquisa` envia `POST /api/search/{web,news,fact-checks,polls}`. A consulta **não** vai para a URL do app (só a aba, ex. `?aba=pesquisas`). Provedor indisponível aparece como `parcial` / `indisponivel`.

## O que não está concluído

- Wikinews mistura anos; a data exibida é a do mecanismo, não validamos o ano da matéria.
- Mojeek pode oscilar para *access denied*.
- Link profundo por protocolo no PesqEle: bloqueado pelo sistema oficial, não por falta de tela.
