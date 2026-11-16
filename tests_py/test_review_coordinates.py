"""Arquivo auxiliar de coordenadas (pkg-1.1/auxiliar)."""
import csv, hashlib, json
from pathlib import Path
import pytest
from evaluation import review_coordinates as C, review_package as P
from evaluation.paths import EV

ENT = P.ROOT / "pkg-1.1" / "entrega"


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_manifesto_hash_e_arquivos_do_pacote_inalterados():
    assert C.verificar() == []
    man = json.loads((C.AUX / "MANIFESTO_COORDENADAS.json").read_text())
    assert man["sha256"] == sha(C.AUX / C.CSV_AUX) and man["n_itens"] == 46
    assert sha(ENT / P.CSV_NOME) == "46892c19a7342cd7d9a0dd07a1aaa8f7fad62565d6e5921d2c6101cc714826ca" and sha(ENT / P.PDF_NOME) == P.PDF_SHA256
    assert sorted(p.name for p in ENT.iterdir()) == sorted([P.HTML_NOME, P.CSV_NOME, P.PDF_NOME])           # entrega/ continua com 3 arquivos
    assert not (C.AUX / C.CSV_AUX).stat().st_mode & 0o222


def test_46_ids_na_ordem_do_csv_com_colunas_e_sem_vazamento():
    ids = [r["id"] for r in csv.DictReader(open(ENT / P.CSV_NOME, encoding="utf-8-sig"))]
    txt = (C.AUX / C.CSV_AUX).read_text(encoding="utf-8"); rows = list(csv.DictReader(open(C.AUX / C.CSV_AUX, encoding="utf-8-sig")))
    assert [r["id"] for r in rows] == ids and list(rows[0].keys()) == C.COLS
    assert P.vazamentos(txt) == [] and not {"role", "papel", "estado", "intervalo", "gabarito", "baseline", "resultado", "outcome"} & set(rows[0].keys())


def test_coordenadas_batem_com_o_pdf_e_com_a_etapa0_e_sao_unicas():
    gt = {t["id"]: t for t in json.loads((EV / "groundtruth" / "real_fernanda.json").read_text())["tokens"]}
    rows = list(csv.DictReader(open(C.AUX / C.CSV_AUX, encoding="utf-8-sig")))
    assert all([round(float(r[k]), 2) for k in ("x0", "y0", "x1", "y1")] == [round(v, 2) for v in gt[r["id"]]["bbox"]] and r["texto"] == gt[r["id"]]["text"] for r in rows)
    assert len({(r["pagina"], r["x0"], r["y0"]) for r in rows}) == 46                       # caixas distintas: resolve os valores repetidos na mesma página
    import pymupdf
    d = pymupdf.open(P.PDF_ORIGEM)
    for r in rows:
        x0, y0, x1, y1 = (float(r[k]) for k in ("x0", "y0", "x1", "y1"))
        assert r["texto"] in [w[4] for w in d[int(r["pagina"]) - 1].get_text("words", clip=pymupdf.Rect(x0 - .5, y0 - .5, x1 + .5, y1 + .5))]


def test_gerar_nao_sobrescreve_e_texto_diferente_e_recusado(tmp_path):
    with pytest.raises(FileExistsError): C.gerar()
    assert sha(P.PDF_ORIGEM) == P.PDF_SHA256                                                  # PDF de origem intacto
    ruim = tmp_path / "c.csv"; linhas = list(csv.reader(open(ENT / P.CSV_NOME, encoding="utf-8-sig"))); linhas[1][2] = "999"
    csv.writer(open(ruim, "w", newline="", encoding="utf-8-sig")).writerows(linhas)
    with pytest.raises(ValueError, match="diferem do CSV"): C.construir(csv_entregue=ruim)
