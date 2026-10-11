# Roteiro de demonstração (entrevista 13/10/2026)

Tempo alvo: 8–10 minutos. Mostre cobertura real, não slides de “100% municípios” se o `coverage` ainda listar pendências.

## Antes

```bash
./scripts/up_stack.sh
curl -s localhost:8070/api/health
atlas-etl coverage -v          # esperado: secao 29/29, pending vazio na API
# frontend: npm --prefix frontend run dev  ou  compose frontend
# seções: ./scripts/resume_load.sh  (só se não houver outro ETL)
```

## Fala + clique

1. **Posicionamento (30 s).** “Painel independente. TSE + IBGE. Não é site oficial. Arquivos por turno, não tempo real.”
2. **Dashboard Presidente.** Ranking, `% dos votos válidos`, situação oficial (2º TURNO / NÃO ELEITO). Datas “Gerado pelo TSE” / “Importado”. Cartão Exterior.
3. **SQL (1 min, terminal ou cobertura).** Denominador de válidos; senador = 2 escolhas. Mostrar que aptos não são somados entre cargos.
4. **ETL (1 min).** Staging → validação → publicação transacional. Mesmo ZIP não duplica. Falha não publica recorte pela metade. Manifesto: CSVs de resultado estavam no CDN e não no catálogo.
5. **Mapa.** Líder municipal, empate, sem dados. Join `cd_municipio_ibge`. Tabela alternativa. ZZ fora do polígono.
6. **Explorar.** Município → zona → local (tipo ≠ escola) → seção. Se `link_status` ≠ confirmado: “Local não identificado”.
7. **Busca integrada.** Aba notícias: POST, resultados com mecanismo (Bing/DuckDuckGo), provedor indisponível visível. Aba pesquisas: cadastro sem %. Aba checagens: “não classificamos verdadeiro/falso”.
8. **Docker/custo zero.** Compose, volume persistente, SearXNG sem porta, sem chave paga.

## Como defender modelagem

- `sq_candidato` + eleição, não número.
- Opção de voto ≠ candidatura.
- Munzona vs seção: mesmos votos, grãos diferentes.
- Correspondência TSE–IBGE oficial; sem fuzzy de nome.

## Se algo falhar

- API degradada: `docker compose logs api` — conferir se `DATABASE_URL` usa `@db:5432` no container.
- Busca vazia: `/api/search/status`; mecanismo bloqueado é parcial, não “erro nosso”.
- UF sem ranking: `coverage` — recorte ainda não publicado.
