"""Fixtures: geram arquivos de exemplo em memória/tmp (nada depende de arquivos privados)."""
import io
import warnings

import pytest

warnings.filterwarnings("ignore")
import pymupdf  # noqa: E402
from PIL import Image  # noqa: E402


def _render_png(words: list[str], size=(900, 500), dpi=200) -> bytes:
    d = pymupdf.open(); pg = d.new_page(width=size[0] * 72 / dpi, height=size[1] * 72 / dpi)
    y = 70
    for w in words:
        pg.insert_text((30, y), w, fontsize=60 * 72 / dpi * 1.4); y += 100
    return pg.get_pixmap(dpi=dpi).tobytes("png")


@pytest.fixture
def png_bytes():
    return _render_png(["4380", "2200"])


@pytest.fixture
def make_pdf(tmp_path):
    def f(name="digital.pdf"):
        d = pymupdf.open(); pg = d.new_page(width=400, height=300)
        for i, w in enumerate(["COZINHA", "4380", "2200", "680", "750", "545", "ARMARIO"]):
            pg.insert_text((20, 30 + i * 25), w, fontsize=12)
        p = tmp_path / name; d.save(p); return p
    return f


@pytest.fixture
def make_png(tmp_path, png_bytes):
    def f(name="img.png"):
        p = tmp_path / name; p.write_bytes(png_bytes); return p
    return f


@pytest.fixture
def make_jpg(tmp_path, png_bytes):
    def f(name="img.jpg"):
        p = tmp_path / name; Image.open(io.BytesIO(png_bytes)).convert("RGB").save(p, quality=90); return p
    return f


@pytest.fixture
def make_tiff(tmp_path):
    import numpy as np, tifffile

    def f(name="multi.tif", frames=("4380", "2200"), mode="raw"):
        p = tmp_path / name
        imgs = [Image.open(io.BytesIO(_render_png([w]))).convert("L") for w in frames]
        if mode == "raw":                                   # tifffile, sem compressão, multipágina
            tifffile.imwrite(p, np.stack([np.asarray(i) for i in imgs]), photometric="minisblack")
        elif mode == "lzw":                                 # Pillow, LZW
            imgs[0].save(p, save_all=True, append_images=imgs[1:], compression="tiff_lzw", dpi=(200, 200))
        elif mode == "g4":                                  # Pillow, CCITT G4 (típico de scan)
            b = [i.point(lambda v: 255 if v > 128 else 0).convert("1") for i in imgs]
            b[0].save(p, save_all=True, append_images=b[1:], compression="group4", dpi=(200, 200))
        return p
    return f


@pytest.fixture
def make_dxf(tmp_path):
    import ezdxf
    from ezdxf import units

    def f(name="p.dxf", unit=units.MM, n_extra=0):
        doc = ezdxf.new("R2018", setup=True); doc.units = unit
        msp = doc.modelspace()
        msp.add_text("COZINHA", dxfattribs={"insert": (10, 10), "height": 5, "layer": "TEXTOS"})
        msp.add_mtext("Prateleira regulavel", dxfattribs={"insert": (10, 30), "layer": "TEXTOS"})
        msp.add_line((0, 0), (100, 0), dxfattribs={"layer": "PECAS"})
        msp.add_lwpolyline([(0, 0), (50, 0), (50, 30), (0, 30)], close=True, dxfattribs={"layer": "PECAS"})
        msp.add_circle((20, 20), 5, dxfattribs={"layer": "FUROS"})
        msp.add_linear_dim(base=(0, -10), p1=(0, 0), p2=(100, 0), dimstyle="EZDXF", dxfattribs={"layer": "COTAS"}).render()
        for i in range(n_extra):
            msp.add_line((i, 0), (i, 10))
        p = tmp_path / name; doc.saveas(p); return p
    return f


@pytest.fixture
def make_xlsx(tmp_path):
    from openpyxl import Workbook

    def f(name="l.xlsx"):
        wb = Workbook(); ws = wb.active; ws.title = "Pecas"
        ws.append(["Peça", "Largura", "Altura", "Qtd"]); ws.append(["Lateral", 800, 560, 2]); ws.append(["Base", 1170.5, 540, 1])
        ws["E2"] = "=B2+C2"                                   # fórmula sem valor em cache
        wb.create_sheet("Notas")["A1"] = "MDF 15"
        p = tmp_path / name; wb.save(p); return p
    return f


@pytest.fixture
def make_xls(tmp_path):
    import xlwt

    def f(name="l.xls"):
        wb = xlwt.Workbook(); ws = wb.add_sheet("Pecas")
        for c, v in enumerate(["Peça", "Largura", "Qtd"]): ws.write(0, c, v)
        for c, v in enumerate(["Lateral", 800, 2]): ws.write(1, c, v)
        p = tmp_path / name; wb.save(str(p)); return p
    return f


@pytest.fixture
def make_csv(tmp_path):
    def f(name="l.csv", text="Peça;Largura;Qtd\nLateral;800,5;2\nBase;1170;1\n", enc="cp1252"):
        p = tmp_path / name; p.write_bytes(text.encode(enc)); return p
    return f


@pytest.fixture
def make_svg(tmp_path):
    def f(name="d.svg", body=None, head='width="100mm" height="50mm" viewBox="0 0 100 50"'):
        body = body if body is not None else ('<text x="5" y="10">COZINHA</text><line x1="0" y1="0" x2="30" y2="40"/>'
                                              '<rect x="1" y="2" width="20" height="10"/><circle cx="50" cy="25" r="5"/><path d="M0 0 L10 0"/>')
        p = tmp_path / name; p.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" {head}>{body}</svg>', encoding="utf-8"); return p
    return f
