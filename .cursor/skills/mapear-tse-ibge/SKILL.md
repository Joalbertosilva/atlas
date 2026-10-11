---
name: mapear-tse-ibge
description: Usa a correspondência oficial TSE–IBGE; não casa município por nome.
---

# Mapear TSE–IBGE

## Entrada
- `municipio_tse_ibge.zip` (dataset oficial) e malhas IBGE v3 qualidade mínima.

## Passos
1. Importar `atlas-etl import municipio_tse_ibge` antes das geometrias.
2. Município brasileiro sem linha oficial: criar sem `cd_municipio_ibge` e listar em cobertura. Não unir por semelhança de nome.
3. ZZ (exterior): sem código IBGE, sem geometria, fora do mapa.
4. `atlas-etl import geometry` — `codarea` da malha = código IBGE.

## Saída
- `core.municipality.cd_municipio_ibge` e `GET /api/coverage` → `municipios_sem_codigo_ibge` / `municipios_sem_geometria`.

## Verificação
- Contagem de municípios com IBGE ≈ 5570. Qualquer residual entra em `docs/COVERAGE.md`, não no mapa.
---
