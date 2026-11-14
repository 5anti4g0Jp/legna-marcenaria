"""Verificação geométrica de cotas. Testes sintéticos (sem arquivos privados) + testes com o PDF real."""
import os, warnings
from pathlib import Path
import pytest

warnings.filterwarnings("ignore")
import pymupdf  # noqa: E402
from ingest.dimensions import analyze_pdf, analyze_page, summarize  # noqa: E402

RED = (0.71, 0.0, 0.0)
SCALE = 2.0  # mm por ponto nos desenhos sintéticos


def _dim_h(page, value, length_pt, y, x0=100):
    """Cota horizontal: linha + 2 riscos + texto."""
    shape = page.new_shape()
    shape.draw_line((x0, y), (x0 + length_pt, y))
    shape.draw_line((x0, y - 4), (x0, y + 4)); shape.draw_line((x0 + length_pt, y - 4), (x0 + length_pt, y + 4))
    shape.finish(color=RED, width=0.5); shape.commit()
    page.insert_text((x0 + length_pt / 2 - 6, y - 3), str(value), fontsize=8)


def _dim_v(page, value, length_pt, x, y0=200):
    shape = page.new_shape()
    shape.draw_line((x, y0), (x, y0 + length_pt))
    shape.draw_line((x - 4, y0), (x + 4, y0)); shape.draw_line((x - 4, y0 + length_pt), (x + 4, y0 + length_pt))
    shape.finish(color=RED, width=0.5); shape.commit()
    page.insert_text((x - 3, y0 + length_pt / 2 + 8), str(value), fontsize=8, rotate=90)


@pytest.fixture
def synthetic(tmp_path):
    doc = pymupdf.open(); pg = doc.new_page(width=700, height=800)
    for v, y in [(200, 50), (300, 80), (100, 110), (400, 140)]:      # corretas: v = L * 2.0
        _dim_h(pg, v, v / SCALE, y)
    _dim_h(pg, 250, 100, 170)                                         # ERRADA: 100 pt valem 200 mm, não 250
    _dim_v(pg, 1000, 500, 600)                                        # vertical correta (500 pt)
    shape = pg.new_shape(); shape.draw_line((50, 450), (650, 450))  # linha LONGA que apenas cruza
    shape.finish(color=RED, width=0.5); shape.commit()
    f = tmp_path / "sint.pdf"; doc.save(f)
    return analyze_page(pymupdf.open(f)[0], 1)


def _by_text(pd, text):
    return [d for d in pd.dims if d.text == text]


def test_escala_da_vista_e_estimada(synthetic):
    assert len(synthetic.scales) == 1 and abs(synthetic.scales[0] - SCALE) < 0.02


def test_cotas_corretas_sao_confirmadas(synthetic):
    for v in ("200", "300", "100", "400"):
        assert _by_text(synthetic, v)[0].status == "confirmado", v


def test_valor_errado_e_detectado_com_sugestao(synthetic):
    d = _by_text(synthetic, "250")[0]
    assert d.status == "conflito"
    assert d.suggestion_mm == 200            # a geometria diz 200; o valor escrito (250) NÃO é aceito


def test_linha_longa_que_so_cruza_nao_vira_marca(synthetic):
    d = _by_text(synthetic, "1000")[0]       # a linha em y=450 cruza a cota vertical no meio dela
    assert d.status == "confirmado" and abs(d.length_pt - 500) < 1


def test_pagina_sem_cotas_suficientes_nao_inventa_escala(tmp_path):
    doc = pymupdf.open(); pg = doc.new_page(width=300, height=300)
    _dim_h(pg, 200, 100, 50); _dim_h(pg, 300, 150, 90)                # só 2 cotas: não forma escala
    f = tmp_path / "poucas.pdf"; doc.save(f)
    pd = analyze_page(pymupdf.open(f)[0], 1)
    assert pd.scales == [] or all(d.status != "conflito" for d in pd.dims)


# ---------------- PDF real ----------------
UP = Path(os.environ.get("LEGNA_FIXTURES", "/root/.claude/uploads/2776f07e-3ad9-5c9f-8cdd-0c5a8af5f4d9"))
TECH = UP / "0ad58788-DETALHAMENTO_DE_MARCENARIA_FERNANDA_SERTORIO.pdf"
real = pytest.mark.skipif(not TECH.exists(), reason="PDF técnico de teste ausente")


@pytest.fixture(scope="module")
def pages():
    return analyze_pdf(TECH)


@real
def test_real_pagina1_escala_e_cotas_principais(pages):
    p = pages[0]
    assert len(p.scales) == 1 and abs(p.scales[0] - 4.853) < 0.02       # mm/pt medido
    for v in ("4380", "2200", "680", "750"):
        assert any(d.text == v and d.status == "confirmado" and abs(d.measured_mm - float(v)) < 6 for d in p.dims), v


@real
def test_real_regressao_cota_cruzada_p16_780(pages):
    # a linha da cota 680 cruza a cota 780; antes isso gerava um falso conflito (585 em vez de 780)
    d = next(d for d in pages[15].dims if d.text == "780")
    assert d.status in ("confirmado", "confirmado_local", "sem_medicao")


@real
def test_real_resumo_global_dentro_do_medido(pages):
    t = summarize(pages)
    n = sum(t.values())
    assert n >= 380
    assert t.get("confirmado", 0) + t.get("confirmado_local", 0) >= 170     # medido: 181
    assert t.get("conflito", 0) <= 30                                        # medido: 23 (parte são falsos alertas)
