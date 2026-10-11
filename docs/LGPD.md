# Privacidade e LGPD

Texto informativo. **Não é parecer jurídico nem certificação de conformidade.**

## Dados tratados neste sistema

| Dado | Origem | Finalidade | Retenção |
|---|---|---|---|
| Resultados e candidaturas (nome de urna, partido, votos agregados) | TSE dados abertos | Exibir painel | Enquanto o recorte estiver publicado |
| Locais de votação (nome, endereço, coords quando válidas) | TSE eleitorado 2026 | Navegação territorial | Idem |
| Pesquisas registradas (empresa, protocolo, metodologia) | TSE | Busca local | Idem |
| Consulta de busca (texto) | Usuário → backend → SearXNG → mecanismos | Responder a busca | Não persistimos o texto. Cache: HMAC + JSON de resultados, TTL 10 min |
| IP do visitante | Conexão | Rate limit em memória (chave HMAC) | Alguns minutos, não gravado |

Não coletamos CPF de visitantes. Não importamos CPF/e-mail/título/nascimento/raça/gênero/ocupação de candidatos. Não construímos perfil de opinião.

Dados públicos do TSE **não** autorizam automaticamente qualquer tratamento extra (ex.: enriquecimento, mailing).

## Terceiros

Consultas de busca são enviadas a mecanismos configurados no SearXNG (DuckDuckGo, Bing, etc.). Cada um aplica a própria política. Sem Google Analytics, pixels ou cookies não essenciais.

## Segurança

Rede Docker interna; SearXNG sem porta pública; API read-only; logs de acesso desligados; SQL parametrizado; sanitização de HTML externo.

## Pendências (não inventar)

- Responsável pelo tratamento
- Canal de contato / DPO
- Fundamento jurídico formal e política de retenção institucional

Quem for publicar o painel precisa preencher isso. Até lá, o uso previsto é demonstração local.
