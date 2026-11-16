"""Levantamento de dados da Legna. Valores usados aqui são FICTÍCIOS DE TESTE (diretório temporário); o formulário real nasce sem nenhum valor."""
import datetime as dt, json, re
from pathlib import Path
import pytest
from openpyxl import load_workbook
from levantamento import campos as K, formulario as F

REPO = Path(__file__).resolve().parents[1]
FORM = REPO / "levantamento" / "formulario_levantamento_legna.xlsx"


@pytest.fixture
def wb_path(tmp_path):
    return F.gerar(tmp_path / "f.xlsx")


def _col(ws, nome): return [c.value for c in ws[1]].index(nome) + 1


def _set(path, aba, linha, **kv):
    wb = load_workbook(path); ws = wb[aba]
    for k, v in kv.items(): ws.cell(linha, _col(ws, k)).value = v
    wb.save(path)


def _linha_campo(path, cid):
    ws = load_workbook(path)["Campos"]
    return next(r[0].row for r in ws.iter_rows(min_row=2) if r[0].value == cid)


def test_formulario_do_repositorio_nasce_sem_nenhum_valor_e_tudo_pendente():
    wb = load_workbook(FORM); ws = wb["Campos"]; ic = _col(ws, "status"); iv = _col(ws, "valor")
    assert {r[ic - 1].value for r in ws.iter_rows(min_row=2)} == {"pendente"} and all(r[iv - 1].value is None for r in ws.iter_rows(min_row=2))
    for t in K.TABELAS:
        w = wb[t["nome"]]
        assert all(c.value in (None, "") for row in w.iter_rows(min_row=3, min_col=2) for c in row), t["nome"]         # tabelas vazias


def test_campos_definem_somente_perguntas_sem_valores_comerciais():
    ids = [c["id"] for c in K.CAMPOS]
    assert len(ids) == len(set(ids)) and all(c["criticidade"] in K.CRITICIDADE and c["tipo"] in K.TIPOS for c in K.CAMPOS)
    texto = json.dumps(K.CAMPOS, ensure_ascii=False) + json.dumps(K.TABELAS, ensure_ascii=False)
    assert not re.search(r"R\$\s*\d|\d+[.,]\d+\s*(mm|%)", texto)                                # nenhum preço/medida embutido nas perguntas


def test_formulario_em_branco_e_valido_mas_nao_pronto(wb_path):
    r = F.validar(wb_path)
    assert r["ok"] and not r["pronto_para_orcamento"] and r["confirmados"] == {} and r["provisorios"] == {}
    assert set(r["campos_criticos_nao_confirmados"]) == {c["id"] for c in K.CAMPOS if c["criticidade"] == "bloqueia_orcamento"}
    assert set(r["tabelas_criticas_sem_linha_confirmada"]) == {"materiais", "fitas", "ferragens", "regra_dobradica"}


@pytest.mark.parametrize("mut,trecho", [
    (dict(status="pendente", valor=3), "pendente' mas tem valor"),
    (dict(status="confirmado", valor=3), "exige fonte"),
    (dict(status="confirmado", valor=3, fonte="doc"), "data da fonte"),
    (dict(status="confirmado", valor=3, fonte="doc", data_fonte="2026-01-01"), "quem confirmou"),
    (dict(status="confirmado", valor=3, fonte="doc", data_fonte="2026-01-01", confirmado_por="Assistente"), "pessoa"),
    (dict(status="confirmado", valor=3, fonte="doc", data_fonte="2999-01-01", confirmado_por="Maria Souza"), "futuro"),
    (dict(status="confirmado", valor="abc", fonte="doc", data_fonte="2026-01-01", confirmado_por="Maria Souza"), "deve ser número"),
    (dict(status="confirmado", valor=-1, fonte="doc", data_fonte="2026-01-01", confirmado_por="Maria Souza"), "negativo"),
    (dict(status="provisorio", valor=3), "justificativa"),
    (dict(status="provisorio", valor=3, justificativa_provisorio="curta"), "justificativa"),
    (dict(status="provisorio"), "exige valor"),
    (dict(status="talvez"), "status inválido"),
    (dict(status=None), "status inválido")])
def test_regras_de_status_em_campos_unicos(wb_path, mut, trecho):
    _set(wb_path, "Campos", _linha_campo(wb_path, "cor.espessura_serra"), **mut)
    r = F.validar(wb_path)
    assert not r["ok"] and any(trecho in e for e in r["erros"]), r["erros"]


def test_confirmado_provisorio_e_nao_pronto_ate_confirmar_criticos(wb_path):
    _set(wb_path, "Campos", _linha_campo(wb_path, "cor.espessura_serra"), status="confirmado", valor="4,5", fonte="TESTE fictício", data_fonte="2026-11-01", confirmado_por="Pessoa de Teste")
    _set(wb_path, "Campos", _linha_campo(wb_path, "cor.refilo"), status="provisorio", valor=10, justificativa_provisorio="TESTE: estimativa para rodar o motor")
    r = F.validar(wb_path)
    assert r["ok"] and r["confirmados"]["cor.espessura_serra"]["valor"] == "4,5" and r["provisorios"]["cor.refilo"]["uso_comercial"] is False
    assert "cor.espessura_serra" not in r["campos_criticos_nao_confirmados"] and "cor.refilo" in r["campos_criticos_nao_confirmados"] and not r["pronto_para_orcamento"]   # provisório não conta


def test_tipos_lista_sim_nao_percentual_data(wb_path):
    ok = dict(status="confirmado", fonte="TESTE", data_fonte="01/11/2026", confirmado_por="Pessoa de Teste")
    _set(wb_path, "Campos", _linha_campo(wb_path, "cor.respeita_veio"), valor="talvez", **ok)
    _set(wb_path, "Campos", _linha_campo(wb_path, "fab.fita_desperdicio"), valor=150, **ok)
    _set(wb_path, "Campos", _linha_campo(wb_path, "fab.pinos_prateleira"), valor=2.5, **ok)
    e = F.validar(wb_path)["erros"]
    assert any("fora das opções" in x for x in e) and any("acima de 100" in x for x in e) and any("inteiro" in x for x in e)


def test_tabela_linha_confirmada_exige_colunas_obrigatorias_fonte_e_status(wb_path):
    _set(wb_path, "materiais", 3, tipo="MDF", espessura_mm=15)                                  # dados sem status
    assert any("sem status" in e for e in F.validar(wb_path)["erros"])
    _set(wb_path, "materiais", 3, status="confirmado")
    e = F.validar(wb_path)["erros"]
    assert any("coluna obrigatória" in x for x in e) and any("exige fonte" in x for x in e)
    _set(wb_path, "materiais", 3, status="pendente")                                            # mesma regra dos campos únicos: pendente = sem valor
    assert any("pendente' mas tem valor" in x for x in F.validar(wb_path)["erros"])
    _set(wb_path, "materiais", 3, status=None, tipo=None, espessura_mm=None)                    # linha limpa: ignorada
    assert F.validar(wb_path)["ok"]


def test_tabela_completa_exporta_so_confirmados_e_marca_provisorios(wb_path, tmp_path):
    linha = dict(tipo="MDF", fabricante_linha="TESTE", cor_acabamento="TESTE", espessura_mm=15, largura_chapa_mm=1000, comprimento_chapa_mm=2000, tem_veio="sim", preco_chapa="1.234,56", fornecedor="TESTE", data_preco="2026-10-01")
    _set(wb_path, "materiais", 3, status="confirmado", fonte="TESTE", data_fonte="2026-10-01", confirmado_por="Pessoa de Teste", **linha)
    _set(wb_path, "materiais", 4, status="provisorio", justificativa_provisorio="TESTE: valor estimado para simulação", **{**linha, "preco_chapa": 1})
    out = tmp_path / "o.json"; r = F.exportar(wb_path, out); d = json.loads(out.read_text())
    assert [l["uso_comercial"] for l in d["tabelas"]["materiais"]] == [True, False] and d["pronto_para_orcamento"] is False and "NÃO podem" in d["aviso"]
    _set(wb_path, "materiais", 5, status="confirmado")
    with pytest.raises(ValueError): F.exportar(wb_path, tmp_path / "x.json")                    # com erro, não exporta


def test_campos_removidos_ou_id_alterado_sao_detectados(wb_path):
    wb = load_workbook(wb_path); ws = wb["Campos"]; ws.cell(2, 1, "campo.inventado"); wb.save(wb_path)
    e = F.validar(wb_path)["erros"]
    assert any("campo desconhecido" in x for x in e) and any("linha removida" in x for x in e)
