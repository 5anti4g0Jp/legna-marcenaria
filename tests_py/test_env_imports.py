"""Uma verificação FUNCIONAL por biblioteca: importar não basta, cada uma executa uma operação real."""
import importlib, importlib.metadata as md, io, warnings

import pytest

warnings.filterwarnings("ignore")


def _v(dist):
    return md.version(dist)


def test_pymupdf():
    import pymupdf
    d = pymupdf.open(); d.new_page().insert_text((10, 20), "olá 123")
    assert "123" in d[0].get_text() and _v("pymupdf")


def test_pdfplumber(make_pdf):
    import pdfplumber
    with pdfplumber.open(make_pdf()) as pdf:
        assert "4380" in (pdf.pages[0].extract_text() or "")


def test_pypdf(make_pdf):
    from pypdf import PdfReader
    r = PdfReader(str(make_pdf())); assert len(r.pages) == 1 and "COZINHA" in r.pages[0].extract_text()


def test_pypdfium2(make_pdf):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(make_pdf())); img = pdf[0].render(scale=1).to_pil()
    assert img.size[0] > 100


def test_pillow():
    from PIL import Image
    im = Image.new("RGB", (4, 4), (255, 0, 0)); b = io.BytesIO(); im.save(b, "PNG")
    assert Image.open(io.BytesIO(b.getvalue())).getpixel((0, 0)) == (255, 0, 0)


def test_numpy_scipy():
    import numpy as np
    from scipy import ndimage
    a = np.zeros((5, 5)); a[2, 2] = 1
    assert ndimage.gaussian_filter(a, 1).sum() == pytest.approx(1.0, abs=1e-6)


def test_opencv():
    import cv2, numpy as np
    g = cv2.cvtColor(np.full((4, 4, 3), 255, np.uint8), cv2.COLOR_BGR2GRAY)
    assert g.shape == (4, 4) and cv2.__version__


def test_tesseract_e_pytesseract(png_bytes):
    import pytesseract
    from PIL import Image
    assert pytesseract.get_tesseract_version() is not None
    assert "por" in pytesseract.get_languages()
    txt = pytesseract.image_to_string(Image.open(io.BytesIO(png_bytes)), lang="por+eng")
    assert "4380" in txt


def test_ezdxf(make_dxf):
    import ezdxf
    doc = ezdxf.readfile(make_dxf()); assert len(list(doc.modelspace())) >= 5


def test_tifffile(tmp_path):
    import numpy as np, tifffile
    p = tmp_path / "a.tif"; tifffile.imwrite(p, np.arange(2 * 8 * 8, dtype="uint8").reshape(2, 8, 8))
    with tifffile.TiffFile(p) as tf:
        assert len(tf.pages) == 2


def test_openpyxl(make_xlsx):
    from openpyxl import load_workbook
    wb = load_workbook(make_xlsx(), data_only=True); assert wb["Pecas"]["B2"].value == 800


def test_calamine_xlsx_e_xls(make_xlsx, make_xls):
    from python_calamine import CalamineWorkbook
    for p in (make_xlsx(), make_xls()):
        rows = CalamineWorkbook.from_path(str(p)).get_sheet_by_name("Pecas").to_python()
        assert rows[1][0] == "Lateral"


def test_pandas(make_csv):
    pd = pytest.importorskip("pandas", reason="pandas é dependência OPCIONAL (requirements/optional.txt)")
    df = pd.read_csv(make_csv(), sep=";", encoding="cp1252", decimal=",")
    assert df["Largura"].iloc[0] == 800.5


def test_csv_stdlib():
    import csv
    assert list(csv.reader(io.StringIO("a;b\n1;2"), delimiter=";"))[1] == ["1", "2"]


def test_lxml_e_svgpathtools():
    from lxml import etree
    from svgpathtools import parse_path
    assert etree.fromstring("<a><b>x</b></a>").find("b").text == "x"
    assert parse_path("M0 0 L10 0").length() == pytest.approx(10.0)


def test_shapely():
    from shapely.geometry import Polygon, box
    p = Polygon([(0, 0), (4, 0), (4, 3), (0, 3)])
    assert p.area == 12 and p.intersection(box(2, 0, 6, 3)).area == 6


def test_anthropic_sdk_importa_e_cria_cliente_sem_rede(monkeypatch):
    import anthropic
    c = anthropic.Anthropic(api_key="sk-ant-teste-000000", max_retries=0)
    assert hasattr(c.messages, "create") and _v("anthropic")


def test_xlwt_dev(make_xls):
    assert make_xls().exists()


def test_sympy_nao_instalado_por_decisao():
    """SymPy foi RECUSADO (sem caso de uso; o motor usa aritmética simples). Se for instalado, revisar esta decisão."""
    try:
        importlib.import_module("sympy")
    except ImportError:
        return
    pytest.skip("sympy presente no ambiente, mas não é dependência do projeto")
