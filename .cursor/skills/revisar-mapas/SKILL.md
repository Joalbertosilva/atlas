---
name: revisar-mapas
description: Revisa o mapa (geometria IBGE + resultados agregados, sem enviar fatos ao browser).
---

# Revisar mapas

## Entrada
- `GET /api/map/geometry?level=municipio&uf=` e `GET /api/results/municipalities`.

## Passos
1. Join no cliente por `cd_municipio_ibge`. Sem geometria no payload de resultados.
2. Empate: `tie=true`, cor `#374151`. Sem dados: `#e5e7eb`.
3. ZZ não entra no GeoJSON. Exterior só no cartão do dashboard.
4. Estilo MapLibre mínimo — sem tiles pagos.
5. Tabela acessível com os mesmos dados.

## Saída
- Checklist: join correto, legendas, empate, vazio, UF filtrada.

## Verificação
- Número de features da malha municipal ≈ municípios IBGE. Municípios TSE sem IBGE não pintam o mapa.
---
