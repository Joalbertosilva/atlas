---
name: inspecionar-layouts
description: Inspeciona layouts reais dos CSVs eleitorais do TSE (cabeçalho, encoding, amostra).
---

# Inspecionar layouts eleitorais

## Entrada
- Chave do manifesto (`consulta_cand_2026`, `votacao_secao_2026_AC`, …) ou caminho do ZIP.

## Passos
1. `atlas-etl inspect <key>` — lista membros, CRC, cabeçalho e 1ª linha.
2. Confirme encoding ISO-8859-1 e separador `;`.
3. Compare colunas com `etl/atlas_etl/loaders.py` (`*_COLS`). Coluna nova ou ausente = parar e ajustar o loader, não improvisar.
4. Anote `DT_GERACAO`/`HH_GERACAO`. Recuse arquivo cujo `ANO_ELEICAO` não coincida com o ano declarado do recurso (2026 ou 2022). Nunca trate arquivo de 2022 como se fosse 2026.

## Saída
- Lista de colunas, tipos observados, recortes (UF/BR/BRASIL), data de geração.

## Verificação
- `python -c` lendo 3 linhas com pandas `dtype=str` deve reproduzir os mesmos nomes.
---
