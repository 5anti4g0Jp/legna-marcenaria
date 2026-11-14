"""Etapa 3 do fluxo: COMPARAR as respostas independentes com o gabarito e DOCUMENTAR as divergências.

Não altera nada: só lê o gabarito original (v0), os resultados da baseline e as respostas registradas.
Uso: python -m evaluation.review_report [--saida relatorio.md]
"""
from __future__ import annotations

import argparse, csv, json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from .hashlog import HashLog
from .paths import Caminhos
from .review_import import ASSOC, ROLE, _cmp
from .review_record import sha

PERGUNTAS = {"q1": "q1_papel", "q2": "q2_intervalo_correto", "q3": "q3_valor_correto"}
NOME_Q = {"q1": "Q1 papel do número", "q2": "Q2 intervalo correto", "q3": "Q3 valor escrito correto"}
LIMIAR_CONTROLE = 0.75


def kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0: return None
    cats = sorted(set(a) | set(b)); po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def carregar(c: Caminhos) -> list[dict]:
    log = HashLog(c.manifesto_respostas); out = []
    for e in log.entradas:
        f = c.respostas / e["arquivo"]
        if sha(f) != e["sha256"]:
            raise ValueError(f"arquivo de respostas alterado após o registro: {e['arquivo']}")
        rows = {r["id"]: r for r in csv.DictReader(open(f, encoding="utf-8-sig"))}
        out.append({"revisor": e["revisor"], "arquivo": e["arquivo"], "sha8": e["sha256"][:8], "rows": rows})
    return out


def esperado_gabarito(t: dict) -> dict:
    return {"q1": ROLE.get(t["role"]), "q2": ASSOC.get(t.get("assoc_verdict_baseline")), "q3": "sim" if t.get("written_value_correct") else None}


def carregar_exclusoes_q2(c: Caminhos) -> dict:
    """Registro formal (pkg-1.1) de itens sem linha azul: a pergunta 2 não se aplica e fica fora da comparação/métricas. Ausente = nenhuma exclusão."""
    f = c.exclusoes_q2
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"ids": []}


def gerar(c: Caminhos | None = None) -> dict:
    c = c or Caminhos()
    exc = carregar_exclusoes_q2(c); excl = set(exc["ids"])
    gt = json.loads(c.gt_v0.read_text()); saved = json.loads(c.resultado_v0.read_text()); itens = json.loads(c.itens.read_text())["itens"]
    tok = {t["id"]: t for t in gt["tokens"]}; out_by_id = {r["id"]: r for r in saved["real"]["linhas"]}; resp = carregar(c)
    por_rev = {r["revisor"]: {q: Counter() for q in PERGUNTAS} for r in resp}
    por_grupo = defaultdict(lambda: defaultdict(Counter)); ctrl = defaultdict(lambda: {"concorda": 0, "discorda": 0})
    itens_rep = []
    for it in itens:
        t = tok[it["id"]]; gab = esperado_gabarito(t); respostas = {}; tipos = set()
        for r in resp:
            row = r["rows"].get(it["id"])
            if not row or not any(row[col].strip() for col in PERGUNTAS.values()): continue
            ans = {q: row[col].strip() for q, col in PERGUNTAS.items()}; cmp_ = {q: _cmp(gab[q], ans[q]) for q in PERGUNTAS}
            if it["id"] in excl: cmp_["q2"] = "excluida"                                  # pergunta 2 não se aplica (sem linha azul): fora de toda comparação/métrica
            respostas[r["revisor"]] = {"respostas": ans, "comparacao": cmp_, "valor_lido": row.get("valor_lido_pelo_revisor", ""), "observacao": row.get("observacao", "")}
            for q, v in cmp_.items():
                por_rev[r["revisor"]][q][v] += 1
                for g in it["grupos"]: por_grupo[g][(r["revisor"], q)][v] += 1
                if "controle" in it["grupos"] and v in ("concorda", "discorda"): ctrl[r["revisor"]][v] += 1
                if v == "discorda": tipos.add("discorda_do_gabarito")
                if v == "nao_sei" and gab[q] is not None: tipos.add("revisor_nao_sei")      # gabarito indeterminado + "não sei" = coerentes, não é divergência
                if v == "gabarito_indeterminado": tipos.add("gabarito_indeterminado_com_resposta")
        for q in PERGUNTAS:                                                            # revisores que discordam entre si
            if q == "q2" and it["id"] in excl: continue
            vals = {rv: d["respostas"][q] for rv, d in respostas.items() if d["respostas"][q] not in ("", "nao_sei")}
            if len(set(vals.values())) > 1: tipos.add("revisores_discordam")
        itens_rep.append({"id": it["id"], "pagina": t["page"], "texto": t["text"], "grupos": it["grupos"], "gabarito": {"papel": t["role"], "associacao": t.get("assoc_verdict_baseline"),
                          "valor_correto": t.get("written_value_correct"), "evidencia": t.get("evidencia") or t.get("evidence")}, "resultado_baseline": out_by_id[it["id"]]["outcome"],
                          "respostas": respostas, "tipos_divergencia": sorted(tipos), "precisa_resolucao": bool(tipos), "sem_resposta": not respostas})
    concord = {}
    for rv, qs in por_rev.items():
        concord[rv] = {}
        for q, cn in qs.items():
            dec = cn["concorda"] + cn["discorda"]
            concord[rv][q] = {"concorda": cn["concorda"], "discorda": cn["discorda"], "nao_sei": cn["nao_sei"], "gabarito_indeterminado": cn["gabarito_indeterminado"], "sem_resposta": cn["sem_resposta"], "excluida": cn["excluida"],
                              "taxa_concordancia": round(cn["concorda"] / dec, 3) if dec else None}
    controle = {rv: {**v, "taxa": round(v["concorda"] / (v["concorda"] + v["discorda"]), 3) if (v["concorda"] + v["discorda"]) else None} for rv, v in ctrl.items()}
    for rv, v in controle.items(): v["alerta"] = (v["taxa"] is not None and v["taxa"] < LIMIAR_CONTROLE)
    inter = {}
    for a, b in combinations([r["revisor"] for r in resp], 2):
        for q in PERGUNTAS:
            pares = [(it["respostas"][a]["respostas"][q], it["respostas"][b]["respostas"][q]) for it in itens_rep if a in it["respostas"] and b in it["respostas"]
                     and not (q == "q2" and it["id"] in excl)
                     and it["respostas"][a]["respostas"][q] and it["respostas"][b]["respostas"][q]]
            inter[f"{a} × {b} · {q}"] = {"itens_em_comum": len(pares), "concordancia_simples": round(sum(x == y for x, y in pares) / len(pares), 3) if pares else None,
                                         "kappa_cohen": kappa([x for x, _ in pares], [y for _, y in pares])}
    return {"gabarito_sha256": sha(c.gt_v0), "algoritmo_sha256": sha(c.algoritmo), "respostas": [{"revisor": r["revisor"], "arquivo": r["arquivo"], "sha8": r["sha8"]} for r in resp],
            "exclusoes_q2": {"ids": sorted(excl), "n": len(excl), "sha256": sha(c.exclusoes_q2) if excl else None}, "itens_total": len(itens), "itens_sem_resposta": [i["id"] for i in itens_rep if i["sem_resposta"]], "concordancia_por_revisor": concord, "controle": controle,
            "inter_revisores": inter, "itens": itens_rep, "precisam_resolucao": [i["id"] for i in itens_rep if i["precisa_resolucao"]],
            "por_grupo": {g: {f"{rv}|{q}": dict(cn) for (rv, q), cn in d.items()} for g, d in por_grupo.items()}}


def render(rep: dict) -> str:
    L = ["# Relatório de concordância — revisão independente da baseline (Etapa 0)", "",
         f"Gabarito original (v0) `sha256 {rep['gabarito_sha256'][:12]}…` · algoritmo congelado `{rep['algoritmo_sha256'][:12]}…`. **O gabarito NÃO foi alterado por este relatório.**", "",
         f"Revisores: {', '.join(f'**{r['revisor']}** (`{r['arquivo']}`)' for r in rep['respostas']) or '— nenhum registrado —'}", "",
         (f"**Pergunta 2 excluída** (sem linha azul; pergunta não se aplica; registro `exclusoes_q2.json` sha {rep['exclusoes_q2']['sha256'][:12]}…) em {rep['exclusoes_q2']['n']} itens: {', '.join(rep['exclusoes_q2']['ids'])}. Eles não entram na comparação, nas taxas, no controle nem na concordância entre revisores." if rep['exclusoes_q2']['n'] else "Nenhuma exclusão da pergunta 2."), "",
         f"Itens na folha: {rep['itens_total']} · sem nenhuma resposta: {len(rep['itens_sem_resposta'])} · **precisam de resolução: {len(rep['precisam_resolucao'])}**", "",
         "## 1. Concordância com o gabarito", "", "| Revisor | Pergunta | Concorda | Discorda | Não sei | Gabarito indeterminado | Sem resposta | Excluída | Taxa (concorda/decididos) |", "|---|---|---|---|---|---|---|---|---|"]
    for rv, qs in rep["concordancia_por_revisor"].items():
        for q, v in qs.items():
            L.append(f"| {rv} | {NOME_Q[q]} | {v['concorda']} | {v['discorda']} | {v['nao_sei']} | {v['gabarito_indeterminado']} | {v['sem_resposta']} | {v['excluida']} | {v['taxa_concordancia'] if v['taxa_concordancia'] is not None else '—'} |")
    L += ["", "## 2. Grupo de controle (itens que o gabarito considera corretos)", ""]
    for rv, v in rep["controle"].items():
        L.append(f"- **{rv}**: {v['concorda']} de {v['concorda'] + v['discorda']} concordâncias ({v['taxa']})" + (" ⚠ **abaixo do limiar: revisar o entendimento das perguntas ou o gabarito**" if v["alerta"] else ""))
    if not rep["controle"]: L.append("- sem dados")
    if rep["inter_revisores"]:
        L += ["", "## 3. Concordância entre revisores", "", "| Par · pergunta | Itens em comum | Concordância | Kappa de Cohen |", "|---|---|---|---|"]
        L += [f"| {k} | {v['itens_em_comum']} | {v['concordancia_simples']} | {v['kappa_cohen']} |" for k, v in rep["inter_revisores"].items()]
    L += ["", "## 4. Divergências que exigem resolução", "", "Tipos: `discorda_do_gabarito` · `revisor_nao_sei` · `gabarito_indeterminado_com_resposta` · `revisores_discordam`.", ""]
    pend = [i for i in rep["itens"] if i["precisa_resolucao"]]
    if pend:
        L += ["| Item | Pág. | Texto | Grupos | Gabarito (papel / associação / valor) | Respostas | Tipo |", "|---|---|---|---|---|---|---|"]
        for i in pend:
            g = i["gabarito"]; rs = "<br>".join(f"**{rv}**: {d['respostas']['q1']}/{d['respostas']['q2']}/{d['respostas']['q3']}" + (f" (leu '{d['valor_lido']}')" if d["valor_lido"] else "") + (f" — {d['observacao']}" if d["observacao"] else "") for rv, d in i["respostas"].items())
            L.append(f"| `{i['id']}` | {i['pagina']} | {i['texto']} | {', '.join(i['grupos'])} | {g['papel']} / {g['associacao']} / {g['valor_correto']} | {rs} | {', '.join(i['tipos_divergencia'])} |")
    else:
        L.append("Nenhuma divergência.")
    if rep["itens_sem_resposta"]:
        L += ["", "## 5. Itens sem resposta", "", ", ".join(f"`{i}`" for i in rep["itens_sem_resposta"])]
    L += ["", "## Próximo passo", "", "Cada item da seção 4 precisa de uma **resolução registrada com evidência** (`python -m evaluation.resolutions`), inclusive quando a decisão for manter o gabarito."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--saida"); a = ap.parse_args()
    txt = render(gerar())
    if a.saida: Path(a.saida).write_text(txt, encoding="utf-8")
    else: print(txt)
