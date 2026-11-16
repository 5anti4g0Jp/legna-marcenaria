"""Arquivo auxiliar de coordenadas dos 46 cartões do pkg-1.1 (para avaliação complementar sem o HTML).

Só localiza o número no PDF: id, página, texto, caixa (pt), rotação, contexto de linha do próprio PDF. NÃO contém gabarito, baseline, estado do algoritmo,
intervalo medido nem qualquer rótulo. As coordenadas são recalculadas do PDF pelo mesmo extrator de tokens que gerou os IDs (`census`).
Não altera o CSV do pacote nem nenhum arquivo existente: grava em `pkg-1.1/auxiliar/`.
"""
from __future__ import annotations
import csv, io, json
from datetime import date
from pathlib import Path

import pymupdf

from . import review_package as P
from .census import census

AUX = P.ROOT / "pkg-1.1" / "auxiliar"
CSV_AUX = "legna_revisao_pkg-1.1_coordenadas.csv"
COLS = ["id", "pagina", "texto", "x0", "y0", "x1", "y1", "centro_x", "centro_y", "rotacao_graus", "pagina_largura_pt", "pagina_altura_pt", "pos_x_pct", "pos_y_pct", "texto_da_linha"]
SISTEMA = ("Unidade: pontos PDF (1 pt = 1/72 in). Origem no canto SUPERIOR ESQUERDO da página; x cresce para a direita, y para baixo (convenção PyMuPDF, página não rotacionada). "
           "Caixa = (x0,y0)-(x1,y1) do texto do número. rotacao_graus: 0 = horizontal; 90 = lido de baixo para cima. pos_*_pct = centro / tamanho da página.")


def construir(pdf_path=P.PDF_ORIGEM, csv_entregue: Path | None = None) -> tuple[str, list[dict]]:
    csv_entregue = csv_entregue or (P.ROOT / "pkg-1.1" / "entrega" / P.CSV_NOME)
    ids = list(csv.DictReader(open(csv_entregue, encoding="utf-8-sig")))
    doc = pymupdf.open(pdf_path); toks = {t.id: t for t in census(pdf_path)}; linhas = []
    for r in ids:
        t = toks[r["id"]]
        if t.text != r["texto"] or str(t.page) != r["pagina"]: raise ValueError(f"{r['id']}: texto/página do PDF diferem do CSV ({t.text}/{t.page} vs {r['texto']}/{r['pagina']})")
        pg = doc[t.page - 1]; x0, y0, x1, y1 = t.bbox
        if pg.rotation != 0: raise ValueError(f"página {t.page} rotacionada: coordenadas exigiriam conversão")
        achados = [w[4] for w in pg.get_text("words", clip=pymupdf.Rect(x0 - 0.5, y0 - 0.5, x1 + 0.5, y1 + 0.5))]
        if t.text not in achados: raise ValueError(f"{r['id']}: o texto '{t.text}' não está na caixa {t.bbox} da página {t.page} (achado: {achados})")
        W, H = pg.rect.width, pg.rect.height; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        linhas.append({"id": r["id"], "pagina": t.page, "texto": t.text, "x0": round(x0, 2), "y0": round(y0, 2), "x1": round(x1, 2), "y1": round(y1, 2), "centro_x": round(cx, 2), "centro_y": round(cy, 2),
                       "rotacao_graus": t.angle, "pagina_largura_pt": round(W, 2), "pagina_altura_pt": round(H, 2), "pos_x_pct": round(100 * cx / W, 1), "pos_y_pct": round(100 * cy / H, 1),
                       "texto_da_linha": t.line_text[:80]})
    b = io.StringIO(newline=""); w = csv.DictWriter(b, fieldnames=COLS, lineterminator="\n"); w.writeheader(); w.writerows(linhas)
    return "﻿" + b.getvalue(), linhas


def gerar(destino: Path = AUX, pdf_path=P.PDF_ORIGEM) -> dict:
    if destino.exists(): raise FileExistsError(f"{destino} já existe; arquivos auxiliares são imutáveis")
    if P.sha(pdf_path) != P.PDF_SHA256: raise ValueError("PDF não confere com o hash do projeto avaliado")
    pre = {n: P.sha(P.ROOT / "pkg-1.1" / "entrega" / n) for n in (P.CSV_NOME, P.PDF_NOME, P.HTML_NOME)}
    txt, linhas = construir(pdf_path)
    if P.vazamentos(txt): raise ValueError(f"termos do gabarito no arquivo auxiliar: {P.vazamentos(txt)}")
    destino.mkdir(parents=True); f = destino / CSV_AUX; f.write_text(txt, encoding="utf-8")
    man = {"arquivo": CSV_AUX, "sha256": P.sha(f), "bytes": f.stat().st_size, "gerado_em": date.today().isoformat(), "n_itens": len(linhas), "pacote": "pkg-1.1",
           "sistema_de_coordenadas": SISTEMA, "colunas": COLS, "fonte": "recalculado do PDF original pelo extrator de tokens da Etapa 0 (census); conferido contra o texto do PDF na caixa e contra o CSV do pacote (id, página, texto)",
           "nao_contem": ["gabarito v0", "baseline", "estado/resultado do algoritmo", "intervalo medido", "rótulos ou respostas esperadas"],
           "entradas": {"pdf_sha256": P.PDF_SHA256, "csv_pacote_sha256": pre[P.CSV_NOME]},
           "arquivos_do_pacote_inalterados": pre}
    m = destino / "MANIFESTO_COORDENADAS.json"; m.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    f.chmod(0o444); m.chmod(0o444)
    assert {n: P.sha(P.ROOT / "pkg-1.1" / "entrega" / n) for n in pre} == pre
    return man


def verificar(destino: Path = AUX) -> list[str]:
    man = json.loads((destino / "MANIFESTO_COORDENADAS.json").read_text()); erros = []
    f = destino / CSV_AUX
    if P.sha(f) != man["sha256"]: erros.append("hash do arquivo de coordenadas diverge do manifesto")
    if sorted(p.name for p in destino.iterdir()) != sorted([CSV_AUX, "MANIFESTO_COORDENADAS.json"]): erros.append("conteúdo inesperado em auxiliar/")
    for n, h in man["arquivos_do_pacote_inalterados"].items():
        if P.sha(P.ROOT / "pkg-1.1" / "entrega" / n) != h: erros.append(f"arquivo do pacote alterado: {n}")
    return erros


if __name__ == "__main__":
    print(json.dumps(gerar(), ensure_ascii=False, indent=1))
