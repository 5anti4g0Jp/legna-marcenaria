"""Gera fixtures a partir do exemplo FICTÍCIO: cada uma quebra UMA regra do contrato. Determinístico.
Uso: python -m contratos.documento_tecnico.v1.gerar_fixtures   (reescreve fixtures/ e fixtures/manifest.json)"""
import copy, json
from pathlib import Path

from . import validar as V

AQUI = Path(__file__).resolve().parent
EX = json.loads((AQUI / "exemplo_ficticio.json").read_text(encoding="utf-8"))


def it(d, i): return next(x for x in d["itens"] if x["id"] == i)


def M(nome, desc, fn, py, ts=None, refin=True, modo="teste", pasta="invalidos"):
    return {"nome": nome, "desc": desc, "fn": fn, "py": py, "ts": ts, "refin": refin, "modo": modo, "pasta": pasta}


def _estado_diverge(d): it(d, "i.cota_largura")["estado"] = "extraido"
def _sem_revisao(d): it(d, "i.cota_largura")["revisao"] = None
def _aprov_sistema(d): it(d, "i.cota_largura")["historico"][-1]["ator"] = {"tipo": "sistema", "id": "leitor-exemplo"}
def _transicao_proibida(d):
    x = it(d, "i.cota_pequena"); x["historico"] = x["historico"][:1] + [{**x["historico"][0], "de": "extraido", "para": "pendente_revisao", "motivo": "m"}, {**x["historico"][0], "de": "pendente_revisao", "para": "extraido", "motivo": "volta (proibido)"}]; x["estado"] = "extraido"
def _ocr_sem_conf(d): it(d, "i.cota_ocr")["origem"]["ocr"]["confianca"] = None
def _sem_pend_espessura(d): d["pendencias"] = [p for p in d["pendencias"] if p["id"] != "pd.esp_material"]
def _espessura_sem_fonte(d): it(d, "i.material")["atributos"]["espessura_mm"] = 15
def _sem_pend_dobradica(d): d["pendencias"] = [p for p in d["pendencias"] if p["id"] != "pd.dobradica"]
def _conflito_sem_entrada(d): d["conflitos"] = []; d["pendencias"] = [p for p in d["pendencias"] if p["id"] != "pd.conflito_prof"]
def _dois_aprovados(d):
    for i in ("i.nota_prof_a", "i.nota_prof_b"):
        x = it(d, i); x["estado"] = "aprovado"; x["historico"] = [x["historico"][0]] + [{"de": "extraido", "para": "pendente_revisao", "ator": {"tipo": "sistema", "id": "s"}, "em": x["historico"][0]["em"], "motivo": "m"},
            {"de": "pendente_revisao", "para": "aprovado", "ator": {"tipo": "humano", "id": "Revisor Exemplo (FICTÍCIO)"}, "em": x["historico"][0]["em"], "motivo": "ok"}]
        x["revisao"] = {"revisor": "Revisor Exemplo (FICTÍCIO)", "decisao": "aprovado", "em": x["historico"][0]["em"], "observacao": None, "valor_confirmado": None}
        x["evidencias"].append({"tipo": "revisao_humana", "descricao": "ok", "metodo": "revisao_humana", "dados": {}, "pagina": None, "coords": None})
def _versao2(d): d["contrato"]["versao"] = "2.0.0"
def _sem_sha(d): del d["documento"]["sha256"]
def _hash_adulterado(d): it(d, "i.cota_altura")["texto_original"] = "701"
def _resumo_errado(d): d["resumo"]["total_itens"] += 1
def _auto_aprov(d): d["resumo"]["aprovadas_automaticamente"] = 1
def _id_dup(d): d["itens"][1]["id"] = d["itens"][0]["id"]
def _sug_sem_valor(d):
    x = it(d, "i.material"); x["estado"] = "aprovado"; x["historico"] = [x["historico"][0], {"de": "extraido", "para": "pendente_revisao", "ator": {"tipo": "sistema", "id": "s"}, "em": x["historico"][0]["em"], "motivo": "m"},
        {"de": "pendente_revisao", "para": "aprovado", "ator": {"tipo": "humano", "id": "Revisor Exemplo (FICTÍCIO)"}, "em": x["historico"][0]["em"], "motivo": "ok"}]
    x["revisao"] = {"revisor": "Revisor Exemplo (FICTÍCIO)", "decisao": "aprovado", "em": x["historico"][0]["em"], "observacao": None, "valor_confirmado": None}
    x["evidencias"].append({"tipo": "revisao_humana", "descricao": "ok", "metodo": "revisao_humana", "dados": {}, "pagina": None, "coords": None})
def _inferida_sem_evid(d): it(d, "i.qtd_gavetas")["evidencias"] = [{"tipo": "leitura", "descricao": "só leitura", "metodo": "x", "dados": {}, "pagina": 1, "coords": None}]
def _unidade_assumida(d): it(d, "i.cota_largura")["valor"]["unidade_fonte"] = "assumida"
def _campo_desconhecido(d): d["pendencias"][0]["campo_legna"] = "campo.inventado"
def _elegib(d): d["elegibilidade"]["pronto_para_calculo"] = True
def _extra_100(d): d["campo_futuro"] = {"x": 1}
def _extra_110(d): d["contrato"]["versao"] = "1.1.0"; d["campo_futuro"] = {"x": 1}
def _pend_rebaixada(d): next(p for p in d["pendencias"] if p["id"] == "pd.dobradica")["bloqueia"] = "nenhum"
def _sem_pend_unidade(d): d["pendencias"] = [p for p in d["pendencias"] if p["id"] != "pd.unidade_p2"]
def _sem_pend_ocr(d): d["pendencias"] = [p for p in d["pendencias"] if p["id"] != "pd.ocr"]

CASOS = [
    M("estado_diverge_do_historico", "estado declarado difere do destino da última transição", _estado_diverge, ["E-ESTADO-HIST"], ["E-ESTADO-HIST"]),
    M("aprovado_sem_revisao_humana", "aprovado sem registro de revisão", _sem_revisao, ["E-APROV-HUMANO"], ["E-APROV-HUMANO"]),
    M("aprovado_por_sistema", "última transição para aprovado feita por ator sistema", _aprov_sistema, ["E-TRANSICAO", "E-APROV-AUTO"], ["E-APROV-AUTO"], refin=False),
    M("transicao_proibida", "extraido->pendente->extraido (fora da tabela PERMITIDAS)", _transicao_proibida, ["E-TRANSICAO"], None),
    M("ocr_sem_confianca", "item de OCR sem confiança", _ocr_sem_conf, ["E-OCR-CONF"], None),
    M("material_sem_pendencia_de_espessura", "espessura ausente sem pendência (preenchimento silencioso)", _sem_pend_espessura, ["E-ESPESSURA"], None),
    M("espessura_sem_fonte", "espessura informada sem fonte (não existe 'assumida')", _espessura_sem_fonte, ["E-ESPESSURA"], None),
    M("porta_sem_ferragem_nem_pendencia", "porta sem dobradiça e sem pendência", _sem_pend_dobradica, ["E-FERRAGEM-PEND"], None),
    M("conflito_sem_entrada", "itens em conflito sem registro em `conflitos`", _conflito_sem_entrada, ["E-CONFLITO-ENTRADA"], None),
    M("dois_aprovados_mesma_chave", "valores diferentes para a mesma entidade, ambos aprovados", _dois_aprovados, ["E-CONFLITO-APROV"], None),
    M("versao_major_incompativel", "contrato 2.0.0", _versao2, ["E-VERSAO"], ["E-VERSAO"], refin=False),
    M("campo_obrigatorio_ausente", "documento.sha256 ausente", _sem_sha, ["E-SCHEMA"], ["E-SCHEMA"], refin=False),
    M("conteudo_alterado_apos_hash", "texto de um item alterado sem recalcular o hash", _hash_adulterado, ["E-HASH"], ["E-HASH"], refin=False),
    M("resumo_incorreto", "resumo não bate com os itens", _resumo_errado, ["E-RESUMO"], ["E-RESUMO"], refin=False),
    M("aprovacao_automatica_no_resumo", "resumo.aprovadas_automaticamente = 1", _auto_aprov, ["E-SCHEMA"], ["E-SCHEMA"], refin=False),
    M("id_duplicado", "dois itens com o mesmo id", _id_dup, ["E-ID-DUP"], ["E-ID-DUP"]),
    M("sugerido_aprovado_sem_valor_confirmado", "material sugerido aprovado sem valor confirmado pela pessoa", _sug_sem_valor, ["E-NAT-REV"], None),
    M("inferido_sem_evidencia_geometrica", "quantidade inferida sem evidência de geometria com coordenadas", _inferida_sem_evid, ["E-INFERIDA-EVID"], None),
    M("unidade_assumida_em_item_aprovado", "item aprovado com unidade assumida", _unidade_assumida, ["E-UNIDADE"], None),
    M("pendencia_com_campo_desconhecido", "campo_legna fora do registro", _campo_desconhecido, ["E-PEND-CAMPO"], None),
    M("elegibilidade_inconsistente", "pronto_para_calculo=true com pendências abertas", _elegib, ["E-ELEG"], ["E-ELEG"], refin=False),
    M("pendencia_critica_rebaixada", "pendência que bloqueia cálculo marcada como 'nenhum'", _pend_rebaixada, ["E-PEND-BLOQ"], None),
    M("pagina_com_cotas_sem_pendencia_de_unidade", "página sem unidade declarada e sem pendência", _sem_pend_unidade, ["E-UNIDADE"], None),
    M("ocr_sem_pendencia_de_revisao", "item de OCR não aprovado sem pendência", _sem_pend_ocr, ["E-PEND-REVISAO"], None),
    M("campo_desconhecido_na_versao_atual", "campo extra em 1.0.0 é recusado", _extra_100, ["E-SCHEMA"], ["E-SCHEMA"], refin=False),
    M("minor_mais_novo_com_campo_extra", "1.1.0 com campo extra: aceito com aviso A-VERSAO-MINOR", _extra_110, [], [], refin=False, pasta="validos"),
]


def main():
    manifest = []
    for pasta in ("invalidos", "validos"): (AQUI / "fixtures" / pasta).mkdir(parents=True, exist_ok=True)
    for c in CASOS:
        d = copy.deepcopy(EX); c["fn"](d)
        if c["refin"]: V.finalizar(d)
        arq = f"fixtures/{c['pasta']}/{c['nome']}.json"; (AQUI / arq).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        manifest.append({"arquivo": arq, "descricao": c["desc"], "modo": c["modo"], "esperado_python": c["py"], "esperado_ts": c["ts"]})
    (AQUI / "fixtures" / "manifest.json").write_text(json.dumps({"aviso": "Fixtures derivadas do exemplo FICTÍCIO. esperado_ts=null: regra verificada só pelo validador Python (fonte única).", "casos": manifest}, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(len(main()), "fixtures geradas")
