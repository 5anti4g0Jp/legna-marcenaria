"""Folha de conferência da linha de base (Etapa 0) para revisão INDEPENDENTE do gabarito.

Gera um HTML autocontido (imagens embutidas) e um CSV-modelo. O revisor responde 3 perguntas por item,
SEM ver o rótulo do gabarito (ele fica num bloco recolhido), e exporta as respostas em CSV/JSON.
Uso: python -m evaluation.review_sheet [--real PDF] [--out DIR]
"""
from __future__ import annotations

import argparse, base64, csv, hashlib, html, importlib.util, io, json, random
from pathlib import Path

import pymupdf

from . import metrics as M

ROOT = Path(__file__).resolve().parent
FROZEN = ROOT / "baseline_etapa0" / "dimensions.py"
RESULT = ROOT / "results" / "etapa0_baseline.json"
GT = ROOT / "groundtruth" / "real_fernanda.json"
DEFAULT_PDF = "/root/.claude/uploads/2776f07e-3ad9-5c9f-8cdd-0c5a8af5f4d9/0ad58788-DETALHAMENTO_DE_MARCENARIA_FERNANDA_SERTORIO.pdf"

GRUPOS = {
    "falsa_confirmacao": "Falsa confirmação (algoritmo aceitou um intervalo que o gabarito diz estar errado)",
    "conflito": "Conflito (algoritmo disse que o valor escrito não bate com a geometria)",
    "assumido": "Assumido correto SEM confirmação visual conclusiva (conflito que não consegui decidir)",
    "confirmada_indeterminada": "Confirmada pelo algoritmo, mas o gabarito não conseguiu decidir a associação",
    "pequena": "Cota pequena / espessura (≤ 60 mm)",
    "deslocada": "Cota deslocada (texto fora dos riscos, com chamada)",
    "controle": "CONTROLE: o gabarito considera correta (serve para detectar viés)",
}
ORDEM = list(GRUPOS)
CSV_COLS = ["id", "pagina", "texto", "grupos", "revisor", "q1_papel", "q2_intervalo_correto", "q3_valor_correto", "valor_lido_pelo_revisor", "observacao", "respondido_em"]
Q1 = [("", "—"), ("cota_regular", "Cota linear, texto junto à linha"), ("cota_deslocada", "Cota linear, texto fora dos riscos (chamada)"),
      ("nota", "Medida em texto de nota"), ("nao_medida", "Não é medida"), ("nao_sei", "Não sei")]
Q23 = [("", "—"), ("sim", "Sim"), ("nao", "Não"), ("nao_sei", "Não sei")]


def load_frozen():
    import sys
    spec = importlib.util.spec_from_file_location("frozen_etapa0_review", str(FROZEN)); mod = importlib.util.module_from_spec(spec)
    sys.modules["frozen_etapa0_review"] = mod; spec.loader.exec_module(mod)      # dataclasses exigem o módulo registrado
    return mod


def select_items(saved: dict, gt: dict, control_n: int = 8, seed: int = 20261114):
    """Devolve (lista ordenada de itens, contagens por grupo). Um item pode estar em vários grupos."""
    tok = {t["id"]: t for t in gt["tokens"]}
    rows = {r["id"]: r for r in saved["real"]["linhas"] if r["role"].startswith("cota")}
    tags: dict[str, set] = {i: set() for i in rows}
    for i, r in rows.items():
        t = tok[i]
        if r["outcome"] == "confirmada_associacao_incorreta": tags[i].add("falsa_confirmacao")
        if r["status"] == "conflito": tags[i].add("conflito")
        if r["outcome"] == "conflito_falso_alarme" and "soma de cadeia" not in (r.get("evidence") or ""): tags[i].add("assumido")
        if r["outcome"] == "confirmada_indeterminada": tags[i].add("confirmada_indeterminada")
        if t.get("size_class") == "<=60mm": tags[i].add("pequena")
        if r["role"] == "cota_deslocada": tags[i].add("deslocada")
    pool = sorted(i for i, r in rows.items() if r["outcome"] == "confirmada_correta" and r["role"] == "cota_regular" and not tags[i])
    for i in random.Random(seed).sample(pool, min(control_n, len(pool))): tags[i].add("controle")
    chosen = [i for i in rows if tags[i]]
    key = lambda i: (min(ORDEM.index(g) for g in tags[i]), tok[i]["page"], int(i.split("-t")[1]))
    chosen.sort(key=key)
    counts = {g: sum(1 for i in chosen if g in tags[i]) for g in ORDEM}
    return [{"id": i, "grupos": sorted(tags[i], key=ORDEM.index)} for i in chosen], counts


def baseline_details(pdf, gt, ids):
    """Roda o algoritmo CONGELADO nas páginas necessárias e alinha as dimensões aos tokens do gabarito."""
    F = load_frozen(); doc = pymupdf.open(pdf); tok = {t["id"]: t for t in gt["tokens"]}; out = {}
    for pn in sorted({tok[i]["page"] for i in ids}):
        pd = F.analyze_page(doc[pn - 1], pn)
        items = [tok[i] for i in ids if tok[i]["page"] == pn]
        out.update(M.align(items, pd.dims))
    return out


def _b64(pix, q=72) -> str:
    return base64.b64encode(pix.tobytes("jpeg", jpg_quality=q)).decode()


def render_crops(pdf, tok, dim, dpi=120):
    """(recorte limpo, recorte com a medição do algoritmo) em base64 PNG."""
    pn = tok["page"]; x0, y0, x1, y1 = tok["bbox"]; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ax0, ax1, ay0, ay1 = cx - 110, cx + 110, cy - 70, cy + 70
    if dim is not None and dim.interval_pt:
        a, b = dim.interval_pt
        if dim.orient == "h": ax0, ax1 = min(ax0, a - 15), max(ax1, b + 15)
        else: ay0, ay1 = min(ay0, a - 15), max(ay1, b + 15)
    ax0, ax1 = max(ax0, cx - 230), min(ax1, cx + 230); ay0, ay1 = max(ay0, cy - 230), min(ay1, cy + 230)
    doc = pymupdf.open(pdf); pg = doc[pn - 1]; rect = pymupdf.Rect(ax0, ay0, ax1, ay1) & pg.rect
    clean = _b64(pg.get_pixmap(clip=rect, dpi=dpi))
    doc2 = pymupdf.open(pdf); p2 = doc2[pn - 1]
    p2.draw_rect(pymupdf.Rect(x0 - 1.5, y0 - 1.5, x1 + 1.5, y1 + 1.5), color=(0.85, 0, 0.85), width=1.6)
    if dim is not None and dim.interval_pt:
        a, b = dim.interval_pt
        if dim.orient == "h": p2.draw_line((a, cy + 9), (b, cy + 9), color=(0, 0.3, 0.95), width=2.4); p2.draw_line((a, cy + 5), (a, cy + 13), color=(0, 0.3, 0.95), width=2.4); p2.draw_line((b, cy + 5), (b, cy + 13), color=(0, 0.3, 0.95), width=2.4)
        else: p2.draw_line((cx + 9, a), (cx + 9, b), color=(0, 0.3, 0.95), width=2.4); p2.draw_line((cx + 5, a), (cx + 13, a), color=(0, 0.3, 0.95), width=2.4); p2.draw_line((cx + 5, b), (cx + 13, b), color=(0, 0.3, 0.95), width=2.4)
    over = _b64(p2.get_pixmap(clip=rect, dpi=dpi))
    return clean, over


def thumb(pdf, pn):
    return _b64(pymupdf.open(pdf)[pn - 1].get_pixmap(dpi=40), q=55)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def template_csv(items, gt) -> str:
    tok = {t["id"]: t for t in gt["tokens"]}; buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(CSV_COLS)
    for it in items:
        t = tok[it["id"]]; w.writerow([it["id"], t["page"], t["text"], "|".join(it["grupos"]), "", "", "", "", "", "", ""])
    return buf.getvalue()


def _opts(opts): return "".join(f'<option value="{v}">{html.escape(l)}</option>' for v, l in opts)


def build_html(pdf, saved, gt, items, counts) -> str:
    tok = {t["id"]: t for t in gt["tokens"]}; rows = {r["id"]: r for r in saved["real"]["linhas"]}
    det = baseline_details(pdf, gt, [i["id"] for i in items]); pages = sorted({tok[i["id"]]["page"] for i in items})
    thumbs = {p: thumb(pdf, p) for p in pages}; psize = {p: pymupdf.open(pdf)[p - 1].rect for p in pages}
    cards = []
    for n, it in enumerate(items, 1):
        t = tok[it["id"]]; r = rows[it["id"]]; d = det[it["id"]]; clean, over = render_crops(pdf, t, d)
        x = ((t["bbox"][0] + t["bbox"][2]) / 2) / psize[t["page"]].width * 100; y = ((t["bbox"][1] + t["bbox"][3]) / 2) / psize[t["page"]].height * 100
        if d is not None and d.interval_pt:
            mm = f"{d.length_pt:.1f} pt × {d.scale:.4f} mm/pt = <b>{d.measured_mm:.0f} mm</b>" if d.measured_mm else f"{d.length_pt:.1f} pt"
            res = f"estado do algoritmo: <b>{html.escape(r['status'] or '—')}</b> · intervalo medido: {mm}"
        else:
            res = f"estado do algoritmo: <b>{html.escape(r['status'] or 'não virou candidato')}</b> · sem intervalo medido"
        tags = " ".join(f'<span class="tag t-{g}">{g}</span>' for g in it["grupos"])
        cards.append(f'''<section class="card" data-id="{it["id"]}" data-pagina="{t["page"]}" data-texto="{html.escape(t["text"])}" data-grupos="{"|".join(it["grupos"])}">
<h3>#{n} · {html.escape(t["text"])} <small>(p.{t["page"]}, {t["orientation"]}) · {it["id"]}</small></h3><div class="tags">{tags}</div>
<div class="imgs"><figure><img src="data:image/jpeg;base64,{clean}" alt="recorte limpo"><figcaption>Recorte limpo</figcaption></figure>
<figure><img src="data:image/jpeg;base64,{over}" alt="recorte com medição"><figcaption>Com a medição do algoritmo (caixa magenta = número; linha azul = intervalo medido)</figcaption></figure>
<figure class="map"><div class="thumbbox th{t["page"]}"><i style="left:{x:.1f}%;top:{y:.1f}%"></i></div><figcaption>Posição na página {t["page"]}</figcaption></figure></div>
<div class="q"><label>1. O que é este número?<select name="q1">{_opts(Q1)}</select></label>
<label>2. A linha azul cobre exatamente o trecho que esta cota mede?<select name="q2">{_opts(Q23)}</select></label>
<label>3. O valor escrito está correto?<select name="q3">{_opts(Q23)}</select></label>
<label>Valor que você leria (se diferente)<input name="valor" size="8"></label><label class="obs">Observação<textarea name="obs" rows="2"></textarea></label></div>
<details><summary>Ver rótulo do gabarito e resultado do algoritmo <em>(só depois de responder)</em></summary><ul>
<li>Rótulo do gabarito: <b>{html.escape(t["role"])}</b> · tamanho <b>{html.escape(str(t.get("size_class")))}</b> · evidência: {html.escape(t.get("evidence") or "—")}</li>
<li>{res}</li><li>Resultado classificado: <b>{html.escape(r["outcome"])}</b>{(" · nota do gabarito: " + html.escape(t.get("assoc_note") or "")) if t.get("assoc_note") else ""}</li></ul></details></section>''')
    legend = "".join(f"<li><span class='tag t-{g}'>{g}</span> {html.escape(GRUPOS[g])} — <b>{counts[g]}</b></li>" for g in ORDEM)
    thumbcss = "".join(f".th{p}{{height:{150 * psize[p].height / psize[p].width:.0f}px;background-image:url(data:image/jpeg;base64,{thumbs[p]})}}" for p in pages)
    css = thumbcss + """body{font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:1180px;margin:20px auto;padding:0 14px;color:#1a1a1a}h1{margin-bottom:4px}.meta{color:#555;font-size:13px}
.card{border:1px solid #ccc;border-radius:8px;padding:12px 14px;margin:16px 0;break-inside:avoid}.card h3{margin:0 0 6px}.card small{color:#666;font-weight:400}.imgs{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-start}
.imgs img{border:1px solid #bbb;max-width:520px;height:auto}figure{margin:0}figcaption{font-size:12px;color:#555;max-width:520px}.map .thumbbox{position:relative;display:inline-block;width:150px;background-size:100% 100%;border:1px solid #bbb}
.map i{position:absolute;width:10px;height:10px;margin:-5px 0 0 -5px;border-radius:50%;background:#d0d;border:1px solid #fff}.q{display:flex;gap:14px;flex-wrap:wrap;margin-top:10px}.q label{display:flex;flex-direction:column;font-size:13px;gap:3px}
.q .obs{flex:1;min-width:240px}.tags{margin:2px 0 8px}.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:10px;background:#eee;margin-right:4px}.t-falsa_confirmacao{background:#fdd}.t-conflito{background:#fde8c8}.t-assumido{background:#fff3b0}
.t-controle{background:#d8ecff}.bar{position:sticky;top:0;background:#fff;border-bottom:2px solid #333;padding:8px 0;z-index:5;display:flex;gap:10px;align-items:center;flex-wrap:wrap}button{padding:6px 12px;cursor:pointer}details{margin-top:10px;background:#fafafa;padding:6px 10px;border-radius:6px}
@media print{.bar{position:static}.card{page-break-inside:avoid}}"""
    js = """
const COLS=%s;
function rows(){return [...document.querySelectorAll('.card')].map(c=>{const g=n=>c.querySelector('[name='+n+']').value;return{id:c.dataset.id,pagina:c.dataset.pagina,texto:c.dataset.texto,grupos:c.dataset.grupos,
revisor:document.getElementById('revisor').value,q1_papel:g('q1'),q2_intervalo_correto:g('q2'),q3_valor_correto:g('q3'),valor_lido_pelo_revisor:g('valor'),observacao:g('obs'),respondido_em:(g('q1')||g('q2')||g('q3'))?new Date().toISOString():''}})}
function dl(name,text,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click()}
function esc(v){v=String(v==null?'':v);return /[",;\\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v}
function exportCSV(){const r=rows();if(!document.getElementById('revisor').value){alert('Preencha o nome do revisor.');return}
dl('revisao_'+document.getElementById('revisor').value.replace(/\\W+/g,'_')+'.csv','\\ufeff'+COLS.join(',')+'\\n'+r.map(x=>COLS.map(c=>esc(x[c])).join(',')).join('\\n'),'text/csv')}
function exportJSON(){dl('revisao.json',JSON.stringify(rows(),null,1),'application/json')}
function prog(){const n=[...document.querySelectorAll('.card')].filter(c=>c.querySelector('[name=q1]').value&&c.querySelector('[name=q2]').value&&c.querySelector('[name=q3]').value).length;document.getElementById('prog').textContent=n+' de '+document.querySelectorAll('.card').length+' itens respondidos'}
document.addEventListener('change',prog);window.addEventListener('load',prog);""" % json.dumps(CSV_COLS)
    head = f"""<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Folha de conferência — linha de base Etapa 0</title><style>{css}</style>
<h1>Folha de conferência da linha de base (Etapa 0)</h1>
<p class="meta">Documento: <b>{html.escape(Path(pdf).name)}</b> · SHA-256 <code>{sha(pdf)[:16]}…</code> · algoritmo avaliado: <code>{saved['meta']['algoritmo']['sha256'][:12]}…</code> (congelado) · {len(items)} itens únicos.</p>
<p>Objetivo: verificar se o <b>gabarito</b> (feito pelo assistente, sem conferência independente) está correto. <b>Responda cada item olhando só o desenho</b>; o rótulo do gabarito e o resultado do algoritmo ficam recolhidos em cada cartão e só devem ser abertos depois.</p>
<ol><li><b>O que é este número?</b> Cota linear (texto junto à linha ou fora dos riscos, com chamada), medida escrita em nota, ou algo que não é medida.</li>
<li><b>A linha azul cobre exatamente o trecho que esta cota mede?</b> (entre as duas marcas/extensões que a cota delimita)</li><li><b>O valor escrito está correto?</b> Confira por contexto e pela soma de cotas vizinhas; se discordar, escreva o valor que leria.</li></ol>
<p>Se não for possível decidir, marque <b>Não sei</b>: isso é uma resposta válida e útil.</p><h3>Grupos incluídos</h3><ul>{legend}</ul>
<div class="bar"><label>Revisor: <input id="revisor" placeholder="seu nome"></label><button onclick="exportCSV()">Exportar respostas (CSV)</button><button onclick="exportJSON()">Exportar (JSON)</button><span id="prog"></span><small>Exporte com frequência: a página não salva sozinha.</small></div>"""
    return head + "\n".join(cards) + f"<script>{js}</script></html>"


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--real", default=DEFAULT_PDF); ap.add_argument("--out", default=str(ROOT / "review"))
    a = ap.parse_args(argv); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    saved = json.loads(RESULT.read_text()); gt = json.loads(GT.read_text()); items, counts = select_items(saved, gt)
    (out / "folha_conferencia_baseline_etapa0.html").write_text(build_html(a.real, saved, gt, items, counts), encoding="utf-8")
    (out / "revisao_independente_template.csv").write_text(template_csv(items, gt), encoding="utf-8")
    (out / "itens_selecionados.json").write_text(json.dumps({"itens": items, "contagem_por_grupo": counts, "total_unico": len(items)}, ensure_ascii=False, indent=1))
    print(f"{len(items)} itens únicos | por grupo: {counts}")
    return items, counts


if __name__ == "__main__":
    main()
