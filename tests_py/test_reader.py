"""Testes da Etapa 1 (leitura). Usam PDFs reais; são pulados se os arquivos não existirem.
Limites de recall do OCR foram definidos a partir de MEDIÇÕES (ver README), com margem."""
import collections, io, os, warnings
from pathlib import Path
import pytest

warnings.filterwarnings("ignore")
import pymupdf  # noqa: E402
from PIL import Image  # noqa: E402
from ingest.reader import UnsupportedFormat, read  # noqa: E402

UP = Path(os.environ.get("LEGNA_FIXTURES", "/root/.claude/uploads/2776f07e-3ad9-5c9f-8cdd-0c5a8af5f4d9"))
TECH = UP / "0ad58788-DETALHAMENTO_DE_MARCENARIA_FERNANDA_SERTORIO.pdf"
DECK = UP / "2a1387d9-MGU_APRESENTA__O_R01.pdf"
needs_tech = pytest.mark.skipif(not TECH.exists(), reason="PDF técnico de teste ausente")
needs_deck = pytest.mark.skipif(not DECK.exists(), reason="PDF de apresentação de teste ausente")


def recall(truth_page, page):
    tn = collections.Counter(t.text for t in truth_page.numbers())
    on = collections.Counter(t.text for t in page.numbers())
    hit = sum(min(c, on[k]) for k, c in tn.items())
    return hit / sum(tn.values()), sum((on - tn).values())


@pytest.fixture(scope="module")
def tech():
    return read(TECH)


@needs_tech
def test_pdf_digital_le_cotas_e_texto_sem_ocr(tech):
    p = tech.pages[0]
    assert p.kind == "digital" and p.unit == "pt"
    nums = {t.text for t in p.numbers()}
    assert {"4380", "2200", "680", "750", "545", "2480"} <= nums
    assert any(t.text == "COZINHA" for t in p.tokens)
    assert all(t.source == "text-layer" for t in p.tokens)


@needs_tech
def test_texto_digital_nunca_e_substituido_por_ocr(tech):
    # regressão: páginas com poucas palavras (ex.: p.15) foram erradamente enviadas ao OCR
    assert all(p.kind == "digital" for p in tech.pages)
    assert all(t.source == "text-layer" for p in tech.pages for t in p.tokens)


@needs_tech
def test_cotas_verticais_sao_detectadas_com_rotacao(tech):
    rot = [t for t in tech.pages[0].numbers() if t.rotation != 0]
    assert len(rot) >= 5  # ex.: 2480, 560, 430 estão escritas na vertical


@needs_tech
@pytest.mark.parametrize("pg,minimo", [(1, 0.90), (6, 0.95), (17, 0.90)])
def test_pdf_escaneado_recupera_cotas(tech, tmp_path, pg, minimo):
    src = pymupdf.open(TECH)
    png = src[pg - 1].get_pixmap(dpi=300).tobytes("png")
    out = pymupdf.open(); q = out.new_page(width=src[pg - 1].rect.width, height=src[pg - 1].rect.height)
    q.insert_image(q.rect, stream=png); f = tmp_path / "scan.pdf"; out.save(f)
    d = read(f).pages[0]
    assert d.kind == "escaneada"
    assert all(t.source == "ocr" and t.conf is not None for t in d.tokens)
    r, _ = recall(tech.pages[pg - 1], d)
    assert r >= minimo


@needs_tech
@pytest.mark.parametrize("ext,kw,minimo", [("png", {}, 0.90), ("jpg", {"quality": 85}, 0.85)])
def test_imagens_png_e_jpg(tech, tmp_path, ext, kw, minimo):
    src = pymupdf.open(TECH)
    im = Image.open(io.BytesIO(src[0].get_pixmap(dpi=300).tobytes("png"))).convert("RGB")
    f = tmp_path / f"img.{ext}"; im.save(f, **kw)
    doc = read(f)
    assert doc.format == ext and doc.pages[0].unit == "px"
    assert any("sem escala" in n for n in doc.pages[0].notes)
    r, _ = recall(tech.pages[0], doc.pages[0])
    assert r >= minimo


@needs_deck
def test_apresentacao_tabela_em_imagem_passa_por_ocr():
    d = read(DECK)
    assert d.pages[1].kind == "escaneada"            # p.2: tabela geral é imagem
    txt = " ".join(t.text.upper() for t in d.pages[1].tokens)
    assert "TABELA" in txt or "SOFÁ" in txt or "MESA" in txt
    assert d.pages[3].kind == "digital"              # p.4: moodboard com texto digital


@pytest.mark.parametrize("nome", ["a.dwg", "a.dxf", "a.tif", "a.tiff", "a.xlsx", "a.xls", "a.csv", "a.svg", "a.docx"])
def test_formatos_nao_testados_sao_recusados(tmp_path, nome):
    f = tmp_path / nome; f.write_bytes(b"conteudo")
    with pytest.raises(UnsupportedFormat):
        read(f)


def test_extensao_que_nao_confere_com_o_conteudo_e_recusada(tmp_path):
    f = tmp_path / "falso.pdf"; f.write_bytes(b"isto nao e pdf")
    with pytest.raises(UnsupportedFormat):
        read(f)
