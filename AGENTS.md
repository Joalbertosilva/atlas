# Agentes — Atlas Eleitoral 2026

Documentação canônica do Cursor: [Rules](https://cursor.com/docs/rules), [Skills](https://cursor.com/docs/skills), [Subagents](https://cursor.com/docs/subagents).

## Contrato antes de paralelizar

1. Modelo: `migrations/` + `docs/DATA_DICTIONARY.md`
2. API: `docs/API.md`
3. Depois disso, agentes editam árvores disjuntas.

| Agente | Árvore | Não toca |
|---|---|---|
| [data-engineer](.cursor/agents/data-engineer.md) | `etl/`, `data/manifests/` | `backend/`, `frontend/` |
| [backend-engineer](.cursor/agents/backend-engineer.md) | `backend/`, `migrations/` | `frontend/`, loaders |
| [frontend-engineer](.cursor/agents/frontend-engineer.md) | `frontend/` | resto |
| [search-engineer](.cursor/agents/search-engineer.md) | `infra/searxng/`, `backend/atlas_api/search/` | ETL |
| [reviewer](.cursor/agents/reviewer.md) | `tests/`, `docs/STATUS.md` | implementação nova |

Se subagentes não estiverem disponíveis, execute os papéis em sequência. Não simule execução.

## Skills

`.cursor/skills/*/SKILL.md`: inspecionar layouts, importar/reprocessar, reconciliar totais, mapear TSE–IBGE, revisar mapas, diagnosticar busca.

## Rules

`.cursor/rules/*.mdc`: integridade eleitoral, SQL parametrizado, segurança/privacidade, acessibilidade, critérios de conclusão.
