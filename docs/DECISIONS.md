# Decisões

| Decisão | Motivo |
|---|---|
| Manifesto + HEAD do CDN para resultados | Catálogo CKAN `resultados-2026` só tinha PDFs em 2026-10-11; CSVs existiam no CDN. |
| Não importar `*_BRASIL.csv` de votos | União dos arquivos por UF; duplicaria fatos. |
| Agregados só de munzona | Seção representa os mesmos votos. |
| Particionar `vote_section` por `sg_ue` | `BR` = Presidente (todas as UFs + ZZ); UF = cargos estaduais. |
| Identidade de aptos com seções não instaladas | 40 linhas do detalhe BR (exterior) quebram `comparecimento+abstenção=aptos`. |
| SearXNG próprio, sem porta | Instâncias públicas bloqueiam JSON; não expor metabusca. |
| Mecanismos sem Google/Brave/Startpage | Teste real: access denied / 429 / CAPTCHA. |
| Sem leitura de página | Evita SSRF, paywall e atribuição insegura de “veredito”. |
| Porta 55432 | 5432 e 54321+ já usados (Postgres/Supabase locais). |
| Sem Kafka/Airflow/K8s | Escopo e máquina do demo. |
| HMAC no cache de busca | Não persistir o texto da consulta. |
