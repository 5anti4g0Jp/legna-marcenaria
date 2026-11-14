"""Registro rastreável do ENVIO do pacote de revisão independente e da validação do RETORNO.

Não envia nada (não há canal de envio neste ambiente): registra o preparo, a confirmação de envio feita por uma pessoa e o retorno.
Log append-only com cadeia de hash em `evaluation/review_package/envios.jsonl`. Não altera pacote, gabarito, baseline nem algoritmo.
"""
from __future__ import annotations
import csv, json, re
from pathlib import Path

from . import review_package as P
from .hashlog import HashLog, agora
from .paths import Caminhos
from .review_record import registrar, validar_csv, sha
from .review_sheet import CSV_COLS

LOG = P.ROOT / "envios.jsonl"
MENSAGEM = P.ROOT / P.VERSAO / "MENSAGEM_AO_REVISOR.md"
NAO_ENVIAR = ["MANIFESTO_PACOTE.json", "evaluation/review/exclusoes_q2.json", "evaluation/groundtruth/*", "evaluation/results/*", "evaluation/baseline_etapa0/*",
              "evaluation/review/itens_selecionados.json", "evaluation/review/folha_conferencia_baseline_etapa0.html", "evaluation/review_package/pkg-1.0/*", "MENSAGEM_AO_REVISOR.md (é texto, não anexo)"]


class EnvioInvalido(Exception):
    pass


def _conferir(root: Path, versao: str) -> dict:
    d = root / versao / "entrega"; man = json.loads((root / versao / "MANIFESTO_PACOTE.json").read_text())
    erros = P.verificar(root, versao)
    if erros: raise EnvioInvalido(f"pacote {versao} não confere: {erros}")
    return {n: m["sha256"] for n, m in man["arquivos_entregues"].items()}


def _estado(log: HashLog, versao: str) -> str | None:
    ev = [e for e in log.entradas if e["pacote"] == versao]
    return ev[-1]["status"] if ev else None


def preparar(root: Path = P.ROOT, versao: str = P.VERSAO, log_path: Path = LOG, mensagem: Path = MENSAGEM, preparado_por: str = "assistente (automático)") -> dict:
    hashes = _conferir(root, versao); log = HashLog(log_path)
    if _estado(log, versao): raise EnvioInvalido(f"{versao} já tem registro de envio (status: {_estado(log, versao)})")
    return log.adicionar(evento="preparado", pacote=versao, status="preparado_aguardando_envio", arquivos_a_enviar=hashes, nao_enviar=NAO_ENVIAR,
                         mensagem_ao_revisor_sha256=sha(mensagem), data=agora()[:10], preparado_por=preparado_por,
                         observacao="nenhum envio foi realizado por este sistema; o envio é feito por uma pessoa e confirmado com confirmar_envio()")


def confirmar_envio(*, destinatario: str, canal: str, enviado_em: str, confirmado_por: str, root: Path = P.ROOT, versao: str = P.VERSAO, log_path: Path = LOG,
                    arquivos_enviados: list[str] | None = None) -> dict:
    """Uma PESSOA confirma que enviou. `arquivos_enviados` deve ser exatamente os 3 arquivos autorizados."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", enviado_em): raise EnvioInvalido("enviado_em deve ser AAAA-MM-DD")
    for nome, v in (("destinatario", destinatario), ("canal", canal), ("confirmado_por", confirmado_por)):
        if len(v.strip()) < 3: raise EnvioInvalido(f"{nome} obrigatório")
    if confirmado_por.strip().lower() in ("assistente", "sistema", "claude", "ia"): raise EnvioInvalido("a confirmação do envio deve ser de uma pessoa")
    hashes = _conferir(root, versao); log = HashLog(log_path)
    if _estado(log, versao) != "preparado_aguardando_envio": raise EnvioInvalido(f"estado atual: {_estado(log, versao)}; esperado: preparado_aguardando_envio")
    if sorted(arquivos_enviados or hashes) != sorted(hashes): raise EnvioInvalido(f"arquivos enviados diferem dos 3 autorizados: {arquivos_enviados}")
    return log.adicionar(evento="envio_confirmado", pacote=versao, status="enviado", arquivos_enviados=hashes, destinatario=destinatario.strip(), canal=canal.strip(),
                         enviado_em=enviado_em, confirmado_por=confirmado_por.strip())


def validar_retorno(csv_path, c: Caminhos | None = None, root: Path = P.ROOT, versao: str = P.VERSAO) -> dict:
    """Valida o CSV devolvido ANTES de registrar: 46 IDs exatos, pré-preenchimento intacto, integridade e regras do registro. Não registra."""
    c = c or Caminhos(); erros = []
    entregue = list(csv.DictReader(open(root / versao / "entrega" / P.CSV_NOME, encoding="utf-8-sig")))
    try: rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
    except Exception as e: return {"ok": False, "erros": [f"CSV ilegível: {e}"]}                      # noqa: BLE001
    if not rows or list(rows[0].keys()) != CSV_COLS: erros.append(f"cabeçalho diferente do CSV entregue: {list(rows[0].keys()) if rows else '—'}")
    ids = [str(r.get("id")) for r in rows]; esperados = [r["id"] for r in entregue]
    if len(ids) != 46 or sorted(ids) != sorted(esperados): erros.append(f"os 46 IDs originais não conferem (faltam {sorted(set(esperados) - set(ids))}, sobram {sorted(set(ids) - set(esperados))}, duplicados {sorted({i for i in ids if ids.count(i) > 1})})")
    base = {r["id"]: r for r in entregue}
    for r in rows:
        o = base.get(r.get("id"))
        if o and any(r.get(k) != o[k] for k in ("pagina", "texto")): erros.append(f"{r['id']}: página/texto alterados em relação ao CSV entregue")
        if r.get("grupos", ""): erros.append(f"{r.get('id')}: coluna grupos preenchida (deveria estar vazia)")
    v = validar_csv(csv_path, c)
    erros += v["erros"]
    return {"ok": not erros, "erros": erros, "avisos": v.get("avisos", []), "itens_respondidos": v.get("itens_respondidos"), "revisor": v.get("revisor"), "sha256": sha(csv_path)}


def registrar_retorno(csv_path, c: Caminhos | None = None, *, recebido_de: str, root: Path = P.ROOT, versao: str = P.VERSAO, log_path: Path = LOG) -> dict:
    """Só registra o retorno se o pacote foi enviado e o CSV passou na validação. Não resolve nem congela nada."""
    log = HashLog(log_path)
    if _estado(log, versao) != "enviado": raise EnvioInvalido(f"pacote {versao} não consta como enviado (status: {_estado(log, versao)})")
    v = validar_retorno(csv_path, c, root, versao)
    if not v["ok"]: raise EnvioInvalido(f"retorno recusado: {v['erros']}")
    e = registrar(csv_path, c, recebido_de=recebido_de)
    return log.adicionar(evento="retorno_registrado", pacote=versao, status="retorno_registrado", csv_sha256=v["sha256"], revisor=v["revisor"], itens_respondidos=v["itens_respondidos"],
                         recebido_de=recebido_de, arquivo_guardado=e["arquivo"])
