# Fontes

Licença TSE: Creative Commons Atribuição (metadados CKAN). IBGE: dados públicos da API de Malhas v3; citar IBGE.

## Verificado em 2026-10-11

| Dataset CKAN | Situação |
|---|---|
| [resultados-2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026) | Catálogo listava **apenas PDFs** de totalização. CSVs `votacao_*` e `detalhe_*` existem no CDN no padrão histórico (`listed_in_catalog: false` no manifesto). HEAD HTTP 200. |
| [candidatos-2026](https://dadosabertos.tse.jus.br/dataset/candidatos-2026) | CSVs no catálogo. |
| [eleitorado-2026](https://dadosabertos.tse.jus.br/dataset/eleitorado-2026) | CSVs no catálogo, inclusive locais de votação. |
| [pesquisas-eleitorais-2026](https://dadosabertos.tse.jus.br/dataset/pesquisas-eleitorais-2026) | CSV de registro (sem percentuais). |
| [códigos TSE–IBGE](https://dadosabertos.tse.jus.br/dataset/codigos-oficiais-de-uf-e-municipios-segundo-o-tse-e-o-ibge) | `municipio_tse_ibge.zip`. |
| Malhas IBGE v3 | `qualidade=minima`, `intrarregiao=municipio` e `UF`. |
| Fotos de candidatura | 2026: portal de resultados `https://resultados.tse.jus.br/oficial/ele2026/{cd_eleicao}/fotos/{ue}/{sq_candidato}.jpeg` (Presidente `6257`/`br`; Governador SP `6259`/`sp`) → `image/jpeg`. 2022: o mesmo caminho 404; o TSE publica os JPEG no ZIP `https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/fotos/foto_cand2022_{UE}_div.zip` (arquivo `F{UE}{sq}_div.jpg\|jpeg`). A API extrai e serve em `/api/photos/2022/{UE}/{sq}`. |

URLs canônicas: `data/manifests/tse_2026.yaml`. `atlas-etl discover` compara CKAN × HEAD do CDN.

Resultados de **2022** estão no manifesto e **importados** (`consulta_cand_2022`, munzona cand/partido/detalhe). Importação: `atlas-etl import … --ano 2022`. Escopos `munzona_cand:2022:BR` etc. não substituem 2026. A UI de comparação é `/comparar` (não uma seção à parte). Ausência ≠ zero.

## Arquivos que o ETL usa

- `consulta_vagas_2026.zip`, `consulta_cand_2026.zip` — vagas e cadastro (sem CPF/e-mail/título).
- `detalhe_votacao_munzona_2026.zip` — aptos, comparecimento, brancos, nulos, válidos (grão oficial de totalização).
- `votacao_candidato_munzona_2026.zip` / `votacao_partido_munzona_2026.zip` — nominais e legenda.
- `votacao_secao_2026_{UE}.zip` — um ZIP por UF + `BR` (Presidente, inclui ZZ) + `ZZ` (vazio neste ciclo).
- `detalhe_votacao_secao_2026.zip`, `eleitorado_local_votacao_2026.zip`.
- `pesquisa_eleitoral_2026.zip` (membro `*_BRASIL.csv`).
- Relatório PDF `Relatorio_Resultado_Totalizacao_2026_BR.zip` — conferência externa.
- GeoJSON IBGE mínima.

Membros `*_BRASIL.csv` (união de UFs) **não** são importados para votos — evitaria duplicar os recortes por UF. Exceção: vagas e pesquisas, que só têm o consolidado útil.

`votacao_secao_2026_ZZ.zip` (2026-10-06) veio **sem linhas de dados**; o exterior da Presidência está em `votacao_secao_2026_BR.csv` (341 766 votos).
