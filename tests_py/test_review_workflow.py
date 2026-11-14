"""Fluxo de revisão independente -> registro -> relatório -> resolução -> congelamento (etapas 2 a 5).

ATENÇÃO: as respostas usadas aqui são SIMULADAS (fixtures de teste), em diretórios temporários. Nenhum arquivo real de revisão é tocado.
"""
import csv, hashlib, json, os, shutil
from pathlib import Path

import pytest

from evaluation import freeze_baseline as FB, resolutions as R, review_record as RC, review_report as RR
from evaluation.hashlog import HashLog, LogAdulterado
from evaluation.paths import EV, Caminhos
from evaluation.review_sheet import CSV_COLS

UP = Path(os.environ.get("LEGNA_FIXTURES", "/root/.claude/uploads/2776f07e-3ad9-5c9f-8cdd-0c5a8af5f4d9"))
TECH = UP / "0ad58788-DETALHAMENTO_DE_MARCENARIA_FERNANDA_SERTORIO.pdf"


def _real():
    try:
        return TECH.exists()
    except PermissionError:
        return False


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


@pytest.fixture
def base(tmp_path):
    """Cópia mínima da estrutura de evaluation/ em diretório temporário."""
    for rel in ("groundtruth/real_fernanda.json", "groundtruth/synthetic_manifest.json", "results/etapa0_baseline.json", "results/etapa0_relatorio.md",
                "baseline_etapa0/dimensions.py", "review/itens_selecionados.json"):
        d = tmp_path / rel; d.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(EV / rel, d)
    return Caminhos(tmp_path)


def gabarito_respostas(c, revisor, overrides=None, so_estes=None):
    """CSV de respostas SIMULADAS que concordam com o gabarito, exceto onde `overrides` disser o contrário."""
    gt = json.loads(c.gt_v0.read_text()); tok = {t["id"]: t for t in gt["tokens"]}; itens = json.loads(c.itens.read_text())["itens"]; overrides = overrides or {}
    p = c.base / f"resp_{revisor.replace(' ', '_')}.csv"
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(CSV_COLS)
        for it in itens:
            t = tok[it["id"]]; esp = RR.esperado_gabarito(t)
            ans = {"q1_papel": esp["q1"], "q2_intervalo_correto": esp["q2"] or "nao_sei", "q3_valor_correto": "sim"}
            ans.update(overrides.get(it["id"], {}))
            if so_estes is not None and it["id"] not in so_estes: ans = {k: "" for k in ans}
            w.writerow([it["id"], t["page"], t["text"], "|".join(it["grupos"]), revisor, ans["q1_papel"], ans["q2_intervalo_correto"], ans["q3_valor_correto"], "", "", ""])
    return p


# ------------------------------------------------------------------ etapa 2: registrar
def test_registro_guarda_byte_a_byte_nao_altera_gabarito_e_encadeia(base):
    antes = {p: sha(p) for p in (base.gt_v0, base.resultado_v0, base.algoritmo)}
    csv_ = gabarito_respostas(base, "Ana Lima"); e = RC.registrar(csv_, base, recebido_de="Legna")
    guardado = base.respostas / e["arquivo"]
    assert guardado.read_bytes() == csv_.read_bytes() and sha(guardado) == e["sha256"] and not os.access(guardado, os.W_OK) or guardado.stat().st_mode & 0o222 == 0
    assert e["revisor"] == "Ana Lima" and e["itens_respondidos"] == e["itens_total"] == 46 and e["recebido_de"] == "Legna"
    assert {p: sha(p) for p in antes} == antes                                          # gabarito, resultados e algoritmo intactos
    HashLog(base.manifesto_respostas)                                                    # cadeia verificável


@pytest.mark.parametrize("quebra,trecho", [
    ("id_desconhecido", "id desconhecido"), ("valor_invalido", "valor inválido"), ("sem_revisor", "exatamente 1 revisor"), ("dois_revisores", "exatamente 1 revisor"),
    ("revisor_sistema", "identificação humana"), ("vazio", "nenhum item respondido"), ("duplicado", "duplicado")])
def test_registro_recusa_arquivos_invalidos(base, quebra, trecho):
    p = gabarito_respostas(base, "Ana Lima", so_estes=set() if quebra == "vazio" else None)
    rows = list(csv.reader(open(p, encoding="utf-8-sig")))
    if quebra == "id_desconhecido": rows[1][0] = "p9-t99"
    if quebra == "valor_invalido": rows[1][5] = "talvez"
    if quebra == "sem_revisor": rows = [r[:4] + [""] + r[5:] for r in rows] and [rows[0]] + [r[:4] + [""] + r[5:] for r in rows[1:]]
    if quebra == "dois_revisores": rows[2][4] = "Outra Pessoa"
    if quebra == "revisor_sistema": rows = [rows[0]] + [r[:4] + ["sistema"] + r[5:] for r in rows[1:]]
    if quebra == "duplicado": rows.append(rows[1])
    csv.writer(open(p, "w", newline="", encoding="utf-8-sig")).writerows(rows)
    with pytest.raises(RC.RespostasInvalidas, match=trecho):
        RC.registrar(p, base)
    assert not base.manifesto_respostas.exists() or not HashLog(base.manifesto_respostas).entradas


def test_registro_recusa_repeticao_e_gabarito_alterado(base):
    p = gabarito_respostas(base, "Ana Lima"); RC.registrar(p, base)
    with pytest.raises(RC.RespostasInvalidas, match="já foi registrado"):
        RC.registrar(p, base)
    base.gt_v0.write_text(base.gt_v0.read_text().replace('"independent_review": false', '"independent_review": true'))      # alguém mexe no gabarito
    with pytest.raises(RC.RespostasInvalidas, match="gabarito original mudou"):
        RC.registrar(gabarito_respostas(base, "Bia Souza"), base)


# ------------------------------------------------------------------ etapa 3: relatório
CENARIO_A = {"p6-t3": {"q1_papel": "cota_regular"},                       # discorda do gabarito (que diz cota_deslocada)
             "p1-t9": {"q1_papel": "nao_sei"},                            # não sei
             "p1-t55": {"q2_intervalo_correto": "sim"}}                   # gabarito indeterminado, revisor responde
CENARIO_B = {"p6-t3": {"q1_papel": "cota_deslocada"}, "p1-t55": {"q2_intervalo_correto": "nao"}}          # B discorda de A em p1-t55 (q2); concorda com o gabarito em p6-t3


def test_relatorio_classifica_divergencias_e_concordancia_entre_revisores(base):
    RC.registrar(gabarito_respostas(base, "Ana Lima", CENARIO_A), base); RC.registrar(gabarito_respostas(base, "Bia Souza", CENARIO_B), base)
    rep = RR.gerar(base); it = {i["id"]: i for i in rep["itens"]}
    assert "discorda_do_gabarito" in it["p6-t3"]["tipos_divergencia"] and "revisor_nao_sei" in it["p1-t9"]["tipos_divergencia"]
    assert {"gabarito_indeterminado_com_resposta", "revisores_discordam"} <= set(it["p1-t55"]["tipos_divergencia"])
    assert set(rep["precisam_resolucao"]) >= {"p6-t3", "p1-t9", "p1-t55"} and not it["p1-t26"]["precisa_resolucao"]
    ana = rep["concordancia_por_revisor"]["Ana Lima"]["q1"]
    assert ana["discorda"] == 1 and ana["nao_sei"] == 1 and ana["concorda"] == 44                               # 46 itens: 44 + 1 + 1
    assert rep["inter_revisores"]["Ana Lima × Bia Souza · q2"]["itens_em_comum"] == 46 and rep["inter_revisores"]["Ana Lima × Bia Souza · q2"]["concordancia_simples"] < 1
    md = RR.render(rep)
    assert "O gabarito NÃO foi alterado" in md and "p6-t3" in md and "revisores_discordam" in md


def test_grupo_de_controle_dispara_alerta(base):
    itens = json.loads(base.itens.read_text())["itens"]; ctrl = [i["id"] for i in itens if "controle" in i["grupos"]]
    RC.registrar(gabarito_respostas(base, "Cris Melo", {i: {"q1_papel": "nota", "q2_intervalo_correto": "nao"} for i in ctrl}), base)
    rep = RR.gerar(base)
    assert rep["controle"]["Cris Melo"]["alerta"] is True and "abaixo do limiar" in RR.render(rep)


def test_relatorio_detecta_arquivo_de_respostas_alterado_depois_do_registro(base):
    e = RC.registrar(gabarito_respostas(base, "Ana Lima"), base); f = base.respostas / e["arquivo"]
    f.chmod(0o644); f.write_text(f.read_text(encoding="utf-8-sig").replace("cota_regular", "nota", 1), encoding="utf-8-sig")
    with pytest.raises(ValueError, match="alterado após o registro"):
        RR.gerar(base)


def test_kappa():
    assert RR.kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert RR.kappa(["a", "a", "b", "b"], ["b", "b", "a", "a"]) == -1.0


# ------------------------------------------------------------------ etapa 4: resolução
def _resolver(base, **kw):
    args = dict(item="p6-t3", campo="papel", decisao="alterar", valor_novo="cota_regular", evidencia_tipo="inspecao_visual",
                evidencia="o texto 15 está entre os riscos da cota de 710; revisor Ana confirmou na folha", decidido_por="Dora Reis")
    args.update(kw); return R.resolver(base, **args)


def test_resolucao_exige_evidencia_decisor_humano_e_valores_validos(base):
    casos = [({"evidencia": "curta"}, "ao menos"), ({"decidido_por": "sistema"}, "humano"), ({"decidido_por": ""}, "humano"), ({"campo": "x"}, "campo inválido"),
             ({"valor_novo": "banana"}, "inválido para papel"), ({"evidencia_tipo": "palpite"}, "tipo de evidência"), ({"item": "p9-t99"}, "não existe"),
             ({"decisao": "alterar", "valor_novo": "cota_deslocada"}, "valor diferente"),            # igual ao atual
             ({"decisao": "manter", "valor_novo": "cota_regular"}, "exige o valor atual"),
             ({"evidencia_tipo": "segundo_revisor"}, "segundo_revisor"),
             ({"item": "p1-t1", "valor_novo": "nao_cota"}, "não existe ou não faz parte")]                                      # token não revisado
    for kw, trecho in casos:
        with pytest.raises(R.ResolucaoInvalida, match=trecho):
            _resolver(base, **kw)
    assert not base.resolucoes.exists() or not HashLog(base.resolucoes).entradas


def test_resolucao_historico_rotulo_efetivo_e_gabarito_original_intacto(base):
    v0 = sha(base.gt_v0); tok = {t["id"]: t for t in json.loads(base.gt_v0.read_text())["tokens"]}["p6-t3"]
    e1 = _resolver(base)
    assert e1["valor_anterior"] == "cota_deslocada" and e1["valor_novo"] == "cota_regular" and e1["decidido_por"] == "Dora Reis"
    assert R.rotulo_efetivo(tok, HashLog(base.resolucoes).entradas)["papel"] == "cota_regular" and R.rotulo_efetivo(tok, [])["papel"] == "cota_deslocada"
    e2 = _resolver(base, decisao="alterar", valor_novo="cota_deslocada", evidencia="segunda análise: a chamada com curva indica texto deslocado; reverter", decidido_por="Eli Prado")
    assert e2["valor_anterior"] == "cota_regular"                                                   # cadeia de valores preservada
    assert sha(base.gt_v0) == v0                                                                     # o original NUNCA muda
    assert [e["seq"] for e in HashLog(base.resolucoes).entradas] == [1, 2]


def test_resolucao_segundo_revisor_exige_resposta_registrada(base):
    e = RC.registrar(gabarito_respostas(base, "Ana Lima"), base)
    r = _resolver(base, evidencia_tipo="segundo_revisor", revisores_citados=[e["sha256"][:8]], evidencia="duas leituras independentes concordam que o texto fica entre os riscos")
    assert r["revisores_citados"] == [e["sha256"][:8]]
    with pytest.raises(R.ResolucaoInvalida):
        _resolver(base, item="p1-t9", campo="papel", valor_novo="cota_regular", evidencia_tipo="segundo_revisor", revisores_citados=["deadbeef"], evidencia="citação de arquivo que não existe no registro")


def test_log_de_resolucoes_detecta_adulteracao(base):
    _resolver(base); _resolver(base, decisao="manter", valor_novo="cota_regular", evidencia="reconferido: o valor permanece, evidência registrada no cartão", decidido_por="Eli Prado")
    linhas = base.resolucoes.read_text().splitlines()
    for nome, ls in {"alterada": [linhas[0].replace("Dora Reis", "Outro Nome")] + linhas[1:], "removida": linhas[1:], "reordenada": linhas[::-1]}.items():
        base.resolucoes.write_text("\n".join(ls) + "\n")
        with pytest.raises(LogAdulterado):
            HashLog(base.resolucoes)


# ------------------------------------------------------------------ etapa 5: congelar
def _preparar_ate_resolvido(base):
    RC.registrar(gabarito_respostas(base, "Ana Lima", CENARIO_A), base)
    rep = RR.gerar(base)
    _resolver(base)                                                                                                               # p6-t3: altera papel
    _resolver(base, item="p1-t9", decisao="manter", valor_novo="cota_deslocada", evidencia="15+650+15=680 confirma o valor; chamada de espessura; papel mantido", decidido_por="Dora Reis")
    _resolver(base, item="p1-t55", campo="veredito_associacao", decisao="alterar", valor_novo="correta", evidencia_tipo="decisao_conjunta",
              evidencia="revisor e responsável concordam: o intervalo azul cobre a cota de 450 entre as prateleiras", decidido_por="Dora Reis")
    return rep


def test_congelar_recusa_sem_respostas_sem_resolver_e_versao_invalida(base):
    with pytest.raises(FB.CongelamentoRecusado, match="nenhuma resposta"):
        FB.congelar(base, "rev1", congelado_por="Dora Reis", avaliar=False)
    RC.registrar(gabarito_respostas(base, "Ana Lima", CENARIO_A), base)
    with pytest.raises(FB.CongelamentoRecusado, match="sem resolução"):
        FB.congelar(base, "rev1", congelado_por="Dora Reis", avaliar=False)
    with pytest.raises(FB.CongelamentoRecusado, match="formato revN"):
        FB.congelar(base, "versao-final", congelado_por="Dora Reis", avaliar=False)


def test_congelar_cria_versao_imutavel_rastreavel_e_verificavel(base):
    _preparar_ate_resolvido(base); antes = {p: sha(p) for p in (base.gt_v0, base.resultado_v0, base.algoritmo)}
    FB.registrar_v0(base)
    e = FB.congelar(base, "rev1", congelado_por="Dora Reis", avaliar=False)
    d = base.versoes_dir / "rev1"; gt = json.loads((d / "real_fernanda.json").read_text()); tok = {t["id"]: t for t in gt["tokens"]}
    assert {p: sha(p) for p in antes} == antes                                                      # v0 intocada
    assert tok["p6-t3"]["role"] == "cota_regular" and tok["p1-t55"]["assoc_verdict_baseline"] == "correta" and tok["p1-t9"]["role"] == "cota_deslocada"
    h = tok["p6-t3"]["historico_alteracoes"][0]
    assert (h["de"], h["para"], h["decidido_por"]) == ("cota_deslocada", "cota_regular", "Dora Reis") and h["evidencia"]
    assert gt["versao"] == "rev1" and gt["derivado_de"]["sha256"] == sha(base.gt_v0) and gt["independent_review"] is True
    assert gt["revisao_independente"]["revisores"] == ["Ana Lima"] and gt["revisao_independente"]["itens_conferidos"] == 46
    assert any("SOMENTE os 46 itens" in x for x in gt["limitacoes"])                                # honestidade: o resto segue sem conferência
    assert all(not os.access(d / n, os.W_OK) for n in ("real_fernanda.json", "MANIFEST.json")) or (d / "MANIFEST.json").stat().st_mode & 0o222 == 0
    assert FB.verificar_versao(base, "rev1") == [] and e["versao"] == "rev1"
    with pytest.raises(FB.CongelamentoRecusado, match="já existe"):
        FB.congelar(base, "rev1", congelado_por="Dora Reis", avaliar=False)
    assert {t["id"] for t in gt["tokens"] if t.get("historico_alteracoes")} == {"p6-t3", "p1-t9", "p1-t55"}      # só os resolvidos mudam/ganham histórico


@pytest.mark.parametrize("o_que", ["arquivo_da_versao", "resolucoes", "respostas", "algoritmo", "gabarito_v0"])
def test_verificacao_detecta_qualquer_adulteracao(base, o_que):
    _preparar_ate_resolvido(base); FB.congelar(base, "rev1", congelado_por="Dora Reis", avaliar=False); assert FB.verificar_versao(base, "rev1") == []
    alvo = {"arquivo_da_versao": base.versoes_dir / "rev1" / "real_fernanda.json", "resolucoes": base.resolucoes, "respostas": next(base.respostas.glob("*.csv")),
            "algoritmo": base.algoritmo, "gabarito_v0": base.gt_v0}[o_que]
    alvo.chmod(0o644); alvo.write_text(alvo.read_text(encoding="utf-8-sig") + ("\n# alterado\n" if o_que in ("algoritmo",) else " "), encoding="utf-8")
    assert FB.verificar_versao(base, "rev1"), o_que


@pytest.mark.skipif(not _real(), reason="PDF real ausente")
def test_congelar_reavalia_com_algoritmo_congelado_e_registra_so_diferencas_de_rotulo(base):
    _preparar_ate_resolvido(base)
    FB.congelar(base, "rev1", congelado_por="Dora Reis", pdf=str(TECH), avaliar=True)
    d = base.versoes_dir / "rev1"; novo = json.loads((d / "etapa0_baseline_rev1.json").read_text()); v0 = json.loads(base.resultado_v0.read_text())
    assert novo["meta"]["algoritmo"]["sha256"] == v0["meta"]["algoritmo"]["sha256"]                    # mesmo algoritmo
    assert novo["sintetico"]["por_estilo"] == v0["sintetico"]["por_estilo"]                            # sintético não depende dos rótulos reais
    a = {r["id"]: r for r in v0["real"]["linhas"]}; b = {r["id"]: r for r in novo["real"]["linhas"]}
    mudaram = {i for i in a if (a[i]["outcome"], a[i]["role"]) != (b[i]["outcome"], b[i]["role"])}
    assert mudaram <= {"p6-t3", "p1-t9", "p1-t55"} and "p6-t3" in mudaram                              # só itens resolvidos podem mudar
    assert {r["status"] for r in b.values()} == {r["status"] for r in a.values()} and [r["status"] for r in b.values()] == [r["status"] for r in a.values()]
    assert (d / "diff_vs_v0.md").read_text().count("p6-t3") >= 1 and FB.verificar_versao(base, "rev1") == []


# ------------------------------------------------------------------ repositório real
def test_v0_real_esta_registrada_e_inalterada():
    c = Caminhos(); antes = HashLog(c.versoes_log).cabeca
    e = FB.registrar_v0(c)                                                  # confirma sem criar entrada nova
    assert e["versao"] == "v0" and HashLog(c.versoes_log).cabeca == antes and e["independent_review"] is False
    assert e["artefatos"]["algoritmo_sha256"] == sha(c.algoritmo) == sha(EV.parent / "ingest" / "dimensions.py")
