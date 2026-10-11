# ETL

CLI: `atlas-etl`. Ordem: TSE–IBGE → geometria → vagas → candidaturas → detalhe munzona → nominais → legendas → agregados → locais → seção → detalhe seção → pesquisas.

## Garantias

1. Download: timeout, retry com backoff, Range, hash SHA-256 em arquivo lateral.
2. ZIP: nomes sem `/` nem `..`; limite de tamanho e razão de compressão.
3. Staging UNLOGGED + `COPY` CSV (ISO-8859-1, `;`, `dtype=str`).
4. Validação (UE, cargos, identidade de aptos, JOIN sem perda/multiplicação).
5. Uma transação substitui o recorte e grava `meta.publication`. Falha faz rollback dos fatos; o publicado anterior permanece.
6. Mesma impressão `membro:crc32:tamanho` → não republica.

## Recortes

- Referências: um scope (`ref:municipio_tse_ibge`, `ref:consulta_vagas`, `polls:BRASIL`).
- Por UE: `cand:AC`, `munzona_cand:BR`, `secao:SP`, `locais:ZZ`, …
- `vote_section` é `PARTITION BY LIST (sg_ue)`: `TRUNCATE` da partição na republicação.

## Comandos

```text
atlas-etl discover | list | download [--kind] [--ue] [--force]
atlas-etl inspect <key> [--member]
atlas-etl import <kind> [--ue] [--force]
atlas-etl import-all [--skip] [--only] [--force]
atlas-etl resume | rebuild-aggregates | reconcile [--show N]
atlas-etl coverage [-v] | cleanup
```

## O que não fazer

- Somar `*_BRASIL.csv` de votos com os arquivos por UF.
- Somar seção + munzona.
- Publicar recorte parcial após exceção.
- Tratar `skipped_duplicate` como falha.
