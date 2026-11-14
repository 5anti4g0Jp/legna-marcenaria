"""Etapa 1: seis estados, modelo rastreável, registro de revisões humanas e equivalência com a baseline da Etapa 0."""
import itertools, json, os
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation import metrics as M
from evaluation.adapters import dims_from_resultado
from evaluation.synthetic import Builder, build_all
from ingest.technical import schema
from ingest.technical.__main__ import main as cli
from ingest.technical.model import (PERMITIDAS, Ator, AtorTipo, Documento, Estado, Evidencia, Medida, Resultado, Transicao, TransicaoProibida, agora)
from ingest.technical.pipeline import analisar_pdf
from ingest.technical.revisao import RegistroAdulterado, RegistroRevisoes, aplicar_revisoes

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evaluation"
UP = Path(os.environ.get("LEGNA_FIXTURES", "/root/.claude/uploads/2776f07e-3ad9-5c9f-8cdd-0c5a8af5f4d9"))
TECH = UP / "0ad58788-DETALHAMENTO_DE_MARCENARIA_FERNANDA_SERTORIO.pdf"
E, G, C, S, P, A = Estado.EXTRAIDO, Estado.GEOMETRICAMENTE_CONSISTENTE, Estado.CONFLITO, Estado.SEM_MEDICAO, Estado.PENDENTE_REVISAO, Estado.APROVADO
SIS, HUM = Ator(tipo=AtorTipo.SISTEMA, id="alg"), Ator(tipo=AtorTipo.HUMANO, id="Maria Souza")


def _real_ok():
    try:
        return TECH.exists()
    except PermissionError:
        return False


real = pytest.mark.skipif(not _real_ok(), reason="PDF real de teste ausente")


def nova(estado=E):
    m = Medida(id="m1", documento=Documento(arquivo="x.pdf", sha256="a" * 64), pagina=1, texto_original="450", coords=(0, 0, 10, 10), metodo_extracao="text-layer",
               evidencias=(Evidencia(tipo="leitura", descricao="lido", metodo="text-layer"),), historico=(Transicao(de=None, para=E, ator=SIS, em=agora(), motivo="lida"),))
    caminho = {E: [], G: [G], C: [C], S: [S], P: [G, P], A: [G, P, A]}[estado]
    for destino in caminho:
        if destino == A: m.aprovar("Maria Souza")
        else: m.transitar(destino, SIS, "caminho")
    return m


# ---------------------------------------------------------------- estados e transições
def test_exatamente_seis_estados():
    assert {e.value for e in Estado} == {"extraido", "geometricamente_consistente", "conflito", "sem_medicao", "pendente_revisao", "aprovado"}


def test_unico_caminho_para_aprovado_e_humano_a_partir_de_pendente():
    assert {k: v for k, v in PERMITIDAS.items() if k[1] == A} == {(P, A): frozenset({AtorTipo.HUMANO})}


@pytest.mark.parametrize("de,para,ator", [(d, p, a) for d, p, a in itertools.product(list(Estado), list(Estado), (SIS, HUM))])
def test_autoridade_de_transicao_exaustiva(de, para, ator):
    m = nova(de)
    esperado = ator.tipo in PERMITIDAS.get((de, para), frozenset())
    if esperado:
        m._checar(para, ator, "teste")                                   # não levanta
    else:
        with pytest.raises(TransicaoProibida):
            m._checar(para, ator, "teste")


def test_transicao_proibida_nao_altera_a_medida():
    m = nova(G); antes = m.model_dump()
    for para, ator in ((A, SIS), (A, HUM), (E, SIS), (G, SIS), (S, SIS), (C, HUM)):          # nenhuma é permitida a partir de G
        with pytest.raises((TransicaoProibida, ValidationError)):
            m.transitar(para, ator, "tentativa")
    assert m.model_dump() == antes


def test_geometricamente_consistente_nunca_vira_aprovado_direto():
    m = nova(G)
    with pytest.raises(TransicaoProibida):
        m.aprovar("Maria Souza")                                         # precisa passar por pendente_revisao
    assert m.estado == G
    m.enfileirar_revisao(SIS); m.aprovar("Maria Souza")
    assert m.estado == A and [t.para for t in m.historico] == [E, G, P, A]


@pytest.mark.parametrize("revisor", ["", "   ", "sistema", "Sistema", "algoritmo", "IA", "claude", "auto"])
def test_aprovacao_exige_humano_identificado(revisor):
    m = nova(P)
    with pytest.raises((ValidationError, TransicaoProibida)):
        m.aprovar(revisor)
    assert m.estado == P and m.revisao is None


def test_sistema_nao_pode_aprovar_nem_com_revisao_forjada():
    m = nova(P)
    with pytest.raises(TransicaoProibida):
        m.transitar(A, SIS, "auto-aprovação")
    assert m.estado == P


def test_estado_nao_e_gravavel_e_colecoes_sao_imutaveis():
    m = nova(G)
    for nome, valor in (("estado", A), ("historico", ()), ("revisao", None), ("evidencias", ()), ("pagina", 9)):
        with pytest.raises(AttributeError):
            setattr(m, nome, valor)
    with pytest.raises(AttributeError):
        m.historico.append(1)
    assert m.estado == G


def test_json_adulterado_e_recusado():
    d = nova(G).model_dump(mode="json")
    d["estado"] = "aprovado"
    with pytest.raises(ValidationError):
        Medida.model_validate(d)                                         # estado declarado difere do histórico
    d2 = nova(G).model_dump(mode="json"); d2.pop("estado")
    d2["historico"].append({"de": "geometricamente_consistente", "para": "aprovado", "ator": {"tipo": "sistema", "id": "alg"}, "em": "t", "motivo": "forjado"})
    with pytest.raises(ValidationError):
        Medida.model_validate(d2)                                        # transição inválida no histórico
    d3 = nova(P).model_dump(mode="json"); d3.pop("estado")
    d3["historico"].append({"de": "pendente_revisao", "para": "aprovado", "ator": {"tipo": "humano", "id": "Maria"}, "em": "t", "motivo": "x"})
    with pytest.raises(ValidationError):
        Medida.model_validate(d3)                                        # 'aprovado' sem revisão registrada


def test_rejeicao_e_revogacao_humanas_preservam_historico():
    m = nova(P); m.rejeitar("Maria Souza", "valor ilegível", "460")
    assert m.estado == C and m.revisao.decisao == "rejeitado" and m.revisao.valor_confirmado == "460"
    m.enfileirar_revisao(HUM); m.aprovar("Joao Lima"); m.revogar("Joao Lima", "conferir de novo")
    assert m.estado == P and m.revisao is None
    assert [t.para for t in m.historico] == [E, G, P, C, P, A, P]                                   # nada é apagado do histórico
    assert sum(1 for e in m.evidencias if e.tipo == "revisao_humana") == 3


# ---------------------------------------------------------------- pipeline (sintético, sem arquivos privados)
@pytest.fixture(scope="module")
def sinteticos(tmp_path_factory):
    d = tmp_path_factory.mktemp("sint"); docs = build_all(d)
    return {s.name: (s, analisar_pdf(s.path)) for s in docs}


def test_nenhuma_medida_sai_aprovada(sinteticos):
    for nome, (_, r) in sinteticos.items():
        assert r.resumo.aprovadas_automaticamente == 0 and r.resumo.por_estado["aprovado"] == 0, nome
        assert all(m.estado != A and all(t.ator.tipo == AtorTipo.SISTEMA for t in m.historico) for m in r.medidas)


def test_enfileirar_leva_tudo_a_pendente_sem_aprovar(tmp_path):
    s = [x for x in build_all(tmp_path) if x.name == "lay_acima"][0]
    r = analisar_pdf(s.path, enfileirar=True)
    assert {m.estado for m in r.medidas} == {P} and r.resumo.aprovadas_automaticamente == 0
    assert all(m.analise_automatica.estado != P for m in r.medidas)      # a análise original continua gravada


def test_rastreabilidade_completa(sinteticos):
    for nome, (s, r) in sinteticos.items():
        assert r.documento.sha256 == __import__("hashlib").sha256(Path(s.path).read_bytes()).hexdigest()
        for m in r.medidas:
            assert m.documento.sha256 == r.documento.sha256 and m.pagina >= 1 and len(m.coords) == 4 and m.metodo_extracao and m.confianca is not None
            assert m.texto_original and m.historico[0].para == E and m.historico[0].de is None
            tipos = [e.tipo for e in m.evidencias]
            assert tipos[:2] == ["leitura", "unidade"] and len(tipos) >= 3
            assert m.analise_automatica.algoritmo_sha256 == r.algoritmo.sha256
            if m.estado == G: assert "geometria" in tipos
            if m.estado == C: assert "conflito_geometrico" in tipos and m.conflitos
            if m.estado == S: assert "sem_medicao" in tipos
            ev = next(e for e in m.evidencias if e.tipo == "leitura")
            assert ev.coords == m.coords


def test_geometricamente_consistente_carrega_ressalva_de_nao_aprovacao(sinteticos):
    _, r = sinteticos["lay_acima"]
    m = next(x for x in r.medidas if x.estado == G)
    ev = next(e for e in m.evidencias if e.tipo == "geometria")
    assert "NÃO é aprovação" in ev.dados["ressalva"] and ev.dados["escala_mm_por_pt"] and ev.dados["intervalo_pt"] and ev.coords


def test_unidade_declarada_x_assumida(tmp_path):
    b = Builder("unid", "lay")
    for i, v in enumerate((200, 300, 100, 400)):
        b.dim((100, 60 + i * 30), (100 + v / 4.0, 60 + i * 30), str(v), "lay", scale=4.0)
    b.page.insert_text((300, 20), "COTAS EM MILÍMETROS", fontsize=9)
    com = analisar_pdf(b.save(tmp_path).path)
    assert all(m.unidade_fonte == "declarada_na_pagina" for m in com.medidas)
    b2 = Builder("unid2", "lay")
    for i, v in enumerate((200, 300, 100, 400)):
        b2.dim((100, 60 + i * 30), (100 + v / 4.0, 60 + i * 30), str(v), "lay", scale=4.0)
    sem = analisar_pdf(b2.save(tmp_path).path)
    assert all(m.unidade_fonte == "assumida" for m in sem.medidas)
    assert any(e.dados.get("assumida") for e in sem.medidas[0].evidencias if e.tipo == "unidade")


def test_texto_inclinado_e_declarado_como_tal(sinteticos):
    _, r = sinteticos["inclinada"]
    assert {m.orientacao for m in r.medidas} == {"inclinada"} and {m.estado for m in r.medidas} == {S}
    assert all(any(e.tipo == "orientacao" for e in m.evidencias) for m in r.medidas)


def test_algoritmo_registrado_e_o_congelado(sinteticos):
    frozen = M.sha256(EV / "baseline_etapa0" / "dimensions.py")
    assert all(r.algoritmo.sha256 == frozen for _, r in sinteticos.values())


# ---------------------------------------------------------------- equivalência com a baseline da Etapa 0
def _outcomes_sinteticos(s, r):
    dims = dims_from_resultado(r)
    items = [{"id": t.id, "text": t.text, "bbox": t.bbox, "role": t.role, "orientation": t.orientation, "planted_error": t.planted_error, "interval_pt": t.interval_pt} for t in s.truths]
    al = M.align(items, dims); out = {}
    for it in items:
        d = al[it["id"]]
        assoc = M.synthetic_assoc(it, d) if (d is not None and d.status in M.MEASURED and it["role"].startswith("cota")) else None
        out[it["id"]] = M.outcome(it, d, assoc)
    return out


def test_equivalencia_sintetica_com_a_baseline(sinteticos):
    saved = {r["id"]: r["outcome"] for r in json.loads((EV / "results" / "etapa0_baseline.json").read_text())["sintetico"]["linhas"]}
    novos = {}
    for s, r in sinteticos.values():
        novos.update(_outcomes_sinteticos(s, r))
    assert novos == saved                                                # mesmos 60 resultados, item a item


def test_estados_equivalem_aos_status_do_baseline(sinteticos):
    mapa = {"confirmado": G, "confirmado_local": G, "conflito": C, "sem_medicao": S, "sem_escala": S}
    for _, r in sinteticos.values():
        assert all(m.estado == mapa[m.analise_automatica.estado_algoritmo] for m in r.medidas)


@real
def test_equivalencia_real_com_a_baseline():
    saved = json.loads((EV / "results" / "etapa0_baseline.json").read_text())
    gt = json.loads((EV / "groundtruth" / "real_fernanda.json").read_text())
    r = analisar_pdf(TECH)
    assert r.resumo.por_estado["aprovado"] == 0 and r.resumo.aprovadas_automaticamente == 0
    base = saved["real"]["estados_baseline_todas_as_paginas"]
    assert r.resumo.por_estado["geometricamente_consistente"] == base["confirmado"] + base["confirmado_local"]
    assert r.resumo.por_estado["conflito"] == base["conflito"]
    assert r.resumo.por_estado["sem_medicao"] == base["sem_medicao"] + base["sem_escala"]
    tok = {t["id"]: t for t in gt["tokens"]}; novos = {}
    for pn in (1, 6, 10):
        items = [t for t in gt["tokens"] if t["page"] == pn and t["reviewed"]]
        al = M.align(items, dims_from_resultado(r, pn))
        for it in items:
            d = al[it["id"]]; assoc = it.get("assoc_verdict_baseline") if (d is not None and d.status in M.MEASURED) else None
            novos[it["id"]] = M.outcome(it, d, assoc)
    assert novos == {x["id"]: x["outcome"] for x in saved["real"]["linhas"]}


# ---------------------------------------------------------------- registro de revisões humanas
@pytest.fixture
def analise(tmp_path):
    s = [x for x in build_all(tmp_path) if x.name == "lay_acima"][0]
    return s, analisar_pdf(s.path)


def test_registro_cadeia_de_hash_detecta_adulteracao(analise, tmp_path):
    _, r = analise; reg = RegistroRevisoes(tmp_path / "r.jsonl")
    for m in r.medidas[:3]:
        reg.registrar(medida=m, decisao="aprovado", revisor="Maria Souza")
    RegistroRevisoes(tmp_path / "r.jsonl")                              # recarrega e verifica: ok
    linhas = (tmp_path / "r.jsonl").read_text().splitlines()
    casos = {"alterada": [linhas[0].replace("Maria Souza", "Outro Nome")] + linhas[1:], "removida": linhas[1:], "reordenada": [linhas[1], linhas[0], linhas[2]],
             "inserida": linhas[:1] + [linhas[0]] + linhas[1:]}
    for nome, ls in casos.items():
        (tmp_path / f"{nome}.jsonl").write_text("\n".join(ls) + "\n")
        with pytest.raises(RegistroAdulterado):
            RegistroRevisoes(tmp_path / f"{nome}.jsonl")


def test_registro_recusa_revisor_nao_humano(analise):
    _, r = analise
    for rev in ("sistema", "", "IA"):
        with pytest.raises((ValidationError, ValueError)):
            RegistroRevisoes().registrar(medida=r.medidas[0], decisao="aprovado", revisor=rev)


def test_aplicar_aprovacao_preserva_analise_e_historico(analise):
    _, r = analise; reg = RegistroRevisoes()
    alvo = next(m for m in r.medidas if m.estado == G); analise_antes = alvo.analise_automatica.model_dump()
    reg.registrar(medida=alvo, decisao="aprovado", revisor="Maria Souza", observacao="conferido no desenho")
    rel = aplicar_revisoes(r, reg)
    assert len(rel["aplicadas"]) == 1 and alvo.estado == A and alvo.revisao.revisor == "Maria Souza"
    assert alvo.analise_automatica.model_dump() == analise_antes         # o que o algoritmo concluiu NÃO é apagado
    assert [t.para for t in alvo.historico] == [E, G, P, A] and alvo.historico[-1].ator.tipo == AtorTipo.HUMANO
    assert r.resumo.por_estado["aprovado"] == 1 and r.resumo.aprovadas_automaticamente == 0
    assert aplicar_revisoes(r, reg)["ja_aplicadas"] and alvo.estado == A  # idempotente


def test_aplicar_rejeicao_e_ultima_decisao_prevalece(analise):
    _, r = analise; reg = RegistroRevisoes(); alvo = r.medidas[0]
    reg.registrar(medida=alvo, decisao="aprovado", revisor="Maria Souza")
    reg.registrar(medida=alvo, decisao="rejeitado", revisor="Joao Lima", observacao="valor errado", valor_confirmado="999")
    aplicar_revisoes(r, reg)
    assert alvo.estado == C and alvo.revisao.revisor == "Joao Lima" and alvo.revisao.valor_confirmado == "999"
    assert A in [t.para for t in alvo.historico]                         # a aprovação anterior continua no histórico


def test_decisao_nao_vale_se_documento_ou_posicao_mudaram(analise, tmp_path):
    s, r = analise; reg = RegistroRevisoes(); alvo = r.medidas[0]
    reg.registrar(medida=alvo, decisao="aprovado", revisor="Maria Souza")
    outro = analisar_pdf(s.path)                                          # mesmo arquivo: aplica
    assert aplicar_revisoes(outro, reg)["aplicadas"]
    outro_dir = tmp_path / "outro"; outro_dir.mkdir()
    b = Builder("lay_acima", "lay"); b.dim((100, 100), (200, 100), "450", "lay", scale=4.0)
    mudado = analisar_pdf(b.save(outro_dir).path)                         # mesmo nome, OUTRO conteúdo (hash diferente)
    rel = aplicar_revisoes(mudado, reg)
    assert not rel["aplicadas"] and rel["nao_aplicadas"] and mudado.resumo.por_estado["aprovado"] == 0
    reg.entradas[0]["medida_id"] = "m-inexistente"
    with pytest.raises(RegistroAdulterado):
        aplicar_revisoes(r, reg)                                          # editar o registro em memória também é detectado


# ---------------------------------------------------------------- esquema e serialização
def test_json_schema_versionado_nao_diverge_do_modelo():
    assert json.loads(schema.CAMINHO.read_text()) == json.loads(json.dumps(schema.gerar()))


def test_ida_e_volta_json(analise):
    _, r = analise
    r2 = Resultado.model_validate_json(r.model_dump_json())
    assert [m.model_dump() for m in r2.medidas] == [m.model_dump() for m in r.medidas]
    assert "estado" in json.loads(r.model_dump_json())["medidas"][0]


# ---------------------------------------------------------------- CLI
def test_cli_fluxo_completo(analise, tmp_path, capsys):
    s, _ = analise; out, reg, fim = str(tmp_path / "a.json"), str(tmp_path / "r.jsonl"), str(tmp_path / "f.json")
    assert cli(["analisar", s.path, out]) == 0
    r = Resultado.model_validate_json(Path(out).read_text()); alvo = next(m for m in r.medidas if m.estado == G)
    assert cli(["decidir", reg, out, "--medida", alvo.id, "--decisao", "aprovado", "--revisor", "Maria Souza"]) == 0
    assert cli(["aplicar", out, reg, fim]) == 0
    f = Resultado.model_validate_json(Path(fim).read_text())
    assert next(m for m in f.medidas if m.id == alvo.id).estado == A and f.resumo.por_estado["aprovado"] == 1
    assert cli(["decidir", reg, out, "--medida", "nao-existe", "--decisao", "aprovado", "--revisor", "Maria Souza"]) == 2
    assert cli(["decidir", reg, out, "--medida", alvo.id, "--decisao", "aprovado", "--revisor", "sistema"]) == 4      # revisor não humano
    Path(reg).write_text(Path(reg).read_text().replace("Maria Souza", "Fulano Tal"))
    assert cli(["aplicar", out, reg, fim]) == 3                           # registro adulterado
