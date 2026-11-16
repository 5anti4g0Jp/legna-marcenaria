"""EXPERIMENTO (isolado): extrai geometria e texto com bibliotecas PERMISSIVAS e entrega ao algoritmo congelado uma "página" com a mesma interface mínima
que ele usa do PyMuPDF (`get_drawings()` e `get_text("dict")`).  Não altera ingest/, leitores, baseline nem algoritmo.

Backends:
  pymupdf   referência (AGPL) — só para comparar
  plumber   pdfplumber 0.11 / pdfminer.six (MIT)
  pdfium    pypdfium2 5.x (Apache-2.0 ou BSD-3; PDFium é BSD-3)
"""
from __future__ import annotations

import ctypes, math

import pypdfium2 as pdfium
import pypdfium2.raw as raw


class Pt:
    __slots__ = ("x", "y")

    def __init__(self, x, y): self.x, self.y = float(x), float(y)


class Rc:
    __slots__ = ("x0", "y0", "x1", "y1")

    def __init__(self, x0, y0, x1, y1): self.x0, self.y0, self.x1, self.y1 = float(x0), float(y0), float(x1), float(y1)


class AdaptedPage:
    def __init__(self, drawings, spans):
        self._d = drawings
        self._b = [{"lines": [{"dir": s["dir"], "spans": [{"text": s["text"], "bbox": s["bbox"]}]} for s in spans]}]
        self.spans = spans

    def get_drawings(self): return self._d

    def get_text(self, mode):
        assert mode == "dict", mode
        return {"blocks": self._b}


def norm_color(c):
    """Normaliza para RGB 0-1 arredondado a 2 casas (como o PyMuPDF entrega)."""
    if c is None: return None
    if isinstance(c, (int, float)): c = (c,)              # pdfplumber devolve escalar em alguns PDFs (cinza)
    c = tuple(float(x) for x in c)
    if len(c) == 1: c = (c[0],) * 3
    elif len(c) == 4:
        C, M, Y, K = c; c = ((1 - C) * (1 - K), (1 - M) * (1 - K), (1 - Y) * (1 - K))
    elif len(c) != 3: return None
    return tuple(round(x, 2) for x in c)


def build_spans(chars):
    """Une caracteres consecutivos (ordem do stream) com mesma fonte/tamanho e ângulo e contíguos ao longo da direção do texto num 'span' (espelha o agrupamento do PyMuPDF).
    chars: dict(text,x0,x1,top,bottom,size,font,ang)  — ang = direção do texto em radianos, y para cima (convenção PDF)."""
    spans, cur = [], None
    for c in chars:
        ok = False
        if cur is not None and cur["font"] == c["font"] and abs(cur["size"] - c["size"]) < 0.11 and abs(cur["ang"] - c["ang"]) < 0.02:
            p = cur["last"]; dx, dy = math.cos(c["ang"]), -math.sin(c["ang"])
            vx, vy = (c["x0"] + c["x1"]) / 2 - (p["x0"] + p["x1"]) / 2, (c["top"] + c["bottom"]) / 2 - (p["top"] + p["bottom"]) / 2
            along, perp = vx * dx + vy * dy, abs(vx * dy - vy * dx); sz = max(c["size"], 1.0)
            ok = 0.1 * sz <= abs(along) <= 1.4 * sz and perp <= 0.3 * sz         # abs: texto de cima p/ baixo ou de baixo p/ cima
        if ok:
            cur["text"] += c["text"]; cur["bbox"] = (min(cur["bbox"][0], c["x0"]), min(cur["bbox"][1], c["top"]), max(cur["bbox"][2], c["x1"]), max(cur["bbox"][3], c["bottom"])); cur["last"] = c
        else:
            if cur: spans.append(cur)
            cur = {"text": c["text"], "bbox": (c["x0"], c["top"], c["x1"], c["bottom"]), "font": c["font"], "size": c["size"], "ang": c["ang"], "last": c}
    if cur: spans.append(cur)
    for s in spans:
        s["dir"] = (math.cos(s["ang"]), -math.sin(s["ang"])); s.pop("last", None)
    return spans


# ----------------------------------------------------------------------------------------------- pdfplumber (MIT)
def plumber_page(plpage) -> AdaptedPage:
    dr = []
    for kind in ("line", "rect", "curve"):
        for o in plpage.objects.get(kind, []):
            col = norm_color(o.get("stroking_color")) if o.get("stroke") else None
            if col is None and o.get("stroke") and o.get("stroking_color") is None: col = (0.0, 0.0, 0.0)
            if kind == "rect":
                it = [("re", Rc(o["x0"], o["top"], o["x1"], o["bottom"]))]
            elif kind == "line":
                (xa, ya), (xb, yb) = o["pts"][0], o["pts"][-1]; it = [("l", Pt(xa, ya), Pt(xb, yb))]
            else:
                it = []; cur = start = None
                for cmd in o.get("path", []):
                    op = cmd[0]
                    if op == "m": cur = start = cmd[1]
                    elif op == "l" and cur is not None: it.append(("l", Pt(*cur), Pt(*cmd[1]))); cur = cmd[1]
                    elif op == "c": cur = cmd[-1]                                   # curva: o algoritmo ignora itens 'c'
                    elif op == "h" and cur is not None and start is not None and cur != start: it.append(("l", Pt(*cur), Pt(*start))); cur = start
            dr.append({"color": col, "items": it})
    chars = []
    for c in plpage.chars:
        m = c["matrix"]; ang = math.atan2(m[1], m[0]) % math.pi
        chars.append({"text": c["text"], "x0": c["x0"], "x1": c["x1"], "top": c["top"], "bottom": c["bottom"], "size": round(c["size"], 2), "font": c["fontname"], "ang": ang})
    return AdaptedPage(dr, build_spans(chars))


# ----------------------------------------------------------------------------------------------- pypdfium2 (Apache-2.0/BSD-3)
def pdfium_page(pg: "pdfium.PdfPage") -> AdaptedPage:
    H = pg.get_size()[1]; dr = []
    for ob in pg.get_objects(filter=[raw.FPDF_PAGEOBJ_PATH]):
        o = ob.raw
        fill = ctypes.c_int(); stroke = ctypes.c_int(); raw.FPDFPath_GetDrawMode(o, fill, stroke)
        if not stroke.value: continue
        r, g, b, a = (ctypes.c_uint() for _ in range(4)); raw.FPDFPageObj_GetStrokeColor(o, r, g, b, a)
        col = tuple(round(v.value / 255, 2) for v in (r, g, b))
        mt = raw.FS_MATRIX(); raw.FPDFPageObj_GetMatrix(o, mt)
        n = raw.FPDFPath_CountSegments(o); pts = []; items = []; start = None
        for i in range(n):
            sg = raw.FPDFPath_GetPathSegment(o, i); t = raw.FPDFPathSegment_GetType(sg)
            x = ctypes.c_float(); y = ctypes.c_float(); raw.FPDFPathSegment_GetPoint(sg, x, y)
            X = mt.a * x.value + mt.c * y.value + mt.e; Y = H - (mt.b * x.value + mt.d * y.value + mt.f); p = (X, Y)
            if t == raw.FPDF_SEGMENT_MOVETO: pts = [p]; start = p
            elif t == raw.FPDF_SEGMENT_LINETO and pts:
                items.append(("l", Pt(*pts[-1]), Pt(*p))); pts.append(p)
            elif t == raw.FPDF_SEGMENT_BEZIERTO: pts = [p]                        # curva: o algoritmo ignora; só avança o ponto corrente
            if raw.FPDFPathSegment_GetClose(sg) and pts and start and pts[-1] != start:
                items.append(("l", Pt(*pts[-1]), Pt(*start))); pts = [start]
        dr.append({"color": col, "items": items})
    tp = pg.get_textpage(); chars = []; tpr = tp.raw
    for i in range(tp.count_chars()):
        if raw.FPDFText_IsGenerated(tpr, i): continue
        u = raw.FPDFText_GetUnicode(tpr, i); ch = chr(u)
        lb = raw.FS_RECTF(); raw.FPDFText_GetLooseCharBox(tpr, i, lb)            # caixa 'solta' (altura da fonte), mais próxima da do PyMuPDF
        l, rr, bb, tt = (ctypes.c_double(v) for v in (lb.left, lb.right, lb.bottom, lb.top))
        mt = raw.FS_MATRIX(); raw.FPDFText_GetMatrix(tpr, i, mt)
        ang = math.atan2(mt.b, mt.a) % math.pi                       # direção pela matriz do texto (FPDFText_GetCharAngle erra com eixo y invertido, comum no LayOut)
        sz = raw.FPDFText_GetFontSize(tpr, i)
        buf = ctypes.create_string_buffer(256); fl = ctypes.c_int(); raw.FPDFText_GetFontInfo(tpr, i, buf, 256, fl)
        chars.append({"text": ch, "x0": l.value, "x1": rr.value, "top": H - tt.value, "bottom": H - bb.value, "size": round(abs(tt.value - bb.value), 1), "font": buf.value.decode("latin-1"), "ang": ang})
    return AdaptedPage(dr, build_spans(chars))
