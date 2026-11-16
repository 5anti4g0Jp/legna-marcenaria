"""Generalização: mesma comparação (token a token) em PDFs ADICIONAIS, sem rótulos de gabarito. Uso: python -m experiments.pdf_permissivo.extra arq.pdf [...]"""
import sys, json
import pymupdf, pdfplumber, pypdfium2 as pdfium
from experiments.pdf_permissivo.compare import carregar, comparar_pagina, somar
from experiments.pdf_permissivo import backends as B

DR = carregar("dims_ref2", False); DN = carregar("dims_nopm2", True)
for path in sys.argv[1:]:
    doc = pymupdf.open(path); ref = [DR.analyze_page(pg, i) for i, pg in enumerate(doc, 1)]; res = {}
    with pdfplumber.open(path) as pl: res["pdfplumber_pdfminer"] = [DN.analyze_page(B.plumber_page(p), i) for i, p in enumerate(pl.pages, 1)]
    d = pdfium.PdfDocument(path); res["pypdfium2"] = [DN.analyze_page(B.pdfium_page(d[i]), i + 1) for i in range(len(d))]
    for n, r in res.items():
        s = somar([comparar_pagina(a, b) for a, b in zip(ref, r)]); print(path.split("/")[-1][:40], len(doc), "págs", n, json.dumps({k: s[k] for k in ("ref_tokens", "alt_tokens", "casados", "mesmo_estado", "perdidos", "extras", "paginas_com_mesma_cor_e_escalas")}))
