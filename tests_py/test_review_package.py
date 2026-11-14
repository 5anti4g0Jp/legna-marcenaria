"""Pacote de revisão independente cego. Respostas usadas aqui são SIMULADAS."""
import csv, hashlib, json, re, shutil
from pathlib import Path
import pytest
from evaluation import review_package as P, review_record as RC
from evaluation.paths import EV, Caminhos

PKG = P.ROOT / P.VERSAO / "entrega"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_entrega_tem_somente_folha_e_csv_e_hashes_conferem():
    assert sorted(p.name for p in PKG.iterdir()) == sorted([P.HTML_NOME, P.CSV_NOME]) and P.verificar() == []
    man = json.loads((PKG.parent / "MANIFESTO_PACOTE.json").read_text())
    assert man["pacote"] == P.VERSAO and all(sha(PKG / n) == m["sha256"] for n, m in man["arquivos_entregues"].items())


def test_ids_originais_preservados_e_sem_vazamento():
    ids = [i["id"] for i in json.loads(P.ITENS.read_text())["itens"]]
    html = (PKG / P.HTML_NOME).read_text(encoding="utf-8")
    rows = list(csv.DictReader(open(PKG / P.CSV_NOME, encoding="utf-8-sig")))
    assert len(ids) == 46 and sorted(re.findall(r'data-id="([^"]+)"', html)) == sorted(ids) == sorted(r["id"] for r in rows)
    assert "<details" not in html and "data-grupos" not in html and all(r["grupos"] == "" for r in rows)
    for n in (P.HTML_NOME, P.CSV_NOME):
        assert P.vazamentos((PKG / n).read_text(encoding="utf-8")) == [], n


def test_instrucoes_e_versao_presentes():
    html = (PKG / P.HTML_NOME).read_text(encoding="utf-8")
    for t in ("O que você vai fazer", "Não sei", "Valores aceitos no CSV", "Como devolver", P.VERSAO):
        assert t in html


def test_detector_de_vazamento_pega_termos():
    assert "gabarito" in P.vazamentos("Rótulo do gabarito: x") and P.vazamentos("texto neutro 15 mm") == []


def test_csv_entregue_preenchido_e_aceito_pelo_registro_SIMULADO(tmp_path):
    for rel in ("groundtruth/real_fernanda.json", "groundtruth/synthetic_manifest.json", "results/etapa0_baseline.json", "results/etapa0_relatorio.md",
                "baseline_etapa0/dimensions.py", "review/itens_selecionados.json"):
        d = tmp_path / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(EV / rel, d)
    rows = list(csv.reader(open(PKG / P.CSV_NOME, encoding="utf-8-sig")))
    for r in rows[1:]:
        r[4], r[5], r[6], r[7] = "Revisor Simulado", "nao_sei", "nao_sei", "nao_sei"
    f = tmp_path / "simulado.csv"
    csv.writer(open(f, "w", newline="", encoding="utf-8-sig")).writerows(rows)
    assert RC.registrar(f, Caminhos(tmp_path))["itens_respondidos"] == 46


def test_gerar_nao_sobrescreve_e_nao_toca_fontes(tmp_path):
    antes = (sha(P.ORIGINAL), sha(P.ITENS))
    man = P.gerar(tmp_path)
    assert man["n_itens"] == 46 and (sha(P.ORIGINAL), sha(P.ITENS)) == antes
    with pytest.raises(FileExistsError):
        P.gerar(tmp_path)
