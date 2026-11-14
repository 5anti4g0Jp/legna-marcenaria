"""Verificação geométrica de cotas em PDF vetorial.

Para cada número escrito no desenho, procura a linha de cota que o acompanha e mede, no próprio
desenho, o intervalo entre as marcas (extensões). Como todas as cotas de uma vista compartilham a
mesma escala (mm por ponto), o valor escrito pode ser CONFERIDO contra a geometria:

  confirmado    valor escrito == comprimento medido x escala da vista (tolerância 2%)
  confirmado_local  não bate com a escala dominante, mas outra cota PRÓXIMA (<= 250 pt) concorda com a mesma
                escala (vista em escala própria, ex.: planta e elevação na mesma página)
  conflito      o valor escrito não bate com a geometria: possível leitura errada ou cota "mentirosa";
                a medida geométrica vira SUGESTÃO, nunca dado confirmado
  sem_medicao   não foi possível associar o número a uma linha de cota (ex.: texto com chamada/leader)
  sem_escala    a página não tem cotas suficientes para estabelecer a escala

Não depende de IA nem de OCR. Só vale para PDF com geometria vetorial (não para imagem escaneada).
"""
from __future__ import annotations
import re, statistics, warnings
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
import pymupdf  # noqa: E402

NUM = re.compile(r"^\d{1,5}$")
TOL = 0.02            # tolerância relativa para "confirmado"
MIN_CLUSTER = 3       # cotas necessárias para considerar uma escala válida


@dataclass
class Dimension:
    page: int
    text: str
    value: float
    orient: str                                 # "h" | "v"
    bbox: tuple[float, float, float, float]
    interval_pt: tuple[float, float] | None = None
    length_pt: float | None = None
    scale: float | None = None                  # mm/pt da vista a que pertence
    measured_mm: float | None = None
    status: str = "sem_medicao"
    suggestion_mm: float | None = None


@dataclass
class PageDims:
    page: int
    dim_color: tuple[float, ...] | None
    scales: list[float] = field(default_factory=list)   # medianas das escalas válidas (mm/pt)
    dims: list[Dimension] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return dict(Counter(d.status for d in self.dims))


def _segments(page: "pymupdf.Page"):
    """Segmentos alinhados aos eixos: (cor, x0, y0, x1, y1)."""
    out = []
    for p in page.get_drawings():
        c = p.get("color")
        if c is None:
            continue
        col = tuple(round(x, 2) for x in c)
        for it in p["items"]:
            if it[0] == "l":
                out.append((col, it[1].x, it[1].y, it[2].x, it[2].y))
            elif it[0] == "re":
                r = it[1]
                out += [(col, r.x0, r.y0, r.x1, r.y0), (col, r.x1, r.y0, r.x1, r.y1),
                        (col, r.x1, r.y1, r.x0, r.y1), (col, r.x0, r.y1, r.x0, r.y0)]
    return out


def _numeric_tokens(page: "pymupdf.Page"):
    toks = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            dx, dy = ln["dir"]
            for sp in ln["spans"]:
                t = sp["text"].strip()
                if NUM.match(t) and int(t) > 0:
                    toks.append((t, tuple(sp["bbox"]), "h" if abs(dx) > abs(dy) else "v"))
    return toks


def _dimension_color(tokens, segs):
    """Cor das linhas que mais aparecem coladas aos números = cor das cotas desta página."""
    votes: Counter = Counter()
    for _t, (x0, y0, x1, y1), _o in tokens:
        for col, sx0, sy0, sx1, sy1 in segs:
            if min(sx0, sx1) - 14 <= x1 and max(sx0, sx1) + 14 >= x0 and min(sy0, sy1) - 14 <= y1 and max(sy0, sy1) + 14 >= y0:
                votes[col] += 1
    return votes.most_common(1)[0][0] if votes else None


TICK_MAX = 14.0       # comprimento máximo (pt) de um risco/marca de cota
END_NEAR = 6.0        # extensão só vale se a linha de cota passa a <= 6 pt de uma das pontas


def _is_boundary(s, axis: str, pos: float) -> bool:
    """s = (cor,x0,y0,x1,y1). `axis`: eixo da linha de cota ('h' ou 'v'); `pos` = coordenada dela no eixo perpendicular.
    Marca válida: segmento curto (risco, inclusive diagonal) OU extensão que termina rente à linha de cota.
    Rejeita linhas longas que apenas CRUZAM a linha de cota (ex.: outra cota)."""
    _c, x0, y0, x1, y1 = s
    perp0, perp1 = (y0, y1) if axis == "h" else (x0, x1)
    if not (min(perp0, perp1) - 1.5 <= pos <= max(perp0, perp1) + 1.5):
        return False                                     # não alcança a linha de cota
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if length <= TICK_MAX:
        return True
    return min(abs(pos - perp0), abs(pos - perp1)) <= END_NEAR


def _measure(tok, segs):
    t, (x0, y0, x1, y1), o = tok
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if o == "h":
        lines = [s for s in segs if abs(s[2] - s[4]) < 0.3 and abs(s[1] - s[3]) > 3 and min(s[1], s[3]) <= cx <= max(s[1], s[3]) and abs(s[2] - cy) <= 14]
        if not lines:
            return None
        ln = min(lines, key=lambda s: abs(s[2] - cy)); pos = ln[2]; a0, a1 = sorted((ln[1], ln[3])); c = cx
        ticks = sorted({round((s[1] + s[3]) / 2, 1) for s in segs
                        if s is not ln and abs(s[2] - s[4]) > 0.3          # não paralelo à linha de cota (vertical ou diagonal)
                        and _is_boundary(s, "h", pos) and a0 - 2 <= (s[1] + s[3]) / 2 <= a1 + 2})
    else:
        lines = [s for s in segs if abs(s[1] - s[3]) < 0.3 and abs(s[2] - s[4]) > 3 and min(s[2], s[4]) <= cy <= max(s[2], s[4]) and abs(s[1] - cx) <= 14]
        if not lines:
            return None
        ln = min(lines, key=lambda s: abs(s[1] - cx)); pos = ln[1]; a0, a1 = sorted((ln[2], ln[4])); c = cy
        ticks = sorted({round((s[2] + s[4]) / 2, 1) for s in segs
                        if s is not ln and abs(s[1] - s[3]) > 0.3          # não paralelo à linha de cota (horizontal ou diagonal)
                        and _is_boundary(s, "v", pos) and a0 - 2 <= (s[2] + s[4]) / 2 <= a1 + 2})
    left = [x for x in ticks if x <= c]; right = [x for x in ticks if x > c]
    if not left or not right:
        return None
    return left[-1], right[0]


def _cluster(ratios: list[float]) -> list[list[float]]:
    out: list[list[float]] = []
    for r in sorted(ratios):
        if out and abs(r - statistics.median(out[-1])) / statistics.median(out[-1]) <= TOL:
            out[-1].append(r)
        else:
            out.append([r])
    return out


def analyze_page(page: "pymupdf.Page", index: int) -> PageDims:
    toks = _numeric_tokens(page)
    segs = _segments(page)
    col = _dimension_color(toks, segs)
    pd = PageDims(index, col)
    dsegs = [s for s in segs if s[0] == col] if col else []
    for tok in toks:
        t, bb, o = tok
        d = Dimension(index, t, float(t), o, bb)
        iv = _measure(tok, dsegs) if dsegs else None
        if iv:
            d.interval_pt = iv; d.length_pt = iv[1] - iv[0]
        pd.dims.append(d)
    measured = [d for d in pd.dims if d.length_pt and d.length_pt > 0]
    clusters = [c for c in _cluster([d.value / d.length_pt for d in measured]) if len(c) >= MIN_CLUSTER]
    pd.scales = sorted(statistics.median(c) for c in clusters)
    def center(d):
        return ((d.bbox[0] + d.bbox[2]) / 2, (d.bbox[1] + d.bbox[3]) / 2)

    for d in measured:
        ratio = d.value / d.length_pt
        if pd.scales:
            best = min(pd.scales, key=lambda s: abs(ratio - s))
            d.scale = best
            d.measured_mm = d.length_pt * best
            if abs(ratio - best) / best <= TOL:
                d.status = "confirmado"; continue
        # escala local: outra cota próxima que concorda com a mesma razão mm/pt
        cx, cy = center(d)
        partner = next((o for o in measured if o is not d and abs(o.value / o.length_pt - ratio) / ratio <= TOL
                        and ((center(o)[0] - cx) ** 2 + (center(o)[1] - cy) ** 2) ** 0.5 <= 250), None)
        if partner:
            d.status = "confirmado_local"; d.scale = ratio; d.measured_mm = d.value
        elif pd.scales:
            d.status = "conflito"
            d.suggestion_mm = round(d.length_pt * d.scale)
        else:
            d.status = "sem_escala"
    return pd


def analyze_pdf(path: str | Path) -> list[PageDims]:
    doc = pymupdf.open(path)
    return [analyze_page(pg, i) for i, pg in enumerate(doc, 1)]


def summarize(pages: list[PageDims]) -> dict:
    c: Counter = Counter()
    for p in pages:
        c.update(d.status for d in p.dims)
    return dict(c)


if __name__ == "__main__":
    import sys, json
    res = analyze_pdf(sys.argv[1])
    print(json.dumps({"resumo": summarize(res), "conflitos": [asdict(d) for p in res for d in p.dims if d.status == "conflito"]}, ensure_ascii=False, indent=1))
