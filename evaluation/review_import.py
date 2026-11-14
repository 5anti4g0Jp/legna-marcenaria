"""Importa as respostas de um revisor independente (CSV exportado da folha) e compara com o gabarito.

NÃO altera o gabarito nem os resultados: só produz um relatório de concordância/discordância para decisão humana.
Uso: python -m evaluation.review_import respostas.csv [saida.json]
"""
from __future__ import annotations

import csv, json, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GT = ROOT / "groundtruth" / "real_fernanda.json"
ROLE = {"cota_regular": "cota_regular", "cota_deslocada": "cota_deslocada", "medida_em_nota": "nota", "nao_cota": "nao_medida"}
ASSOC = {"correta": "sim", "incorreta": "nao"}


def _cmp(gab, rev):
    """concorda | discorda | nao_sei | sem_resposta | gabarito_indeterminado"""
    if not rev: return "sem_resposta"
    if rev == "nao_sei": return "nao_sei"
    if gab is None: return "gabarito_indeterminado"
    return "concorda" if gab == rev else "discorda"


def import_review(csv_path, gt_path=GT) -> dict:
    gt = json.loads(Path(gt_path).read_text()); tok = {t["id"]: t for t in gt["tokens"]}
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
    out = {"arquivo": str(csv_path), "revisores": sorted({r.get("revisor", "") for r in rows if r.get("revisor")}), "itens_no_arquivo": len(rows),
           "q1": Counter(), "q2": Counter(), "q3": Counter(), "por_grupo": defaultdict(lambda: defaultdict(Counter)), "discordancias": [], "indeterminados_do_gabarito": [], "ids_desconhecidos": []}
    for r in rows:
        t = tok.get(r["id"])
        if t is None: out["ids_desconhecidos"].append(r["id"]); continue
        gab_role = ROLE.get(t["role"]); gab_assoc = ASSOC.get(t.get("assoc_verdict_baseline")); gab_val = "sim" if t.get("written_value_correct") else None
        res = {"q1": _cmp(gab_role, r.get("q1_papel", "")), "q2": _cmp(gab_assoc, r.get("q2_intervalo_correto", "")), "q3": _cmp(gab_val, r.get("q3_valor_correto", ""))}
        gabs = {"q1": gab_role, "q2": gab_assoc, "q3": gab_val}; revs = {"q1": r.get("q1_papel"), "q2": r.get("q2_intervalo_correto"), "q3": r.get("q3_valor_correto")}
        for q, v in res.items():
            out[q][v] += 1
            for g in (r.get("grupos") or "").split("|"):
                if g: out["por_grupo"][g][q][v] += 1
            if v == "discorda":
                out["discordancias"].append({"id": r["id"], "pergunta": q, "gabarito": gabs[q], "revisor": revs[q], "valor_lido": r.get("valor_lido_pelo_revisor"), "observacao": r.get("observacao"), "grupos": r.get("grupos")})
            if v == "gabarito_indeterminado":
                out["indeterminados_do_gabarito"].append({"id": r["id"], "pergunta": q, "revisor": revs[q], "observacao": r.get("observacao")})
    out["q1"], out["q2"], out["q3"] = dict(out["q1"]), dict(out["q2"]), dict(out["q3"])
    out["por_grupo"] = {g: {q: dict(c) for q, c in d.items()} for g, d in out["por_grupo"].items()}
    dec = lambda c: c.get("concorda", 0) + c.get("discorda", 0)
    out["concordancia"] = {q: (round(out[q].get("concorda", 0) / dec(out[q]), 3) if dec(out[q]) else None) for q in ("q1", "q2", "q3")}
    out["nota"] = "Relatório de concordância. O gabarito NÃO foi alterado; discordâncias exigem decisão humana."
    return out


if __name__ == "__main__":
    res = import_review(sys.argv[1])
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    if len(sys.argv) > 2: Path(sys.argv[2]).write_text(txt); print(f"{res['itens_no_arquivo']} itens; concordância {res['concordancia']} -> {sys.argv[2]}")
    else: print(txt)
