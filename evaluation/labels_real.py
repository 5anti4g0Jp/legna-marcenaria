"""Gabarito do PDF real (detalhamento de marcenaria, SketchUp LayOut, 34 págs).

HONESTIDADE: os rótulos foram feitos pelo assistente, por regras e por inspeção visual de overlays, e
NÃO foram conferidos por pessoa independente (`independent_review: false`). Só as páginas listadas em
REVIEWED_PAGES têm rótulos de papel/associação revisados; as demais ficam `reviewed: false` e entram só
nas contagens de universo, nunca nas métricas de acerto.

Papéis (role):
  cota_regular     número de uma cota linear, escrito junto à linha de cota
  cota_deslocada   número de uma cota linear escrito FORA dos riscos (chamada/leader; ex.: espessuras 15, 30, 50)
  medida_em_nota   medida em texto de nota (ex.: "PROFUNDIDADE ... = 34 CM"): informação técnica, não é cota geométrica
  nao_cota         número que não é medida (temperatura de cor, potência, código de produto)
Veredito de associação do baseline (assoc_verdict_baseline), só para tokens que o baseline mediu:
  correta | incorreta | indeterminada
"""
from __future__ import annotations

import json, re
from pathlib import Path

from .census import Tok, census

REVIEWED_PAGES = (1, 6, 10)

# ids dos tokens, lidos na tabela de tokens + overlay da revisão
DESLOCADA = {
    1: {"t6", "t7", "t9", "t13", "t16", "t20", "t30", "t32", "t34"},
    6: {"t3", "t6", "t18", "t22", "t24", "t31"},
    10: {"t4", "t13", "t14"},
}
# nota: token -> (papel, subtipo)
NOTAS = {
    1: {"t52": ("nao_cota", "potencia_led"), "t53": ("nao_cota", "temperatura_cor"), "t54": ("medida_em_nota", "perfil_led_12mm")},
    6: {"t27": ("medida_em_nota", "profundidade_cm"), "t28": ("medida_em_nota", "profundidade_cm"), "t32": ("medida_em_nota", "profundidade_cm"),
        "t33": ("nao_cota", "potencia_led"), "t34": ("nao_cota", "temperatura_cor"), "t35": ("medida_em_nota", "perfil_led_12mm")},
    10: {},
}
# veredito da associação do baseline onde a revisão visual achou algo diferente de "correta"
ASSOC_OVERRIDE = {
    1: {"t9": ("incorreta", "'15' é chamada de espessura; o baseline mediu um intervalo de ~195 pt (640 mm)"),
        "t26": ("indeterminada", "escrito 45, geometria 50 mm (+11%); não decidível pela imagem"),
        "t55": ("indeterminada", "escrito 450, geometria 437 mm (-2,9%); não decidível pela imagem")},
    6: {"t3": ("incorreta", "'15' deslocado confirmado contra a escala espúria 0,082 mm/pt"),
        "t6": ("incorreta", "'15' deslocado confirmado contra a escala espúria 0,082 mm/pt"),
        "t24": ("incorreta", "'15' deslocado confirmado contra a escala espúria 0,082 mm/pt"),
        "t8": ("indeterminada", "escrito 230, geometria 215 mm (-6%); não decidível pela imagem")},
    10: {k: ("indeterminada", "baseline mediu 1825/1601 mm para 1720 etc.; valores escritos fecham por soma (200+1720+200=2120)")
         for k in ("t3", "t5", "t6", "t7", "t10", "t11", "t12", "t16", "t17", "t19", "t20", "t21", "t22")},
}
# evidência independente de que o valor ESCRITO está correto (soma de cadeia verificada por aritmética)
SOMAS = {10: "200+1720+200=2120; 200+170=370; 200+300=500; 18+294+18=330"}


def size_class(v: float) -> str:
    return "<=60mm" if v <= 60 else ("61-600mm" if v <= 600 else ">600mm")


def _num(t: str):
    t = re.sub(r"[^\d,.]", "", t).replace(".", "").replace(",", ".") if "," in t else re.sub(r"[^\d.]", "", t)
    try:
        return float(t)
    except ValueError:
        return None


def orientation(angle: int) -> str:
    return "horizontal" if angle in (0, 180, 360) else ("vertical" if angle in (90, 270) else "inclinada")


def build(pdf_path) -> dict:
    toks = census(pdf_path)
    items = []
    for t in toks:
        key = t.id.split("-")[1]
        rec = {"id": t.id, "page": t.page, "text": t.text, "bbox": [round(v, 2) for v in t.bbox], "angle": t.angle, "fmt": t.fmt,
               "orientation": orientation(t.angle), "context": t.line_text[:80], "reviewed": t.page in REVIEWED_PAGES}
        if t.page not in REVIEWED_PAGES:
            rec.update(role="nao_revisado", size_class=None, written_value_correct=None, assoc_verdict_baseline=None, evidence="página não revisada")
            items.append(rec); continue
        if key in NOTAS[t.page]:
            role, sub = NOTAS[t.page][key]
            rec.update(role=role, subtype=sub, size_class=None, written_value_correct=True, assoc_verdict_baseline=None,
                       evidence="texto de nota (rótulo/regra)")
        else:
            v = _num(t.text)
            rec.update(role="cota_deslocada" if key in DESLOCADA[t.page] else "cota_regular", size_class=size_class(v) if v is not None else None,
                       value_mm=v, written_value_correct=True,
                       evidence=("soma de cadeia: " + SOMAS[t.page]) if t.page in SOMAS else "revisão visual do overlay (valor escrito assumido correto; desenho real sem erro plantado)")
            ov = ASSOC_OVERRIDE.get(t.page, {}).get(key)
            rec["assoc_verdict_baseline"] = ov[0] if ov else "correta"
            rec["assoc_note"] = ov[1] if ov else "intervalo medido alinhado ao texto no overlay (revisão visual global, não token a token)"
        items.append(rec)
    return {
        "documento": "DETALHAMENTO DE MARCENARIA (SketchUp LayOut, 34 págs)", "independent_review": False,
        "reviewed_pages": list(REVIEWED_PAGES), "tokens_total": len(items), "tokens_revisados": sum(1 for i in items if i["reviewed"]),
        "como_foi_feito": "census independente de tokens + regras + inspeção visual de overlays do baseline nas páginas revisadas; valores escritos assumidos corretos",
        "limitacoes": ["rótulos feitos pelo assistente, sem conferência independente",
                       "veredito de associação 'correta' vem de verificação visual global do overlay, não de cada token",
                       "valores escritos assumidos corretos (não há erro plantado no PDF real)"],
        "tokens": items,
    }


if __name__ == "__main__":
    import sys
    gt = build(sys.argv[1]); Path(sys.argv[2]).write_text(json.dumps(gt, ensure_ascii=False, indent=1))
    print(f"{gt['tokens_total']} tokens, {gt['tokens_revisados']} revisados -> {sys.argv[2]}")
