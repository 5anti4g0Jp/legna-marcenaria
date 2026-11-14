"""Etapa 0: garante que a linha de base é reproduzível, que o algoritmo atual não foi alterado e que o gabarito é coerente."""
import hashlib, json, os, tempfile
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from evaluation import metrics as M
from evaluation import report, run_baseline
from evaluation.synthetic import build_all, manifest

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evaluation"
RESULT = EV / "results" / "etapa0_baseline.json"
FROZEN = EV / "baseline_etapa0" / "dimensions.py"
UP = Path(os.environ.get("LEGNA_FIXTURES", "/root/.claude/uploads/2776f07e-3ad9-5c9f-8cdd-0c5a8af5f4d9"))
TECH = UP / "0ad58788-DETALHAMENTO_DE_MARCENARIA_FERNANDA_SERTORIO.pdf"


def _exists(p):
    try:
        return p.exists()
    except PermissionError:
        return False


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def saved():
    return json.loads(RESULT.read_text())


# ------------------------------------------------------------- preservação
def test_algoritmo_atual_identico_ao_congelado_e_ao_registrado(saved):
    """Condição da Etapa 0: NÃO alterar o algoritmo. Quando a Etapa 1 alterar ingest/dimensions.py, esta verificação
    deve ser trocada por uma que compare só o congelado (a baseline continua reproduzível por ele)."""
    assert sha(FROZEN) == saved["meta"]["algoritmo"]["sha256"]
    assert sha(ROOT / "ingest" / "dimensions.py") == sha(FROZEN)


def test_testes_antigos_de_dimensions_preservados(saved):
    assert sha(ROOT / "tests_py" / "test_dimensions.py") == saved["meta"]["testes_dimensions_sha256"]


# ------------------------------------------------------------- gabarito sintético
def test_sintetico_e_deterministico(tmp_path):
    a = manifest(build_all(tmp_path / "a")); b = manifest(build_all(tmp_path / "b"))
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def test_verdade_sintetica_e_coerente(tmp_path):
    for d in build_all(tmp_path):
        for t in d.truths:
            assert t.bbox is not None, (d.name, t.text)                       # todo item achado no PDF gerado
            if t.role.startswith("cota"):
                if t.planted_error:
                    assert abs(t.written_mm - t.value_mm) / t.value_mm > 0.005
                else:
                    assert abs(t.written_mm - t.value_mm) / t.value_mm < 0.005, (d.name, t.text, t.written_mm, t.value_mm)
            else:
                assert t.value_mm is None


# ------------------------------------------------------------- métricas
def D(status, orient="h", length=100.0, bbox=(0, 0, 10, 10), text="450"):
    return NS(status=status, orient=orient, length_pt=length, bbox=bbox, text=text)


@pytest.mark.parametrize("item,dim,assoc,esperado", [
    ({"role": "cota_regular"}, None, None, "perdida_leitura"),
    ({"role": "cota_regular"}, D("sem_medicao"), None, "perdida_medicao"),
    ({"role": "cota_regular"}, D("sem_escala"), None, "perdida_medicao"),
    ({"role": "cota_regular"}, D("confirmado"), "correta", "confirmada_correta"),
    ({"role": "cota_regular"}, D("confirmado_local"), "correta", "confirmada_correta"),
    ({"role": "cota_deslocada"}, D("confirmado"), "incorreta", "confirmada_associacao_incorreta"),
    ({"role": "cota_regular"}, D("confirmado"), "indeterminada", "confirmada_indeterminada"),
    ({"role": "cota_regular"}, D("conflito"), "correta", "conflito_falso_alarme"),
    ({"role": "cota_regular", "planted_error": True}, D("conflito"), None, "erro_plantado_detectado"),
    ({"role": "cota_regular", "planted_error": True}, D("confirmado"), "correta", "erro_plantado_aceito"),
    ({"role": "cota_regular", "planted_error": True}, D("sem_medicao"), None, "erro_plantado_perdido"),
    ({"role": "cota_regular", "planted_error": True}, None, None, "erro_plantado_perdido"),
    ({"role": "medida_em_nota"}, None, None, "nota_nao_lida"),
    ({"role": "medida_em_nota"}, D("sem_medicao"), None, "nota_tratada_como_cota"),
    ({"role": "nao_cota"}, None, None, "ignorada_corretamente"),
    ({"role": "nao_cota"}, D("conflito"), None, "falsa_deteccao_medida"),
    ({"role": "nao_cota"}, D("confirmado"), None, "falsa_deteccao_medida"),
    ({"role": "nao_cota"}, D("sem_medicao"), None, "falso_candidato_sem_medicao"),
])
def test_outcome(item, dim, assoc, esperado):
    assert M.outcome(item, dim, assoc) == esperado


def test_associacao_sintetica():
    t = {"orientation": "horizontal", "interval_pt": 100.0}
    assert M.synthetic_assoc(t, D("confirmado", "h", 100.4)) == "correta"
    assert M.synthetic_assoc(t, D("confirmado", "h", 130.0)) == "incorreta"      # intervalo errado
    assert M.synthetic_assoc(t, D("confirmado", "v", 100.0)) == "incorreta"      # orientação errada
    assert M.synthetic_assoc({"orientation": "inclinada", "interval_pt": 100}, D("confirmado", "h", 100)) == "incorreta"


def test_alinhamento_um_para_um():
    items = [{"id": "a", "text": "450", "bbox": (0, 0, 10, 10)}, {"id": "b", "text": "450", "bbox": (1, 0, 11, 10)}]
    dims = [D("confirmado", bbox=(0.2, 0, 10.2, 10))]
    al = M.align(items, dims)
    assert sum(v is not None for v in al.values()) == 1                           # a mesma dimensão não casa duas vezes


# ------------------------------------------------------------- resultados salvos
def test_resultados_salvos_sao_consistentes(saved):
    syn = saved["sintetico"]
    assert sum(v["_total"] for v in syn["por_papel"].values()) == syn["itens"] == len(syn["linhas"])
    ruins = [r for r in syn["linhas"] if r["outcome"] not in ("confirmada_correta", "ignorada_corretamente", "erro_plantado_detectado")]
    assert sum(1 for f in saved["falhas"] if f["origem"].startswith("sintetico")) == len(ruins)
    assert saved["meta"]["algoritmo"]["alterado_nesta_etapa"] is False
    if saved["real"]:
        real = saved["real"]; assert real["revisao_independente"] is False
        assert real["tokens_total"] == 462 and real["tokens_revisados"] == len(real["linhas"]) == 113


def test_gabarito_real_integro():
    gt = json.loads((EV / "groundtruth" / "real_fernanda.json").read_text())
    assert gt["independent_review"] is False and gt["limitacoes"]
    assert gt["tokens_total"] == len(gt["tokens"]) == 462
    rev = [t for t in gt["tokens"] if t["reviewed"]]
    assert {t["page"] for t in rev} == set(gt["reviewed_pages"])
    assert all(t["role"] in ("cota_regular", "cota_deslocada", "medida_em_nota", "nao_cota") for t in rev)
    assert all(t["role"] == "nao_revisado" for t in gt["tokens"] if not t["reviewed"])


def test_relatorio_nao_foi_editado_a_mao(saved):
    assert (EV / "results" / "etapa0_relatorio.md").read_text().rstrip("\n") == report.render(saved).rstrip("\n")


# ------------------------------------------------------------- reprodutibilidade
def test_baseline_reproduz_resultados_salvos(saved, tmp_path):
    """Reexecuta o algoritmo CONGELADO e compara agregados com o que está salvo (sintético sempre; real se o PDF existir)."""
    real = TECH if _exists(TECH) else tmp_path / "ausente.pdf"
    r = run_baseline.main(["--algo", str(FROZEN), "--out", str(tmp_path), "--tag", "repro", "--no-write-gt", "--real", str(real)])
    norm = lambda x: json.loads(json.dumps(x, default=str))          # chaves int viram str ao salvar em JSON
    s0, s1 = saved["sintetico"], norm(r["sintetico"]); r = {**r, "real": norm(r["real"]) if r["real"] else None}
    for k in ("por_estilo", "por_papel", "por_orientacao", "por_formato", "escalas"):
        assert s1[k] == s0[k], k
    assert [(x["id"], x["outcome"]) for x in s1["linhas"]] == [(x["id"], x["outcome"]) for x in s0["linhas"]]
    if saved["real"] and r["real"]:
        for k in ("por_papel", "por_orientacao", "por_tamanho", "por_formato", "estados_baseline_todas_as_paginas", "paginas_com_varias_escalas_proximas", "escalas_espurias_por_pagina"):
            assert r["real"][k] == saved["real"][k], k
        assert [x["outcome"] for x in r["real"]["linhas"]] == [x["outcome"] for x in saved["real"]["linhas"]]
