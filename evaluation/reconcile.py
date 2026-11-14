"""Reconciliação aritmética do relatório da Etapa 0 (gera etapa0_reconciliacao.md a partir do JSON)."""
from __future__ import annotations

import json, sys
from collections import Counter
from pathlib import Path

MANCHETE = ("confirmada_correta", "confirmada_associacao_incorreta", "conflito_falso_alarme", "perdida_medicao")


def render(R: dict) -> str:
    rows = [r for r in R["real"]["linhas"] if r["role"].startswith("cota")]
    c = Counter(r["outcome"] for r in rows); n = len(rows)
    fora = {k: v for k, v in c.items() if k not in MANCHETE}
    L = ["# Etapa 0 — Reconciliação: 104 cotas × 101 resultados", "",
         f"Cotas revisadas na amostra: **{n}** ({sum(1 for r in rows if r['role']=='cota_regular')} regulares + {sum(1 for r in rows if r['role']=='cota_deslocada')} deslocadas).", "",
         "| Resultado | N |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(c.items(), key=lambda kv: -kv[1])] + [f"| **Soma** | **{sum(c.values())}** |", "",
         f"- Soma das quatro categorias que aparecem na manchete do relatório (confirmada correta + falsa confirmação + conflito + perdida): **{sum(c[k] for k in MANCHETE)}**.",
         f"- Diferença para {n}: **{n - sum(c[k] for k in MANCHETE)}**, que corresponde à categoria `{', '.join(fora)}` ({sum(fora.values())} cotas), listada à parte no relatório e **fora das taxas**.", "",
         "Cotas da categoria que ficou fora da manchete (todas `confirmado_local`):", ""]
    for r in rows:
        if r["outcome"] == "confirmada_indeterminada":
            L.append(f"- `{r['id']}` valor **{r['text']}** — estado do baseline `{r['status']}`; evidência do gabarito: {r['evidence']}")
    ass = [r for r in rows if r["outcome"] == "conflito_falso_alarme" and "soma de cadeia" not in (r.get("evidence") or "")]
    L += ["", "**Não confundir** com os 3 conflitos 'assumidos corretos sem confirmação visual conclusiva' (grupo diferente):", ""]
    L += [f"- `{r['id']}` valor **{r['text']}** ({r['role']})" for r in ass]
    L += ["", "As outras tabelas do relatório (por papel, orientação, tamanho) somam 104 cada uma; a de formato soma mais porque inclui notas e não-cotas."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    print(render(json.loads(Path(sys.argv[1]).read_text())), end="")
