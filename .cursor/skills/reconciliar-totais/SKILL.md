---
name: reconciliar-totais
description: Reconcilia totais entre opções, detalhe munzona, seção e relatório PDF do TSE.
---

# Reconciliar totais

## Entrada
- Banco publicado + `data/downloads/` (inclui `Relatorio_Resultado_Totalizacao_2026_BR.zip` se for comparar o PDF).

## Passos
1. `atlas-etl reconcile --show 40`
2. Interprete: `validos_opcoes_vs_detalhe` inclui nominais convertidos à legenda; nulos técnicos somam na identidade de votos digitados.
3. Senador: `qt_votos == 2 * comparecimento`.
4. Seção vs munzona só depois de ambos publicados. Não some os dois.
5. PDF: exige `pdftotext`. Se o padrão não for encontrado, a checagem fica `ok=false` com `reason` — não aprove.

## Saída
- Linhas em `meta.reconciliation` e relatório em `docs/STATUS.md`.

## Verificação
- Presidente 1º turno (leitura 2026-10-11): válidos 119300788, comparecimento 125275835, nº 22 = 56104503, nº 13 = 53879538, ZZ comparecimento 341766.
---
