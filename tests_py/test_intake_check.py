"""Conferência de recebimento: somente leitura, origem como evidência (nunca prova) e detecção de armadilhas de exportação."""
import csv, hashlib, os
from pathlib import Path

import pytest

from evaluation import intake_check as IC
from evaluation.synthetic import Builder

UP = Path(os.environ.get("LEGNA_FIXTURES", "/root/.claude/uploads/2776f07e-3ad9-5c9f-8cdd-0c5a8af5f4d9"))
TECH = UP / "0ad58788-DETALHAMENTO_DE_MARCENARIA_FERNANDA_SERTORIO.pdf"


def _real():
    try:
        return TECH.exists()
    except PermissionError:
        return False


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pdf_simples(tmp_path, nome="a.pdf", creator=None):
    b = Builder(nome[:-4], "lay")
    for i, v in enumerate((200, 300, 100, 400)):
        b.dim((100, 60 + i * 30), (100 + v / 4.0, 60 + i * 30), str(v), "lay", scale=4.0)
    if creator is not None:
        b.doc.set_metadata({"creator": creator, "producer": creator})
    return Path(b.save(tmp_path).path)


@pytest.mark.skipif(not _real(), reason="PDF real ausente")
def test_pdf_real_origem_por_metadado_nao_confirmada():
    r = IC.inspecionar(TECH)
    assert r["origem"]["software_inferido"] == "SketchUp/LayOut" and r["origem"]["confirmada"] is False
    assert r["paginas"] == 34 and r["diagnostico_preliminar_cotas"]["numeros_inteiros_candidatos"] == 405
    assert "NÃO é afirmação de compatibilidade" in r["diagnostico_preliminar_cotas"]["aviso"] and r["unidade_declarada_no_texto"] is True


def test_origem_nunca_e_confirmada_automaticamente(tmp_path):
    for creator in ("AutoCAD 2023 - DWG To PDF.pc3", "Promob Plus", "Microsoft: Print To PDF"):
        r = IC.inspecionar(pdf_simples(tmp_path, f"x{abs(hash(creator))}.pdf", creator))
        assert r["origem"]["confirmada"] is False and "evidência, não prova" in r["origem"]["ressalva"]
    assert IC.inspecionar(pdf_simples(tmp_path, "sem.pdf", ""))["origem"]["software_inferido"] == "desconhecido"
    assert IC.dica_origem("AutoCAD 2023 - DWG To PDF.pc3", "")["software_inferido"] == "AutoCAD/Autodesk"
    assert IC.dica_origem("", "Microsoft: Print To PDF")["software_inferido"].startswith("Microsoft Print to PDF")


def test_texto_em_curvas_e_escaneado_sao_sinalizados(tmp_path):
    import pymupdf
    d = pymupdf.open(); pg = d.new_page(width=600, height=800)
    for i in range(300):
        pg.draw_line((10 + i, 10), (10 + i, 700), color=(0, 0, 0), width=0.2)            # muito vetor, nenhum texto
    d.save(tmp_path / "curvas.pdf")
    r = IC.inspecionar(tmp_path / "curvas.pdf")
    assert r["detalhe_paginas"][0]["texto_possivelmente_em_curvas"] and any("convertido em curvas" in a for a in r["avisos"])
    png = pg.get_pixmap(dpi=100).tobytes("png"); d2 = pymupdf.open(); p2 = d2.new_page(width=600, height=800); p2.insert_image(p2.rect, stream=png); d2.save(tmp_path / "scan.pdf")
    r2 = IC.inspecionar(tmp_path / "scan.pdf")
    assert r2["detalhe_paginas"][0]["possivelmente_escaneada"] and any("digitalização" in a for a in r2["avisos"])


def test_dxf_planilha_csv_e_dwg(tmp_path, make_dxf, make_xlsx, make_csv):
    r = IC.inspecionar(make_dxf())
    assert r["tipo"] == "dxf" and r["cotas_dimension"] >= 1 and r["unidade_insunits"] == 4 and r["entidades_modelo"]["LINE"] >= 1
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = "Pecas"; ws.append(["Peça", "Comprimento", "Largura", "Espessura", "Qtd", "Material"]); ws.append(["Lateral", 800, 560, 15, 2, "MDF"])
    wb.create_sheet("Notas").append(["observações gerais"]); wb.save(tmp_path / "l.xlsx")
    ab = {a["aba"]: a for a in IC.inspecionar(tmp_path / "l.xlsx")["abas"]}
    assert ab["Pecas"]["parece_lista_de_pecas"] is True and ab["Notas"]["parece_lista_de_pecas"] is False
    assert IC.inspecionar(make_csv(text="peca;comprimento;largura;qtd\nL;800;560;2\n"))["abas"][0]["parece_lista_de_pecas"] is True
    (tmp_path / "x.dwg").write_bytes(b"AC1032" + b"\x00" * 50)
    d = IC.inspecionar(tmp_path / "x.dwg")
    assert d["versao"] == "2018" and any("DXF" in a for a in d["avisos"])                # pede o DXF do mesmo projeto


def test_arquivo_ruim_nao_derruba_o_lote(tmp_path):
    (tmp_path / "falso.pdf").write_bytes(b"isto nao e pdf"); (tmp_path / "x.step").write_bytes(b"x"); (tmp_path / "quebrado.dxf").write_bytes(b"0\nSECTION\nlixo")
    for n in ("falso.pdf", "x.step", "quebrado.dxf"):
        assert "erro" in IC.inspecionar(tmp_path / n)


def test_somente_leitura(tmp_path):
    p = pdf_simples(tmp_path); antes = sha(p); IC.inspecionar(p); IC.render([IC.inspecionar(p)])
    assert sha(p) == antes


def _ficha(tmp_path, linhas):
    f = tmp_path / "ficha.csv"
    with open(f, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, IC.FICHA_COLS); w.writeheader()
        for l in linhas: w.writerow({c: l.get(c, "") for c in IC.FICHA_COLS})
    return f


def test_ficha_detecta_inconsistencias(tmp_path):
    ok = pdf_simples(tmp_path, "ok.pdf", "AutoCAD 2023 - DWG To PDF.pc3")
    base = {"projeto_id": "P1", "papel_do_arquivo": "pdf_executivo", "unidade": "mm", "autorizado_uso": "sim"}
    f = _ficha(tmp_path, [
        {**base, "arquivo": "ok.pdf", "software": "AutoCAD 2023", "sha256": sha(ok)},                                  # consistente
        {**base, "arquivo": "ok.pdf", "software": "Promob Plus", "sha256": "0" * 64},                                   # software e hash divergentes
        {**base, "arquivo": "nao_existe.pdf", "software": "AutoCAD"},                                                     # arquivo ausente
        {**base, "arquivo": "ok.pdf", "software": "", "papel_do_arquivo": "planta", "autorizado_uso": ""},               # vazio/papel inválido/sem autorização
    ])
    pdf_simples(tmp_path, "sobra.pdf")                                                                                    # arquivo sem ficha
    r = IC.conferir_ficha(f, tmp_path); texto = " | ".join(p["problema"] for p in r["problemas"])
    for esperado in ("difere do indício", "SHA-256 da ficha difere", "não encontrado", "papel_do_arquivo inválido", "'software' vazio", "NÃO autorizado"):
        assert esperado in texto, esperado
    assert "sobra.pdf" in r["arquivos_sem_ficha"] and not [p for p in r["problemas"] if p["linha"] == 2]               # a linha consistente não gera problema


def test_cli_gera_relatorio(tmp_path):
    p = pdf_simples(tmp_path); out = tmp_path / "rel.md"
    assert IC.main([str(p), "--saida", str(out)]) == 0
    assert "Relatório de recebimento" in out.read_text() and out.with_suffix(".json").exists()
