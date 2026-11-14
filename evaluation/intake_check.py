"""Conferência de RECEBIMENTO de projetos reais (PDF, DXF, DWG, planilhas, CSV) — somente leitura.

Objetivo: antes de usar um arquivo como teste de compatibilidade, registrar o que ele realmente é (metadados, texto
vetorial x curvas, geometria, unidades, cotas detectáveis) e comparar com o que a ficha declara. A origem NUNCA é
considerada confirmada só pela declaração: o metadado do arquivo é uma EVIDÊNCIA, não uma prova (pode ser regravado).

Uso: python -m evaluation.intake_check ARQUIVO_OU_PASTA... [--ficha ficha.csv] [--saida relatorio.md]
O diagnóstico de cotas é PRELIMINAR e usa o algoritmo atual só para contar; não é afirmação de compatibilidade.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, re, sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
import pymupdf  # noqa: E402

FICHA_COLS = ["projeto_id", "arquivo", "papel_do_arquivo", "software", "versao_software", "gerado_por", "como_exportado", "unidade", "escala_plotagem",
              "estilo_cotas", "tipo_movel", "folhas", "material_padrao", "espessura_padrao_mm", "ferragens", "tem_lista_producao_real",
              "autorizado_uso", "anonimizado", "sha256", "observacoes"]
PAPEIS = {"pdf_executivo", "dxf", "dwg", "lista_pecas", "scan", "nativo", "outro"}
ORIGENS = [(r"autocad|autodesk|dwg to pdf|ac1\d{3}", "AutoCAD/Autodesk"), (r"promob", "Promob"), (r"layout in sketchup|sketchup", "SketchUp/LayOut"),
           (r"powerpoint", "Microsoft PowerPoint"), (r"microsoft.*print to pdf|print to pdf", "Microsoft Print to PDF (impressora virtual)"),
           (r"bluebeam", "Bluebeam"), (r"adobe|acrobat|distiller", "Adobe"), (r"libreoffice|openoffice", "LibreOffice"), (r"cairo", "cairo"),
           (r"pdfcreator|cutepdf|bullzip|dopdf", "impressora/PDF virtual de terceiros"), (r"pymupdf|mupdf", "PyMuPDF (gerado por programa)")]
COLUNAS_LISTA = {"comprimento": ("comprimento", "compr", "length", "c."), "largura": ("largura", "larg", "width", "l."), "espessura": ("espessura", "esp", "thickness"),
                 "quantidade": ("quantidade", "qtd", "qtde", "qty"), "material": ("material", "acabamento", "cor", "mdf")}


def sha256(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def dica_origem(*textos) -> dict:
    t = " ".join(x or "" for x in textos).lower()
    achados = [nome for rx, nome in ORIGENS if re.search(rx, t)]
    return {"software_inferido": achados[0] if achados else "desconhecido", "todos_os_indicios": achados,
            "confirmada": False, "ressalva": "metadado é evidência, não prova: pode ter sido regravado por outro programa; confirmar com quem gerou o arquivo"}


def _pdf(p: Path) -> dict:
    doc = pymupdf.open(p)
    if doc.needs_pass:
        return {"erro": "PDF protegido por senha"}
    md = doc.metadata or {}
    paginas = []
    for i, pg in enumerate(doc, 1):
        infos = pg.get_image_info(); area = pg.rect.width * pg.rect.height
        cov = min(1.0, sum((x["bbox"][2] - x["bbox"][0]) * (x["bbox"][3] - x["bbox"][1]) for x in infos) / area) if area else 0
        palavras = len(pg.get_text("words")); vet = len(pg.get_drawings()); fontes = pg.get_fonts()
        paginas.append({"pagina": i, "tamanho_pt": [round(pg.rect.width), round(pg.rect.height)], "palavras": palavras, "vetores": vet, "imagens": len(infos),
                        "cobertura_imagem": round(cov, 2), "fontes": sorted({f"{f[3].split('+')[-1]} ({f[2]})" for f in fontes}),
                        "texto_possivelmente_em_curvas": palavras < 5 and vet > 200 and cov < 0.25,
                        "possivelmente_escaneada": palavras < 5 and cov >= 0.25})
    out = {"tipo": "pdf", "metadados": {k: md.get(k) for k in ("creator", "producer", "title", "author", "creationDate", "format")}, "paginas": len(doc), "detalhe_paginas": paginas,
           "origem": dica_origem(md.get("creator"), md.get("producer"))}
    out["avisos"] = []
    if any(x["texto_possivelmente_em_curvas"] for x in paginas):
        out["avisos"].append("há página com muito vetor e quase nenhum texto: o texto pode ter sido convertido em curvas (sem camada de texto); exigirá OCR ou arquivo CAD")
    if any(x["possivelmente_escaneada"] for x in paginas):
        out["avisos"].append("há página dominada por imagem: provável digitalização; leitura dependerá de OCR (não confiável para cotas)")
    # diagnóstico PRELIMINAR de cotas (algoritmo atual, só para contar)
    try:
        import ingest.dimensions as D
        pds = [D.analyze_page(pg, i) for i, pg in enumerate(doc, 1)]
        from collections import Counter
        c = Counter(d.status for pd in pds for d in pd.dims)
        cores = Counter(str(pd.dim_color) for pd in pds if pd.dim_color)
        out["diagnostico_preliminar_cotas"] = {"aviso": "contagem do algoritmo atual; NÃO é afirmação de compatibilidade", "numeros_inteiros_candidatos": sum(c.values()),
                                               "estados": dict(c), "cor_das_cotas_por_pagina": dict(cores)}
        txt = " ".join(pg.get_text() for pg in doc)
        out["unidade_declarada_no_texto"] = bool(re.search(r"cotas?\s+em\s+mil[ií]metros|medidas?\s+em\s+(?:mm|mil[ií]metros)|\(\s*mm\s*\)", txt, re.I))
        out["numeros_com_decimal_ou_unidade"] = len(re.findall(r"\b\d+[.,]\d+\b|\b\d+\s?(?:mm|cm)\b", txt, re.I))
    except Exception as e:                                       # noqa: BLE001
        out["diagnostico_preliminar_cotas"] = {"erro": f"{type(e).__name__}: {e}"}
    return out


def _dxf(p: Path) -> dict:
    import ezdxf
    from collections import Counter
    doc = ezdxf.readfile(p); ents = Counter(e.dxftype() for e in doc.modelspace())
    layouts = [l.name for l in doc.layouts]
    return {"tipo": "dxf", "versao_dxf": doc.dxfversion, "unidade_insunits": doc.header.get("$INSUNITS", 0), "camadas": len(doc.layers), "layouts": layouts,
            "entidades_modelo": dict(ents), "cotas_dimension": ents.get("DIMENSION", 0), "textos": ents.get("TEXT", 0) + ents.get("MTEXT", 0),
            "origem": dica_origem(doc.header.get("$ACADVER"), str(doc.header.get("$LASTSAVEDBY", "")), str(doc.header.get("$USERI1", ""))),
            "avisos": ([] if doc.header.get("$INSUNITS", 0) else ["$INSUNITS=0: DXF sem unidade declarada"]) +
                      (["nenhuma entidade DIMENSION: cotas podem ser textos soltos (sem medida associada)"] if not ents.get("DIMENSION") else [])}


def _dwg(p: Path) -> dict:
    vers = {b"AC1015": "2000", b"AC1018": "2004", b"AC1021": "2007", b"AC1024": "2010", b"AC1027": "2013", b"AC1032": "2018"}
    head = p.read_bytes()[:6]
    return {"tipo": "dwg", "versao": vers.get(head, f"desconhecida ({head!r})"), "origem": dica_origem(head.decode("latin1")),
            "avisos": ["DWG NÃO pode ser lido neste ambiente (ODA File Converter indisponível): peça também o DXF do mesmo projeto"]}


def _planilha(p: Path) -> dict:
    out = {"tipo": p.suffix.lower().lstrip("."), "abas": []}
    if p.suffix.lower() == ".csv":
        txt = p.read_bytes().decode("utf-8-sig", errors="replace"); linhas = [l for l in txt.splitlines() if l.strip()]
        abas = [("(csv)", [re.split(r"[;,\t|]", l) for l in linhas[:50]], len(linhas))]
    else:
        from python_calamine import CalamineWorkbook
        wb = CalamineWorkbook.from_path(str(p)); abas = []
        for n in wb.sheet_names:
            rows = wb.get_sheet_by_name(n).to_python(); abas.append((n, [[str(c) for c in r] for r in rows[:50]], len(rows)))
    for nome, rows, total in abas:
        cab = [str(c).strip().lower() for c in (rows[0] if rows else [])]
        achadas = {k: [c for c in cab if any(s in c for s in v)] for k, v in COLUNAS_LISTA.items()}
        achou = sum(1 for v in achadas.values() if v)
        out["abas"].append({"aba": nome, "linhas": total, "cabecalho": cab[:12], "colunas_de_lista_de_pecas": {k: v for k, v in achadas.items() if v},
                            "parece_lista_de_pecas": achou >= 3})
    return out


def inspecionar(path) -> dict:
    p = Path(path)
    base = {"arquivo": p.name, "bytes": p.stat().st_size, "sha256": sha256(p), "extensao": p.suffix.lower()}
    try:
        ext = p.suffix.lower(); head = p.read_bytes()[:8]
        if ext == ".pdf":
            if not head.startswith(b"%PDF"): return {**base, "erro": "extensão .pdf mas o conteúdo não é PDF"}
            return {**base, **_pdf(p)}
        if ext == ".dxf": return {**base, **_dxf(p)}
        if ext == ".dwg": return {**base, **_dwg(p)}
        if ext in (".xlsx", ".xlsm", ".xls", ".csv"): return {**base, **_planilha(p)}
        return {**base, "erro": f"formato '{ext}' não tratado pelo recebimento (aceitos: pdf, dxf, dwg, xlsx, xls, csv)"}
    except Exception as e:                                       # noqa: BLE001  (um arquivo ruim não derruba o lote)
        return {**base, "erro": f"{type(e).__name__}: {str(e)[:160]}"}


def conferir_ficha(ficha_csv, pasta, inspecoes: dict | None = None) -> dict:
    rows = list(csv.DictReader(open(ficha_csv, encoding="utf-8-sig"))); pasta = Path(pasta); probs = []; vistos = set()
    faltam = [c for c in ("projeto_id", "arquivo", "papel_do_arquivo", "software") if rows and c not in rows[0]]
    if faltam: probs.append({"linha": 0, "problema": f"colunas obrigatórias ausentes: {faltam}"})
    for i, r in enumerate(rows, 2):
        arq = (r.get("arquivo") or "").strip(); vistos.add(arq)
        if (r.get("papel_do_arquivo") or "") not in PAPEIS: probs.append({"linha": i, "arquivo": arq, "problema": f"papel_do_arquivo inválido ('{r.get('papel_do_arquivo')}'); use {sorted(PAPEIS)}"})
        for c in ("software", "unidade"):
            if not (r.get(c) or "").strip(): probs.append({"linha": i, "arquivo": arq, "problema": f"campo '{c}' vazio (não será presumido)"})
        if (r.get("autorizado_uso") or "").strip().lower() != "sim": probs.append({"linha": i, "arquivo": arq, "problema": "uso NÃO autorizado/indefinido: não usar até confirmar"})
        f = pasta / arq
        if not f.is_file(): probs.append({"linha": i, "arquivo": arq, "problema": "arquivo da ficha não encontrado na pasta"}); continue
        insp = (inspecoes or {}).get(arq) or inspecionar(f)
        if (r.get("sha256") or "").strip() and r["sha256"].strip().lower() != insp["sha256"]: probs.append({"linha": i, "arquivo": arq, "problema": "SHA-256 da ficha difere do arquivo recebido"})
        decl = (r.get("software") or "").lower(); inf = (insp.get("origem") or {}).get("software_inferido", "desconhecido")
        if inf != "desconhecido" and decl and not any(w in inf.lower() or inf.lower() in decl for w in re.split(r"[\s/]+", decl) if len(w) > 2):
            probs.append({"linha": i, "arquivo": arq, "problema": f"software declarado '{r.get('software')}' difere do indício no metadado ('{inf}'): arquivo pode não ser exportação nativa"})
        if inf == "desconhecido" and insp.get("tipo") in ("pdf", "dxf"): probs.append({"linha": i, "arquivo": arq, "problema": "metadado sem indício de software: origem só pela declaração"})
    extras = sorted(p.name for p in pasta.iterdir() if p.is_file() and p.suffix.lower() in (".pdf", ".dxf", ".dwg", ".xlsx", ".xls", ".csv") and p.name not in vistos)
    return {"linhas": len(rows), "problemas": probs, "arquivos_sem_ficha": extras}


def coletar(entradas) -> list[Path]:
    out = []
    for e in map(Path, entradas):
        out += sorted(x for x in e.iterdir() if x.is_file() and x.suffix.lower() in (".pdf", ".dxf", ".dwg", ".xlsx", ".xlsm", ".xls", ".csv")) if e.is_dir() else [e]
    return out


def render(insp: list[dict], ficha: dict | None = None) -> str:
    L = ["# Relatório de recebimento de projetos", "", "Diagnóstico **preliminar**: não afirma compatibilidade com nenhum software.", ""]
    for r in insp:
        L += [f"## {r['arquivo']}", f"- {r['bytes']:,} bytes · sha256 `{r['sha256'][:16]}…`"]
        if "erro" in r: L += [f"- **ERRO:** {r['erro']}", ""]; continue
        o = r.get("origem")
        if o: L.append(f"- Origem inferida pelo metadado: **{o['software_inferido']}** (não confirmada). {o['ressalva']}")
        if r["tipo"] == "pdf":
            L += [f"- Metadados: {r['metadados']}", f"- {r['paginas']} páginas; fontes: {sorted({f for p in r['detalhe_paginas'] for f in p['fontes']})[:4]}"]
            d = r.get("diagnostico_preliminar_cotas", {})
            if "estados" in d: L += [f"- Cotas (preliminar): {d['numeros_inteiros_candidatos']} números inteiros candidatos; estados {d['estados']}; cor das cotas {d['cor_das_cotas_por_pagina']}",
                                    f"- Unidade declarada no texto: {r.get('unidade_declarada_no_texto')} · números com decimal/unidade: {r.get('numeros_com_decimal_ou_unidade')}"]
        elif r["tipo"] == "dxf": L += [f"- DXF {r['versao_dxf']}; unidade $INSUNITS={r['unidade_insunits']}; {r['camadas']} camadas; layouts {r['layouts']}; DIMENSION: {r['cotas_dimension']}; textos: {r['textos']}"]
        elif r["tipo"] == "dwg": L += [f"- DWG versão {r['versao']}"]
        else:
            for a in r["abas"]: L.append(f"- Aba `{a['aba']}`: {a['linhas']} linhas; cabeçalho {a['cabecalho']}; **lista de peças? {a['parece_lista_de_pecas']}** {a['colunas_de_lista_de_pecas']}")
        for a in r.get("avisos", []): L.append(f"- ⚠ {a}")
        L.append("")
    if ficha is not None:
        L += ["## Conferência da ficha", f"- {ficha['linhas']} linhas; **{len(ficha['problemas'])} problemas**; arquivos sem ficha: {ficha['arquivos_sem_ficha']}"]
        L += [f"  - linha {p['linha']} `{p.get('arquivo', '')}`: {p['problema']}" for p in ficha["problemas"]]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("entradas", nargs="+"); ap.add_argument("--ficha"); ap.add_argument("--saida")
    a = ap.parse_args(argv); arquivos = coletar(a.entradas); insp = [inspecionar(f) for f in arquivos]
    ficha = conferir_ficha(a.ficha, arquivos[0].parent, {i["arquivo"]: i for i in insp}) if a.ficha else None
    txt = render(insp, ficha)
    if a.saida: Path(a.saida).write_text(txt, encoding="utf-8"); Path(a.saida).with_suffix(".json").write_text(json.dumps({"arquivos": insp, "ficha": ficha}, ensure_ascii=False, indent=1, default=str))
    else: print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
