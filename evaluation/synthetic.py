"""Desenhos sintéticos de cotas com RESPOSTA EXATA por construção (determinísticos).

Cada documento declara a verdade: valor geométrico real (mm), valor escrito, papel, orientação, intervalo
em pontos, escala da vista e se há ERRO PLANTADO (texto diferente da geometria).
Estilos modelados a partir de convenções comuns; NÃO provam compatibilidade com Promob/AutoCAD/etc.
"""
from __future__ import annotations

import math, re, warnings
from dataclasses import dataclass, field, asdict
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
import pymupdf  # noqa: E402

from .census import census

RED, BLACK, BLUE = (0.71, 0, 0), (0, 0, 0), (0, 0, 0.8)


@dataclass
class STruth:
    id: str
    text: str
    role: str                       # cota_regular | cota_deslocada | nao_cota
    orientation: str                # horizontal | vertical | inclinada
    value_mm: float | None          # valor GEOMÉTRICO verdadeiro (None p/ não-cota)
    written_mm: float | None        # valor que o texto expressa (None p/ não-cota)
    interval_pt: float | None       # comprimento verdadeiro do intervalo medido
    scale: float | None
    view: str
    planted_error: bool = False
    fmt: str = "inteiro"
    size_class: str | None = None
    anchor: tuple = (0, 0)          # centro aproximado do texto
    bbox: tuple | None = None       # preenchido a partir do PDF gerado
    component: str | None = None    # componente a que a cota pertence (para etapas futuras)


@dataclass
class SDoc:
    name: str
    style: str
    path: str
    truths: list[STruth] = field(default_factory=list)
    scales: dict = field(default_factory=dict)   # view -> mm/pt verdadeiro


def _size_class(v):
    return None if v is None else ("<=60mm" if v <= 60 else ("61-600mm" if v <= 600 else ">600mm"))


def _parse(text: str) -> float | None:
    t = text.strip().lower()
    unit = 10.0 if t.endswith("cm") else 1.0
    t = re.sub(r"(mm|cm)$", "", t)
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", t): t = t.replace(".", "")
    t = t.replace(",", ".")
    try: return float(t) * unit
    except ValueError: return None


def _fmt(text: str) -> str:
    t = text.lower()
    if t.endswith(("mm", "cm")): return "unidade"
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", t): return "milhar"
    if re.fullmatch(r"\d+[.,]\d+", t): return "decimal"
    return "inteiro"


STYLES = {
    "lay": dict(color=RED, width=0.5, tick="perp", ext=True, text="above", fs=9, off=3.0),
    "lay_abaixo": dict(color=RED, width=0.5, tick="perp", ext=True, text="below", fs=12, off=17.8),
    "cad": dict(color=BLACK, width=0.35, tick="slash", ext=True, text="above", fs=8, off=2.0),
    "setas": dict(color=BLUE, width=0.5, tick="arrow", ext=False, text="on_line", fs=9, off=0),
}


class Builder:
    def __init__(self, name, style_name):
        self.doc = pymupdf.open(); self.page = self.doc.new_page(width=600, height=800)
        self.sd = SDoc(name, style_name, ""); self.n = 0

    def outline(self, rect, color=(0, 0, 0)):
        self.page.draw_rect(pymupdf.Rect(*rect), color=color, width=0.8)

    def dim(self, p0, p1, text, style, *, scale, view="v1", role="cota_regular", planted=False, true_mm=None, component=None,
            side=1, text_out=False):
        """Cota entre p0 e p1 (pontos da página). `true_mm` = valor geométrico real (padrão: comprimento*escala)."""
        st = STYLES[style] if isinstance(style, str) else style
        L = math.dist(p0, p1); u = ((p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L); nrm = (-u[1] * side, u[0] * side)
        col, w = st["color"], st["width"]; sh = self.page.new_shape()
        mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        fs = st["fs"]; tw = pymupdf.get_text_length(text, fontsize=fs)
        gap = st["text"] == "on_line"
        segs = [(p0, p1)]
        if gap:
            h = tw / 2 + 2; segs = [(p0, (mid[0] - u[0] * h, mid[1] - u[1] * h)), ((mid[0] + u[0] * h, mid[1] + u[1] * h), p1)]
        for a, b in segs: sh.draw_line(a, b)
        for p in (p0, p1):
            if st["tick"] == "perp": sh.draw_line((p[0] - nrm[0] * 4, p[1] - nrm[1] * 4), (p[0] + nrm[0] * 4, p[1] + nrm[1] * 4))
            elif st["tick"] == "slash":
                d = ((u[0] + nrm[0]) * 3, (u[1] + nrm[1]) * 3); sh.draw_line((p[0] - d[0], p[1] - d[1]), (p[0] + d[0], p[1] + d[1]))
            if st["ext"]: sh.draw_line((p[0] + nrm[0] * 3, p[1] + nrm[1] * 3), (p[0] - nrm[0] * 30, p[1] - nrm[1] * 30))
        sh.finish(color=col, width=w); sh.commit()
        if st["tick"] == "arrow":
            for p, s in ((p0, 1), (p1, -1)):
                tri = [p, (p[0] + s * u[0] * 7 + nrm[0] * 2, p[1] + s * u[1] * 7 + nrm[1] * 2), (p[0] + s * u[0] * 7 - nrm[0] * 2, p[1] + s * u[1] * 7 - nrm[1] * 2)]
                sh2 = self.page.new_shape(); sh2.draw_polyline(tri + [tri[0]]); sh2.finish(color=col, fill=col, width=0.3); sh2.commit()
        # texto: centralizado ao longo da linha, deslocado em `off` pela normal
        ang = math.degrees(math.atan2(u[1], u[0])) % 180
        off = st["off"]
        cx, cy = mid[0] + nrm[0] * (-off if st["text"] == "above" else off) * (1 if st["text"] != "on_line" else 0), mid[1] + nrm[1] * (-off if st["text"] == "above" else off) * (1 if st["text"] != "on_line" else 0)
        if text_out:   # texto deslocado para fora dos riscos (chamada)
            cx, cy = p1[0] + u[0] * 14 + nrm[0] * 9, p1[1] + u[1] * 14 + nrm[1] * 9
            sh3 = self.page.new_shape(); sh3.draw_curve(p1, (p1[0] + u[0] * 4 + nrm[0] * 6, p1[1] + u[1] * 4 + nrm[1] * 6), (cx - u[0] * 4, cy - u[1] * 4)); sh3.finish(color=col, width=0.4); sh3.commit()
        if abs(ang) < 1 or abs(ang - 180) < 1:
            self.page.insert_text((cx - tw / 2, cy + fs * 0.32), text, fontsize=fs, color=BLACK); orient = "horizontal"
        elif abs(ang - 90) < 1:
            self.page.insert_text((cx + fs * 0.32, cy + tw / 2), text, fontsize=fs, color=BLACK, rotate=90); orient = "vertical"
        else:
            bx, by = cx - tw / 2, cy + fs * 0.32
            self.page.insert_text((bx, by), text, fontsize=fs, color=BLACK, morph=(pymupdf.Point(cx, cy), pymupdf.Matrix(-ang)))
            orient = "inclinada"
        val = true_mm if true_mm is not None else L * scale
        self.n += 1
        self.sd.truths.append(STruth(f"{self.sd.name}-d{self.n}", text, role, orient, round(val, 3), _parse(text), round(L, 3), scale, view, planted,
                                     _fmt(text), _size_class(_parse(text)), (round(cx, 1), round(cy, 1)), None, component))
        self.sd.scales[view] = scale

    def note(self, xy, text, subtype="nota"):
        """Nota livre. A verdade é registrada no TOKEN que tem dígito (ex.: 'REV 3' -> '3')."""
        self.page.insert_text(xy, text, fontsize=9, color=BLACK)
        words = text.split(); idx = next(i for i, w in enumerate(words) if re.search(r"\d", w)); tok = words[idx]
        pre = pymupdf.get_text_length(" ".join(words[:idx]) + (" " if idx else ""), fontsize=9)
        cx = xy[0] + pre + pymupdf.get_text_length(tok, fontsize=9) / 2
        self.n += 1
        self.sd.truths.append(STruth(f"{self.sd.name}-n{self.n}", tok, "nao_cota", "horizontal", None, None, None, None, "-", False, _fmt(tok), None,
                                     (round(cx, 1), xy[1] - 3), None, subtype))

    def save(self, outdir: Path) -> SDoc:
        p = outdir / f"{self.sd.name}.pdf"; self.doc.save(p); self.sd.path = str(p)
        toks = census(p)
        for t in self.sd.truths:                       # bbox real do token no PDF gerado
            best = min((k for k in toks if k.text.split()[0] == t.text.split()[0] or k.text == t.text), key=lambda k: math.dist(t.anchor, ((k.bbox[0] + k.bbox[2]) / 2, (k.bbox[1] + k.bbox[3]) / 2)), default=None)
            if best and math.dist(t.anchor, ((best.bbox[0] + best.bbox[2]) / 2, (best.bbox[1] + best.bbox[3]) / 2)) < 15: t.bbox = tuple(round(v, 2) for v in best.bbox)
        return self.sd


def _frame(b: Builder, style, scale, ox=100, oy=300, W=400, H=200, vals=(1000, 600, 400), view="v1", prefix=""):
    """Caixa com cadeia horizontal (parciais + total) e duas verticais."""
    b.outline((ox, oy, ox + W, oy + H))
    for t in b.sd.truths[:0]: pass
    x = ox
    L = lambda mm: mm / scale
    total = sum(vals); wtot = L(total)
    b.dim((ox, oy + H + 30), (ox + wtot, oy + H + 30), str(total), style, scale=scale, view=view, component="total")
    xx = ox
    for v in vals:
        b.dim((xx, oy + H + 12), (xx + L(v), oy + H + 12), str(v), style, scale=scale, view=view, component="parcial")
        xx += L(v)
    b.dim((ox - 14, oy), (ox - 14, oy + L(800)), "800", style, scale=scale, view=view, component="altura")
    b.dim((ox - 34, oy), (ox - 34, oy + L(450)), "450", style, scale=scale, view=view, component="vao")


def build_all(outdir: str | Path) -> list[SDoc]:
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True); docs = []
    for name, style, scale in (("lay_acima", "lay", 4.0), ("lay_abaixo", "lay_abaixo", 4.0), ("cad_preto_slash", "cad", 4.0), ("setas_texto_na_linha", "setas", 4.0)):
        b = Builder(name, style); _frame(b, style, scale)
        if name == "lay_acima":
            b.note((60, 120), "10 UNIDADES", "quantidade"); b.note((200, 120), "3000K", "temperatura_cor"); b.note((330, 120), "REV 3", "revisao")
            # números SOLTOS (span só com dígitos), que o baseline considera candidatos: um colado à linha de cota, um isolado
            b.note((340, 526), "3", "marca_de_nota_junto_a_cota"); b.note((150, 100), "2", "numero_isolado")
        docs.append(b.save(out))
    # decimais, milhar e unidades
    b = Builder("decimais_unidades", "lay")
    for i, (txt, mm) in enumerate((("12,5", 12.5), ("1.200", 1200), ("45cm", 450), ("7.5", 7.5), ("300mm", 300))):
        y = 60 + i * 40; Lpt = 80.0; sc = mm / Lpt          # cada cota tem escala própria: 80 pt de comprimento, verdade geométrica = valor escrito
        b.dim((120, y), (120 + Lpt, y), txt, "lay", scale=sc, view=f"v{i}", true_mm=mm)
    docs.append(b.save(out))
    # inclinada
    b = Builder("inclinada", "lay")
    for i, (ang, mm) in enumerate(((30, 600), (45, 800), (120, 500))):
        L = mm / 4.0; a = math.radians(ang); p0 = (150, 200 + i * 150); p1 = (p0[0] + L * math.cos(a), p0[1] - L * math.sin(a))
        b.dim(p0, p1, str(mm), "lay", scale=4.0)
    docs.append(b.save(out))
    # duas escalas na mesma página + não-cotas
    b = Builder("duas_escalas", "lay")
    for view, sc, ox in (("vistaA", 4.0, 40), ("vistaB", 6.5, 330)):
        b.outline((ox, 150, ox + 220, 300))
        for i, mm in enumerate((800, 600, 400)):
            L = mm / sc; b.dim((ox, 320 + i * 22), (ox + L, 320 + i * 22), str(mm), "lay", scale=sc, view=view)
    b.note((40, 600), "ARMARIO 2", "titulo"); b.note((200, 600), "10 UNIDADES", "quantidade")
    docs.append(b.save(out))
    # erros plantados (texto != geometria)
    b = Builder("erro_plantado", "lay"); sc = 5.0
    cases = [("1000", 1000, False), ("450", 450, False), ("764", 764, False),
             ("430", 450, True), ("100", 1000, True), ("746", 764, True), ("1010", 1000, True), ("600", 600, False)]
    for i, (txt, true_mm, planted) in enumerate(cases):
        y = 60 + i * 34; b.dim((100, y), (100 + true_mm / sc, y), txt, "lay", scale=sc, planted=planted, true_mm=true_mm)
    docs.append(b.save(out))
    # cotas deslocadas (chamada/leader) — espessuras pequenas
    b = Builder("deslocada_chamada", "lay"); sc = 2.0
    for i, (txt, mm) in enumerate((("15", 15), ("18", 18), ("25", 25), ("15", 15))):
        y = 80 + i * 40; Lp = mm / sc; b.dim((200, y), (200 + Lp, y), txt, "lay", scale=sc, role="cota_deslocada", text_out=True)
    b.outline((120, 300, 420, 420)); b.dim((120, 440), (120 + 600 / 2.0, 440), "600", "lay", scale=2.0)   # 600 mm a 2,0 mm/pt = 300 pt
    b.dim((120, 460), (120 + 150, 460), "300", "lay", scale=2.0); b.dim((120 + 150, 460), (120 + 300, 460), "300", "lay", scale=2.0)
    docs.append(b.save(out))
    return docs


def manifest(docs: list[SDoc]) -> dict:
    return {"docs": [dict(name=d.name, style=d.style, scales=d.scales, truths=[asdict(t) for t in d.truths]) for d in docs]}
