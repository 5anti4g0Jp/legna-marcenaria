"""Censo INDEPENDENTE de tokens numéricos de um PDF (não usa ingest.dimensions).

Serve de universo para o gabarito: todo token com dígito, com texto original, caixa, ângulo e formato.
"""
from __future__ import annotations

import math, re, warnings
from dataclasses import dataclass, asdict

warnings.filterwarnings("ignore", category=FutureWarning)
import pymupdf  # noqa: E402

INT = re.compile(r"^\d+$")
DEC = re.compile(r"^\d+[.,]\d+$")
THOU = re.compile(r"^\d{1,3}(\.\d{3})+(,\d+)?$")
UNIT = re.compile(r"^\d+([.,]\d+)?(mm|cm|m|w|k|kw|°|%|x)$", re.I)


def classify_format(t: str) -> str:
    if INT.match(t): return "inteiro"
    if DEC.match(t): return "decimal"
    if THOU.match(t): return "milhar"
    if UNIT.match(t): return "unidade"
    return "misto"


@dataclass
class Tok:
    id: str
    page: int
    text: str
    bbox: tuple
    angle: int          # graus, 0 = horizontal; 90 = lido de baixo para cima
    fmt: str
    line_text: str      # texto da linha onde aparece (contexto: ex. "PROFUNDIDADE ... = 34,5 CM")

    def to_dict(self):
        d = asdict(self); d["bbox"] = [round(v, 2) for v in self.bbox]; return d


def census(pdf_path) -> list[Tok]:
    doc = pymupdf.open(pdf_path)
    out: list[Tok] = []
    for pn, pg in enumerate(doc, 1):
        lines = []
        for b in pg.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                ang = round(math.degrees(math.atan2(-ln["dir"][1], ln["dir"][0]))) % 360
                lines.append((pymupdf.Rect(ln["bbox"]), ang, " ".join(sp["text"] for sp in ln["spans"]).strip()))
        n = 0
        for x0, y0, x1, y1, w, *_ in pg.get_text("words"):
            if not re.search(r"\d", w):
                continue
            c = pymupdf.Point((x0 + x1) / 2, (y0 + y1) / 2)
            ang, ctx = 0, w
            for r, a, t in lines:
                if r.contains(c):
                    ang, ctx = a, t; break
            n += 1
            out.append(Tok(f"p{pn}-t{n}", pn, w, (x0, y0, x1, y1), ang, classify_format(w), ctx))
    return out
