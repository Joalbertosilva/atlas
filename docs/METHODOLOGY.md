# Metodologia

O Atlas **republica** arquivos de totalização do TSE. Não apura urna, não projeta, não declara eleito.

1. Grão oficial de totalização = município/zona (`detalhe` + `votacao_candidato` + `votacao_partido`).
2. Seção = detalhe de navegação e prova de reconciliação.
3. Percentuais usam o denominador do mesmo recorte (ver `docs/SQL.md`).
4. Situação de candidatura e destinação vêm do arquivo; o ranking é só ordenação.
5. Mapa: líder = máximo de válidos no município; empate explícito.
6. Pesquisas: cadastro de registro, sem intenção de voto. Percentuais exibidos na ficha vêm só de trechos de notícia casados com candidaturas oficiais; confronto com a urna no 1º turno. Sem arquivo do instituto.
7. Checagens: atalho para páginas de editorias listadas, sem veredito automático.
8. Arquivos são por turno. Quando o TSE publicar o 2º turno, um novo `nr_turno=2` entra — o 1º não é “tempo real”.
