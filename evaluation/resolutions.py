"""Etapa 4 do fluxo: RESOLVER divergências com evidência e manter o histórico das alterações.

O gabarito original (v0) NUNCA é editado. Cada decisão (alterar ou manter) vira uma entrada num log encadeado por hash, com
evidência obrigatória e decisor humano identificado. O rótulo efetivo = v0 + resoluções aplicadas em ordem.
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

from ingest.technical.model import Ator, AtorTipo

from .hashlog import HashLog
from .paths import Caminhos

CAMPOS = {"papel": {"cota_regular", "cota_deslocada", "medida_em_nota", "nao_cota"}, "veredito_associacao": {"correta", "incorreta", "indeterminada"}, "valor_escrito_correto": {True, False, None}}
ORIGEM_CAMPO = {"papel": "role", "veredito_associacao": "assoc_verdict_baseline", "valor_escrito_correto": "written_value_correct"}
TIPOS_EVIDENCIA = {"soma_cadeia", "inspecao_visual", "documento", "segundo_revisor", "decisao_conjunta"}
DECISOES = {"alterar", "manter"}
MIN_EVIDENCIA = 20


class ResolucaoInvalida(Exception):
    pass


def rotulo_inicial(token: dict) -> dict:
    return {c: token.get(o) for c, o in ORIGEM_CAMPO.items()}


def rotulo_efetivo(token: dict, entradas: list[dict]) -> dict:
    r = rotulo_inicial(token)
    for e in entradas:
        if e["item"] == token["id"] and e["decisao"] == "alterar":
            r[e["campo"]] = e["valor_novo"]
    return r


def resolver(c: Caminhos | None = None, *, item: str, campo: str, decisao: str, valor_novo, evidencia_tipo: str, evidencia: str, decidido_por: str,
             revisores_citados: list[str] | None = None, observacao: str | None = None) -> dict:
    c = c or Caminhos(); gt = json.loads(c.gt_v0.read_text()); tok = {t["id"]: t for t in gt["tokens"]}
    folha = {i["id"] for i in json.loads(c.itens.read_text())["itens"]}
    if item not in tok or item not in folha: raise ResolucaoInvalida(f"item '{item}' não existe ou não faz parte da folha de conferência")
    if campo not in CAMPOS: raise ResolucaoInvalida(f"campo inválido '{campo}' (use {sorted(CAMPOS)})")
    if decisao not in DECISOES: raise ResolucaoInvalida(f"decisão inválida '{decisao}' (use {sorted(DECISOES)})")
    if valor_novo not in CAMPOS[campo]: raise ResolucaoInvalida(f"valor '{valor_novo}' inválido para {campo} (aceitos: {sorted(map(str, CAMPOS[campo]))})")
    if evidencia_tipo not in TIPOS_EVIDENCIA: raise ResolucaoInvalida(f"tipo de evidência inválido (use {sorted(TIPOS_EVIDENCIA)})")
    if len((evidencia or "").strip()) < MIN_EVIDENCIA: raise ResolucaoInvalida(f"a evidência precisa de ao menos {MIN_EVIDENCIA} caracteres: descreva O QUE foi observado/calculado")
    try: Ator(tipo=AtorTipo.HUMANO, id=decidido_por)
    except Exception as e: raise ResolucaoInvalida(f"decisor precisa ser humano identificado: {str(e).splitlines()[0]}") from e      # noqa: BLE001
    log = HashLog(c.resolucoes); atual = rotulo_efetivo(tok[item], log.entradas)[campo]
    if decisao == "alterar" and valor_novo == atual: raise ResolucaoInvalida(f"'alterar' exige valor diferente do atual ({atual!r}); use decisao='manter'")
    if decisao == "manter" and valor_novo != atual: raise ResolucaoInvalida(f"'manter' exige o valor atual ({atual!r})")
    if evidencia_tipo == "segundo_revisor":
        sha8 = {e["sha256"][:8] for e in HashLog(c.manifesto_respostas).entradas}
        if not revisores_citados or not set(revisores_citados) <= sha8: raise ResolucaoInvalida("evidência 'segundo_revisor' exige citar respostas registradas (sha8 do arquivo)")
    return log.adicionar(item=item, campo=campo, decisao=decisao, valor_anterior=atual, valor_novo=valor_novo, evidencia_tipo=evidencia_tipo, evidencia=evidencia.strip(),
                         decidido_por=Ator(tipo=AtorTipo.HUMANO, id=decidido_por).id, revisores_citados=revisores_citados or [], observacao=observacao)


def pendentes(c: Caminhos, relatorio: dict) -> list[str]:
    """Itens que o relatório marcou como divergentes e ainda NÃO têm nenhuma resolução registrada."""
    resolvidos = {e["item"] for e in HashLog(c.resolucoes).entradas}
    return [i for i in relatorio["precisam_resolucao"] if i not in resolvidos]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); [a.add_argument(f"--{k}", required=True) for k in ("item", "campo", "decisao", "valor", "evidencia-tipo", "evidencia", "decidido-por")]; a.add_argument("--revisores-citados", nargs="*"); a.add_argument("--obs")
    sub.add_parser("list")
    args = ap.parse_args(); conv = {"true": True, "false": False, "null": None}
    if args.cmd == "list":
        for e in HashLog(Caminhos().resolucoes).entradas: print(f"#{e['seq']} {e['item']} {e['campo']}: {e['valor_anterior']!r} -> {e['valor_novo']!r} ({e['decisao']}, {e['evidencia_tipo']}, por {e['decidido_por']})")
        sys.exit(0)
    try:
        v = conv.get(args.valor, args.valor)
        e = resolver(item=args.item, campo=args.campo, decisao=args.decisao, valor_novo=v, evidencia_tipo=args.evidencia_tipo, evidencia=args.evidencia, decidido_por=args.decidido_por, revisores_citados=args.revisores_citados, observacao=args.obs)
        print(f"resolução #{e['seq']} registrada")
    except ResolucaoInvalida as ex:
        print(f"RECUSADA: {ex}", file=sys.stderr); sys.exit(2)
