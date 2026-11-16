"""Gera o formulário (xlsx) do levantamento de dados da Legna e valida as respostas.

  python -m levantamento.formulario gerar  levantamento/formulario_levantamento_legna.xlsx
  python -m levantamento.formulario validar <arquivo.xlsx>        # resumo + erros; exit 1 se houver erro
  python -m levantamento.formulario exportar <arquivo.xlsx> saida.json   # só CONFIRMADOS (e provisórios, separados e marcados)

Nenhum valor comercial é gerado aqui: o arquivo nasce com todos os campos `pendente` e valores vazios.
"""
from __future__ import annotations

import datetime as dt, json, re, sys
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .campos import CAMPOS, COMUNS, LINHAS_TABELA, STATUS, TABELAS

NAO_HUMANOS = ("assistente", "claude", "ia", "sistema", "chatgpt", "gpt", "bot", "automatico", "automático")
COR = {"cab": "1F3A5F", "pendente": "FFF3CD", "confirmado": "D4EDDA", "provisorio": "FFE0B2", "ro": "EEEEEE"}
LEIA_ME = [
    "LEVANTAMENTO DE DADOS DA LEGNA — como preencher",
    "",
    "Objetivo: o sistema só usa dados REAIS da Legna. Nada neste arquivo foi preenchido por nós; tudo começa como PENDENTE.",
    "",
    "Status de cada campo (coluna 'status'):",
    "  confirmado  O dado é real e a Legna garante. Exige: valor + fonte (ex.: tabela do fornecedor X, nota fiscal, regra da oficina) + data da fonte + quem confirmou (pessoa).",
    "  pendente    Ainda não sabemos / não informado. Deixe o valor vazio. O sistema vai PERGUNTAR em vez de inventar.",
    "  provisorio  Estimativa para podermos testar enquanto o dado real não chega. Exige valor + justificativa. NUNCA aparece como preço real e NUNCA vai para orçamento ao cliente.",
    "",
    "Regras:",
    "  1. Se não souber, deixe PENDENTE. Não chute: um valor chutado marcado como confirmado é pior do que um campo vazio.",
    "  2. Preço sempre com fornecedor e data. Preço sem data não é confirmado.",
    "  3. Informe unidades (mm, R$ por m², %...). Decimal com vírgula ou ponto.",
    "  4. Campos com criticidade 'bloqueia_orcamento' impedem o orçamento enquanto não estiverem CONFIRMADOS.",
    "  5. Nas abas de tabela (materiais, fitas, ferragens...), use uma linha por item; linhas em branco são ignoradas.",
    "  6. Quem confirma deve ser uma pessoa da Legna (nome completo).",
    "",
    "Abas: Campos (itens únicos) · materiais · fitas · ferragens · terceirizados · fornecedores · regra_dobradica · regra_corredica.",
    "Devolva o arquivo .xlsx preenchido. Ele será validado automaticamente e os dados confirmados alimentam a configuração do sistema.",
]


def _estilo_cab(ws, linha=1):
    for c in ws[linha]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor=COR["cab"]); c.alignment = Alignment(wrap_text=True, vertical="center")


def gerar(destino: str | Path) -> Path:
    wb = Workbook(); ws = wb.active; ws.title = "LEIA-ME"
    for i, t in enumerate(LEIA_ME, 1):
        ws.cell(i, 1, t).font = Font(bold=(i == 1), size=14 if i == 1 else 11)
    ws.column_dimensions["A"].width = 150
    # --- Campos únicos
    ws = wb.create_sheet("Campos")
    cab = ["id", "seção", "campo", "como responder", "tipo", "unidade", "criticidade", "alimenta", "opções"] + COMUNS
    ws.append(cab); _estilo_cab(ws)
    dv_status = DataValidation(type="list", formula1='"' + ",".join(STATUS) + '"', allow_blank=False); ws.add_data_validation(dv_status)
    for i, c in enumerate(CAMPOS, 2):
        ws.append([c["id"], c["secao"], c["rotulo"], c["ajuda"], c["tipo"], c["unidade"], c["criticidade"], c["alimenta"], "; ".join(c["opcoes"]), "pendente", None, None, None, None, None, None])
        dv_status.add(f"{get_column_letter(cab.index('status') + 1)}{i}")
        if c["opcoes"] and c["tipo"] in ("lista", "sim_nao"):
            dv = DataValidation(type="list", formula1='"' + ",".join(c["opcoes"]) + '"', allow_blank=True); ws.add_data_validation(dv); dv.add(f"{get_column_letter(cab.index('valor') + 1)}{i}")
        for k in range(1, 10):
            ws.cell(i, k).fill = PatternFill("solid", fgColor=COR["ro"])
        ws.cell(i, cab.index("status") + 1).fill = PatternFill("solid", fgColor=COR["pendente"])
    for k, w in zip("ABCDEFGHI", (18, 22, 46, 60, 11, 9, 20, 14, 28)): ws.column_dimensions[k].width = w
    for k in "JKLMNOP": ws.column_dimensions[k].width = 26
    ws.freeze_panes = "D2"
    # --- Tabelas
    for t in TABELAS:
        ws = wb.create_sheet(t["nome"]); cab = ["linha"] + [c["id"] for c in t["colunas"]] + COMUNS[:1] + COMUNS[2:]       # sem 'valor' (cada coluna é um valor)
        ws.append(cab); _estilo_cab(ws)
        ws.append(["(descrição)"] + [f'{c["rotulo"]}{" (" + c["unidade"] + ")" if c["unidade"] else ""}{"" if c["obrigatoria"] else " — opcional"}' for c in t["colunas"]] + [""] * (len(COMUNS) - 1))
        for c in ws[2]: c.font = Font(italic=True, color="555555"); c.alignment = Alignment(wrap_text=True)
        dv_status = DataValidation(type="list", formula1='"' + ",".join(STATUS) + '"', allow_blank=True); ws.add_data_validation(dv_status)
        ic_status = cab.index("status") + 1
        for r in range(1, LINHAS_TABELA + 1):
            row = 2 + r; ws.cell(row, 1, r); dv_status.add(f"{get_column_letter(ic_status)}{row}")
        for j, c in enumerate(t["colunas"], 2):
            if c["opcoes"]:
                dv = DataValidation(type="list", formula1='"' + ",".join(c["opcoes"]) + '"', allow_blank=True); ws.add_data_validation(dv); dv.add(f"{get_column_letter(j)}3:{get_column_letter(j)}{2 + LINHAS_TABELA}")
            ws.column_dimensions[get_column_letter(j)].width = 24
        for j in range(len(t["colunas"]) + 2, len(cab) + 1): ws.column_dimensions[get_column_letter(j)].width = 24
        ws.freeze_panes = "B3"
    wb.save(destino)
    return Path(destino)


# ------------------------------------------------------------------------------------------------ leitura e validação
def _vazio(v) -> bool: return v is None or (isinstance(v, str) and not v.strip())


def _num(v):
    if isinstance(v, bool): return None
    if isinstance(v, (int, float)): return float(v)
    t = str(v).strip().replace("R$", "").replace("%", "").replace(" ", "")
    if "," in t: t = t.replace(".", "").replace(",", ".")                 # 1.234,56 -> 1234.56 ; 12,5 -> 12.5
    try: return float(t)
    except ValueError: return None


def _data(v):
    if isinstance(v, dt.datetime): return v.date()
    if isinstance(v, dt.date): return v
    for f in ("%Y-%m-%d", "%d/%m/%Y"):
        try: return dt.datetime.strptime(str(v).strip(), f).date()
        except ValueError: pass
    return None


def _erro_tipo(tipo, valor, opcoes) -> str | None:
    if tipo in ("numero", "inteiro", "moeda_brl", "percentual"):
        n = _num(valor)
        if n is None: return f"deve ser número (recebido: {valor!r})"
        if n < 0: return "não pode ser negativo"
        if tipo == "inteiro" and n != int(n): return "deve ser inteiro"
        if tipo == "percentual" and n > 100: return "percentual acima de 100"
    elif tipo in ("sim_nao", "lista"):
        if str(valor).strip().lower() not in [o.lower() for o in opcoes]: return f"valor fora das opções {opcoes}"
    elif tipo == "data":
        if _data(valor) is None: return "data inválida (use AAAA-MM-DD ou DD/MM/AAAA)"
    return None


def _regras_status(status, tem_valor, fonte, data_fonte, por, just, valor_ok_data=True):
    e = []
    if status not in STATUS: return [f"status inválido: {status!r} (use {list(STATUS)})"]
    if status == "pendente" and tem_valor: e.append("está 'pendente' mas tem valor: marque 'provisorio' (com justificativa) ou 'confirmado' (com fonte)")
    if status == "provisorio":
        if not tem_valor: e.append("'provisorio' exige valor")
        if _vazio(just) or len(str(just).strip()) < 10: e.append("'provisorio' exige justificativa (mín. 10 caracteres)")
    if status == "confirmado":
        if not tem_valor: e.append("'confirmado' exige valor")
        if _vazio(fonte): e.append("'confirmado' exige fonte")
        if _vazio(data_fonte) or _data(data_fonte) is None: e.append("'confirmado' exige data da fonte válida")
        elif _data(data_fonte) > dt.date.today(): e.append("data da fonte no futuro")
        if _vazio(por) or len(str(por).strip()) < 3: e.append("'confirmado' exige quem confirmou (pessoa)")
        elif str(por).strip().lower() in NAO_HUMANOS: e.append("quem confirmou deve ser uma pessoa, não um sistema/IA")
    return e


def validar(path: str | Path) -> dict:
    wb = load_workbook(path, data_only=True); erros, resumo = [], {}
    campos = {c["id"]: c for c in CAMPOS}; criticos_abertos = []; confirmados = {}; provisorios = {}
    ws = wb["Campos"]; cab = [c.value for c in ws[1]]; ix = {k: i for i, k in enumerate(cab)}; cont = {s: 0 for s in STATUS}; vistos = set()
    for r in ws.iter_rows(min_row=2, values_only=True):
        if _vazio(r[0]): continue
        cid = r[ix["id"]]; c = campos.get(cid)
        if c is None: erros.append(f"Campos/{cid}: campo desconhecido (não altere a coluna 'id')"); continue
        vistos.add(cid); st = (r[ix["status"]] or "").strip().lower() if isinstance(r[ix["status"]], str) else r[ix["status"]]; v = r[ix["valor"]]; tem = not _vazio(v)
        for m in _regras_status(st, tem, r[ix["fonte"]], r[ix["data_fonte"]], r[ix["confirmado_por"]], r[ix["justificativa_provisorio"]]): erros.append(f"Campos/{cid}: {m}")
        if tem and st in ("confirmado", "provisorio"):
            m = _erro_tipo(c["tipo"], v, c["opcoes"])
            if m: erros.append(f"Campos/{cid}: valor {m}")
        if st in cont: cont[st] += 1
        if st == "confirmado" and not any(e.startswith(f"Campos/{cid}:") for e in erros): confirmados[cid] = {"valor": v, "unidade": c["unidade"], "fonte": r[ix["fonte"]], "data_fonte": str(_data(r[ix["data_fonte"]])), "confirmado_por": r[ix["confirmado_por"]]}
        if st == "provisorio" and tem: provisorios[cid] = {"valor": v, "unidade": c["unidade"], "justificativa": r[ix["justificativa_provisorio"]], "uso_comercial": False}
        if c["criticidade"] == "bloqueia_orcamento" and st != "confirmado": criticos_abertos.append(cid)
    for cid in set(campos) - vistos: erros.append(f"Campos/{cid}: linha removida do formulário")
    resumo["Campos"] = cont
    tabelas_conf = {}
    for t in TABELAS:
        if t["nome"] not in wb.sheetnames: erros.append(f"aba ausente: {t['nome']}"); continue
        ws = wb[t["nome"]]; cab = [c.value for c in ws[1]]; ix = {k: i for i, k in enumerate(cab)}; cont = {s: 0 for s in STATUS}; linhas = []
        for n, r in enumerate(ws.iter_rows(min_row=3, values_only=True), 3):
            dados = {c["id"]: r[ix[c["id"]]] for c in t["colunas"]}
            if all(_vazio(v) for v in dados.values()) and _vazio(r[ix["status"]]): continue
            st = r[ix["status"]]; st = st.strip().lower() if isinstance(st, str) else st; tem_todos = all(not _vazio(dados[c["id"]]) for c in t["colunas"] if c["obrigatoria"])
            rot = f"{t['nome']}/linha {n - 2}"
            if _vazio(st): erros.append(f"{rot}: linha com dados sem status"); continue
            for m in _regras_status(st, any(not _vazio(v) for v in dados.values()), r[ix["fonte"]], r[ix["data_fonte"]], r[ix["confirmado_por"]], r[ix["justificativa_provisorio"]]): erros.append(f"{rot}: {m}")
            if st in ("confirmado", "provisorio"):
                for c in t["colunas"]:
                    v = dados[c["id"]]
                    if _vazio(v):
                        if c["obrigatoria"]: erros.append(f"{rot}: coluna obrigatória '{c['id']}' vazia em linha '{st}'")
                        continue
                    m = _erro_tipo(c["tipo"], v, c["opcoes"])
                    if m: erros.append(f"{rot}: {c['id']} {m}")
            if st in cont: cont[st] += 1
            if st in STATUS and not any(e.startswith(rot + ":") for e in erros):
                linhas.append({"status": st, **{k: (str(_data(v)) if (_data(v) and next(c for c in t["colunas"] if c["id"] == k)["tipo"] == "data") else v) for k, v in dados.items()},
                               "fonte": r[ix["fonte"]], "data_fonte": str(_data(r[ix["data_fonte"]])) if not _vazio(r[ix["data_fonte"]]) else None, "confirmado_por": r[ix["confirmado_por"]],
                               "justificativa_provisorio": r[ix["justificativa_provisorio"]], "uso_comercial": st == "confirmado"})
        resumo[t["nome"]] = cont; tabelas_conf[t["nome"]] = linhas
    tabelas_criticas = ("materiais", "fitas", "ferragens", "regra_dobradica")
    sem_tabela = [n for n in tabelas_criticas if not any(l["status"] == "confirmado" for l in tabelas_conf.get(n, []))]
    pronto = not erros and not criticos_abertos and not sem_tabela
    return {"ok": not erros, "erros": erros, "resumo_por_aba": resumo, "campos_criticos_nao_confirmados": criticos_abertos, "tabelas_criticas_sem_linha_confirmada": sem_tabela,
            "pronto_para_orcamento": pronto, "confirmados": confirmados, "provisorios": provisorios, "tabelas": tabelas_conf}


def exportar(path, destino) -> dict:
    r = validar(path)
    if not r["ok"]: raise ValueError(f"formulário com {len(r['erros'])} erro(s); corrija antes de exportar")
    out = {"aviso": "Somente itens com status 'confirmado' são dados reais da Legna. 'provisorios' são estimativas marcadas e NÃO podem ser usadas em orçamento.",
           "pronto_para_orcamento": r["pronto_para_orcamento"], "confirmados": r["confirmados"], "provisorios": r["provisorios"],
           "tabelas": {n: [l for l in ls] for n, ls in r["tabelas"].items()}, "pendentes_criticos": r["campos_criticos_nao_confirmados"]}
    Path(destino).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "gerar": print("gerado:", gerar(a[1]))
    elif len(a) >= 2 and a[0] == "validar":
        r = validar(a[1]); print(json.dumps({k: r[k] for k in ("ok", "resumo_por_aba", "pronto_para_orcamento", "campos_criticos_nao_confirmados", "tabelas_criticas_sem_linha_confirmada")}, ensure_ascii=False, indent=1))
        for e in r["erros"]: print("ERRO:", e)
        sys.exit(0 if r["ok"] else 1)
    elif len(a) >= 3 and a[0] == "exportar": exportar(a[1], a[2]); print("exportado:", a[2])
    else: print(__doc__)
