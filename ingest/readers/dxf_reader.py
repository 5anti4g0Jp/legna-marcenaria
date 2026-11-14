"""DXFReader: entidades de DXF via ezdxf. Converte para mm quando a unidade do desenho ($INSUNITS) é conhecida."""
from __future__ import annotations

import ezdxf
from ezdxf import units as dxfunits

from .base import CorruptFile, Extracted, ReadResult, check_file

EXTS = {".dxf"}
MAX_ENTITIES = int(__import__("os").environ.get("LEGNA_MAX_ENTITIES", "2000000"))


def _is_dxf(h: bytes) -> bool:
    # DXF ASCII começa com "0\nSECTION" (com espaços/CRLF possíveis); DXF binário tem assinatura própria
    s = h.lstrip()
    return s.startswith(b"0") or s.startswith(b"AutoCAD Binary DXF")


def _mm_factor(doc) -> tuple[float, str, list[str]]:
    code = doc.header.get("$INSUNITS", 0)
    if code in (0, None):
        return 1.0, "unitless", ["DXF sem unidade ($INSUNITS=0): valores mantidos em unidades do desenho (não confirmadas)"]
    try:
        return dxfunits.conversion_factor(code, dxfunits.MM), "mm", []
    except Exception:
        return 1.0, "unitless", [f"$INSUNITS={code} sem conversão conhecida para mm"]


def _pt(v):
    return (float(v[0]), float(v[1]))


def read_doc(doc, name: str, fmt: str = "dxf", method: str = "ezdxf") -> ReadResult:
    factor, unit, warns = _mm_factor(doc)
    res = ReadResult(name, fmt, warnings=list(warns), meta={"dxf_version": doc.dxfversion, "units": unit, "layers": sorted(l.dxf.name for l in doc.layers)})
    n = 0
    used_layers = set()
    for e in doc.modelspace():
        n += 1
        used_layers.add(e.dxf.layer)
        if n > MAX_ENTITIES:
            res.warnings.append(f"leitura interrompida em {MAX_ENTITIES} entidades (LEGNA_MAX_ENTITIES)")
            break
        t = e.dxftype(); loc = {"layer": e.dxf.layer, "handle": e.dxf.handle, "entity": t}
        try:
            if t == "TEXT":
                x, y = _pt(e.dxf.insert)
                res.items.append(Extracted(e.dxf.text, "text", name, fmt, loc, (x * factor, y * factor, x * factor, y * factor), unit, method, 1.0))
            elif t == "MTEXT":
                x, y = _pt(e.dxf.insert)
                res.items.append(Extracted(e.plain_text(), "text", name, fmt, loc, (x * factor, y * factor, x * factor, y * factor), unit, method, 1.0))
            elif t == "DIMENSION":
                m = e.get_measurement()
                val = float(m) * factor if isinstance(m, (int, float)) else None
                res.items.append(Extracted({"measured": val, "text_override": e.dxf.get("text", "")}, "dimension", name, fmt, loc, None, unit, method, 1.0,
                                           extra={"dimtype": e.dimtype}))
            elif t == "LINE":
                a, b = _pt(e.dxf.start), _pt(e.dxf.end)
                length = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 * factor
                res.items.append(Extracted({"length": length}, "entity", name, fmt, loc,
                                           tuple(v * factor for v in (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))), unit, method, 1.0))
            elif t == "LWPOLYLINE":
                pts = [(p[0], p[1]) for p in e.get_points("xy")]
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                length = sum(((pts[i][0] - pts[i - 1][0]) ** 2 + (pts[i][1] - pts[i - 1][1]) ** 2) ** 0.5 for i in range(1, len(pts))) * factor
                res.items.append(Extracted({"closed": bool(e.closed), "vertices": len(pts), "length": length}, "entity", name, fmt, loc,
                                           tuple(v * factor for v in (min(xs), min(ys), max(xs), max(ys))), unit, method, 1.0))
            elif t == "CIRCLE":
                x, y = _pt(e.dxf.center); r = float(e.dxf.radius) * factor
                res.items.append(Extracted({"radius": r}, "entity", name, fmt, loc, (x * factor - r, y * factor - r, x * factor + r, y * factor + r), unit, method, 1.0))
            elif t == "INSERT":
                x, y = _pt(e.dxf.insert)
                res.items.append(Extracted({"block": e.dxf.name}, "entity", name, fmt, loc, (x * factor, y * factor, x * factor, y * factor), unit, method, 1.0))
        except Exception as ex:   # uma entidade defeituosa não derruba o arquivo; fica registrada
            res.warnings.append(f"entidade {t} {e.dxf.handle} ignorada: {type(ex).__name__}: {ex}")
    # layers declarados na tabela + layers realmente usados por entidades (DXF pode usar layer não declarado)
    res.meta["layers"] = sorted(set(res.meta["layers"]) | used_layers)
    res.meta["entities_seen"] = n
    return res


def read(path) -> ReadResult:
    p = check_file(path, EXTS, _is_dxf)
    try:
        doc = ezdxf.readfile(p)
    except (ezdxf.DXFError, OSError, UnicodeDecodeError, ValueError, IndexError) as e:
        raise CorruptFile(f"{p.name}: DXF ilegível ({type(e).__name__}: {e})") from e
    return read_doc(doc, p.name)
