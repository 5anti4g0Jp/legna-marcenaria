"""Mede tempo e memória de pico (RSS) de cada leitor em processo isolado.
Uso: python -m ingest.bench [saida.md]"""
from __future__ import annotations

import json, resource, subprocess, sys, tempfile, time
from pathlib import Path

CHILD = r'''
import sys, time, resource, warnings; warnings.filterwarnings("ignore")
from ingest.readers import read_any
t=time.perf_counter(); r=read_any(sys.argv[1]); dt=time.perf_counter()-t
print(len(r.items), round(dt,3), round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1))
'''


def _samples(d: Path) -> dict[str, Path]:
    import io, warnings; warnings.filterwarnings("ignore")
    import ezdxf, numpy as np, pymupdf, tifffile
    from ezdxf import units
    from openpyxl import Workbook
    from PIL import Image
    out = {}
    doc = pymupdf.open()
    for n in range(10):
        pg = doc.new_page(width=842, height=595)
        for i in range(40):
            pg.insert_text((30, 20 + i * 13), f"{1000 + n * 40 + i}", fontsize=9)
    doc.save(d / "pdf10pag.pdf"); out["pdf 10 págs (400 nºs/pág)"] = d / "pdf10pag.pdf"
    pix = pymupdf.open(); pg = pix.new_page(width=842, height=595)
    for i in range(30): pg.insert_text((30, 25 + i * 18), f"{2000 + i}", fontsize=14)
    png = pg.get_pixmap(dpi=200).tobytes("png"); (d / "a.png").write_bytes(png); out["png A4 200dpi (OCR)"] = d / "a.png"
    img = Image.open(io.BytesIO(png)).convert("L")
    tifffile.imwrite(d / "m.tif", np.stack([np.asarray(img)] * 3), photometric="minisblack"); out["tiff 3 págs (OCR)"] = d / "m.tif"
    dxf = ezdxf.new("R2018"); dxf.units = units.MM; m = dxf.modelspace()
    for i in range(50000): m.add_line((i, 0), (i, 10))
    dxf.saveas(d / "big.dxf"); out["dxf 50.000 linhas"] = d / "big.dxf"
    wb = Workbook(); ws = wb.active
    for r in range(1, 20001): ws.append([r, r * 2, "x", r / 3])
    wb.save(d / "big.xlsx"); out["xlsx 20.000 linhas x 4"] = d / "big.xlsx"
    (d / "big.csv").write_text("\n".join(f"{r};{r*2};x;{r/3}" for r in range(1, 50001))); out["csv 50.000 linhas"] = d / "big.csv"
    return out


def main(dest: str | None = None):
    rows = ["| Arquivo | Itens | Tempo (s) | Pico de RAM (MB) |", "|---|---|---|---|"]
    with tempfile.TemporaryDirectory() as t:
        for label, path in _samples(Path(t)).items():
            r = subprocess.run([sys.executable, "-c", CHILD, str(path)], capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1])
            if r.returncode:
                rows.append(f"| {label} | ERRO | - | {r.stderr[-120:]!r} |"); continue
            n, dt, mb = r.stdout.split()
            rows.append(f"| {label} | {n} | {dt} | {mb} |")
    txt = "\n".join(rows)
    print(txt)
    if dest: Path(dest).write_text(txt + "\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
