"""Pacote de revisão independente (cego): gera SOMENTE a folha HTML e o CSV de respostas.

A folha original (`evaluation/review/folha_conferencia_baseline_etapa0.html`) NÃO é cega: traz rótulo do gabarito, resultado do algoritmo,
nomes de grupos (falsa_confirmacao, conflito, controle...) e hashes. Este módulo NÃO a altera: reconstrói cada cartão apenas com o que o revisor precisa
(imagens, mapa da página, 3 perguntas) e grava em pasta nova. Nada do gabarito/baseline/algoritmo é modificado.
"""
from __future__ import annotations
import csv, hashlib, html, json, os, re, sys
from datetime import date
from pathlib import Path

from .paths import EV
from .review_sheet import CSV_COLS

VERSAO = "pkg-1.0"
ROOT = EV / "review_package"
HTML_NOME = f"legna_revisao_{VERSAO}_folha.html"
CSV_NOME = f"legna_revisao_{VERSAO}_respostas.csv"
ORIGINAL = EV / "review" / "folha_conferencia_baseline_etapa0.html"
ITENS = EV / "review" / "itens_selecionados.json"

# termos que NUNCA podem aparecer nos arquivos entregues (verificado em teste e em `verificar`)
PROIBIDOS = ["gabarito", "baseline", "algoritmo", "conflito", "falsa_confirmacao", "falsa confirm", "controle", "assumido", "indeterminad", "confirmad",
             "696a8b83", "bb6385f7", "fernanda", "sertorio", "sertório", "etapa 0", "etapa0", "evidência", "mm/pt", "pontos de partida"]

INSTRUCOES = """
<h1>Folha de conferência de cotas — revisão independente</h1>
<p class="meta">Pacote <b>%(versao)s</b> · projeto executivo de marcenaria (PDF de 34 páginas) · 46 itens</p>
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
<li><b>A linha azul cobre exatamente o trecho que esta cota mede?</b> Ou seja, entre as duas marcas que a cota delimita. "Sim" só se as pontas da linha azul coincidirem com as marcas da cota; caso contrário, "Não".</li>
<li><b>O valor escrito está correto?</b> Confira pelo contexto e pela soma das cotas vizinhas. Se discordar, escreva o valor que você leria no campo "Valor que você leria".</li>
</ol>
<h2>Regras</h2>
<ul>
<li><b>"Não sei" é uma resposta válida e útil.</b> Prefira "Não sei" a adivinhar. Deixar em branco significa que você não olhou o item.</li>
<li>Faça sozinho(a). Não consulte outras pessoas nem outros arquivos do projeto de avaliação; o objetivo é uma leitura independente.</li>
<li>Escreva livremente no campo "Observação" qualquer dúvida (ex.: "imagem cortada", "não consegui ver o riscos").</li>
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
           f'<style>{_css(orig)}</style>\n{INSTRUCOES % {"versao": VERSAO}}{barra}\n' + "\n".join(partes) + f"\n{js}</html>")
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


def gerar(root: Path = ROOT, orig_path=ORIGINAL, itens_path=ITENS) -> dict:
    destino = root / VERSAO
    if destino.exists(): raise FileExistsError(f"{destino} já existe; pacotes são imutáveis (crie pkg-1.1)")
    pre = {str(p): sha(p) for p in (orig_path, itens_path)}
    doc, ids = construir_html(orig_path, itens_path); csv_txt = construir_csv(ids, itens_path, orig_path)
    for nome, t in ((HTML_NOME, doc), (CSV_NOME, csv_txt)):
        v = vazamentos(t)
        if v: raise ValueError(f"{nome} vaza termos do gabarito: {v}")
    ent = destino / "entrega"; ent.mkdir(parents=True)
    (ent / HTML_NOME).write_text(doc, encoding="utf-8"); (ent / CSV_NOME).write_text(csv_txt, encoding="utf-8")
    man = {"pacote": VERSAO, "gerado_em": date.today().isoformat(), "arquivos_entregues": {n: {"sha256": sha(ent / n), "bytes": (ent / n).stat().st_size} for n in (HTML_NOME, CSV_NOME)},
           "ids": ids, "n_itens": len(ids), "ordem": "por página e índice do token (a ordem da folha original agrupava por categoria e foi descartada)",
           "origem": {"folha_original_sha256": pre[str(orig_path)], "itens_selecionados_sha256": sha(itens_path)},
           "removido_da_folha_original": ["rótulo do gabarito", "estado/resultado do algoritmo", "nomes e legenda de grupos (inclui o grupo de controle)", "hash do algoritmo e do PDF",
                                          "nome do arquivo/cliente do PDF", "botão JSON", "coluna `grupos` (mantida vazia por compatibilidade com o registro)"],
           "nao_incluido": "o PDF original do projeto (decisão pendente do responsável)"}
    (destino / "MANIFESTO_PACOTE.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in (ent / HTML_NOME, ent / CSV_NOME, destino / "MANIFESTO_PACOTE.json"): p.chmod(0o444)
    assert {str(p): sha(p) for p in (orig_path, itens_path)} == pre
    return man


def verificar(root: Path = ROOT) -> list[str]:
    d = root / VERSAO; man = json.loads((d / "MANIFESTO_PACOTE.json").read_text()); erros = []
    nomes = sorted(p.name for p in (d / "entrega").iterdir())
    if nomes != sorted([HTML_NOME, CSV_NOME]): erros.append(f"conteúdo de entrega/ inesperado: {nomes}")
    for n, m in man["arquivos_entregues"].items():
        p = d / "entrega" / n
        if not p.exists() or sha(p) != m["sha256"]: erros.append(f"hash divergente: {n}")
        elif vazamentos(p.read_text(encoding="utf-8")): erros.append(f"vazamento em {n}")
    return erros


if __name__ == "__main__":
    print(json.dumps(gerar(), ensure_ascii=False, indent=1))
