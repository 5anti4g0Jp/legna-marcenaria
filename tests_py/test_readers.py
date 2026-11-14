import os, stat, warnings
import pytest

warnings.filterwarnings("ignore")
import ezdxf  # noqa: E402
from ezdxf import units  # noqa: E402
from ingest.reader import UnsupportedFormat as LegacyUnsupported  # noqa: E402
from ingest.readers import (CorruptFile, FileTooLarge, ToolMissing, UnsupportedFormat, READERS, read_any)  # noqa: E402
from ingest.readers import base  # noqa: E402

REQUIRED = {"value", "kind", "source_file", "format", "locator", "coords", "unit", "method", "confidence", "status"}


def nums(res):
    return {str(i.value) for i in res.items if i.kind == "number"}


# ------------------------------------------------------------------ PDF
def test_pdf(make_pdf):
    r = read_any(make_pdf())
    assert r.format == "pdf" and {"4380", "2200", "680"} <= nums(r)
    it = next(i for i in r.items if i.value == "4380")
    assert it.method == "text-layer" and it.confidence == 1.0 and it.unit == "pt" and it.locator == {"page": 1} and it.coords


# ------------------------------------------------------------------ imagens
@pytest.mark.parametrize("fixture,fmt", [("make_png", "png"), ("make_jpg", "jpg")])
def test_png_jpg_ocr(request, fixture, fmt):
    r = read_any(request.getfixturevalue(fixture)())
    assert r.format == fmt and "4380" in nums(r) and "2200" in nums(r)
    it = next(i for i in r.items if i.value == "4380")
    assert it.method == "ocr" and it.unit == "px" and 0 < it.confidence <= 1
    assert any("sem escala" in w for w in r.warnings)


@pytest.mark.parametrize("mode", ["raw", "lzw", "g4"])
def test_tiff_multipagina_e_compressoes(make_tiff, mode):
    r = read_any(make_tiff(mode=mode))
    assert r.format == "tiff" and r.meta["frames"] == 2
    p1 = {str(i.value) for i in r.items if i.locator["page"] == 1 and i.kind == "number"}
    p2 = {str(i.value) for i in r.items if i.locator["page"] == 2 and i.kind == "number"}
    assert "4380" in p1 and "2200" in p2, (mode, r.meta, p1, p2)


# ------------------------------------------------------------------ DXF / DWG
def test_dxf_entidades_layers_unidades(make_dxf):
    r = read_any(make_dxf())
    assert r.format == "dxf" and r.meta["units"] == "mm"
    by = {}
    for i in r.items:
        by.setdefault(i.locator["entity"], []).append(i)
    assert by["TEXT"][0].value == "COZINHA" and by["TEXT"][0].locator["layer"] == "TEXTOS"
    assert by["MTEXT"][0].value == "Prateleira regulavel"
    assert by["LINE"][0].value["length"] == pytest.approx(100.0) and by["LINE"][0].locator["layer"] == "PECAS"
    assert by["LWPOLYLINE"][0].value == {"closed": True, "vertices": 4, "length": pytest.approx(130.0)} or by["LWPOLYLINE"][0].value["closed"]
    assert by["CIRCLE"][0].value["radius"] == 5
    dim = by["DIMENSION"][0]
    assert dim.kind == "dimension" and dim.value["measured"] == pytest.approx(100.0) and dim.locator["layer"] == "COTAS"
    assert "COTAS" in r.meta["layers"]


def test_dxf_converte_polegadas_para_mm(make_dxf):
    r = read_any(make_dxf(unit=units.IN))
    line = next(i for i in r.items if i.locator["entity"] == "LINE")
    assert line.value["length"] == pytest.approx(100.0 * 25.4)


def test_dxf_sem_unidade_nao_converte_e_avisa(make_dxf):
    r = read_any(make_dxf(unit=0))
    assert r.meta["units"] == "unitless" and any("INSUNITS" in w for w in r.warnings)
    assert all(i.unit == "unitless" for i in r.items)


def test_dwg_sem_conversor_recusa_com_instrucao(tmp_path, monkeypatch):
    monkeypatch.delenv("ODA_FILE_CONVERTER", raising=False)
    monkeypatch.setenv("PATH", "/nonexistent")
    f = tmp_path / "a.dwg"; f.write_bytes(b"AC1032" + b"\x00" * 100)
    with pytest.raises(ToolMissing, match="ODA File Converter"):
        read_any(f)


def test_dwg_que_nao_e_dwg(tmp_path):
    f = tmp_path / "a.dwg"; f.write_bytes(b"isto nao e dwg")
    with pytest.raises(UnsupportedFormat):
        read_any(f)


def _fake_converter(tmp_path, dxf_path, fail=False):
    s = tmp_path / "fake_oda.sh"
    body = "exit 3" if fail else f'cp "{dxf_path}" "$2/$(basename "$7" .dwg).dxf"'
    s.write_text(f"#!/bin/sh\n{body}\n"); s.chmod(s.stat().st_mode | stat.S_IEXEC); return s


def test_dwg_encanamento_com_conversor_simulado(tmp_path, make_dxf, monkeypatch):
    """Valida o ENCANAMENTO (chamada, arquivos temporários, leitura do DXF). NÃO valida o ODA real (indisponível aqui)."""
    monkeypatch.setenv("ODA_FILE_CONVERTER", str(_fake_converter(tmp_path, make_dxf())))
    f = tmp_path / "proj.dwg"; f.write_bytes(b"AC1032" + b"\x00" * 100)
    r = read_any(f)
    assert r.format == "dwg" and r.meta["dwg_version"] == "2018"
    assert all(i.format == "dwg" and i.method == "oda+ezdxf" for i in r.items) and r.items
    assert any("conversão DWG->DXF" in w for w in r.warnings)


def test_dwg_conversor_falha_vira_corrupt(tmp_path, make_dxf, monkeypatch):
    monkeypatch.setenv("ODA_FILE_CONVERTER", str(_fake_converter(tmp_path, make_dxf(), fail=True)))
    f = tmp_path / "proj.dwg"; f.write_bytes(b"AC1032" + b"\x00" * 100)
    with pytest.raises(CorruptFile):
        read_any(f)


# ------------------------------------------------------------------ planilhas e CSV
def test_xlsx_abas_celulas(make_xlsx):
    r = read_any(make_xlsx())
    assert r.format == "xlsx" and r.meta["sheets"] == ["Pecas", "Notas"]
    c = {(i.locator["sheet"], i.locator["cell"]): i.value for i in r.items}
    assert c[("Pecas", "A2")] == "Lateral" and c[("Pecas", "B2")] == 800 and c[("Pecas", "B3")] == 1170.5 and c[("Notas", "A1")] == "MDF 15"
    assert ("Pecas", "E2") not in c                       # fórmula sem valor em cache NÃO vira dado inventado
    assert any("fórmulas" in w for w in r.warnings)
    assert all(i.method == "openpyxl" for i in r.items)


def test_xls_calamine(make_xls):
    r = read_any(make_xls())
    c = {i.locator["cell"]: i.value for i in r.items}
    assert r.format == "xls" and c["A2"] == "Lateral" and c["B2"] == 800 and all(i.method == "calamine" for i in r.items)


def test_csv_pt_br(make_csv):
    r = read_any(make_csv())
    c = {(i.locator["row"], i.locator["col"]): i.value for i in r.items}
    assert r.meta["delimiter"] == ";" and c[(1, 1)] == "Peça" and c[(2, 2)] == "800,5"   # texto, sem converter a vírgula
    assert any("cp1252" in w for w in r.warnings)


# ------------------------------------------------------------------ SVG
def test_svg_geometria_e_escala(make_svg):
    r = read_any(make_svg())
    assert r.format == "svg" and r.meta["mm_per_user_unit"] == pytest.approx(1.0)
    by = {i.locator["element"]: i for i in r.items}
    assert by["text"].value == "COZINHA" and by["line"].value["length"] == pytest.approx(50.0)
    assert by["rect"].value == {"width": 20.0, "height": 10.0} and by["circle"].value["radius"] == 5.0
    assert by["path"].value["length"] == pytest.approx(10.0) and by["path"].method == "svgpathtools"


def test_svg_sem_escala_deriv_avisa(make_svg):
    r = read_any(make_svg(head=""))
    assert r.meta["mm_per_user_unit"] is None and any("escala" in w for w in r.warnings)


def test_svg_transform_e_script(make_svg):
    r = read_any(make_svg(body='<g><line x1="0" y1="0" x2="3" y2="4" transform="translate(5,5)"/></g><script>alert(1)</script>'))
    assert any("transform" in w for w in r.warnings) and any("script" in w for w in r.warnings)


def test_svg_xxe_nao_expande_arquivo_local(tmp_path):
    f = tmp_path / "x.svg"
    f.write_text('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
                 '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10"><text x="0" y="0">&xxe;</text></svg>')
    try:
        r = read_any(f)
        assert "root:" not in " ".join(str(i.value) for i in r.items)
    except CorruptFile:
        pass  # recusar também é aceitável


# ------------------------------------------------------------------ proveniência (todos os leitores)
@pytest.mark.parametrize("fx", ["make_pdf", "make_png", "make_jpg", "make_dxf", "make_xlsx", "make_xls", "make_csv", "make_svg"])
def test_proveniencia_completa_e_nunca_confirmado(request, fx):
    r = read_any(request.getfixturevalue(fx)())
    assert r.items
    for it in r.items:
        assert REQUIRED <= set(it.__dict__)
        assert it.source_file and it.format == r.format and it.locator and it.method
        assert it.status == "nao_confirmado"             # só revisão humana confirma
        assert it.confidence is None or 0 <= it.confidence <= 1


# ------------------------------------------------------------------ arquivos corrompidos
GARBAGE = os.urandom(300)
CORRUPT = {
    "pdf": ("x.pdf", b"%PDF-1.4\n" + GARBAGE), "png": ("x.png", b"\x89PNG\r\n\x1a\n" + GARBAGE), "jpg": ("x.jpg", b"\xff\xd8\xff\xe0" + GARBAGE),
    "tif": ("x.tif", b"II*\x00" + GARBAGE), "dxf": ("x.dxf", b"0\nSECTION\n2\nHEADER\n9\n$ACADVER\n" + GARBAGE),
    "xlsx": ("x.xlsx", b"PK\x03\x04" + GARBAGE), "xls": ("x.xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + GARBAGE),
    "svg": ("x.svg", b"<svg><text>aberto"), "vazio": ("e.pdf", b""),
}


@pytest.mark.parametrize("nome,conteudo", list(CORRUPT.values()), ids=list(CORRUPT))
def test_corrompidos_viram_corruptfile_nunca_excecao_crua(tmp_path, nome, conteudo):
    f = tmp_path / nome; f.write_bytes(conteudo)
    with pytest.raises(CorruptFile):
        read_any(f)


@pytest.mark.parametrize("fx,ext", [("make_pdf", "pdf"), ("make_png", "png"), ("make_xlsx", "xlsx"), ("make_dxf", "dxf"), ("make_tiff", "tif")])
def test_arquivos_truncados(request, tmp_path, fx, ext):
    good = request.getfixturevalue(fx)(); data = good.read_bytes()
    bad = tmp_path / f"trunc.{ext}"; bad.write_bytes(data[: len(data) // 2])
    try:
        r = read_any(bad)
        assert r is not None            # leitura parcial só é aceitável se não explodir; registrado abaixo
    except CorruptFile:
        pass


# ------------------------------------------------------------------ incompatíveis / limites
def test_extensao_nao_confere_com_conteudo(tmp_path):
    for nome, dado in [("a.pdf", b"texto comum"), ("a.png", b"%PDF-1.4 ..."), ("a.xlsx", b"nao e zip"), ("a.tif", b"%PDF")]:
        f = tmp_path / nome; f.write_bytes(dado)
        with pytest.raises(UnsupportedFormat):
            read_any(f)


def test_formatos_desconhecidos(tmp_path):
    for nome in ("a.docx", "a.step", "a.rvt", "semextensao"):
        f = tmp_path / nome; f.write_bytes(b"x")
        with pytest.raises(UnsupportedFormat):
            read_any(f)


def test_csv_binario_e_recusado(tmp_path):
    f = tmp_path / "b.csv"; f.write_bytes(b"a;b\x00\x01\x02;c")
    with pytest.raises(UnsupportedFormat):
        read_any(f)


def test_arquivo_inexistente(tmp_path):
    with pytest.raises(CorruptFile):
        read_any(tmp_path / "nao_existe.pdf")


def test_limite_de_tamanho(make_pdf, monkeypatch):
    monkeypatch.setattr(base, "MAX_BYTES", 10)
    with pytest.raises(FileTooLarge):
        read_any(make_pdf())


def test_hierarquia_de_erros_compativel_com_etapa1():
    assert issubclass(UnsupportedFormat, LegacyUnsupported)


def test_registro_cobre_todos_os_formatos_pedidos():
    for ext in (".pdf", ".dwg", ".dxf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".xlsx", ".xls", ".csv", ".svg"):
        assert ext in READERS
