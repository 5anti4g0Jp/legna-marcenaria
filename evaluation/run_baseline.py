"""Executa o algoritmo ATUAL (ingest/dimensions.py, sem alterações) contra o gabarito e grava o resultado.

Uso: python -m evaluation.run_baseline [--real PDF] [--out DIR] [--tag NOME]
"""
from __future__ import annotations

import argparse, json, platform, statistics, tempfile, time
from collections import Counter
from datetime import datetime
from pathlib import Path

import pymupdf

import ingest.dimensions as D
from . import metrics as M
from .labels_real import REVIEWED_PAGES, build as build_real
from .synthetic import build_all, manifest

ROOT = Path(__file__).resolve().parent


def use_algorithm(path):
    """Troca o algoritmo avaliado (módulo com a mesma API de ingest/dimensions.py), sem alterar nenhum arquivo."""
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("algoritmo_avaliado", str(path)); mod = importlib.util.module_from_spec(spec)
    sys.modules["algoritmo_avaliado"] = mod; spec.loader.exec_module(mod)
    globals()["D"] = mod; M.D = mod
    return mod


def _time(fn, n=3):
    ts = []
    for _ in range(n):
        t = time.perf_counter(); r = fn(); ts.append(time.perf_counter() - t)
    return r, statistics.median(ts)


def run_synthetic(workdir):
    docs = build_all(workdir); rows = []; per_doc = {}; scales = {}; failures = []
    for s in docs:
        res, t = _time(lambda: D.analyze_pdf(s.path))
        pd = res[0]; items = [dict(**{"id": x.id, "text": x.text, "bbox": x.bbox, "role": x.role, "orientation": x.orientation, "planted_error": x.planted_error,
                                       "interval_pt": x.interval_pt, "fmt": x.fmt, "size_class": x.size_class}) for x in s.truths]
        al = M.align(items, pd.dims)
        for it, x in zip(items, s.truths):
            d = al[it["id"]]
            assoc = M.synthetic_assoc(it, d) if (d is not None and d.status in M.MEASURED and it['role'].startswith('cota')) else None
            oc = M.outcome(it, d, assoc)
            row = {**{k: it[k] for k in ("id", "text", "role", "orientation", "fmt", "size_class")}, "estilo": s.name, "outcome": oc, "status": d.status if d else None,
                   "planted_error": it["planted_error"], "verdade_mm": x.value_mm, "escrito_mm": x.written_mm,
                   "medido_mm": round(d.measured_mm, 2) if d and d.measured_mm else None}
            rows.append(row)
            if oc not in ("confirmada_correta", "ignorada_corretamente", "erro_plantado_detectado", "conflito_falso_alarme_nenhum"):
                failures.append({"origem": f"sintetico/{s.name}", "id": it["id"], "texto": it["text"], "papel": it["role"], "orientacao": it["orientation"], "resultado": oc, "status_baseline": row["status"],
                                 "verdade_mm": x.value_mm, "escrito_mm": x.written_mm, "medido_mm": row["medido_mm"]})
        ts = M.page_scales(pd); true_sc = sorted(set(s.scales.values()))
        det = [e[0] for e in ts.get("escalas", [])]
        ok = [t_ for t_ in true_sc if any(abs(d_ - t_) / t_ <= 0.02 for d_ in det)]
        spur = [d_ for d_ in det if not any(abs(d_ - t_) / t_ <= 0.05 for t_ in true_sc)]
        scales[s.name] = {"verdadeiras": true_sc, "detectadas": det, "corretas": ok, "perdidas": [t_ for t_ in true_sc if t_ not in ok], "espurias": spur}
        per_doc[s.name] = {"tempo_s": round(t, 4), "tokens": len(pd.dims)}
    return docs, rows, per_doc, scales, failures


def run_real(pdf, out_gt):
    gt = build_real(pdf)
    if out_gt is not None:
        Path(out_gt).write_text(json.dumps(gt, ensure_ascii=False, indent=1))
    doc = pymupdf.open(pdf)
    res, t_total = _time(lambda: D.analyze_pdf(pdf))
    rows = []; failures = []; scales = {}; per_page = {}
    for pn, pd in enumerate(res, 1):
        items = [t for t in gt["tokens"] if t["page"] == pn]
        al = M.align(items, pd.dims)
        _, tp = _time(lambda: D.analyze_page(doc[pn - 1], pn), 3); per_page[pn] = round(tp * 1000, 1)
        scales[pn] = M.page_scales(pd)
        for it in items:
            if not it["reviewed"]:
                continue
            d = al[it["id"]]; assoc = it.get("assoc_verdict_baseline") if (d is not None and d.status in M.MEASURED) else None
            oc = M.outcome(it, d, assoc)
            row = {"id": it["id"], "page": pn, "text": it["text"], "role": it["role"], "orientation": it["orientation"], "fmt": it["fmt"], "size_class": it.get("size_class"),
                   "outcome": oc, "status": d.status if d else None, "evidence": it.get("evidence")}
            rows.append(row)
            if oc not in ("confirmada_correta", "ignorada_corretamente"):
                cause = None
                if oc == "perdida_medicao" and it["role"] == "cota_regular": cause = M.diagnose(doc[pn - 1], d)
                elif oc == "perdida_medicao": cause = "cota deslocada (texto fora dos riscos, com chamada)"
                elif oc == "perdida_leitura": cause = {"decimal": "decimal não reconhecido pelo regex (só inteiros)", "unidade": "valor com unidade não reconhecido", "misto": "token misto não reconhecido"}.get(it["fmt"], "texto em span misto/ângulo não suportado")
                elif oc == "confirmada_associacao_incorreta": cause = it.get("assoc_note")
                elif oc == "conflito_falso_alarme": cause = it.get("assoc_note")
                failures.append({"origem": f"real/p{pn}", "id": it["id"], "texto": it["text"], "papel": it["role"], "orientacao": it["orientation"], "resultado": oc,
                                 "status_baseline": row["status"], "causa": cause})
    return gt, res, rows, per_page, scales, failures, t_total


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", default="/root/.claude/uploads/2776f07e-3ad9-5c9f-8cdd-0c5a8af5f4d9/0ad58788-DETALHAMENTO_DE_MARCENARIA_FERNANDA_SERTORIO.pdf")
    ap.add_argument("--out", default=str(ROOT / "results")); ap.add_argument("--tag", default="etapa0_baseline")
    ap.add_argument("--algo", default=str(ROOT.parent / "ingest" / "dimensions.py"), help="arquivo do algoritmo a avaliar")
    ap.add_argument("--no-write-gt", action="store_true", help="não regravar o gabarito (usado ao reavaliar)")
    a = ap.parse_args(argv); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    use_algorithm(a.algo)
    result = {"meta": {"tag": a.tag, "gerado_em": datetime.now().isoformat(timespec="seconds"), "python": platform.python_version(), "pymupdf": pymupdf.__version__,
                       "testes_dimensions_sha256": M.sha256(ROOT.parent / "tests_py" / "test_dimensions.py"),
                       "algoritmo": {"arquivo": str(Path(a.algo).resolve().relative_to(ROOT.parent)) if Path(a.algo).resolve().is_relative_to(ROOT.parent) else a.algo, "sha256": M.sha256(a.algo), "TOL": D.TOL, "MIN_CLUSTER": D.MIN_CLUSTER,
                                     "TICK_MAX": D.TICK_MAX, "END_NEAR": D.END_NEAR, "janela_busca_pt": 14.0, "alterado_nesta_etapa": False}}}
    with tempfile.TemporaryDirectory() as tmp:
        docs, srows, sdoc, sscale, sfail = run_synthetic(tmp)
    if not a.no_write_gt:
        (ROOT / "groundtruth" / "synthetic_manifest.json").write_text(json.dumps(manifest(docs), ensure_ascii=False, indent=1, default=str))
    crows = [r for r in srows if r["role"].startswith("cota")]      # tabelas por tipo contam só COTAS; não-cotas ficam em por_papel
    result["sintetico"] = {"itens": len(srows), "por_estilo": M.aggregate(crows, "estilo"), "por_papel": M.aggregate(srows, "role"), "por_orientacao": M.aggregate(crows, "orientation"),
                           "por_formato": M.aggregate(crows, "fmt"), "por_tamanho": M.aggregate(crows, "size_class"), "escalas": sscale, "tempo": sdoc, "linhas": srows}
    failures = list(sfail)
    if Path(a.real).exists():
        gt, res, rrows, per_page, rscale, rfail, t_total = run_real(a.real, None if a.no_write_gt else ROOT / "groundtruth" / "real_fernanda.json")
        multi = [p for p, s in rscale.items() if s.get("multiplas_proximas")]; esp = {p: s["espurias"] for p, s in rscale.items() if s.get("espurias")}
        status_all = Counter(d.status for pd in res for d in pd.dims)
        result["real"] = {"documento": gt["documento"], "paginas": len(res), "tokens_total": gt["tokens_total"], "tokens_revisados": gt["tokens_revisados"], "paginas_revisadas": list(REVIEWED_PAGES),
                          "revisao_independente": False, "por_papel": M.aggregate(rrows, "role"), "por_orientacao": M.aggregate([r for r in rrows if r["role"].startswith("cota")], "orientation"),
                          "por_tamanho": M.aggregate([r for r in rrows if r["role"].startswith("cota")], "size_class"), "por_formato": M.aggregate(rrows, "fmt"),
                          "estados_baseline_todas_as_paginas": dict(status_all), "paginas_com_varias_escalas_proximas": multi, "escalas_espurias_por_pagina": esp,
                          "tempo": {"total_s": round(t_total, 3), "por_pagina_ms": per_page, "mediana_pagina_ms": round(statistics.median(per_page.values()), 1)}, "linhas": rrows}
        failures += rfail
    else:
        result["real"] = None
    result["falhas"] = failures
    (out / f"{a.tag}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str))
    print(f"-> {out / (a.tag + '.json')}  | falhas catalogadas: {len(failures)}")
    return result


if __name__ == "__main__":
    main()
