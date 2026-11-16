"""EXPERIMENTO (isolado): compara PyMuPDF (referência, AGPL) com pdfplumber/pdfminer (MIT) e pypdfium2 (Apache/BSD) usando o algoritmo CONGELADO da Etapa 0.

O algoritmo é carregado do arquivo congelado (sha verificado) SEM PyMuPDF: um módulo vazio `pymupdf` é injetado só durante o carregamento (o algoritmo usa pymupdf apenas
em anotações de tipo e em `analyze_pdf`, que não é chamado nos backends alternativos). Nenhum arquivo do projeto é alterado.

Uso: python -m experiments.pdf_permissivo.compare [--pdf ...] [--out experiments/pdf_permissivo/results]
"""
from __future__ import annotations

import argparse, hashlib, importlib.util, json, statistics, sys, tempfile, time, types
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
ALGO = REPO / "evaluation" / "baseline_etapa0" / "dimensions.py"
ALGO_SHA = "696a8b83ee411915"
PDF = Path("/root/.claude/uploads/2776f07e-3ad9-5c9f-8cdd-0c5a8af5f4d9/0ad58788-DETALHAMENTO_DE_MARCENARIA_FERNANDA_SERTORIO.pdf")


def carregar(nome: str, sem_pymupdf: bool):
    spec = importlib.util.spec_from_file_location(nome, str(ALGO)); mod = importlib.util.module_from_spec(spec); sys.modules[nome] = mod
    if sem_pymupdf:
        antigo = sys.modules.get("pymupdf"); sys.modules["pymupdf"] = types.ModuleType("pymupdf")
        try: spec.loader.exec_module(mod)
        finally:
            if antigo is not None: sys.modules["pymupdf"] = antigo
            else: sys.modules.pop("pymupdf", None)
    else:
        spec.loader.exec_module(mod)
    return mod


def mediana(f, n=3):
    ts = []
    for _ in range(n):
        t = time.perf_counter(); r = f(); ts.append(time.perf_counter() - t)
    return r, statistics.median(ts)


def centro(b): return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def casar(ref, alt, tol=3.0):
    """Casa cada token de referência com o token alternativo de mesmo texto e centro mais próximo (<= tol pt), sem reutilizar."""
    usados, pares, perdidos = set(), [], []
    for r in ref:
        cr = centro(r.bbox); cand = [(((centro(a.bbox)[0] - cr[0]) ** 2 + (centro(a.bbox)[1] - cr[1]) ** 2) ** .5, i) for i, a in enumerate(alt) if a.text == r.text and i not in usados]
        cand = [c for c in cand if c[0] <= tol]
        if cand:
            d, i = min(cand); usados.add(i); pares.append((r, alt[i], d))
        else: perdidos.append(r)
    extras = [a for i, a in enumerate(alt) if i not in usados]
    return pares, perdidos, extras


def comparar_pagina(ref_pd, alt_pd):
    pares, perdidos, extras = casar(ref_pd.dims, alt_pd.dims)
    st = sum(r.status == a.status for r, a, _ in pares)
    iv = sum(bool((r.interval_pt is None and a.interval_pt is None) or (r.interval_pt and a.interval_pt and all(abs(x - y) <= 0.5 for x, y in zip(r.interval_pt, a.interval_pt)))) for r, a, _ in pares)
    ori = sum(r.orient == a.orient for r, a, _ in pares)
    mm = sum(bool((r.measured_mm is None and a.measured_mm is None) or (r.measured_mm and a.measured_mm and abs(r.measured_mm - a.measured_mm) <= max(0.5, 0.005 * r.measured_mm))) for r, a, _ in pares)
    return {"ref_tokens": len(ref_pd.dims), "alt_tokens": len(alt_pd.dims), "casados": len(pares), "perdidos": [(d.text, [round(v, 1) for v in d.bbox]) for d in perdidos],
            "extras": [(d.text, [round(v, 1) for v in d.bbox]) for d in extras], "mesmo_estado": st, "mesmo_intervalo": iv, "mesma_orientacao": ori, "mesmo_mm_medido": mm,
            "desvio_max_bbox_pt": round(max((d for _, _, d in pares), default=0.0), 2),
            "escalas_ref": [round(s, 4) for s in ref_pd.scales], "escalas_alt": [round(s, 4) for s in alt_pd.scales], "mesmas_escalas": [round(s, 3) for s in ref_pd.scales] == [round(s, 3) for s in alt_pd.scales],
            "cor_dim_ref": ref_pd.dim_color, "cor_dim_alt": alt_pd.dim_color,
            "estados_ref": dict(ref_pd.counts()), "estados_alt": dict(alt_pd.counts()),
            "divergencias_estado": [(r.text, r.status, a.status) for r, a, _ in pares if r.status != a.status][:20]}


def somar(paginas):
    k = ("ref_tokens", "alt_tokens", "casados", "mesmo_estado", "mesmo_intervalo", "mesma_orientacao", "mesmo_mm_medido")
    t = {x: sum(p[x] for p in paginas) for x in k}
    t["perdidos"] = sum(len(p["perdidos"]) for p in paginas); t["extras"] = sum(len(p["extras"]) for p in paginas)
    t["paginas_com_mesma_cor_e_escalas"] = sum(1 for p in paginas if p["mesmas_escalas"] and p["cor_dim_ref"] == p["cor_dim_alt"]); t["paginas"] = len(paginas)
    t["desvio_max_bbox_pt"] = max(p["desvio_max_bbox_pt"] for p in paginas)
    return t


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--pdf", default=str(PDF)); ap.add_argument("--out", default=str(REPO / "experiments" / "pdf_permissivo" / "results"))
    a = ap.parse_args(argv)
    sha = hashlib.sha256(ALGO.read_bytes()).hexdigest()
    assert sha.startswith(ALGO_SHA), "algoritmo congelado alterado"
    import pymupdf, pdfplumber, pypdfium2 as pdfium, importlib.metadata as im
    from evaluation import metrics as M, run_baseline as RB
    from evaluation.synthetic import build_all
    from evaluation.labels_real import build as build_real
    from experiments.pdf_permissivo import backends as B
    DR = carregar("dims_ref", False); DN = carregar("dims_semmupdf", True); M.D = DR
    versoes = {p: im.version(p) for p in ("pymupdf", "pdfplumber", "pdfminer.six", "pypdfium2")}
    out = {"algoritmo_sha256": sha, "versoes": versoes, "pdf": a.pdf}

    # ---------------------------------------------------------------- PDF real: execução e tempos
    doc = pymupdf.open(a.pdf)
    ref_pages, t_ref = mediana(lambda: [DR.analyze_page(pg, i) for i, pg in enumerate(doc, 1)], 3)
    # extração e algoritmo separados para cada backend
    def run_plumber():
        with pdfplumber.open(a.pdf) as pl:
            t0 = time.perf_counter(); ad = [B.plumber_page(p) for p in pl.pages]; te = time.perf_counter() - t0
        t0 = time.perf_counter(); res = [DN.analyze_page(x, i) for i, x in enumerate(ad, 1)]; return res, ad, te, time.perf_counter() - t0
    def run_pdfium():
        d = pdfium.PdfDocument(a.pdf); t0 = time.perf_counter(); ad = [B.pdfium_page(d[i]) for i in range(len(d))]; te = time.perf_counter() - t0
        t0 = time.perf_counter(); res = [DN.analyze_page(x, i) for i, x in enumerate(ad, 1)]; return res, ad, te, time.perf_counter() - t0
    out["desempenho_s"] = {}
    gt = build_real(a.pdf); base = json.loads((REPO / "evaluation" / "results" / "etapa0_baseline.json").read_text()); linhas = {r["id"]: r for r in base["real"]["linhas"]}
    out["referencia_etapa0"] = {"linhas_revisadas": len(linhas), "medicoes (estado medido)": sum(1 for r in linhas.values() if r["status"] in M.MEASURED)}
    t_ref_ext = mediana(lambda: [DR._segments(pg) and DR._numeric_tokens(pg) for pg in doc], 3)[1]
    out["desempenho_s"]["pymupdf"] = {"total_34_pags": round(t_ref, 3), "extracao_aprox": round(t_ref_ext, 3)}
    out["backends"] = {}
    for nome, fn in (("pdfplumber_pdfminer", run_plumber), ("pypdfium2", run_pdfium)):
        try:
            (res, ad, te, ta), tt = mediana(fn, 2)
        except Exception as e:                                             # noqa: BLE001
            out["backends"][nome] = {"erro": f"{type(e).__name__}: {e}"}; continue
        pags = [comparar_pagina(r, x) for r, x in zip(ref_pages, res)]; out["desempenho_s"][nome] = {"total_34_pags": round(tt, 3), "extracao": round(te, 3), "algoritmo": round(ta, 3)}
        # ---- as 113 linhas revisadas (104 medidas?) — mesma lógica de run_real, com o resultado do backend alternativo
        linhas_alt = {};
        for pn, pd in enumerate(res, 1):
            items = [t for t in gt["tokens"] if t["page"] == pn]; al = M.align(items, pd.dims)
            for it in items:
                if not it["reviewed"]: continue
                d = al[it["id"]]; assoc = it.get("assoc_verdict_baseline") if (d is not None and d.status in M.MEASURED) else None
                linhas_alt[it["id"]] = {"status": d.status if d else None, "outcome": M.outcome(it, d, assoc), "medido_mm": round(d.measured_mm, 1) if d and d.measured_mm else None}
        igual_st = sum(linhas[i]["status"] == linhas_alt[i]["status"] for i in linhas); igual_oc = sum(linhas[i]["outcome"] == linhas_alt[i]["outcome"] for i in linhas)
        med = [i for i, r in linhas.items() if r["status"] in M.MEASURED]
        cotas = [i for i, r in linhas.items() if r["role"] in ("cota_regular", "cota_deslocada")]
        out["backends"][nome] = {"paginas": somar(pags), "por_pagina": pags,
                                 "cotas_104": {"total": len(cotas), "medidas_na_referencia": sum(linhas[i]["status"] in M.MEASURED for i in cotas),
                                               "mesmo_estado": sum(linhas[i]["status"] == linhas_alt[i]["status"] for i in cotas), "mesmo_outcome": sum(linhas[i]["outcome"] == linhas_alt[i]["outcome"] for i in cotas)},
                                 "linhas_revisadas": {"total": len(linhas), "mesmo_estado": igual_st, "mesmo_outcome": igual_oc,
                                                      "medicoes_referencia": len(med), "medicoes_mesmo_estado": sum(linhas[i]["status"] == linhas_alt[i]["status"] for i in med),
                                                      "medicoes_mesmo_outcome": sum(linhas[i]["outcome"] == linhas_alt[i]["outcome"] for i in med),
                                                      "diferencas": [{"id": i, "ref": [linhas[i]["status"], linhas[i]["outcome"]], "alt": [linhas_alt[i]["status"], linhas_alt[i]["outcome"]]} for i in linhas if (linhas[i]["status"], linhas[i]["outcome"]) != (linhas_alt[i]["status"], linhas_alt[i]["outcome"])]}}

    # ---------------------------------------------------------------- sintéticos (9 estilos; gerados com PyMuPDF como FIXTURE)
    sint = {}
    with tempfile.TemporaryDirectory() as td:
        docs = build_all(td)
        for s in docs:
            d0 = pymupdf.open(s.path); ref = DR.analyze_page(d0[0], 1)
            reg = {"referencia_pymupdf": ref}
            with pdfplumber.open(s.path) as pl: reg["pdfplumber_pdfminer"] = DN.analyze_page(B.plumber_page(pl.pages[0]), 1)
            reg["pypdfium2"] = DN.analyze_page(B.pdfium_page(pdfium.PdfDocument(s.path)[0]), 1)
            items = [dict(id=x.id, text=x.text, bbox=x.bbox, role=x.role, orientation=x.orientation, planted_error=x.planted_error, interval_pt=x.interval_pt, fmt=x.fmt, size_class=x.size_class) for x in s.truths]
            linha = {}
            for nome, pd in reg.items():
                al = M.align(items, pd.dims); oc = Counter()
                for it, x in zip(items, s.truths):
                    d = al[it["id"]]; assoc = M.synthetic_assoc(it, d) if (d is not None and d.status in M.MEASURED and it["role"].startswith("cota")) else None
                    oc[M.outcome(it, d, assoc)] += 1
                linha[nome] = {"estados": dict(pd.counts()), "outcomes": dict(oc)}
            for nome in ("pdfplumber_pdfminer", "pypdfium2"):
                c = comparar_pagina(ref, reg[nome]); linha[nome]["vs_referencia"] = {k: c[k] for k in ("ref_tokens", "alt_tokens", "casados", "mesmo_estado", "mesmo_intervalo")}; linha[nome]["perdidos"] = c["perdidos"]; linha[nome]["extras"] = c["extras"]
            sint[s.name] = linha
    out["sintetico"] = sint
    Path(a.out).mkdir(parents=True, exist_ok=True); (Path(a.out) / "comparacao.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    return out


if __name__ == "__main__":
    o = main()
    for n, b in o["backends"].items():
        print(n, b.get("erro") or json.dumps({"paginas": b["paginas"], "linhas": {k: v for k, v in b["linhas_revisadas"].items() if k != "diferencas"}, "cotas_104": b["cotas_104"]}, ensure_ascii=False))
    print(json.dumps(o["desempenho_s"]), json.dumps(o["referencia_etapa0"]))
