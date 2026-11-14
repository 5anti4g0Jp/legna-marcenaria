"""SVGReader: lxml (parser endurecido contra XXE/rede) + svgpathtools para comprimentos de caminhos.
Transformações (`transform`) NÃO são aplicadas: coordenadas ficam em unidades do usuário."""
from __future__ import annotations

import re

from lxml import etree
from svgpathtools import parse_path

from .base import CorruptFile, Extracted, MM_PER, ReadResult, check_file

EXTS = {".svg"}
_LEN = re.compile(r"^\s*([0-9.+-eE]+)\s*(mm|cm|in|pt|px|m)?\s*$")


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _mm_per_user_unit(root) -> float | None:
    w, vb = root.get("width"), root.get("viewBox")
    if not w or not vb:
        return None
    m = _LEN.match(w)
    parts = vb.replace(",", " ").split()
    if not m or len(parts) != 4 or float(parts[2]) == 0:
        return None
    return float(m.group(1)) * MM_PER[m.group(2) or "px"] / float(parts[2])


def read(path) -> ReadResult:
    p = check_file(path, EXTS)
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False, recover=False)
    try:
        root = etree.parse(str(p), parser).getroot()
    except (etree.XMLSyntaxError, OSError) as e:
        raise CorruptFile(f"{p.name}: SVG/XML inválido ({e})") from e
    if _local(root.tag) != "svg":
        from .base import UnsupportedFormat
        raise UnsupportedFormat(f"{p.name}: o elemento raiz não é <svg>")
    k = _mm_per_user_unit(root)
    res = ReadResult(p.name, "svg", meta={"mm_per_user_unit": k, "width": root.get("width"), "height": root.get("height"), "viewBox": root.get("viewBox")})
    if k is None:
        res.warnings.append("escala não derivável de width+viewBox: valores em unidades do usuário, sem conversão para mm")
    transformed = scripts = 0
    for el in root.iter():
        t = _local(el.tag)
        if not t or t in ("svg", "g", "defs", "style", "title", "desc", "metadata"):
            continue
        if t == "script":
            scripts += 1; continue
        if el.get("transform"):
            transformed += 1
        loc = {"element": t, "id": el.get("id"), "line": el.sourceline}
        f = lambda a: float(el.get(a, 0) or 0)
        try:
            if t in ("text", "tspan"):
                txt = "".join(el.itertext()).strip()
                if txt and (t == "text" or True):
                    res.items.append(Extracted(txt, "text", p.name, "svg", loc, (f("x"), f("y"), f("x"), f("y")), "user-units", "lxml", 1.0, extra={"mm_per_unit": k}))
            elif t == "line":
                x1, y1, x2, y2 = f("x1"), f("y1"), f("x2"), f("y2")
                res.items.append(Extracted({"length": ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5}, "entity", p.name, "svg", loc,
                                           (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)), "user-units", "lxml", 1.0, extra={"mm_per_unit": k}))
            elif t == "rect":
                res.items.append(Extracted({"width": f("width"), "height": f("height")}, "entity", p.name, "svg", loc,
                                           (f("x"), f("y"), f("x") + f("width"), f("y") + f("height")), "user-units", "lxml", 1.0, extra={"mm_per_unit": k}))
            elif t == "circle":
                r = f("r")
                res.items.append(Extracted({"radius": r}, "entity", p.name, "svg", loc, (f("cx") - r, f("cy") - r, f("cx") + r, f("cy") + r), "user-units", "lxml", 1.0, extra={"mm_per_unit": k}))
            elif t == "path":
                path_ = parse_path(el.get("d", ""))
                xmin, xmax, ymin, ymax = path_.bbox()
                res.items.append(Extracted({"length": path_.length(), "segments": len(path_)}, "path", p.name, "svg", loc, (xmin, ymin, xmax, ymax), "user-units", "svgpathtools", 1.0, extra={"mm_per_unit": k}))
        except Exception as e:
            res.warnings.append(f"<{t}> linha {el.sourceline} ignorado: {type(e).__name__}: {e}")
    if transformed:
        res.warnings.append(f"{transformed} elemento(s) com `transform` NÃO tiveram a transformação aplicada")
    if scripts:
        res.warnings.append(f"{scripts} <script> ignorado(s) (nunca executados)")
    return res
