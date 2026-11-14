"""Etapa 2 do fluxo: REGISTRAR as respostas de um revisor independente, sem modificar o gabarito.

O CSV recebido é guardado byte a byte (nunca editado) em review/respostas/, com hash em um manifesto encadeado.
Uso: python -m evaluation.review_record respostas.csv [--recebido-de "Nome"]
"""
from __future__ import annotations

import argparse, csv, hashlib, json, re, shutil, sys
from datetime import datetime
from pathlib import Path

from ingest.technical.model import Ator, AtorTipo

from .hashlog import HashLog
from .paths import Caminhos
from .review_sheet import CSV_COLS

Q1 = {"", "cota_regular", "cota_deslocada", "nota", "nao_medida", "nao_sei"}
Q23 = {"", "sim", "nao", "nao_sei"}


class RespostasInvalidas(Exception):
    pass


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def validar_csv(csv_path, c: Caminhos) -> dict:
    erros, avisos = [], []
    itens = {i["id"] for i in json.loads(c.itens.read_text())["itens"]}
    try:
        rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
    except Exception as e:                                                   # noqa: BLE001
        return {"ok": False, "erros": [f"CSV ilegível: {e}"], "avisos": []}
    if not rows:
        return {"ok": False, "erros": ["CSV sem linhas"], "avisos": []}
    falta = [col for col in CSV_COLS if col not in rows[0]]
    if falta:
        return {"ok": False, "erros": [f"colunas ausentes: {falta}"], "avisos": []}
    ids = [r["id"] for r in rows]
    for dup in sorted({i for i in ids if ids.count(i) > 1}): erros.append(f"id duplicado: {dup}")
    for i in sorted(set(ids) - itens): erros.append(f"id desconhecido (não está na folha): {i}")
    revisores = {r["revisor"].strip() for r in rows if r["revisor"].strip()}
    if len(revisores) != 1:
        erros.append(f"o arquivo deve ter exatamente 1 revisor; encontrados: {sorted(revisores) or 'nenhum'}")
    else:
        try: Ator(tipo=AtorTipo.HUMANO, id=next(iter(revisores)))
        except Exception as e: erros.append(f"revisor não é uma identificação humana válida: {str(e).splitlines()[0]}")      # noqa: BLE001
    for r in rows:
        for col, ok in (("q1_papel", Q1), ("q2_intervalo_correto", Q23), ("q3_valor_correto", Q23)):
            if r[col].strip() not in ok: erros.append(f"{r['id']}: valor inválido em {col}: '{r[col]}' (aceitos: {sorted(x for x in ok if x)})")
    resp = [r for r in rows if any(r[c_].strip() for c_ in ("q1_papel", "q2_intervalo_correto", "q3_valor_correto"))]
    comp = [r for r in resp if all(r[c_].strip() for c_ in ("q1_papel", "q2_intervalo_correto", "q3_valor_correto"))]
    if not resp: erros.append("nenhum item respondido")
    if len(comp) < len(resp): avisos.append(f"{len(resp) - len(comp)} item(ns) respondidos parcialmente (faltam perguntas)")
    if itens - set(ids): avisos.append(f"{len(itens - set(ids))} itens da folha não constam no arquivo")
    if erros: return {"ok": False, "erros": erros, "avisos": avisos}
    return {"ok": True, "erros": [], "avisos": avisos, "revisor": next(iter(revisores)), "itens_total": len(itens), "itens_respondidos": len(resp), "itens_completos": len(comp)}


def registrar(csv_path, c: Caminhos | None = None, recebido_de: str | None = None) -> dict:
    c = c or Caminhos(); v = validar_csv(csv_path, c)
    if not v["ok"]:
        raise RespostasInvalidas("; ".join(v["erros"]))
    log = HashLog(c.manifesto_respostas)
    gt = sha(c.gt_v0)
    if any(e["gabarito_sha256"] != gt for e in log.entradas):
        raise RespostasInvalidas("o gabarito original mudou desde um recebimento anterior: investigar antes de registrar")
    h = sha(csv_path); slug = re.sub(r"\W+", "_", v["revisor"]).strip("_").lower()
    destino = c.respostas / f"{datetime.now().strftime('%Y%m%d')}_{slug}_{h[:8]}.csv"
    if destino.exists() or any(e["sha256"] == h for e in log.entradas):
        raise RespostasInvalidas("este arquivo (mesmo conteúdo) já foi registrado")
    c.respostas.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(csv_path, destino)                                        # byte a byte
    assert sha(destino) == h
    destino.chmod(0o444)
    return log.adicionar(arquivo=destino.name, sha256=h, revisor=v["revisor"], itens_total=v["itens_total"], itens_respondidos=v["itens_respondidos"],
                         itens_completos=v["itens_completos"], avisos=v["avisos"], recebido_de=recebido_de, gabarito_sha256=gt, resultados_sha256=sha(c.resultado_v0),
                         algoritmo_sha256=sha(c.algoritmo))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--recebido-de")
    a = ap.parse_args()
    try:
        e = registrar(a.csv, recebido_de=a.recebido_de); print(f"registrado #{e['seq']}: {e['arquivo']} ({e['itens_respondidos']}/{e['itens_total']} itens; revisor {e['revisor']})")
    except RespostasInvalidas as ex:
        print(f"RECUSADO: {ex}", file=sys.stderr); sys.exit(2)
