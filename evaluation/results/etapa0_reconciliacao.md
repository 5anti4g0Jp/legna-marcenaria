# Etapa 0 — Reconciliação: 104 cotas × 101 resultados

Cotas revisadas na amostra: **104** (86 regulares + 18 deslocadas).

| Resultado | N |
|---|---|
| confirmada_correta | 53 |
| perdida_medicao | 31 |
| conflito_falso_alarme | 14 |
| confirmada_indeterminada | 3 |
| confirmada_associacao_incorreta | 3 |
| **Soma** | **104** |

- Soma das quatro categorias que aparecem na manchete do relatório (confirmada correta + falsa confirmação + conflito + perdida): **101**.
- Diferença para 104: **3**, que corresponde à categoria `confirmada_indeterminada` (3 cotas), listada à parte no relatório e **fora das taxas**.

Cotas da categoria que ficou fora da manchete (todas `confirmado_local`):

- `p1-t55` valor **450** — estado do baseline `confirmado_local`; evidência do gabarito: revisão visual do overlay (valor escrito assumido correto; desenho real sem erro plantado)
- `p10-t17` valor **18** — estado do baseline `confirmado_local`; evidência do gabarito: soma de cadeia: 200+1720+200=2120; 200+170=370; 200+300=500; 18+294+18=330
- `p10-t22` valor **200** — estado do baseline `confirmado_local`; evidência do gabarito: soma de cadeia: 200+1720+200=2120; 200+170=370; 200+300=500; 18+294+18=330

**Não confundir** com os 3 conflitos 'assumidos corretos sem confirmação visual conclusiva' (grupo diferente):

- `p1-t9` valor **15** (cota_deslocada)
- `p1-t26` valor **45** (cota_regular)
- `p6-t8` valor **230** (cota_regular)

As outras tabelas do relatório (por papel, orientação, tamanho) somam 104 cada uma; a de formato soma mais porque inclui notas e não-cotas.
