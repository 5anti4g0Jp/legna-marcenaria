"""Pacotes de revisão independente cegos (pkg-1.0 histórico, pkg-1.1 vigente). Respostas usadas aqui são SIMULADAS."""
import csv, hashlib, json, re, shutil
from pathlib import Path
import pytest
from evaluation import review_package as P, review_record as RC, review_report as RR
from evaluation.hashlog import HashLog
from evaluation.paths import EV, Caminhos

PKG10, PKG11 = P.ROOT / "pkg-1.0" / "entrega", P.ROOT / "pkg-1.1" / "entrega"
H10 = {"legna_revisao_pkg-1.0_folha.html": "8d345e85f371c62d3e706088c0de564b4ad23479a59db1b23ff98676cb909a5e",
       "legna_revisao_pkg-1.0_respostas.csv": "46892c19a7342cd7d9a0dd07a1aaa8f7fad62565d6e5921d2c6101cc714826ca"}
SEM_LINHA = ["p1-t6", "p1-t7", "p1-t13", "p1-t16", "p1-t20", "p1-t30", "p1-t32", "p1-t34", "p1-t37", "p6-t18", "p6-t22", "p6-t25", "p6-t31", "p10-t4", "p10-t13", "p10-t14"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_pkg10_historico_preservado_e_verificavel():
    assert {n: sha(PKG10 / n) for n in H10} == H10 and P.verificar(versao="pkg-1.0") == []
    assert sorted(p.name for p in PKG10.iterdir()) == sorted(H10)                      # continua com somente 2 arquivos


@pytest.mark.parametrize("versao,esperado", [("pkg-1.0", 2), ("pkg-1.1", 3)])
def test_entrega_hashes_conferem(versao, esperado):
    d = P.ROOT / versao; man = json.loads((d / "MANIFESTO_PACOTE.json").read_text())
    assert len(list((d / "entrega").iterdir())) == esperado == len(man["arquivos_entregues"]) and P.verificar(versao=versao) == []
    assert all(sha(d / "entrega" / n) == m["sha256"] for n, m in man["arquivos_entregues"].items())


def test_pkg11_conteudo_exato_e_pdf_identico_ao_original():
    assert sorted(p.name for p in PKG11.iterdir()) == sorted([P.HTML_NOME, P.CSV_NOME, P.PDF_NOME])
    assert sha(PKG11 / P.PDF_NOME) == P.PDF_SHA256 and P.inspecionar_pdf(PKG11 / P.PDF_NOME) == []
    for n in (P.HTML_NOME, P.CSV_NOME, P.PDF_NOME):
        assert not (PKG11 / n).stat().st_mode & 0o222, n                                # somente leitura
    assert "fernanda" not in P.PDF_NOME.lower() and "sertorio" not in P.PDF_NOME.lower()


def test_pkg11_ids_preservados_sem_vazamento_e_csv_igual_ao_pkg10():
    ids = [i["id"] for i in json.loads(P.ITENS.read_text())["itens"]]
    html = (PKG11 / P.HTML_NOME).read_text(encoding="utf-8")
    rows = list(csv.DictReader(open(PKG11 / P.CSV_NOME, encoding="utf-8-sig")))
    assert len(ids) == 46 and sorted(re.findall(r'data-id="([^"]+)"', html)) == sorted(ids) == sorted(r["id"] for r in rows)
    assert "<details" not in html and "data-grupos" not in html and all(r["grupos"] == "" for r in rows)
    assert P.vazamentos(html) == [] and P.vazamentos((PKG11 / P.CSV_NOME).read_text(encoding="utf-8")) == []
    assert sha(PKG11 / P.CSV_NOME) == sha(PKG10 / "legna_revisao_pkg-1.0_respostas.csv")      # instrumento de resposta idêntico


def test_pkg11_instrucoes_corrigidas_e_novas():
    html = (PKG11 / P.HTML_NOME).read_text(encoding="utf-8")
    assert "o riscos" not in html and "os riscos" in html
    for t in ("sem linha azul", "Não sei", "Material de referência", P.PDF_NOME, "somente leitura", "Valores aceitos no CSV", "pkg-1.1"): assert t in html
    assert "o riscos" in (PKG10 / "legna_revisao_pkg-1.0_folha.html").read_text(encoding="utf-8")   # histórico intacto (com o erro original)


def test_pkg11_manifesto_documenta_alteracoes_exclusoes_e_historico():
    man = json.loads((P.ROOT / "pkg-1.1" / "MANIFESTO_PACOTE.json").read_text())
    assert man["substitui"] == "pkg-1.0" and len(man["alteracoes_vs_pkg_1_0"]) >= 5 and man["exclusoes_q2"]["ids"] == SEM_LINHA
    assert man["exclusoes_q2"]["sha256"] == sha(EV / "review" / "exclusoes_q2.json")
    assert man["preservado_do_pkg_1_0"]["manifesto_sha256_inalterado"] and "MANIFESTO_PACOTE.json" in man["preservado_do_pkg_1_0"]["arquivos_e_hashes"]
    assert {n: man["preservado_do_pkg_1_0"]["arquivos_e_hashes"][f"entrega/{n}"] for n in H10} == H10


def test_exclusoes_detectadas_conferem_com_imagens_e_nao_alteram_gabarito():
    sem, sep = P.sem_linha_azul()
    assert sem == SEM_LINHA and sep["max_pixels_nos_sem_linha"] < sep["min_pixels_nos_com_linha"]
    exc = json.loads((EV / "review" / "exclusoes_q2.json").read_text())
    assert exc["ids"] == SEM_LINHA and exc["gabarito_v0_alterado"] is False and set(exc["ids"]) <= {i["id"] for i in json.loads(P.ITENS.read_text())["itens"]}


def test_detector_de_vazamento_pega_termos():
    assert "gabarito" in P.vazamentos("Rótulo do gabarito: x") and P.vazamentos("texto neutro 15 mm") == []


# ---------------------------------------------------------------- relatório com exclusão (SIMULADO, diretório temporário)
@pytest.fixture
def base(tmp_path):
    for rel in ("groundtruth/real_fernanda.json", "groundtruth/synthetic_manifest.json", "results/etapa0_baseline.json", "results/etapa0_relatorio.md",
                "baseline_etapa0/dimensions.py", "review/itens_selecionados.json"):
        d = tmp_path / rel; d.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(EV / rel, d)
    return Caminhos(tmp_path)


def _resp(c, nome, q2_excl):
    from test_review_workflow import gabarito_respostas
    return gabarito_respostas(c, nome, {i: {"q2_intervalo_correto": q2_excl} for i in SEM_LINHA})


def test_csv_do_pacote_preenchido_e_aceito_pelo_registro_SIMULADO(base):
    rows = list(csv.reader(open(PKG11 / P.CSV_NOME, encoding="utf-8-sig")))
    for r in rows[1:]: r[4], r[5], r[6], r[7] = "Revisor Simulado", "nao_sei", "nao_sei", "nao_sei"
    f = base.base / "simulado.csv"; csv.writer(open(f, "w", newline="", encoding="utf-8-sig")).writerows(rows)
    assert RC.registrar(f, base)["itens_respondidos"] == 46


def test_relatorio_sem_exclusao_conta_q2_dos_16_como_divergencia_e_com_exclusao_nao(base):
    RC.registrar(_resp(base, "Ana Lima", "nao_sei"), base)                          # instrução do pkg-1.1: Q2 = "Não sei" nos itens sem linha
    sem = RR.gerar(base)
    assert set(SEM_LINHA) <= set(sem["precisam_resolucao"]) and sem["exclusoes_q2"]["n"] == 0                   # sem o registro: 16 falsas divergências
    shutil.copyfile(EV / "review" / "exclusoes_q2.json", base.exclusoes_q2)
    com = RR.gerar(base)
    assert not set(SEM_LINHA) & set(com["precisam_resolucao"]) and com["exclusoes_q2"]["n"] == 16
    q2 = com["concordancia_por_revisor"]["Ana Lima"]["q2"]
    assert q2["excluida"] == 16 and q2["discorda"] == 0 and sum(q2[k] for k in ("concorda", "discorda", "nao_sei", "gabarito_indeterminado", "sem_resposta", "excluida")) == 46
    assert "Pergunta 2 excluída" in RR.render(com)


def test_exclusao_vale_mesmo_se_revisor_responder_outra_coisa_e_nao_afeta_q1_q3_nem_controle(base):
    RC.registrar(_resp(base, "Ana Lima", "nao"), base); RC.registrar(_resp(base, "Bia Souza", "sim"), base)
    shutil.copyfile(EV / "review" / "exclusoes_q2.json", base.exclusoes_q2)
    rep = RR.gerar(base)
    it = {i["id"]: i for i in rep["itens"]}
    for i in SEM_LINHA:
        assert it[i]["respostas"]["Ana Lima"]["comparacao"]["q2"] == "excluida" and "revisores_discordam" not in it[i]["tipos_divergencia"] and not it[i]["precisa_resolucao"]
    assert rep["inter_revisores"]["Ana Lima × Bia Souza · q2"]["itens_em_comum"] == 46 - 16
    assert rep["controle"]["Ana Lima"]["alerta"] is False
    # Q1/Q3 desses itens continuam comparados
    assert it["p1-t6"]["respostas"]["Ana Lima"]["comparacao"]["q1"] in ("concorda", "discorda") and it["p1-t6"]["respostas"]["Ana Lima"]["comparacao"]["q3"] == "concorda"


def test_gerar_pkg_novo_nao_sobrescreve_e_nao_toca_fontes(tmp_path):
    if not P.PDF_ORIGEM.exists(): pytest.skip("PDF de origem ausente")
    antes = (sha(P.ORIGINAL), sha(P.ITENS), sha(PKG10 / "legna_revisao_pkg-1.0_folha.html"))
    exc = tmp_path / "exc.json"; man = P.gerar(tmp_path, exclusoes_path=exc)
    assert man["n_itens"] == 46 and exc.exists() and (sha(P.ORIGINAL), sha(P.ITENS), sha(PKG10 / "legna_revisao_pkg-1.0_folha.html")) == antes
    with pytest.raises(FileExistsError): P.gerar(tmp_path, exclusoes_path=tmp_path / "outro.json")
    assert P.verificar(tmp_path) == []


def test_gerar_recusa_pdf_que_nao_confere(tmp_path):
    falso = tmp_path / "x.pdf"; falso.write_bytes(b"%PDF-1.4 falso")
    with pytest.raises(ValueError, match="não confere"): P.gerar(tmp_path / "r", pdf_path=falso, exclusoes_path=tmp_path / "e.json")
