"""Métricas de avaliação do algoritmo de cotas (comparáveis entre etapas).

Resultado por item de verdade (outcome):
  cotas (regular/deslocada):
    perdida_leitura                      o número nem virou candidato (ex.: decimal, unidade, texto em ângulo)
    perdida_medicao                      virou candidato mas ficou sem medição (sem_medicao/sem_escala)
    confirmada_correta                   confirmada E associada ao intervalo certo
    confirmada_associacao_incorreta      confirmada contra o intervalo ERRADO (falsa confirmação)
    confirmada_indeterminada             confirmada, associação não decidível
    conflito_falso_alarme                marcada conflito, mas o valor escrito está correto
    erro_plantado_detectado / _aceito / _perdido
  medida_em_nota:   nota_nao_lida | nota_tratada_como_cota
  nao_cota:         ignorada_corretamente | falsa_deteccao_medida | falso_candidato_sem_medicao
"""
from __future__ import annotations

import math, statistics, time, hashlib
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

import ingest.dimensions as D

MEASURED = ("confirmado", "confirmado_local", "conflito")
ACCEPTED = ("confirmado", "confirmado_local")


def center(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def align(items, dims, tol=3.0):
    """item.bbox <-> Dimension por texto igual e centro próximo; um-para-um."""
    used, out = set(), {}
    for it in items:
        if not it.get("bbox"):
            out[it["id"]] = None; continue
        c = center(it["bbox"]); best = None; bd = tol
        for i, d in enumerate(dims):
            if i in used or d.text != it["text"]:
                continue
            dd = math.dist(c, center(d.bbox))
            if dd <= bd: best, bd = i, dd
        if best is not None: used.add(best)
        out[it["id"]] = dims[best] if best is not None else None
    return out


def synthetic_assoc(truth, d) -> str:
    """Associação correta = mesma orientação e comprimento medido ~ comprimento verdadeiro (±1 pt ou ±1%)."""
    exp_orient = {"horizontal": "h", "vertical": "v"}.get(truth["orientation"])
    if exp_orient is None or d.orient != exp_orient:
        return "incorreta"
    if d.length_pt is None:
        return "indeterminada"
    return "correta" if abs(d.length_pt - truth["interval_pt"]) <= max(1.0, 0.01 * truth["interval_pt"]) else "incorreta"


def outcome(item, d, assoc) -> str:
    role = item["role"]
    if role in ("cota_regular", "cota_deslocada"):
        planted = item.get("planted_error", False)
        if d is None:
            return "erro_plantado_perdido" if planted else "perdida_leitura"
        if d.status not in MEASURED:
            return "erro_plantado_perdido" if planted else "perdida_medicao"
        if planted:
            return "erro_plantado_detectado" if d.status == "conflito" else "erro_plantado_aceito"
        if d.status == "conflito":
            return "conflito_falso_alarme"
        return {"correta": "confirmada_correta", "incorreta": "confirmada_associacao_incorreta"}.get(assoc, "confirmada_indeterminada")
    if role == "medida_em_nota":
        return "nota_nao_lida" if d is None else "nota_tratada_como_cota"
    if role == "nao_cota":
        if d is None: return "ignorada_corretamente"
        return "falsa_deteccao_medida" if d.status in MEASURED else "falso_candidato_sem_medicao"
    return "nao_avaliado"


def aggregate(rows, key):
    """rows: dicts com 'outcome' e o campo `key`. Devolve {valor: {outcome: n, '_total': n}}."""
    agg = defaultdict(Counter)
    for r in rows:
        k = r.get(key) or "-"
        agg[k][r["outcome"]] += 1; agg[k]["_total"] += 1
    return {k: dict(v) for k, v in sorted(agg.items())}


def rates(counter: dict) -> dict:
    """Taxas sobre as COTAS (regular+deslocada) de um agregado."""
    t = counter.get("_total", 0)
    g = lambda *ks: sum(counter.get(k, 0) for k in ks)
    ok = g("confirmada_correta")
    return {
        "total": t,
        "confirmada_correta": ok,
        "falsa_confirmacao": g("confirmada_associacao_incorreta", "erro_plantado_aceito"),
        "perdida": g("perdida_leitura", "perdida_medicao", "erro_plantado_perdido"),
        "falso_alarme": g("conflito_falso_alarme"),
        "indeterminada": g("confirmada_indeterminada"),
        "erro_plantado_detectado": g("erro_plantado_detectado"),
    }


def page_scales(pd: "D.PageDims", scales_true=None):
    meas = [d for d in pd.dims if d.length_pt]
    cl = [c for c in D._cluster([d.value / d.length_pt for d in meas]) if len(c) >= D.MIN_CLUSTER] if meas else []
    if not cl: return {"grupos": 0}
    dom = max(cl, key=len); dm = statistics.median(dom)
    meds = sorted((statistics.median(c), len(c)) for c in cl)
    spur = [m for m, n in meds if m != dm and (m / dm < 0.5 or m / dm > 2)]
    return {"grupos": len(cl), "escalas": [(round(m, 4), n) for m, n in meds], "dominante": round(dm, 4), "espurias": [round(m, 4) for m in spur],
            "multiplas_proximas": any(m != dm and 0.5 <= m / dm <= 2 for m, _ in meds)}


def diagnose(pg, d) -> str:
    """Causa provável de uma cota regular sem medição (usa os internos do baseline, só leitura)."""
    segs = D._segments(pg); toks = D._numeric_tokens(pg); col = D._dimension_color(toks, segs)
    if not col: return "página sem cor de cota detectável"
    ds = [s for s in segs if s[0] == col]; cx, cy = center(d.bbox)
    if d.orient == "h":
        cands = [abs(s[2] - cy) for s in ds if abs(s[2] - s[4]) < 0.3 and abs(s[1] - s[3]) > 3 and min(s[1], s[3]) <= cx <= max(s[1], s[3])]
    else:
        cands = [abs(s[1] - cx) for s in ds if abs(s[1] - s[3]) < 0.3 and abs(s[2] - s[4]) > 3 and min(s[2], s[4]) <= cy <= max(s[2], s[4])]
    if not cands: return "nenhuma linha paralela cobrindo o texto"
    m = min(cands)
    if 14.0 < m <= 24.0: return f"limite fixo de busca de 14 pt: linha a {m:.1f} pt"
    if m <= 14.0: return "linha encontrada, mas faltam marcas válidas dos dois lados"
    return f"linha paralela mais próxima a {m:.0f} pt (texto deslocado/chamada)"


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
