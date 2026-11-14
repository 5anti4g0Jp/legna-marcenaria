"""Etapa 5 do fluxo: CONGELAR e VERSIONAR a baseline revisada.

v0 = baseline original (gabarito do assistente, sem revisão independente). revN = v0 + resoluções registradas (evidência + decisor humano).
A versão nova vai para uma pasta própria (groundtruth/versoes/revN/); v0 e seus resultados NUNCA são alterados. O algoritmo é o congelado
da Etapa 0: as diferenças entre v0 e revN vêm só dos RÓTULOS. Cada versão tem manifesto de hashes verificável.
"""
from __future__ import annotations

import copy, hashlib, json, re
from pathlib import Path

from ingest.technical.model import Ator, AtorTipo

from . import report as relatorio_md
from . import resolutions as R
from . import review_report as RR
from .hashlog import HashLog, agora
from .labels_real import _num, size_class
from .paths import Caminhos


class CongelamentoRecusado(Exception):
    pass


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _artefatos_v0(c: Caminhos) -> dict:
    out = {"gabarito_sha256": sha(c.gt_v0), "resultados_sha256": sha(c.resultado_v0), "algoritmo_sha256": sha(c.algoritmo)}
    for k, p in (("sintetico_manifest_sha256", c.sintetico_manifest), ("relatorio_sha256", c.resultado_v0.with_name("etapa0_relatorio.md"))):
        if p.exists(): out[k] = sha(p)
    return out


def registrar_v0(c: Caminhos | None = None) -> dict:
    """Registra (uma vez) a baseline ORIGINAL como v0 e, nas chamadas seguintes, confirma que continua idêntica."""
    c = c or Caminhos(); log = HashLog(c.versoes_log); atual = _artefatos_v0(c)
    existente = next((e for e in log.entradas if e["versao"] == "v0"), None)
    if existente:
        mud = [k for k, v in atual.items() if existente["artefatos"].get(k) != v]
        if mud: raise CongelamentoRecusado(f"a baseline v0 foi ALTERADA desde o registro: {mud}")
        return existente
    return log.adicionar(versao="v0", pai=None, descricao="baseline original da Etapa 0 (gabarito do assistente, sem revisão independente)", artefatos=atual, independent_review=False)


def _humano(nome: str) -> str:
    return Ator(tipo=AtorTipo.HUMANO, id=nome).id


def construir_gabarito(c: Caminhos, versao: str, entradas: list[dict], rev: list[dict]) -> dict:
    gt = json.loads(c.gt_v0.read_text()); novo = copy.deepcopy(gt); conferidos = sorted({i for r in rev for i, row in r["rows"].items() if any(row[k].strip() for k in ("q1_papel", "q2_intervalo_correto", "q3_valor_correto"))})
    por_item: dict[str, list[dict]] = {}
    for e in entradas: por_item.setdefault(e["item"], []).append(e)
    for t in novo["tokens"]:
        if t["id"] not in por_item: continue
        ef = R.rotulo_efetivo(t, entradas)
        t["role"], t["assoc_verdict_baseline"], t["written_value_correct"] = ef["papel"], ef["veredito_associacao"], ef["valor_escrito_correto"]
        if t["role"].startswith("cota") and not t.get("size_class") and _num(t["text"]) is not None:
            t["value_mm"] = _num(t["text"]); t["size_class"] = size_class(t["value_mm"])
        t["historico_alteracoes"] = [{"seq": e["seq"], "decisao": e["decisao"], "campo": e["campo"], "de": e["valor_anterior"], "para": e["valor_novo"], "evidencia_tipo": e["evidencia_tipo"],
                                      "evidencia": e["evidencia"], "decidido_por": e["decidido_por"], "em": e["em"]} for e in por_item[t["id"]]]
    novo.update(versao=versao, derivado_de={"versao": "v0", "sha256": sha(c.gt_v0)}, independent_review=True,
                revisao_independente={"revisores": sorted({r["revisor"] for r in rev}), "arquivos": [r["sha8"] for r in rev], "itens_conferidos": len(conferidos), "ids_conferidos": conferidos,
                                      "resolucoes": len(entradas), "resolucoes_hash_cabeca": HashLog(c.resolucoes).cabeca})
    novo["limitacoes"] = list(gt["limitacoes"]) + [f"{versao}: SOMENTE os {len(conferidos)} itens da folha de conferência tiveram revisão independente; os demais tokens revisados seguem sem conferência independente"]
    return novo


def _diff(v0_res: dict, novo_res: dict, entradas: list[dict], versao: str) -> str:
    a = {r["id"]: r for r in v0_res["real"]["linhas"]}; b = {r["id"]: r for r in novo_res["real"]["linhas"]}
    mud = [(i, a[i], b[i]) for i in a if a[i]["outcome"] != b[i]["outcome"] or a[i]["role"] != b[i]["role"]]
    ca = {k: sum(1 for r in a.values() if r["outcome"] == k and r["role"].startswith("cota")) for k in sorted({r["outcome"] for r in list(a.values()) + list(b.values())})}
    cb = {k: sum(1 for r in b.values() if r["outcome"] == k and r["role"].startswith("cota")) for k in ca}
    L = [f"# Diferenças v0 → {versao}", "", "O algoritmo é o **mesmo** (congelado): toda diferença vem dos **rótulos** alterados pelas resoluções.", "",
         f"## Resoluções ({len(entradas)})", "", "| # | Item | Campo | Decisão | De → Para | Evidência | Decidido por |", "|---|---|---|---|---|---|---|"]
    L += [f"| {e['seq']} | `{e['item']}` | {e['campo']} | {e['decisao']} | {e['valor_anterior']} → {e['valor_novo']} | ({e['evidencia_tipo']}) {e['evidencia']} | {e['decidido_por']} |" for e in entradas]
    L += ["", f"## Resultados que mudaram ({len(mud)})", "", "| Item | Texto | Papel v0 → rev | Resultado v0 → rev |", "|---|---|---|---|"]
    L += [f"| `{i}` | {x['text']} | {x['role']} → {y['role']} | {x['outcome']} → {y['outcome']} |" for i, x, y in mud] or ["| — | — | — | — |"]
    L += ["", "## Cotas por resultado", "", "| Resultado | v0 | " + versao + " |", "|---|---|---|"] + [f"| {k} | {ca[k]} | {cb[k]} |" for k in ca]
    return "\n".join(L) + "\n"


def congelar(c: Caminhos | None = None, versao: str = "rev1", *, congelado_por: str, pdf: str | None = None, avaliar: bool = True) -> dict:
    c = c or Caminhos(); por = _humano(congelado_por)
    if not re.fullmatch(r"rev\d+", versao): raise CongelamentoRecusado("versão deve ter o formato revN (ex.: rev1)")
    destino = c.versoes_dir / versao
    if destino.exists(): raise CongelamentoRecusado(f"a versão {versao} já existe e é imutável")
    registrar_v0(c)
    if not HashLog(c.manifesto_respostas).entradas: raise CongelamentoRecusado("nenhuma resposta de revisão independente foi registrada")
    rep = RR.gerar(c); pend = R.pendentes(c, rep)
    if pend: raise CongelamentoRecusado(f"{len(pend)} divergência(s) sem resolução registrada: {pend}")
    entradas = HashLog(c.resolucoes).entradas; rev = RR.carregar(c)
    destino.mkdir(parents=True)
    gt_novo = construir_gabarito(c, versao, entradas, rev); (destino / "real_fernanda.json").write_text(json.dumps(gt_novo, ensure_ascii=False, indent=1))
    arquivos = ["real_fernanda.json"]
    if avaliar:
        if not pdf or not Path(pdf).exists(): raise CongelamentoRecusado("avaliação pede o PDF real (--pdf); use avaliar=False para congelar só os rótulos")
        from . import run_baseline as RB
        original = RB.build_real; RB.build_real = lambda _p: copy.deepcopy(gt_novo)          # mesmos cálculos, rótulos revisados
        try:
            RB.main(["--algo", str(c.algoritmo), "--out", str(destino), "--tag", f"etapa0_baseline_{versao}", "--no-write-gt", "--real", str(pdf)])
        finally:
            RB.build_real = original
        arq_res = destino / f"etapa0_baseline_{versao}.json"; res = json.loads(arq_res.read_text())
        res["meta"]["gabarito"] = {"versao": versao, "sha256": sha(destino / "real_fernanda.json"), "derivado_de": "v0"}; arq_res.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
        (destino / f"etapa0_relatorio_{versao}.md").write_text(relatorio_md.render(res), encoding="utf-8")
        (destino / "diff_vs_v0.md").write_text(_diff(json.loads(c.resultado_v0.read_text()), res, entradas, versao), encoding="utf-8")
        arquivos += [arq_res.name, f"etapa0_relatorio_{versao}.md", "diff_vs_v0.md"]
    manifesto = {"versao": versao, "congelada_em": agora(), "congelado_por": por, "pai": "v0", "avaliada": avaliar,
                 "entradas": {"gabarito_v0_sha256": sha(c.gt_v0), "resolucoes_sha256": sha(c.resolucoes), "resolucoes_hash_cabeca": HashLog(c.resolucoes).cabeca,
                              "respostas_manifesto_sha256": sha(c.manifesto_respostas), "respostas_hash_cabeca": HashLog(c.manifesto_respostas).cabeca,
                              "respostas_arquivos": {r["arquivo"]: sha(c.respostas / r["arquivo"]) for r in rev}, "algoritmo_sha256": sha(c.algoritmo), "resultados_v0_sha256": sha(c.resultado_v0)},
                 "arquivos": {n: sha(destino / n) for n in arquivos}}
    (destino / "MANIFEST.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=1))
    for n in arquivos + ["MANIFEST.json"]: (destino / n).chmod(0o444)
    return HashLog(c.versoes_log).adicionar(versao=versao, pai="v0", descricao="baseline revisada: v0 + resoluções com evidência", manifesto_sha256=sha(destino / "MANIFEST.json"),
                                            gabarito_sha256=sha(destino / "real_fernanda.json"), resolucoes_hash_cabeca=HashLog(c.resolucoes).cabeca, independent_review=True)


def verificar_versao(c: Caminhos | None = None, versao: str = "rev1") -> list[str]:
    """Lista de problemas (vazia = íntegra): hashes dos arquivos, das entradas, dos logs e do registro de versões."""
    c = c or Caminhos(); p: list[str] = []
    try: registrar_v0(c)
    except CongelamentoRecusado as e: p.append(str(e))
    d = c.versoes_dir / versao
    if not (d / "MANIFEST.json").exists(): return p + [f"versão {versao} não existe"]
    m = json.loads((d / "MANIFEST.json").read_text())
    for n, h in m["arquivos"].items():
        if not (d / n).exists() or sha(d / n) != h: p.append(f"arquivo alterado ou ausente: {n}")
    e = m["entradas"]
    for rot, f, h in (("gabarito v0", c.gt_v0, e["gabarito_v0_sha256"]), ("resolucoes", c.resolucoes, e["resolucoes_sha256"]), ("manifesto de respostas", c.manifesto_respostas, e["respostas_manifesto_sha256"]),
                      ("algoritmo", c.algoritmo, e["algoritmo_sha256"]), ("resultados v0", c.resultado_v0, e["resultados_v0_sha256"])):
        if sha(f) != h: p.append(f"{rot} mudou desde o congelamento")
    for n, h in e["respostas_arquivos"].items():
        if not (c.respostas / n).exists() or sha(c.respostas / n) != h: p.append(f"arquivo de respostas alterado: {n}")
    for rot, log in (("resolucoes", c.resolucoes), ("respostas", c.manifesto_respostas), ("versoes", c.versoes_log)):
        try: HashLog(log)
        except Exception as ex: p.append(f"log {rot} adulterado: {ex}")                      # noqa: BLE001
    reg = next((x for x in HashLog(c.versoes_log).entradas if x["versao"] == versao), None)
    if not reg or reg["manifesto_sha256"] != sha(d / "MANIFEST.json"): p.append("registro de versões não confere com o manifesto")
    return p


if __name__ == "__main__":
    import argparse, sys
    ap = argparse.ArgumentParser(); ap.add_argument("versao"); ap.add_argument("--congelado-por", required=True); ap.add_argument("--pdf"); ap.add_argument("--sem-avaliar", action="store_true"); ap.add_argument("--verificar", action="store_true")
    a = ap.parse_args()
    try:
        if a.verificar: pr = verificar_versao(versao=a.versao); print("ÍNTEGRA" if not pr else "\n".join(pr)); sys.exit(1 if pr else 0)
        e = congelar(versao=a.versao, congelado_por=a.congelado_por, pdf=a.pdf, avaliar=not a.sem_avaliar); print(f"{a.versao} congelada ({e['gabarito_sha256'][:12]}…)")
    except CongelamentoRecusado as ex:
        print(f"RECUSADO: {ex}", file=sys.stderr); sys.exit(2)
