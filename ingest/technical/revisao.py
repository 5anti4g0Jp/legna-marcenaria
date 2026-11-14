"""Registro de revisões HUMANAS (append-only, com cadeia de hash) e sua aplicação sobre um resultado de análise.

A análise automática é regerável e determinística; a decisão humana vive neste registro, separado. Uma decisão só é aplicada
se o DOCUMENTO (hash), a PÁGINA, o TEXTO e a POSIÇÃO da medida baterem: se o arquivo mudou, a aprovação não vale mais.
"""
from __future__ import annotations

import hashlib, json
from pathlib import Path

from .model import Ator, AtorTipo, Estado, Resultado, agora, resumir

CAMPOS = ("seq", "em", "medida_id", "documento_sha256", "pagina", "coords", "texto_original", "decisao", "revisor", "observacao", "valor_confirmado", "hash_anterior")
TOL_COORD = 0.5


class RegistroAdulterado(Exception):
    pass


def _hash(entrada: dict) -> str:
    base = {k: entrada[k] for k in CAMPOS}
    return hashlib.sha256(json.dumps(base, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class RegistroRevisoes:
    def __init__(self, caminho: str | Path | None = None):
        self.caminho = Path(caminho) if caminho else None
        self.entradas: list[dict] = []
        if self.caminho and self.caminho.exists():
            self.entradas = [json.loads(l) for l in self.caminho.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.verificar()

    def verificar(self) -> None:
        """Levanta RegistroAdulterado se qualquer entrada foi alterada, removida, reordenada ou inserida."""
        anterior = "0" * 64
        for i, e in enumerate(self.entradas):
            if e.get("seq") != i + 1 or e.get("hash_anterior") != anterior or e.get("hash") != _hash(e):
                raise RegistroAdulterado(f"cadeia de hash quebrada na entrada {i + 1}")
            anterior = e["hash"]

    def registrar(self, *, medida, decisao: str, revisor: str, observacao: str | None = None, valor_confirmado: str | None = None, em: str | None = None) -> dict:
        """Registra uma decisão humana sobre uma `Medida`. Exige revisor humano identificado."""
        if decisao not in ("aprovado", "rejeitado"):
            raise ValueError("decisão deve ser 'aprovado' ou 'rejeitado'")
        ator = Ator(tipo=AtorTipo.HUMANO, id=revisor)                 # valida identificação humana
        e = {"seq": len(self.entradas) + 1, "em": em or agora(), "medida_id": medida.id, "documento_sha256": medida.documento.sha256, "pagina": medida.pagina,
             "coords": list(medida.coords), "texto_original": medida.texto_original, "decisao": decisao, "revisor": ator.id, "observacao": observacao,
             "valor_confirmado": valor_confirmado, "hash_anterior": self.entradas[-1]["hash"] if self.entradas else "0" * 64}
        e["hash"] = _hash(e)
        self.entradas.append(e)
        if self.caminho:
            with open(self.caminho, "a", encoding="utf-8") as f:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        return e


def aplicar_revisoes(resultado: Resultado, registro: RegistroRevisoes) -> dict:
    """Aplica as decisões do registro (em ordem) às medidas do resultado. Devolve relatório {aplicadas, ja_aplicadas, nao_aplicadas}."""
    registro.verificar()
    por_id = {m.id: m for m in resultado.medidas}
    rel = {"aplicadas": [], "ja_aplicadas": [], "nao_aplicadas": []}
    for e in registro.entradas:
        m = por_id.get(e["medida_id"])
        if m is None:
            rel["nao_aplicadas"].append({"seq": e["seq"], "medida_id": e["medida_id"], "motivo": "medida_nao_encontrada"}); continue
        if e["documento_sha256"] != m.documento.sha256:
            rel["nao_aplicadas"].append({"seq": e["seq"], "medida_id": m.id, "motivo": "documento_diferente (o arquivo mudou: a decisão não vale)"}); continue
        if e["pagina"] != m.pagina or e["texto_original"] != m.texto_original or any(abs(a - b) > TOL_COORD for a, b in zip(e["coords"], m.coords)):
            rel["nao_aplicadas"].append({"seq": e["seq"], "medida_id": m.id, "motivo": "posicao_ou_texto_diferente"}); continue
        humano = Ator(tipo=AtorTipo.HUMANO, id=e["revisor"])
        if m.estado == Estado.APROVADO:
            if e["decisao"] == "aprovado":
                rel["ja_aplicadas"].append({"seq": e["seq"], "medida_id": m.id}); continue
            m.revogar(e["revisor"], f"decisão posterior (#{e['seq']}) rejeita")                       # a última decisão humana prevalece
        elif m.estado == Estado.PENDENTE_REVISAO:
            pass
        else:
            m.enfileirar_revisao(humano, f"revisão humana iniciada (decisão #{e['seq']})")
        (m.aprovar if e["decisao"] == "aprovado" else m.rejeitar)(e["revisor"], e.get("observacao"), e.get("valor_confirmado"))
        rel["aplicadas"].append({"seq": e["seq"], "medida_id": m.id, "decisao": e["decisao"], "revisor": e["revisor"]})
    resultado.resumo = resumir(resultado.medidas)
    return rel
