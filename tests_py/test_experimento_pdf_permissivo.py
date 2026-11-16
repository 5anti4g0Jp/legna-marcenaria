"""EXPERIMENTO isolado: bibliotecas permissivas (pdfplumber/pdfminer, pypdfium2) alimentando o algoritmo CONGELADO, comparadas ao PyMuPDF."""
import hashlib, json
from pathlib import Path
import pytest

pytest.importorskip("pdfplumber"); pytest.importorskip("pypdfium2")
from experiments.pdf_permissivo import compare as CP

PDF = CP.PDF


def _pode():
    try: return PDF.exists()
    except PermissionError: return False


def test_algoritmo_congelado_inalterado_e_carrega_sem_pymupdf():
    assert hashlib.sha256(CP.ALGO.read_bytes()).hexdigest().startswith(CP.ALGO_SHA)
    dn = CP.carregar("dims_teste_semmupdf", True)
    assert not hasattr(dn.pymupdf, "open")                                       # o módulo vazio foi injetado: nenhuma chamada ao PyMuPDF no algoritmo alternativo
    assert dn.TOL == 0.02 and dn.MIN_CLUSTER == 3 and dn.TICK_MAX == 14.0


@pytest.mark.skipif(not _pode(), reason="PDF real ausente")
def test_backends_permissivos_reproduzem_baseline_nas_104_cotas_e_nos_sinteticos(tmp_path):
    o = CP.main(["--out", str(tmp_path)])
    for nome, b in o["backends"].items():
        assert "erro" not in b, (nome, b)
        assert b["cotas_104"]["total"] == 104 and b["cotas_104"]["mesmo_estado"] == 104 and b["cotas_104"]["mesmo_outcome"] == 104, nome
        assert b["linhas_revisadas"]["mesmo_estado"] == b["linhas_revisadas"]["total"] == 113 and b["linhas_revisadas"]["diferencas"] == [], nome
        assert b["paginas"]["casados"] == b["paginas"]["ref_tokens"] == 405 and b["paginas"]["mesmo_estado"] == 405 and b["paginas"]["paginas_com_mesma_cor_e_escalas"] == 34, nome
        assert b["paginas"]["desvio_max_bbox_pt"] <= 0.5, nome
    for estilo, l in o["sintetico"].items():
        ref = l["referencia_pymupdf"]
        for nome in ("pdfplumber_pdfminer", "pypdfium2"):
            assert l[nome]["outcomes"] == ref["outcomes"] and l[nome]["estados"] == ref["estados"], (estilo, nome)
    assert len(o["sintetico"]) == 9
