---
name: diagnosticar-busca
description: Diagnostica o SearXNG interno (JSON, mecanismos, bloqueios, cache).
---

# Diagnosticar busca online

## Entrada
- Serviço `searxng` no Compose e `GET /api/search/status`.

## Passos
1. De dentro da rede: `wget -q -O - 'http://searxng:8080/search?q=TSE&format=json&language=pt-BR'`.
2. HTTP 403 = `formats` sem `json` em `infra/searxng/settings.yml`.
3. `unresponsive_engines`: registrar motivo (CAPTCHA, 429, access denied). Desativar no `keep_only`. Não contornar.
4. Conferir `GET /api/search/status` (versão, engines, cache).
5. Testar `POST /api/search/web` e `/news` pelo backend — o React não fala com o SearXNG.
6. Cache HMAC: mesma consulta não deve republicar como “agora” se `cache.hit=true` (mostrar horário de obtenção).

## Saída
- Lista de mecanismos ok/indisponível (como em `docs/SEARCH.md`).

## Verificação
- Consulta real devolve título+URL no JSON. Sem chave paga. Google não é dependência.
---
