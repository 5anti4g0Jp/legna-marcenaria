"""Pacote de revisão independente (cego): gera SOMENTE a folha HTML e o CSV de respostas.

A folha original (`evaluation/review/folha_conferencia_baseline_etapa0.html`) NÃO é cega: traz rótulo do gabarito, resultado do algoritmo,
nomes de grupos (falsa_confirmacao, conflito, controle...) e hashes. Este módulo NÃO a altera: reconstrói cada cartão apenas com o que o revisor precisa
(imagens, mapa da página, 3 perguntas) e grava em pasta nova. Nada do gabarito/baseline/algoritmo é modificado.
"""
from __future__ import annotations
import csv, hashlib, html, json, os, re, shutil, sys
from datetime import date
from pathlib import Path

from .paths import EV
from .review_sheet import CSV_COLS

VERSAO = "pkg-1.1"
ANTERIOR = "pkg-1.0"
ROOT = EV / "review_package"
HTML_NOME = f"legna_revisao_{VERSAO}_folha.html"
CSV_NOME = f"legna_revisao_{VERSAO}_respostas.csv"
PDF_NOME = f"legna_revisao_{VERSAO}_projeto_referencia.pdf"
PDF_SHA256 = "bb6385f7eac3d67d5c6303a3033beb5340577b1af3bef1cfac1e2a77c0dd83dc"
PDF_ORIGEM = Path("/root/.claude/uploads/2776f07e-3ad9-5c9f-8cdd-0c5a8af5f4d9/0ad58788-DETALHAMENTO_DE_MARCENARIA_FERNANDA_SERTORIO.pdf")
EXCLUSOES = EV / "review" / "exclusoes_q2.json"
ORIGINAL = EV / "review" / "folha_conferencia_baseline_etapa0.html"
ITENS = EV / "review" / "itens_selecionados.json"

# termos que NUNCA podem aparecer nos arquivos entregues (verificado em teste e em `verificar`)
PROIBIDOS = ["gabarito", "baseline", "algoritmo", "conflito", "falsa_confirmacao", "falsa confirm", "controle", "assumido", "indeterminad", "confirmad",
             "696a8b83", "bb6385f7", "fernanda", "sertorio", "sertório", "etapa 0", "etapa0", "evidência", "mm/pt", "pontos de partida"]

INSTRUCOES = """
<h1>Folha de conferência de cotas — revisão independente</h1>
<p class="meta">Pacote <b>%(versao)s</b> · projeto executivo de marcenaria (PDF de 34 páginas, enviado junto como referência) · 46 itens</p>
<h2>O que você vai fazer</h2>
<p>Cada cartão mostra <b>um número</b> do desenho (caixa magenta) e um <b>trecho candidato</b> (linha azul). Responda <b>olhando só o desenho</b>. Não há resposta "esperada":
o que importa é a sua leitura independente. Responda mesmo quando a sua leitura parecer óbvia.</p>
<h2>As três perguntas de cada cartão</h2>
<ol>
<li><b>O que é este número?</b>
 <ul><li><i>Cota linear, texto junto à linha</i>: o número está entre as duas marcas (riscos/setas) da cota.</li>
 <li><i>Cota linear, texto fora dos riscos (chamada)</i>: é uma cota, mas o número foi escrito fora do trecho que mede, geralmente com uma chamada/curva.</li>
 <li><i>Medida em texto de nota</i>: o número aparece dentro de uma frase/nota, não junto a uma linha de cota.</li>
 <li><i>Não é medida</i>: é código, quantidade, numeração ou outra coisa.</li></ul></li>
<li><b>A linha azul cobre exatamente o trecho que esta cota mede?</b> Ou seja, entre as duas marcas que a cota delimita. "Sim" só se as pontas da linha azul coincidirem com as marcas da cota; caso contrário, "Não".
 <br><b>Atenção: alguns cartões não têm linha azul</b> (não há trecho candidato). Neles a pergunta 2 não se aplica: responda <b>"Não sei"</b> na pergunta 2 e escreva <b>sem linha azul</b> no campo "Observação". As perguntas 1 e 3 continuam valendo normalmente.</li>
<li><b>O valor escrito está correto?</b> Confira pelo contexto e pela soma das cotas vizinhas, <b>usando o PDF de referência</b> (a página do cartão, ex.: "p.6", é a página do PDF). Se discordar, escreva o valor que você leria no campo "Valor que você leria".</li>
</ol>
<h2>Material de referência</h2>
<p>O arquivo <code>%(pdf)s</code> é o projeto original, <b>somente leitura</b>, enviado só para você conferir as cotas vizinhas na pergunta 3. Ele não contém respostas esperadas. Não o edite nem anote nele; as respostas vão apenas na folha/CSV.</p>
<h2>Regras</h2>
<ul>
<li><b>"Não sei" é uma resposta válida e útil.</b> Prefira "Não sei" a adivinhar. Deixar em branco significa que você não olhou o item.</li>
<li>Faça sozinho(a). Não consulte outras pessoas nem outros arquivos além do PDF de referência; o objetivo é uma leitura independente.</li>
<li>Escreva livremente no campo "Observação" qualquer dúvida (ex.: "imagem cortada", "não consegui ver os riscos").</li>
<li>Não altere os códigos dos itens (ex.: p6-t3).</li>
<li>Informe <b>seu nome completo</b> no campo "Revisor". Ele é registrado junto às respostas.</li>
</ul>
<h2>Como devolver</h2>
<ol>
<li>Preencha os cartões nesta página e clique em <b>Exportar respostas (CSV)</b>. A página <b>não salva sozinha</b>: exporte com frequência.</li>
<li>Envie <b>somente o arquivo CSV exportado</b>, sem alterações. (Alternativa: preencher a planilha CSV entregue junto, usando apenas os valores abaixo.)</li>
</ol>
<p><b>Valores aceitos no CSV</b> — q1_papel: <code>cota_regular</code>, <code>cota_deslocada</code>, <code>nota</code>, <code>nao_medida</code>, <code>nao_sei</code> · q2_intervalo_correto e q3_valor_correto: <code>sim</code>, <code>nao</code>, <code>nao_sei</code>.
Deixe a coluna <code>grupos</code> vazia. Preencha a coluna <code>revisor</code> em todas as linhas respondidas com o mesmo nome.</p>
"""


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _ordem(i: str) -> tuple[int, int]:
    m = re.fullmatch(r"p(\d+)-t(\d+)", i); return (int(m[1]), int(m[2]))


def _cartoes(orig: str) -> dict[str, dict]:
    out = {}
    for m in re.finditer(r'<section class="card" data-id="([^"]+)" data-pagina="(\d+)" data-texto="([^"]*)"[^>]*>(.*?)</section>', orig, re.S):
        i, pag, txt, corpo = m.groups()
        h3 = re.search(r"<h3>#\d+ · (.*?) <small>\(p\.(\d+), (\w+)\)", corpo, re.S)
        figs = re.findall(r'<figure><img src="(data:image/[a-z]+;base64,[A-Za-z0-9+/=]+)" alt="([^"]*)">', corpo)
        mapa = re.search(r'<figure class="map">.*?</figure>', corpo, re.S)
        q = re.search(r'<div class="q">.*?</div>(?=\s*<details>)', corpo, re.S)
        if not (h3 and len(figs) == 2 and mapa and q): raise ValueError(f"cartão {i} fora do formato esperado")
        out[i] = {"pagina": pag, "texto": txt, "orient": h3.group(3), "figs": figs, "mapa": mapa.group(0), "q": q.group(0)}
    return out


def _css(orig: str) -> str:
    th = re.findall(r"\.th\d+\{[^}]*\}", orig)                      # miniaturas (fundo das páginas)
    base = re.search(r"</style>", orig); css = re.search(r"<style>(.*?)</style>", orig, re.S).group(1)
    css = re.sub(r"\.th\d+\{[^}]*\}", "", css); css = re.sub(r"\.t-[a-z_]+\{[^}]*\}", "", css)    # sem cores de grupos
    return "".join(th) + css


def construir_html(orig_path=ORIGINAL, itens_path=ITENS) -> tuple[str, list[str]]:
    orig = Path(orig_path).read_text(encoding="utf-8"); cards = _cartoes(orig)
    ids = sorted(json.loads(Path(itens_path).read_text())["itens"] and [i["id"] for i in json.loads(Path(itens_path).read_text())["itens"]], key=_ordem)
    if set(ids) != set(cards): raise ValueError(f"ids da folha original diferem da lista de itens: {set(ids) ^ set(cards)}")
    partes = []
    for n, i in enumerate(ids, 1):
        c = cards[i]; f1, f2 = c["figs"]
        partes.append(
            f'<section class="card" data-id="{i}" data-pagina="{c["pagina"]}" data-texto="{html.escape(c["texto"], quote=True)}">\n'
            f'<h3>#{n} · {c["texto"]} <small>(p.{c["pagina"]}, {c["orient"]}) · {i}</small></h3>\n'
            f'<div class="imgs"><figure><img src="{f1[0]}" alt="recorte limpo"><figcaption>Recorte limpo</figcaption></figure>\n'
            f'<figure><img src="{f2[0]}" alt="recorte com trecho candidato"><figcaption>Com o trecho candidato (caixa magenta = número; linha azul = trecho a verificar)</figcaption></figure>\n'
            f'{c["mapa"]}</div>\n{c["q"]}</section>')
    js = re.search(r"<script>.*?</script>", orig, re.S).group(0).replace("grupos:c.dataset.grupos", "grupos:''")
    barra = ('<div class="bar"><label>Revisor (nome completo): <input id="revisor" placeholder="seu nome"></label><button onclick="exportCSV()">Exportar respostas (CSV)</button>'
             '<span id="prog"></span><small>Exporte com frequência: a página não salva sozinha.</small></div>')
    doc = (f'<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Folha de conferência de cotas · {VERSAO}</title><meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<style>{_css(orig)}</style>\n{INSTRUCOES % {"versao": VERSAO, "pdf": PDF_NOME}}{barra}\n' + "\n".join(partes) + f"\n{js}</html>")
    doc = doc.replace("function exportJSON(){dl('revisao.json',JSON.stringify(rows(),null,1),'application/json')}", "")
    return doc, ids


def construir_csv(ids, itens_path=ITENS, orig_path=ORIGINAL) -> str:
    cards = _cartoes(Path(orig_path).read_text(encoding="utf-8"))
    import io; b = io.StringIO(newline=""); w = csv.writer(b, lineterminator="\n"); w.writerow(CSV_COLS)
    for i in ids: w.writerow([i, cards[i]["pagina"], cards[i]["texto"]] + [""] * (len(CSV_COLS) - 3))
    return "﻿" + b.getvalue()


def vazamentos(texto: str) -> list[str]:
    sem_img = re.sub(r"data:image/[a-z]+;base64,[A-Za-z0-9+/=]+", "", texto).lower()
    return [t for t in PROIBIDOS if t in sem_img]


def sem_linha_azul(orig_path=ORIGINAL) -> tuple[list[str], dict]:
    """Cartões cujo recorte 'com trecho candidato' não tem nenhum pixel azul (algoritmo não mediu intervalo). Retorna ids e a separação observada."""
    import base64, io
    from PIL import Image
    h = Path(orig_path).read_text(encoding="utf-8"); n_por = {}
    for i, b in re.findall(r'<section class="card" data-id="([^"]+)".*?alt="recorte limpo".*?<img src="data:image/jpeg;base64,([A-Za-z0-9+/=]+)" alt="recorte com medição"', h, re.S):
        im = Image.open(io.BytesIO(base64.b64decode(b))).convert("RGB"); r, g, bl = im.split()
        n_por[i] = sum(1 for x, y, z in zip(r.tobytes(), g.tobytes(), bl.tobytes()) if z > 200 and x < 60 and y < 120)
    sem = sorted((i for i, n in n_por.items() if n < 30), key=_ordem); com = [n for i, n in n_por.items() if n >= 30]
    return sem, {"cartoes_analisados": len(n_por), "limiar_pixels_azuis": 30, "max_pixels_nos_sem_linha": max((n_por[i] for i in sem), default=0), "min_pixels_nos_com_linha": min(com, default=0)}


def inspecionar_pdf(path) -> list[str]:
    """Problemas que impediriam entregar o PDF como referência neutra (anotações, anexos, metadados/texto com termos do gabarito)."""
    import pymupdf
    d = pymupdf.open(path); erros = []
    if d.embfile_count(): erros.append("PDF com arquivos embutidos")
    if any(list(pg.annots() or []) for pg in d): erros.append("PDF com anotações")
    meta = " ".join(str(v) for v in d.metadata.values()).lower(); txt = " ".join(pg.get_text() for pg in d).lower()
    benignos = ("evidência", "mm/pt", "pontos de partida")
    erros += [f"termo '{t}' no PDF" for t in PROIBIDOS if t not in benignos and (t in meta or t in txt)]
    return erros


def gerar(root: Path = ROOT, orig_path=ORIGINAL, itens_path=ITENS, pdf_path=PDF_ORIGEM, exclusoes_path=EXCLUSOES) -> dict:
    destino = root / VERSAO
    if destino.exists(): raise FileExistsError(f"{destino} já existe; pacotes são imutáveis (crie o próximo)")
    if Path(exclusoes_path).exists(): raise FileExistsError(f"{exclusoes_path} já existe; o registro de exclusões é imutável")
    if sha(pdf_path) != PDF_SHA256: raise ValueError("PDF de origem não confere com o hash do projeto avaliado")
    pdf_problemas = inspecionar_pdf(pdf_path)
    if pdf_problemas: raise ValueError(f"PDF não pode ser entregue como referência neutra: {pdf_problemas}")
    ant = root / ANTERIOR; man_ant = ant / "MANIFESTO_PACOTE.json"; hashes_ant = {}
    if man_ant.exists():
        hashes_ant = {str(p.relative_to(ant)): sha(p) for p in sorted(ant.rglob("*")) if p.is_file()}
    pre = {str(p): sha(p) for p in (orig_path, itens_path)}
    doc, ids = construir_html(orig_path, itens_path); csv_txt = construir_csv(ids, itens_path, orig_path)
    for nome, t in ((HTML_NOME, doc), (CSV_NOME, csv_txt)):
        v = vazamentos(t)
        if v: raise ValueError(f"{nome} vaza termos do gabarito: {v}")
    sem, sep = sem_linha_azul(orig_path)
    if sep["max_pixels_nos_sem_linha"] >= sep["min_pixels_nos_com_linha"]: raise ValueError(f"detecção de linha azul ambígua: {sep}")
    exc = {"regra": "Nos itens abaixo NÃO há linha azul (o algoritmo não mediu intervalo); a pergunta 2 não se aplica. A resposta à pergunta 2 desses itens NÃO entra na comparação com o gabarito, "
                    "na concordância por revisor/grupo, no grupo de controle, na concordância entre revisores nem na lista de divergências. As perguntas 1 e 3 continuam valendo.",
           "pacote": VERSAO, "aprovado_por": "responsável pelo projeto (aprovação registrada na conversa de 2026-11-14)", "gabarito_v0_alterado": False,
           "ids": sem, "n": len(sem), "metodo_de_deteccao": sep, "itens_selecionados_sha256": sha(itens_path)}
    Path(exclusoes_path).write_text(json.dumps(exc, ensure_ascii=False, indent=1), encoding="utf-8")
    ent = destino / "entrega"; ent.mkdir(parents=True)
    (ent / HTML_NOME).write_text(doc, encoding="utf-8"); (ent / CSV_NOME).write_text(csv_txt, encoding="utf-8"); shutil.copyfile(pdf_path, ent / PDF_NOME)
    entregues = (HTML_NOME, CSV_NOME, PDF_NOME)
    man = {"pacote": VERSAO, "substitui": ANTERIOR, "gerado_em": date.today().isoformat(),
           "arquivos_entregues": {n: {"sha256": sha(ent / n), "bytes": (ent / n).stat().st_size} for n in entregues},
           "papel_dos_arquivos": {HTML_NOME: "instrumento de resposta", CSV_NOME: "instrumento de resposta", PDF_NOME: "material de referência somente leitura (cópia byte a byte do PDF avaliado; sem anotações, anexos ou termos do gabarito)"},
           "ids": ids, "n_itens": len(ids), "ordem": "por página e índice do token",
           "exclusoes_q2": {"arquivo_interno": "evaluation/review/exclusoes_q2.json", "sha256": sha(exclusoes_path), "ids": sem, "n": len(sem)},
           "origem": {"folha_original_sha256": pre[str(orig_path)], "itens_selecionados_sha256": sha(itens_path), "pdf_sha256": PDF_SHA256},
           "alteracoes_vs_pkg_1_0": ["erro de digitação corrigido nas instruções (\"os riscos\")",
                                     "instrução: cartões sem linha azul -> pergunta 2 = \"Não sei\" + observação \"sem linha azul\"",
                                     f"{len(sem)} itens sem linha azul excluídos da comparação/métrica da pergunta 2 (registro interno exclusoes_q2.json); gabarito v0 NÃO alterado",
                                     "PDF original incluído como material de referência somente leitura (nome neutro)",
                                     "instrução sobre o PDF de referência e ajuste da regra de consulta"],
           "preservado_do_pkg_1_0": {"manifesto_sha256_inalterado": bool(hashes_ant) and sha(man_ant) == hashes_ant["MANIFESTO_PACOTE.json"], "arquivos_e_hashes": hashes_ant},
           "removido_da_folha_original": ["rótulo do gabarito", "estado/resultado do algoritmo", "nomes e legenda de grupos (inclui o grupo de controle)", "hash do algoritmo e do PDF",
                                          "nome do arquivo/cliente do PDF", "botão JSON", "coluna `grupos` (mantida vazia por compatibilidade com o registro)"]}
    (destino / "MANIFESTO_PACOTE.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in [ent / n for n in entregues] + [destino / "MANIFESTO_PACOTE.json", Path(exclusoes_path)]: p.chmod(0o444)
    assert {str(p): sha(p) for p in (orig_path, itens_path)} == pre
    if hashes_ant: assert {str(p.relative_to(ant)): sha(p) for p in sorted(ant.rglob("*")) if p.is_file()} == hashes_ant, "pkg-1.0 foi alterado"
    return man


def verificar(root: Path = ROOT, versao: str = VERSAO) -> list[str]:
    d = root / versao; man = json.loads((d / "MANIFESTO_PACOTE.json").read_text()); erros = []
    nomes = sorted(p.name for p in (d / "entrega").iterdir())
    if nomes != sorted(man["arquivos_entregues"]): erros.append(f"conteúdo de entrega/ inesperado: {nomes}")
    for n, m in man["arquivos_entregues"].items():
        p = d / "entrega" / n
        if not p.exists() or sha(p) != m["sha256"]: erros.append(f"hash divergente: {n}")
        elif n.endswith((".html", ".csv")) and vazamentos(p.read_text(encoding="utf-8")): erros.append(f"vazamento em {n}")
        elif n.endswith(".pdf") and inspecionar_pdf(p): erros.append(f"PDF não neutro: {inspecionar_pdf(p)}")
    return erros


if __name__ == "__main__":
    print(json.dumps(gerar(), ensure_ascii=False, indent=1))
