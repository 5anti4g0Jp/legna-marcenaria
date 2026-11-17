"""Contrato `documento_tecnico` v1 (lado Python). Todos os dados são o EXEMPLO FICTÍCIO e derivados dele; nada vem de projeto real."""
import copy, json
from pathlib import Path

import jsonschema
import pytest

from contratos.documento_tecnico.v1 import gerar_fixtures as GF, validar as V
from ingest.technical import model as MODELO

V1 = Path(V.__file__).resolve().parent
EX = json.loads((V1 / "exemplo_ficticio.json").read_text(encoding="utf-8"))
MAN = json.loads((V1 / "fixtures" / "manifest.json").read_text(encoding="utf-8"))["casos"]


def novo(): return copy.deepcopy(EX)


def test_esquema_e_valido_draft_2020_12_e_documenta_estados_do_python():
    jsonschema.Draft202012Validator.check_schema(V.SCHEMA)
    assert V.SCHEMA["$defs"]["estado"]["enum"] == [e.value for e in MODELO.Estado]            # sem divergência com a máquina de estados do Python
    ts = (V1 / "ts" / "documento_tecnico.ts").read_text(encoding="utf-8")
    for e in MODELO.Estado: assert f'"{e.value}"' in ts                                          # o TS lista os mesmos seis estados


def test_fonte_unica_da_maquina_de_estados():
    assert V.PERMITIDAS is MODELO.PERMITIDAS
    assert "PERMITIDAS =" not in (V1 / "validar.py").read_text(encoding="utf-8")                  # o validador não redefine a tabela
    assert "PERMITIDAS" not in (V1 / "ts" / "documento_tecnico.ts").read_text(encoding="utf-8")   # nem o TS (a tabela existe só no Python)


def test_exemplo_e_ficticio_valido_em_teste_e_recusado_em_producao():
    assert EX["marcador_exemplo"]["ficticio"] is True and "FICT" in EX["projeto"]["nome"].upper()
    r = V.validar(novo(), "teste"); assert r.ok and not r.avisos, r.erros
    assert V.validar(novo(), "producao").codigos() == {"E-EXEMPLO"}
    assert all("FICT" in i["historico"][-1]["ator"]["id"].upper() for i in EX["itens"] if i["estado"] == "aprovado")


def test_exemplo_demonstra_pendencias_e_nao_esta_pronto():
    assert EX["elegibilidade"]["pronto_para_calculo"] is False and EX["elegibilidade"]["orcamento_completo"] is False
    assert EX["resumo"]["aprovadas_automaticamente"] == 0 and EX["resumo"]["por_estado"]["conflito"] == 2
    tipos = {p["tipo"] for p in EX["pendencias"]}
    assert {"ausente_no_pdf", "sugerido_sem_confirmacao", "inferido_sem_revisao", "ocr_sem_revisao", "conflito", "unidade_nao_declarada"} <= tipos


@pytest.mark.parametrize("caso", MAN, ids=lambda c: c["arquivo"].split("/")[-1])
def test_fixture_dispara_exatamente_as_regras_esperadas(caso):
    d = json.loads((V1 / caso["arquivo"]).read_text(encoding="utf-8")); r = V.validar(d, caso["modo"])
    if caso["esperado_python"]:
        assert not r.ok and set(caso["esperado_python"]) <= r.codigos(), (r.codigos(), r.erros[:3])
    else:
        assert r.ok and "A-VERSAO-MINOR" in {a["codigo"] for a in r.avisos}


def test_fixtures_sao_reproduzidas_a_partir_do_exemplo():
    for c, m in zip(GF.CASOS, MAN):
        d = copy.deepcopy(GF.EX); c["fn"](d)
        if c["refin"]: V.finalizar(d)
        assert d == json.loads((V1 / m["arquivo"]).read_text(encoding="utf-8")), c["nome"]
    assert len(GF.CASOS) == len(MAN) >= 20


def test_formato_dos_erros_e_campo_ausente_e_tipo_errado():
    d = novo(); del d["documento"]["sha256"]; d["itens"][0]["pagina"] = "um"
    r = V.validar(d, "teste")
    assert not r.ok and all(set(e) == {"codigo", "caminho", "mensagem"} for e in r.erros)
    assert any(e["caminho"].startswith("/documento") for e in r.erros) and any(e["caminho"] == "/itens/0/pagina" for e in r.erros)
    assert V.validar({}, "teste").codigos() == {"E-VERSAO"}                                      # sem versão: recusado cedo, sem tentar interpretar


@pytest.mark.parametrize("versao,esperado", [("1.0.0", "ok"), ("1.0.7", "ok"), ("2.0.0", "E-VERSAO"), ("0.9.0", "E-VERSAO"), ("abc", "E-VERSAO"), ("1.2.0", "A-VERSAO-MINOR")])
def test_compatibilidade_de_versoes(versao, esperado):
    d = novo(); d["contrato"]["versao"] = versao; d["campo_futuro"] = 1
    r = V.validar(d, "teste")
    if esperado == "ok": assert "E-VERSAO" not in r.codigos()
    elif esperado == "A-VERSAO-MINOR": assert "A-VERSAO-MINOR" in {a["codigo"] for a in r.avisos} and "E-SCHEMA" not in r.codigos()
    else: assert r.codigos() == {"E-VERSAO"}


def test_hash_canonico_ignora_formatacao_numerica_e_ordem_de_chaves():
    a = {"x": 800.0, "y": [1, 2], "z": "é"}; b = {"z": "é", "y": [1, 2], "x": 800}
    assert V.canonico(a) == V.canonico(b) == '{"x":800,"y":[1,2],"z":"é"}'
    d = novo(); h = V.hash_conteudo(d); d["itens"][0]["coords"] = [float(c) for c in d["itens"][0]["coords"]]
    assert V.hash_conteudo(d) == h
    d["itens"][0]["texto_original"] += "x"; assert V.hash_conteudo(d) != h


def test_finalizar_e_idempotente_e_gera_derivados_consistentes():
    d = novo(); a = V.finalizar(copy.deepcopy(d)); b = V.finalizar(copy.deepcopy(a))
    assert a == b == d


def test_regras_obrigatorias_do_pedido_estao_cobertas_por_fixtures():
    cobertas = {c for m in MAN for c in m["esperado_python"]}
    for cod in ("E-APROV-HUMANO", "E-APROV-AUTO", "E-OCR-CONF", "E-NAT-REV", "E-ESPESSURA", "E-FERRAGEM-PEND", "E-INFERIDA-EVID", "E-CONFLITO-ENTRADA", "E-CONFLITO-APROV", "E-ELEG", "E-HASH", "E-RESUMO", "E-VERSAO"):
        assert cod in cobertas, cod


# ---------------------------------------------------------------- registro de campos que dependem da Legna
REG = V.REGISTRO["campos"]


def test_registro_cobre_as_categorias_pedidas_e_nao_tem_valores_comerciais():
    cats = {c["categoria"] for c in REG}
    assert {"espessuras", "fitas de borda", "parafusos e acessórios", "regras de fabricação", "folgas e tolerâncias", "preços e fornecedores", "ferragens", "materiais"} <= cats
    ids = [c["id"] for c in REG]; assert len(ids) == len(set(ids))
    assert any("dobradi" in c["descricao"].lower() for c in REG) and any("corredi" in c["descricao"].lower() for c in REG)
    import re
    assert not re.search(r"R\$\s*\d|\b\d+[.,]\d+\s*(mm|%)", json.dumps(REG, ensure_ascii=False))
    assert all(c["bloqueia"] in ("nenhum", "calculo", "orcamento") and c["ausente_no_pdf"] in ("nunca_aparece", "aparece_parcialmente") for c in REG)


def test_registro_aponta_lacunas_do_formulario_sem_escondê_las():
    lacunas = {c["id"] for c in REG if "lacuna_formulario" in c}
    assert {"acess.parafusos_cavilhas", "mat.superficie_aplicacao"} <= lacunas
    assert all(c["formulario_ref"] or "lacuna_formulario" in c for c in REG)                   # todo campo está ligado ao formulário OU tem lacuna declarada


def test_referencias_ao_formulario_existem(monkeypatch):
    campos = pytest.importorskip("levantamento.campos")                                          # só existe na branch fase2/levantamento-dados
    unicos = {c["id"] for c in campos.CAMPOS}; cols = {(t["nome"], c["id"]) for t in campos.TABELAS for c in t["colunas"]}
    for c in REG:
        for ref in c["formulario_ref"]:
            if ref.startswith("Campos:"): assert ref[7:] in unicos, ref
            else:
                aba, col = ref[len("tabela:"):].split("."); assert (aba, col) in cols, ref


def test_pendencias_do_exemplo_so_referenciam_campos_do_registro():
    ids = {c["id"] for c in REG}
    assert all(p["campo_legna"] in ids for p in EX["pendencias"] if p["campo_legna"])
