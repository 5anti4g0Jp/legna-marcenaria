"""Pipeline da Etapa 1: transforma a saída do algoritmo de cotas (ingest/dimensions.py, INALTERADO) no modelo rastreável.

O algoritmo decide só a análise geométrica. Este módulo NÃO a otimiza: apenas traduz, registra evidências e aplica a
máquina de estados. Nenhuma medida sai `aprovado`: a aprovação é exclusivamente humana (ver revisao.py).
"""
from __future__ import annotations

import hashlib, math, re, warnings
from pathlib import Path
from types import ModuleType
from typing import Callable

warnings.filterwarnings("ignore", category=FutureWarning)
import pymupdf  # noqa: E402

from .model import (Algoritmo, AnaliseAutomatica, Ator, AtorTipo, Documento, Estado, Evidencia, Medida, Resultado, Transicao, agora, resumir)

NOME_ALGORITMO = "ingest.dimensions (algoritmo da Etapa 0, inalterado)"
UNIDADE_DECLARADA = re.compile(r"cotas?\s+em\s+mil[ií]metros|medidas?\s+em\s+(?:mm|mil[ií]metros)|\(\s*mm\s*\)", re.I)
SISTEMA = Ator(tipo=AtorTipo.SISTEMA, id="algoritmo-cotas-etapa0")


def sha256_arquivo(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _angulos(page) -> list[tuple[pymupdf.Rect, float]]:
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for sp in ln["spans"]:
                out.append((pymupdf.Rect(sp["bbox"]), math.degrees(math.atan2(-ln["dir"][1], ln["dir"][0])) % 360))
    return out


def _orientacao(ang: float | None) -> str:
    if ang is None:
        return "desconhecida"
    for alvo, nome in ((0, "horizontal"), (180, "horizontal"), (360, "horizontal"), (90, "vertical"), (270, "vertical")):
        if abs(ang - alvo) <= 2.0:
            return nome
    return "inclinada"


def _analise(d, geom: ModuleType) -> tuple[Estado, list[Evidencia], list[dict]]:
    """Traduz o resultado do algoritmo para (estado, evidências, conflitos). Nunca produz `aprovado`."""
    metodo = f"{NOME_ALGORITMO}; TOL={geom.TOL}; MIN_CLUSTER={geom.MIN_CLUSTER}"
    x0, y0, x1, y1 = d.bbox; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    linha = None
    if d.interval_pt:
        a, b = d.interval_pt
        linha = (a, cy, b, cy) if d.orient == "h" else (cx, a, cx, b)
    base = {"estado_algoritmo": d.status, "eixo_assumido_pelo_algoritmo": d.orient, "intervalo_pt": list(d.interval_pt) if d.interval_pt else None,
            "comprimento_pt": d.length_pt, "escala_mm_por_pt": d.scale, "valor_escrito": d.value,
            "posicao_da_linha": "aproximada: ao longo do eixo medido, na altura/largura do texto (o algoritmo não expõe a linha exata)"}
    if d.status in ("confirmado", "confirmado_local"):
        local = d.status == "confirmado_local"
        geo = d.length_pt * d.scale if (d.length_pt and d.scale) else None
        dados = {**base, "tipo_confirmacao": "escala_local" if local else "escala_da_pagina", "valor_geometrico_mm": geo,
                 "desvio_mm": (geo - d.value) if geo is not None else None, "desvio_relativo": ((geo - d.value) / d.value) if geo is not None else None,
                 "tolerancia_relativa": geom.TOL, "verificacao_independente": not local,
                 "ressalva": "consistência geométrica NÃO é aprovação; a geometria só não contradiz o valor escrito"}
        if local:
            dados["ressalva_local"] = "escala derivada do próprio par (valor/comprimento): só vale porque outra cota próxima concorda; o desvio é nulo por construção"
        return Estado.GEOMETRICAMENTE_CONSISTENTE, [Evidencia(tipo="geometria", descricao="valor escrito compatível com a medida no desenho", metodo=metodo, dados=dados, coords=linha)], []
    if d.status == "conflito":
        geo = d.measured_mm; desvio = (geo - d.value) if geo is not None else None
        dados = {**base, "valor_geometrico_mm": geo, "sugestao_mm": d.suggestion_mm, "desvio_mm": desvio,
                 "desvio_relativo": (desvio / d.value) if desvio is not None else None, "tolerancia_relativa": geom.TOL,
                 "ressalva": "a cota escrita prevalece sobre o desenho; a sugestão NÃO é aplicada e o conflito pode ser falso alarme (associação do intervalo errada)"}
        conf = {"tipo": "valor_escrito_vs_geometria", "valor_escrito": d.value, "valor_geometrico_mm": geo, "sugestao_mm": d.suggestion_mm, "desvio_relativo": dados["desvio_relativo"]}
        return Estado.CONFLITO, [Evidencia(tipo="conflito_geometrico", descricao="valor escrito diverge da medida no desenho", metodo=metodo, dados=dados, coords=linha)], [conf]
    motivo = ("a página não tem cotas suficientes para estabelecer escala (mínimo de cotas coerentes não atingido)" if d.status == "sem_escala"
              else "o algoritmo não associou este número a uma linha de cota com marcas válidas nos dois lados")
    return Estado.SEM_MEDICAO, [Evidencia(tipo="sem_medicao", descricao=motivo, metodo=metodo, dados={"estado_algoritmo": d.status, "eixo_assumido_pelo_algoritmo": d.orient})], []


def analisar_pdf(path, *, geometria: ModuleType | None = None, enfileirar: bool = False, relogio: Callable[[], str] | None = None) -> Resultado:
    """Analisa um PDF. `geometria` = módulo com a API de ingest.dimensions (padrão: o atual). `enfileirar=True` leva todas as
    medidas a `pendente_revisao` (ainda sem aprovar nenhuma)."""
    if geometria is None:
        import ingest.dimensions as geometria  # noqa: PLC0415
    p = Path(path); sha = sha256_arquivo(p); doc = pymupdf.open(p)
    documento = Documento(arquivo=p.name, sha256=sha, paginas=len(doc))
    alg_sha = sha256_arquivo(geometria.__file__)
    medidas: list[Medida] = []; usados: dict[str, int] = {}; avisos: list[str] = []
    for pn, pg in enumerate(doc, 1):
        pd = geometria.analyze_page(pg, pn); angs = _angulos(pg); texto = pg.get_text()
        decl = UNIDADE_DECLARADA.search(texto)
        for d in pd.dims:
            ang = next((a for r, a in angs if abs(r.x0 - d.bbox[0]) < 0.6 and abs(r.y0 - d.bbox[1]) < 0.6 and abs(r.x1 - d.bbox[2]) < 0.6), None)
            orient = _orientacao(ang)
            estado, evs, conflitos = _analise(d, geometria)
            leitura = Evidencia(tipo="leitura", descricao="número lido da camada de texto do PDF", metodo="text-layer",
                                dados={"texto_original": d.text, "angulo_graus": ang}, coords=tuple(d.bbox))
            unidade = (Evidencia(tipo="unidade", descricao="unidade declarada no texto da página", metodo="regex sobre o texto da página",
                                 dados={"unidade": "mm", "trecho": decl.group(0)}) if decl else
                       Evidencia(tipo="unidade", descricao="unidade NÃO declarada nesta página; mm assumido (convenção de desenho de marcenaria)", metodo="premissa",
                                 dados={"unidade": "mm", "assumida": True}))
            mid = f"m-{sha[:8]}-p{pn}-{round(d.bbox[0])}x{round(d.bbox[1])}-{d.text}"
            usados[mid] = usados.get(mid, 0) + 1
            if usados[mid] > 1:
                mid += f"-{usados[mid]}"
            hist = (Transicao(de=None, para=Estado.EXTRAIDO, ator=SISTEMA, em=relogio() if relogio else agora(), motivo="número lido do documento"),)
            m = Medida(id=mid, documento=documento, pagina=pn, texto_original=d.text, valor_normalizado=float(d.value), unidade="mm",
                       unidade_fonte="declarada_na_pagina" if decl else "assumida", orientacao=orient, angulo_graus=ang, coords=tuple(d.bbox),
                       metodo_extracao="text-layer", confianca=1.0,
                       analise_automatica=AnaliseAutomatica(estado=estado, estado_algoritmo=d.status, algoritmo_sha256=alg_sha),
                       evidencias=(leitura, unidade), historico=hist)
            # a evidência do algoritmo entra junto com a transição de análise (fica amarrada ao histórico)
            m.transitar(estado, SISTEMA, f"análise geométrica do algoritmo: {d.status}", evidencia=evs[0])
            if orient == "inclinada":
                m._mutar(evidencias=m.evidencias + (Evidencia(tipo="orientacao", descricao="texto inclinado: o algoritmo só trata eixos horizontal/vertical",
                                                              metodo="ângulo do texto no PDF", dados={"angulo_graus": ang, "eixo_assumido_pelo_algoritmo": d.orient}),))
            if conflitos:
                m._mutar(conflitos=tuple(conflitos))
            if enfileirar:
                m.enfileirar_revisao(SISTEMA)
            medidas.append(m)
    if any(m.orientacao == "inclinada" for m in medidas):
        avisos.append("há texto inclinado: o algoritmo da Etapa 0 não o trata (ficam sem_medicao)")
    avisos.append("vista e componente não são determinados nesta etapa (campos nulos)")
    return Resultado(gerado_em=agora(), documento=documento,
                     algoritmo=Algoritmo(nome=NOME_ALGORITMO, arquivo="ingest/dimensions.py", sha256=alg_sha,
                                         parametros={"TOL": geometria.TOL, "MIN_CLUSTER": geometria.MIN_CLUSTER, "TICK_MAX": geometria.TICK_MAX, "END_NEAR": geometria.END_NEAR}),
                     medidas=medidas, resumo=resumir(medidas), avisos=avisos)
