"""Folha de conferência e importador de revisão independente."""
import csv, hashlib, json, os, re
from pathlib import Path

import pytest

from evaluation import review_import, review_sheet as RS

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evaluation"
UP = Path(os.environ.get("LEGNA_FIXTURES", "/root/.claude/uploads/2776f07e-3ad9-5c9f-8cdd-0c5a8af5f4d9"))
TECH = UP / "0ad58788-DETALHAMENTO_DE_MARCENARIA_FERNANDA_SERTORIO.pdf"


def _can_read(p):
    try:
        return p.exists()
    except PermissionError:
        return False


@pytest.fixture(scope="module")
def data():
    saved = json.loads(RS.RESULT.read_text()); gt = json.loads(RS.GT.read_text())
    items, counts = RS.select_items(saved, gt)
    return saved, gt, items, counts


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ids_of(items, g):
    return {i["id"] for i in items if g in i["grupos"]}


def test_grupos_pedidos_batem_com_a_baseline(data):
    _, _, items, c = data
    assert c == {"falsa_confirmacao": 3, "conflito": 14, "assumido": 3, "confirmada_indeterminada": 3, "pequena": 24, "deslocada": 18, "controle": 8}
    assert ids_of(items, "falsa_confirmacao") == {"p6-t3", "p6-t6", "p6-t24"}
    assert ids_of(items, "assumido") == {"p1-t9", "p1-t26", "p6-t8"}
    assert ids_of(items, "confirmada_indeterminada") == {"p1-t55", "p10-t17", "p10-t22"}
    assert len({i["id"] for i in items}) == len(items) == 46                   # itens únicos, sem duplicar quem está em vários grupos


def test_controle_e_deterministico_e_nao_sobrepoe(data):
    saved, gt, items, _ = data
    again, _ = RS.select_items(saved, gt)
    assert ids_of(items, "controle") == ids_of(again, "controle")
    assert all(i["grupos"] == ["controle"] for i in items if "controle" in i["grupos"])
    rows = {r["id"]: r for r in saved["real"]["linhas"]}
    assert all(rows[i]["outcome"] == "confirmada_correta" for i in ids_of(items, "controle"))


def test_modelo_csv(data):
    _, gt, items, _ = data
    rows = list(csv.reader(RS.template_csv(items, gt).splitlines()))
    assert rows[0] == RS.CSV_COLS and len(rows) == 47
    assert all(r[4:] == [""] * 7 for r in rows[1:])                           # nenhuma resposta pré-preenchida


@pytest.mark.skipif(not _can_read(TECH), reason="PDF real de teste ausente")
def test_html_autocontido_cego_e_sem_alterar_artefatos(data, tmp_path):
    saved, gt, items, counts = data
    antes = {p: sha(p) for p in (RS.RESULT, RS.GT, RS.FROZEN)}
    html = RS.build_html(str(TECH), saved, gt, items, counts)
    assert all(f'data-id="{i["id"]}"' in html for i in items)
    assert not re.findall(r'(?:src|href)="https?://', html) and "@import" not in html
    assert html.count("<details>") == len(items) and "<details open" not in html     # rótulo do gabarito recolhido (cego)
    assert all(q in html for q in ("O que é este número?", "A linha azul cobre exatamente", "O valor escrito está correto?"))
    assert len(html) < 5_000_000
    assert antes == {p: sha(p) for p in antes}                                # gerar a folha não altera gabarito nem resultados


def _answers(tmp_path, data, overrides):
    _, gt, items, _ = data
    p = tmp_path / "resp.csv"; rows = list(csv.reader(RS.template_csv(items, gt).splitlines()))
    hdr = rows[0]
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(hdr)
        for r in rows[1:]:
            d = dict(zip(hdr, r)); d.update(overrides.get(d["id"], {})); w.writerow([d[c] for c in hdr])
    return p


def test_importador_concordancia_e_discordancia(data, tmp_path):
    ov = {"p6-t3": {"revisor": "Ana", "q1_papel": "cota_deslocada", "q2_intervalo_correto": "nao", "q3_valor_correto": "sim"},        # concorda em tudo
          "p6-t6": {"revisor": "Ana", "q1_papel": "cota_regular", "q2_intervalo_correto": "sim", "q3_valor_correto": "nao", "valor_lido_pelo_revisor": "18", "observacao": "li 18"},  # discorda nas 3
          "p1-t9": {"revisor": "Ana", "q1_papel": "nao_sei", "q2_intervalo_correto": "sim", "q3_valor_correto": "sim"}}                  # q1 não sei; q2 gabarito 'incorreta'
    r = review_import.import_review(_answers(tmp_path, data, ov))
    assert r["revisores"] == ["Ana"] and r["itens_no_arquivo"] == 46
    assert r["q1"]["concorda"] == 1 and r["q1"]["discorda"] == 1 and r["q1"]["nao_sei"] == 1 and r["q1"]["sem_resposta"] == 43
    d = {(x["id"], x["pergunta"]) for x in r["discordancias"]}
    assert ("p6-t6", "q1") in d and ("p6-t6", "q2") in d and ("p6-t6", "q3") in d and ("p1-t9", "q2") in d
    assert all(x["pergunta"] != "q1" or x["id"] != "p1-t9" for x in r["discordancias"])         # 'não sei' nunca conta como discordância
    assert r["nota"].startswith("Relatório") and 0 <= r["concordancia"]["q1"] <= 1


def test_importador_marca_indeterminado_do_gabarito(data, tmp_path):
    # p1-t55 é 'confirmada_indeterminada': gabarito sem veredito de associação; resposta do revisor vira pendência de decisão
    r = review_import.import_review(_answers(tmp_path, data, {"p1-t55": {"revisor": "Bia", "q2_intervalo_correto": "sim"}}))
    assert {"id": "p1-t55", "pergunta": "q2", "revisor": "sim", "observacao": ""} in r["indeterminados_do_gabarito"]


def test_importador_nao_altera_gabarito(data, tmp_path):
    antes = sha(RS.GT)
    review_import.import_review(_answers(tmp_path, data, {"p6-t3": {"revisor": "Ana", "q1_papel": "nao_medida"}}))
    assert sha(RS.GT) == antes
