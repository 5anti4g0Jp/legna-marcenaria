"""Validação do contrato `documento_tecnico` v1 (lado Python): esquema JSON + regras semânticas.

NÃO duplica a máquina de estados: as transições permitidas e os atores autorizados vêm de `ingest.technical.model.PERMITIDAS`
(fonte única). Este módulo só verifica que o documento respeita essa tabela.
Uso: validar(doc, modo="producao"|"teste") -> Resultado(ok, erros, avisos); cada erro = {codigo, caminho, mensagem}.
"""
from __future__ import annotations

import hashlib, json
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

from ingest.technical.model import PERMITIDAS, Estado

AQUI = Path(__file__).resolve().parent
VERSAO_SUPORTADA = (1, 0)                    # (major, minor) que este validador entende
ESCOPO_HASH = ["projeto", "documento", "extracao", "paginas", "vistas", "modulos", "itens", "conflitos", "pendencias"]
SCHEMA = json.loads((AQUI / "documento_tecnico.schema.json").read_text(encoding="utf-8"))
REGISTRO = json.loads((AQUI / "campos_dependentes_legna.json").read_text(encoding="utf-8"))
CAMPOS_LEGNA = {c["id"]: c for c in REGISTRO["campos"]}
ESTADOS = [e.value for e in Estado]
ATORES_APROVAM = {"humano"}


@dataclass
class Resultado:
    erros: list[dict] = field(default_factory=list)
    avisos: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.erros

    def codigos(self) -> set[str]:
        return {e["codigo"] for e in self.erros}

    def erro(self, codigo, caminho, msg): self.erros.append({"codigo": codigo, "caminho": caminho, "mensagem": msg})
    def aviso(self, codigo, caminho, msg): self.avisos.append({"codigo": codigo, "caminho": caminho, "mensagem": msg})


# ---------------------------------------------------------------- canonicalização e hash
def _norm(o):
    if isinstance(o, bool) or o is None or isinstance(o, str): return o
    if isinstance(o, float): return int(o) if o == int(o) else o          # 800.0 -> 800 (JS e Python concordam)
    if isinstance(o, int): return o
    if isinstance(o, list): return [_norm(x) for x in o]
    if isinstance(o, dict): return {k: _norm(v) for k, v in o.items()}
    raise TypeError(type(o))


def canonico(o) -> str:
    """json-ordenado-v1: chaves ordenadas, sem espaços, UTF-8 sem escape, inteiros sem '.0'. Números: sem notação exponencial."""
    return json.dumps(_norm(o), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_conteudo(doc: dict) -> str:
    return hashlib.sha256(canonico({k: doc[k] for k in ESCOPO_HASH}).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- derivados
def derivar_resumo(doc: dict) -> dict:
    por_estado = {e: 0 for e in ESTADOS}; por_tipo: dict[str, int] = {}; auto = 0
    for it in doc["itens"]:
        por_estado[it["estado"]] += 1; por_tipo[it["tipo"]] = por_tipo.get(it["tipo"], 0) + 1
        auto += sum(1 for t in it["historico"] if t["para"] == "aprovado" and t["ator"]["tipo"] != "humano")
    return {"total_itens": len(doc["itens"]), "por_estado": por_estado, "por_tipo": por_tipo, "aprovadas_automaticamente": auto}


def derivar_elegibilidade(doc: dict) -> dict:
    bloq = [p["id"] for p in doc["pendencias"] if p["bloqueia"] in ("calculo", "orcamento")]
    calc = [p["id"] for p in doc["pendencias"] if p["bloqueia"] == "calculo"]
    abertos = [c for c in doc["conflitos"] if c["estado"] == "aberto"]
    return {"pronto_para_calculo": not calc and not abertos, "orcamento_completo": not bloq and not abertos, "bloqueios": bloq}


def finalizar(doc: dict) -> dict:
    """Preenche os campos derivados (resumo, elegibilidade, integridade). Uso: produtores e testes."""
    doc["resumo"] = derivar_resumo(doc); doc["elegibilidade"] = {**derivar_elegibilidade(doc), **({"nota": doc["elegibilidade"]["nota"]} if "nota" in doc.get("elegibilidade", {}) else {})}
    doc["integridade"] = {**doc.get("integridade", {"canonicalizacao": "json-ordenado-v1", "escopo": ESCOPO_HASH, "gerado_por": "leitor-python"}), "hash_conteudo": hash_conteudo(doc)}
    return doc


# ---------------------------------------------------------------- validação
def _versao(doc, r: Resultado):
    v = (doc.get("contrato") or {}).get("versao")
    try: major, minor, _ = (int(x) for x in str(v).split("."))
    except Exception:                                                     # noqa: BLE001
        r.erro("E-VERSAO", "/contrato/versao", f"versão inválida: {v!r}"); return None
    if major != VERSAO_SUPORTADA[0]:
        r.erro("E-VERSAO", "/contrato/versao", f"major {major} incompatível com o suportado ({VERSAO_SUPORTADA[0]}.x): recusado, sem tentativa de leitura parcial"); return None
    if minor > VERSAO_SUPORTADA[1]:
        r.aviso("A-VERSAO-MINOR", "/contrato/versao", f"minor {minor} mais novo que o suportado ({VERSAO_SUPORTADA[1]}): campos desconhecidos são ignorados; nada desconhecido pode aprovar dados")
        return "minor_novo"
    return "ok"


def validar(doc: dict, modo: str = "producao") -> Resultado:
    r = Resultado()
    estado_versao = _versao(doc, r)
    if estado_versao is None: return r
    validator = jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.FormatChecker())
    for e in sorted(validator.iter_errors(doc), key=lambda e: list(map(str, e.absolute_path))):
        if estado_versao == "minor_novo" and e.validator == "additionalProperties": continue      # tolerância a campos novos de minor maior
        r.erro("E-SCHEMA", "/" + "/".join(map(str, e.absolute_path)), e.message[:200])
    if r.erros: return r                                                  # regras semânticas só em documento estruturalmente válido
    if "marcador_exemplo" in doc and modo == "producao": r.erro("E-EXEMPLO", "/marcador_exemplo", "documento de exemplo/fictício não pode ser aceito em modo produção")
    _referencias(doc, r); _estados(doc, r); _regras_de_dados(doc, r); _pendencias(doc, r); _derivados(doc, r)
    return r


def _referencias(doc, r):
    ids: dict[str, str] = {}
    def reg(i, caminho):
        if i in ids: r.erro("E-ID-DUP", caminho, f"id duplicado: {i}")
        ids[i] = caminho
    for k in ("itens", "vistas", "modulos", "pendencias", "conflitos"):
        for n, x in enumerate(doc[k]): reg(x["id"], f"/{k}/{n}/id")
    itens = {x["id"] for x in doc["itens"]}; vistas = {x["id"] for x in doc["vistas"]}; mods = {x["id"] for x in doc["modulos"]}; todos = set(ids)
    npag = doc["documento"]["paginas"]
    if len(doc["paginas"]) != npag or [p["numero"] for p in doc["paginas"]] != list(range(1, npag + 1)):
        r.erro("E-PAG", "/paginas", f"`paginas` deve listar 1..{npag} em ordem (documento.paginas={npag})")
    dims = {p["numero"]: (p["largura_pt"], p["altura_pt"]) for p in doc["paginas"]}
    for n, it in enumerate(doc["itens"]):
        c = f"/itens/{n}"
        if it["pagina"] > npag: r.erro("E-PAG", c + "/pagina", f"página {it['pagina']} > {npag}")
        elif it["pagina"] in dims:
            w, h = dims[it["pagina"]]; x0, y0, x1, y1 = it["coords"]
            if x0 < -1 or y0 < -1 or x1 > w + 1 or y1 > h + 1: r.aviso("A-COORD", c + "/coords", "caixa fora dos limites da página")
        for k, rel in enumerate(it.get("relacoes", [])):
            if rel["alvo_id"] not in todos: r.erro("E-REF", f"{c}/relacoes/{k}/alvo_id", f"alvo inexistente: {rel['alvo_id']}")
        q = it.get("atributos", {}).get("quantidade_item_id")
        if q and q not in itens: r.erro("E-REF", c + "/atributos/quantidade_item_id", f"item inexistente: {q}")
    for n, m in enumerate(doc["modulos"]):
        for k, v in m["dimensoes"].items():
            if v and v not in itens: r.erro("E-REF", f"/modulos/{n}/dimensoes/{k}", f"item inexistente: {v}")
        for v in m.get("item_ids", []):
            if v not in itens: r.erro("E-REF", f"/modulos/{n}/item_ids", f"item inexistente: {v}")
        for v in m.get("vista_ids", []):
            if v not in vistas: r.erro("E-REF", f"/modulos/{n}/vista_ids", f"vista inexistente: {v}")
    for n, v in enumerate(doc["vistas"]):
        if v["pagina"] > npag: r.erro("E-PAG", f"/vistas/{n}/pagina", "página inexistente")
    for n, p in enumerate(doc["pendencias"]):
        for v in p["item_ids"]:
            if v not in itens: r.erro("E-REF", f"/pendencias/{n}/item_ids", f"item inexistente: {v}")
        if p.get("modulo_id") and p["modulo_id"] not in mods: r.erro("E-REF", f"/pendencias/{n}/modulo_id", "módulo inexistente")
        if p["campo_legna"] is None:
            if p["tipo"] not in ("conflito", "inferido_sem_revisao", "ocr_sem_revisao"): r.erro("E-PEND-CAMPO", f"/pendencias/{n}/campo_legna", "campo_legna nulo só é permitido em pendências de revisão (conflito, inferido_sem_revisao, ocr_sem_revisao)")
        elif p["campo_legna"] not in CAMPOS_LEGNA: r.erro("E-PEND-CAMPO", f"/pendencias/{n}/campo_legna", f"campo fora do registro campos_dependentes_legna: {p['campo_legna']}")
    for n, c in enumerate(doc["conflitos"]):
        for v in c["item_ids"]:
            if v not in itens: r.erro("E-REF", f"/conflitos/{n}/item_ids", f"item inexistente: {v}")


def _estados(doc, r):
    for n, it in enumerate(doc["itens"]):
        c = f"/itens/{n}"; h = it["historico"]
        if h[0]["de"] is not None: r.erro("E-TRANSICAO", c + "/historico/0", "a primeira transição deve partir de null (criação)")
        anterior = None
        for k, t in enumerate(h):
            de = None if t["de"] is None else Estado(t["de"]); para = Estado(t["para"]); ator = t["ator"]["tipo"]
            if (t["de"] or None) != (anterior.value if anterior else None): r.erro("E-TRANSICAO", f"{c}/historico/{k}", "histórico descontínuo (`de` não é o destino da transição anterior)")
            permitidos = PERMITIDAS.get((de, para))
            if permitidos is None: r.erro("E-TRANSICAO", f"{c}/historico/{k}", f"transição proibida: {t['de']} -> {t['para']}")
            elif ator not in {a.value for a in permitidos}: r.erro("E-TRANSICAO", f"{c}/historico/{k}", f"ator '{ator}' sem autoridade para {t['de']} -> {t['para']}")
            if para == Estado.APROVADO and ator != "humano": r.erro("E-APROV-AUTO", f"{c}/historico/{k}", "aprovação por ator não humano")
            anterior = para
        if it["estado"] != h[-1]["para"]: r.erro("E-ESTADO-HIST", c + "/estado", f"estado '{it['estado']}' difere do destino da última transição '{h[-1]['para']}'")
        rev = it.get("revisao")
        if it["estado"] == "aprovado":
            ok = rev and rev["decisao"] == "aprovado" and h[-1]["ator"]["tipo"] == "humano" and h[-1]["ator"]["id"] == rev["revisor"]
            if not ok: r.erro("E-APROV-HUMANO", c, "aprovado exige `revisao` (decisao=aprovado) do mesmo humano que fez a última transição")
            if not any(e["tipo"] == "revisao_humana" for e in it["evidencias"]): r.erro("E-APROV-HUMANO", c + "/evidencias", "aprovado exige evidência do tipo revisao_humana")
            if it["natureza"] in ("sugerida", "inferida") and not (rev and rev.get("valor_confirmado")):
                r.erro("E-NAT-REV", c + "/revisao/valor_confirmado", f"item de natureza '{it['natureza']}' só é aprovado com o valor confirmado pela pessoa")
            if it["valor"]["unidade_fonte"] in ("assumida", "desconhecida"): r.erro("E-UNIDADE", c + "/valor/unidade_fonte", "valor com unidade assumida/desconhecida não pode estar aprovado sem ser declarada pelo revisor")
        elif rev and rev["decisao"] == "aprovado" and it["estado"] != "pendente_revisao":
            r.erro("E-APROV-HUMANO", c + "/revisao", "revisão de aprovação sem estado aprovado")
        if it["origem"]["metodo_extracao"] == "ocr":
            ocr = it["origem"].get("ocr")
            if not ocr or ocr.get("confianca") is None: r.erro("E-OCR-CONF", c + "/origem/ocr/confianca", "item de OCR exige confiança informada")
        if it["natureza"] == "inferida" and not any(e["tipo"] in ("geometria", "quantidade_inferida") and e.get("coords") for e in it["evidencias"]):
            r.erro("E-INFERIDA-EVID", c + "/evidencias", "item inferido exige evidência de geometria/quantidade_inferida com coordenadas")


def _regras_de_dados(doc, r):
    pend = doc["pendencias"]
    def tem_pend(campo, item_id=None, modulo=None):
        return any(p["campo_legna"] == campo and (item_id is None or item_id in p["item_ids"]) and (modulo is None or p.get("modulo_id") == modulo) for p in pend)
    itens = {x["id"]: x for x in doc["itens"]}
    for n, it in enumerate(doc["itens"]):
        c = f"/itens/{n}"; a = it.get("atributos", {})
        if "espessura_mm" in a and a["espessura_mm"] is not None and a.get("espessura_fonte") is None:
            r.erro("E-ESPESSURA", c + "/atributos", "espessura informada exige `espessura_fonte` (não existe espessura 'assumida')")
        if it["tipo"] == "material" and a.get("espessura_mm") is None and not tem_pend("mat.espessura", it["id"]):
            r.erro("E-ESPESSURA", c, "material sem espessura exige pendência `mat.espessura` (não preencher silenciosamente)")
        if it["tipo"] == "material" and it["natureza"] == "sugerida" and it["estado"] != "aprovado" and not tem_pend("mat.especificacao_confirmada", it["id"]):
            r.erro("E-SUGERIDO", c, "material sugerido não confirmado exige pendência `mat.especificacao_confirmada`")
        if it["tipo"] == "rotulo_componente":
            cat = a.get("categoria"); alvo = {"porta": "ferr.dobradica", "gaveta": "ferr.corredica"}.get(cat)
            if alvo:
                usa = any(rel["tipo"] == "usa_ferragem" and itens.get(rel["alvo_id"], {}).get("tipo") == "ferragem" for rel in it.get("relacoes", []))
                if not usa and not tem_pend(alvo, it["id"]): r.erro("E-FERRAGEM-PEND", c, f"componente '{cat}' sem ferragem associada exige pendência `{alvo}`")
        if it["estado"] != "aprovado":
            for tipo_p, cond in (("ocr_sem_revisao", it["origem"]["metodo_extracao"] == "ocr"), ("inferido_sem_revisao", it["natureza"] == "inferida")):
                if cond and not any(p["tipo"] == tipo_p and it["id"] in p["item_ids"] for p in pend):
                    r.erro("E-PEND-REVISAO", c, f"item {'de OCR' if tipo_p.startswith('ocr') else 'inferido'} não aprovado exige pendência `{tipo_p}`")
        if it["estado"] == "conflito" and not any(it["id"] in k["item_ids"] for k in doc["conflitos"]): r.erro("E-CONFLITO-ENTRADA", c, "item em conflito precisa constar em `conflitos`")
    por_chave: dict[str, list[dict]] = {}
    for it in doc["itens"]:
        if it.get("chave_semantica"): por_chave.setdefault(it["chave_semantica"], []).append(it)
    for chave, grupo in por_chave.items():
        vals = {(g["valor"].get("numero"), g["valor"].get("unidade"), g["valor"].get("texto") if g["valor"].get("numero") is None else None) for g in grupo}
        if len(vals) > 1:
            aprov = [g for g in grupo if g["estado"] == "aprovado"]
            if len(aprov) > 1: r.erro("E-CONFLITO-APROV", f"chave:{chave}", "valores diferentes para a mesma entidade e mais de um aprovado")
            existe = any(set(k["item_ids"]) >= {g["id"] for g in grupo} or chave == k["chave_semantica"] for k in doc["conflitos"])
            if not aprov and not existe: r.erro("E-CONFLITO-ENTRADA", f"chave:{chave}", "valores divergentes sem entrada em `conflitos` (informação conflitante deve permanecer em conflito)")
    for n, k in enumerate(doc["conflitos"]):
        if k["estado"] == "resolvido":
            if not k.get("resolucao") or k["resolucao"]["item_id_vencedor"] not in k["item_ids"]: r.erro("E-CONFLITO-ENTRADA", f"/conflitos/{n}", "conflito resolvido exige `resolucao` com item vencedor entre os conflitantes")
            elif itens[k["resolucao"]["item_id_vencedor"]]["estado"] != "aprovado": r.erro("E-CONFLITO-APROV", f"/conflitos/{n}", "o vencedor de um conflito resolvido deve estar aprovado")
        elif any(itens[i]["estado"] == "aprovado" for i in k["item_ids"] if i in itens): r.erro("E-CONFLITO-APROV", f"/conflitos/{n}", "conflito aberto com item aprovado: resolva o conflito")
    for p in doc["paginas"]:
        cotas = [it for it in doc["itens"] if it["pagina"] == p["numero"] and it["tipo"] == "cota"]
        if cotas and p.get("unidade_declarada") is None and not any(x["campo_legna"] == "doc.unidade_desenho" and (x.get("pagina") in (None, p["numero"])) for x in pend):
            r.erro("E-UNIDADE", f"/paginas/{p['numero'] - 1}", "página com cotas e sem unidade declarada exige pendência `doc.unidade_desenho`")


def _pendencias(doc, r):
    for n, p in enumerate(doc["pendencias"]):
        reg = CAMPOS_LEGNA.get(p["campo_legna"]) if p["campo_legna"] else None
        if reg and p["bloqueia"] == "nenhum" and reg["bloqueia"] != "nenhum": r.erro("E-PEND-BLOQ", f"/pendencias/{n}/bloqueia", f"`{p['campo_legna']}` bloqueia {reg['bloqueia']} no registro; não pode ser rebaixada para 'nenhum'")


def _derivados(doc, r):
    if doc["resumo"] != derivar_resumo(doc): r.erro("E-RESUMO", "/resumo", "resumo não corresponde aos itens")
    if doc["resumo"]["aprovadas_automaticamente"] != 0: r.erro("E-APROV-AUTO", "/resumo/aprovadas_automaticamente", "aprovações automáticas são proibidas")
    esperado = derivar_elegibilidade(doc); el = doc["elegibilidade"]
    if {k: el[k] for k in ("pronto_para_calculo", "orcamento_completo", "bloqueios")} != esperado: r.erro("E-ELEG", "/elegibilidade", f"elegibilidade inconsistente com as pendências (esperado {esperado})")
    if doc["integridade"]["hash_conteudo"] != hash_conteudo(doc): r.erro("E-HASH", "/integridade/hash_conteudo", "hash do conteúdo não confere: documento alterado após a geração")
