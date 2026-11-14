"""Registro de envio/retorno do pacote de revisão. Confirmações e respostas aqui são SIMULADAS (logs em diretório temporário)."""
import csv, hashlib, shutil
from pathlib import Path
import pytest
from evaluation import review_dispatch as D, review_package as P
from evaluation.hashlog import HashLog, LogAdulterado
from evaluation.paths import EV, Caminhos

ENT = P.ROOT / P.VERSAO / "entrega"


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_mensagem_traz_as_orientacoes_obrigatorias_e_so_os_3_arquivos():
    m = D.MENSAGEM.read_text(encoding="utf-8")
    for t in ("Primeiro o desenho, depois a medição", "Não sei", "indeterminado", "sem linha azul", "nome completo", "somente o CSV exportado", *[p.name for p in ENT.iterdir()]): assert t in m
    assert [t for t in P.vazamentos(m) if t != "indeterminad"] == []          # 'indeterminado' é o termo pedido ao revisor, não um rótulo do gabarito


def test_preparar_registra_hashes_data_e_status_sem_afirmar_envio(tmp_path):
    antes = {p.name: sha(p) for p in ENT.iterdir()}
    e = D.preparar(log_path=tmp_path / "e.jsonl")
    assert e["status"] == "preparado_aguardando_envio" and e["arquivos_a_enviar"] == antes and sorted(antes) == sorted([P.HTML_NOME, P.CSV_NOME, P.PDF_NOME])
    assert "MANIFESTO_PACOTE.json" in e["nao_enviar"] and e["data"] and e["pacote"] == "pkg-1.1" and "nenhum envio foi realizado" in e["observacao"]
    assert {p.name: sha(p) for p in ENT.iterdir()} == antes                                   # arquivos intactos
    with pytest.raises(D.EnvioInvalido, match="já tem registro"): D.preparar(log_path=tmp_path / "e.jsonl")


def test_confirmar_envio_exige_pessoa_estado_e_os_3_arquivos(tmp_path):
    lp = tmp_path / "e.jsonl"; kw = dict(destinatario="Revisor Teste", canal="e-mail", enviado_em="2026-11-14", confirmado_por="Fulano da Silva", log_path=lp)
    with pytest.raises(D.EnvioInvalido, match="esperado: preparado"): D.confirmar_envio(**kw)
    D.preparar(log_path=lp)
    for ruim in ({"confirmado_por": "assistente"}, {"enviado_em": "14/11/2026"}, {"destinatario": ""}, {"arquivos_enviados": [P.HTML_NOME]},
                 {"arquivos_enviados": [P.HTML_NOME, P.CSV_NOME, P.PDF_NOME, "MANIFESTO_PACOTE.json"]}):
        with pytest.raises(D.EnvioInvalido): D.confirmar_envio(**{**kw, **ruim})
    e = D.confirmar_envio(**kw)
    assert e["status"] == "enviado" and e["confirmado_por"] == "Fulano da Silva" and e["arquivos_enviados"] == {p.name: sha(p) for p in ENT.iterdir()}
    log = HollowLog = HashLog(lp); assert [x["evento"] for x in log.entradas] == ["preparado", "envio_confirmado"]
    linhas = lp.read_text().splitlines(); lp.write_text(linhas[0].replace("pkg-1.1", "pkg-9.9") + "\n" + linhas[1] + "\n")
    with pytest.raises(LogAdulterado): HashLog(lp)


def test_preparar_recusa_pacote_adulterado(tmp_path):
    d = tmp_path / "pkg-1.1"; shutil.copytree(P.ROOT / "pkg-1.1", d)
    (d / "entrega" / P.CSV_NOME).chmod(0o644); (d / "entrega" / P.CSV_NOME).write_text("alterado", encoding="utf-8")
    with pytest.raises(D.EnvioInvalido, match="não confere"): D.preparar(root=tmp_path, log_path=tmp_path / "e.jsonl")


# ---------------------------------------------------------------- retorno (SIMULADO)
@pytest.fixture
def base(tmp_path):
    for rel in ("groundtruth/real_fernanda.json", "groundtruth/synthetic_manifest.json", "results/etapa0_baseline.json", "results/etapa0_relatorio.md",
                "baseline_etapa0/dimensions.py", "review/itens_selecionados.json"):
        d = tmp_path / rel; d.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(EV / rel, d)
    return Caminhos(tmp_path)


def _csv(tmp, mut=None):
    rows = list(csv.reader(open(ENT / P.CSV_NOME, encoding="utf-8-sig")))
    for r in rows[1:]: r[4], r[5], r[6], r[7] = "Revisor Simulado", "nao_sei", "nao_sei", "nao_sei"
    if mut: rows = mut(rows)
    f = tmp / "ret.csv"; csv.writer(open(f, "w", newline="", encoding="utf-8-sig")).writerows(rows); return f


@pytest.mark.parametrize("nome,mut,trecho", [
    ("falta_id", lambda r: r[:-1], "46 IDs"), ("id_extra", lambda r: r + [["p9-t99"] + r[1][1:]], "46 IDs"), ("duplicado", lambda r: r + [r[1]], "46 IDs"),
    ("texto_alterado", lambda r: [r[0], [r[1][0], r[1][1], "999"] + r[1][3:]] + r[2:], "alterados"),
    ("grupos_preenchido", lambda r: [r[0], r[1][:3] + ["controle"] + r[1][4:]] + r[2:], "grupos"),
    ("cabecalho", lambda r: [["x"] + r[0][1:]] + r[1:], "cabeçalho"),
    ("valor_invalido", lambda r: [r[0], r[1][:5] + ["talvez"] + r[1][6:]] + r[2:], "valor inválido")])
def test_validar_retorno_recusa_e_nao_registra(base, tmp_path, nome, mut, trecho):
    f = _csv(tmp_path, mut); v = D.validar_retorno(f, base)
    assert not v["ok"] and any(trecho in e for e in v["erros"]), v
    assert not base.respostas.exists() or not list(base.respostas.glob("*.csv"))


def test_retorno_so_e_registrado_se_enviado_e_valido_e_nao_resolve_nada(base, tmp_path):
    lp = tmp_path / "e.jsonl"; f = _csv(tmp_path); assert D.validar_retorno(f, base)["ok"]
    D.preparar(log_path=lp)
    with pytest.raises(D.EnvioInvalido, match="não consta como enviado"): D.registrar_retorno(f, base, recebido_de="Fulano", log_path=lp)
    D.confirmar_envio(destinatario="Revisor Simulado", canal="e-mail", enviado_em="2026-11-14", confirmado_por="Fulano da Silva", log_path=lp)
    gt = sha(base.gt_v0); e = D.registrar_retorno(f, base, recebido_de="Fulano", log_path=lp)
    assert e["status"] == "retorno_registrado" and e["itens_respondidos"] == 46 and sha(base.gt_v0) == gt
    assert not base.resolucoes.exists() and not base.versoes_log.exists()                      # nada resolvido/congelado
