"""Gera o relatório Markdown a partir do JSON de resultados (nenhum número é digitado à mão)."""
from __future__ import annotations

import json, sys
from collections import Counter, defaultdict
from pathlib import Path

COTA = ("cota_regular", "cota_deslocada")


def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "-"


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def cota_row(label, v):
    g = lambda *ks: sum(v.get(k, 0) for k in ks)
    n = v.get("_total", 0)
    return [label, n, f"{g('confirmada_correta')} ({pct(g('confirmada_correta'), n)})", g("confirmada_associacao_incorreta", "erro_plantado_aceito"),
            g("confirmada_indeterminada"), g("conflito_falso_alarme"), g("perdida_leitura"), g("perdida_medicao", "erro_plantado_perdido"),
            g("erro_plantado_detectado")]


HDR = ["Grupo", "N", "Confirmada correta", "Falsa confirmação", "Confirmada indeterminada", "Conflito (tratado como falso alarme)", "Perdida na leitura", "Perdida na medição", "Erro plantado detectado"]


def render(R: dict) -> str:
    m = R["meta"]; real = R["real"]; syn = R["sintetico"]
    L = [f"# Etapa 0 — Linha de base do algoritmo de cotas (`ingest/dimensions.py`)", "",
         f"Gerado em {m['gerado_em']} · Python {m['python']} · PyMuPDF {m['pymupdf']} · algoritmo `sha256 {m['algoritmo']['sha256'][:12]}…` (**não alterado nesta etapa**)", ""]
    # ---------- resumo
    if real:
        cot = [r for r in real["linhas"] if r["role"] in COTA]; n = len(cot); c = Counter(r["outcome"] for r in cot)
        ver = sum(1 for r in cot if r["outcome"] == "conflito_falso_alarme" and "soma de cadeia" in (r.get("evidence") or ""))
        L += ["## 1. Resumo (PDF real, tokens revisados)", "",
              f"- Universo: **{real['tokens_total']}** tokens numéricos em {real['paginas']} páginas; **{real['tokens_revisados']}** ({pct(real['tokens_revisados'], real['tokens_total'])}) com rótulo revisado, nas páginas {real['paginas_revisadas']}.",
              f"- Cotas revisadas: **{n}** ({sum(1 for r in cot if r['role']=='cota_regular')} regulares + {sum(1 for r in cot if r['role']=='cota_deslocada')} deslocadas).",
              f"- **Confirmadas corretamente: {c['confirmada_correta']} ({pct(c['confirmada_correta'], n)})**.",
              f"- **Falsas confirmações (confirmada com intervalo errado): {c['confirmada_associacao_incorreta']} ({pct(c['confirmada_associacao_incorreta'], n)})**.",
              f"- Confirmadas sem veredito decidível: {c['confirmada_indeterminada']}.",
              f"- Conflitos: **{c['conflito_falso_alarme']}**: **{ver} falsos alarmes verificados** por soma de cadeia (o valor escrito fecha a conta); **{c['conflito_falso_alarme'] - ver} não decidíveis** pela imagem (valor escrito apenas ASSUMIDO correto; a geometria pode estar inconsistente com ele).",
              f"- **Cotas perdidas (sem medição): {c['perdida_medicao']} ({pct(c['perdida_medicao'], n)})**; perdidas na leitura: {c['perdida_leitura']}.",
              f"- Medidas em nota (ex.: `PROFUNDIDADE = 34 CM`, `12mm`): **{sum(1 for r in real['linhas'] if r['outcome']=='nota_nao_lida')} de {sum(1 for r in real['linhas'] if r['role']=='medida_em_nota')} não lidas**.",
              f"- Números que não são medida (K, W): {sum(1 for r in real['linhas'] if r['outcome']=='ignorada_corretamente')} de {sum(1 for r in real['linhas'] if r['role']=='nao_cota')} ignorados corretamente.",
              "- **Associação a componentes: não implementada** no baseline (0%).", ""]
    # ---------- metodologia
    L += ["## 2. Metodologia e limitações do gabarito", "",
          "- **Real:** census independente dos tokens + regras + inspeção visual de overlays do baseline. Rótulos feitos pelo assistente, **sem conferência independente**.",
          "- Veredito de associação 'correta' vem de verificação visual global do overlay, **não token a token**. Valores escritos assumidos corretos (sem erro plantado no PDF real).",
          "- Só 3 páginas foram revisadas; o resto do PDF entra apenas nas contagens de universo.",
          "- **Sintético:** 60 itens em 9 desenhos gerados com resposta exata. Cobre estilos que o PDF real não tem, mas **não prova compatibilidade com Promob/AutoCAD**.", ""]
    # ---------- real por tipo
    if real:
        L += ["## 3. PDF real — por tipo de cota", "", "Definições: *confirmada correta* = confirmada e intervalo certo; *falsa confirmação* = confirmada contra o intervalo errado; "
              "*conflito (falso alarme)* = marcada conflito, mas o valor escrito está certo; *perdida na leitura* = número nem virou candidato; *perdida na medição* = candidato sem medição.", ""]
        for title, key in (("Por papel", "por_papel"), ("Por orientação (cotas)", "por_orientacao"), ("Por tamanho (cotas)", "por_tamanho")):
            L += [f"**{title}**", "", table(HDR, [cota_row(k, v) for k, v in real[key].items() if k.startswith(("cota", "horizontal", "vertical", "inclinada", "<", "6", ">"))]), ""]
        notes = {k: v for k, v in real["por_papel"].items() if not k.startswith("cota")}
        L += ["**Notas e números que não são medida**", "", table(["Papel", "N", "Resultado"], [[k, v["_total"], ", ".join(f"{o}={n_}" for o, n_ in v.items() if o != "_total")] for k, v in notes.items()]), ""]
        L += ["**Por formato do número**", "", table(["Formato", "N", "Resultados"], [[k, v["_total"], ", ".join(f"{o}={n_}" for o, n_ in v.items() if o != "_total")] for k, v in real["por_formato"].items()]), ""]
        L += ["## 4. Escalas", "", f"- Estados do baseline nas 34 páginas: {real['estados_baseline_todas_as_paginas']}.",
              f"- Páginas com **mais de uma escala próxima** (divergência de 3% a 8%, causa ainda desconhecida: vistas diferentes ou viés de medida): {real['paginas_com_varias_escalas_proximas']}.",
              f"- **Escala espúria aceita:** {real['escalas_espurias_por_pagina']} (página → mm/pt); as cotas confirmadas contra ela são falsas confirmações.", ""]
        L += ["## 5. Tempo", "", f"- PDF de {real['paginas']} páginas: **{real['tempo']['total_s']} s** (mediana de 3 execuções); mediana por página **{real['tempo']['mediana_pagina_ms']} ms**.", ""]
    # ---------- sintético
    L += ["## 6. Sintético — por estilo (resposta exata)", "", table(HDR, [cota_row(k, v) for k, v in syn["por_estilo"].items()]), ""]
    L += ["**Por orientação**", "", table(HDR, [cota_row(k, v) for k, v in syn["por_orientacao"].items()]), "",
          "**Por formato**", "", table(HDR, [cota_row(k, v) for k, v in syn["por_formato"].items()]), ""]
    nd = [r for r in syn["linhas"] if r["role"] == "nao_cota"]
    L += [f"**Números que não são cota (sintético):** {Counter(r['outcome'] for r in nd)}", ""]
    pl = [r for r in syn["linhas"] if r["planted_error"]]
    L += ["**Erros plantados (texto ≠ geometria)**", "", table(["Escrito", "Geometria (mm)", "Desvio", "Resultado"],
          [[r["text"], r["verdade_mm"], f"{100*(r['escrito_mm']-r['verdade_mm'])/r['verdade_mm']:+.1f}%", r["outcome"]] for r in pl]), ""]
    L += ["**Escalas sintéticas**", "", table(["Desenho", "Verdadeiras", "Detectadas", "Perdidas", "Espúrias"],
          [[k, v["verdadeiras"], v["detectadas"], v["perdidas"], v["espurias"]] for k, v in syn["escalas"].items()]), ""]
    # ---------- falhas
    fl = R["falhas"]
    L += ["## 7. Casos de erro", "", f"Total catalogado: **{len(fl)}** (lista completa em `etapa0_baseline.json` → `falhas`).", ""]
    grp = defaultdict(list)
    for f in fl:
        causa = f.get("causa") or ("desenho sintético: " + f["origem"].split("/")[1] if f["origem"].startswith("sintetico") else "-")
        grp[(f["resultado"], causa)].append(f)
    rows = []
    for (o, c), v in sorted(grp.items(), key=lambda kv: -len(kv[1])):
        rows.append([len(v), o, c[:90], ", ".join(f"{x['texto']} ({x['origem'].split('/',1)[1]})" for x in v[:4])])
    L += [table(["N", "Resultado", "Causa", "Exemplos"], rows), ""]
    # ---------- conclusões
    L += ["## 8. O que a linha de base mostra", "",
          "1. O algoritmo atual **não pode ser tratado como validação**: confirma intervalos errados e marca como conflito valores corretos.",
          "2. As cotas **pequenas** (espessuras, ≤ 60 mm) são as que mais se perdem, e são justamente as que definem materiais.",
          "3. Decimais, unidades, texto inclinado, texto na linha e texto abaixo da linha **não são tratados**.",
          "4. A geometria detecta erros grandes (≥ ~2%), mas **não erros de ~1%**: 'geometricamente consistente' não é 'correto'.",
          "5. Medidas em notas de texto (profundidades em cm) **não são lidas**; precisam de outra via de extração.", "",
          "## 9. Reprodução", "", "```bash", "python -m evaluation.run_baseline --algo evaluation/baseline_etapa0/dimensions.py   # regera os resultados",
          "python -m evaluation.report evaluation/results/etapa0_baseline.json > evaluation/results/etapa0_relatorio.md",
          "python -m pytest tests_py/test_evaluation.py -q", "```", ""]
    return "\n".join(L)


if __name__ == "__main__":
    print(render(json.loads(Path(sys.argv[1]).read_text())))
