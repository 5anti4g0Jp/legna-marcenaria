import json, sys, math
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

src = sys.argv[1]; out = sys.argv[2]
d = json.load(open(src)); P = d["project"]; R = d["report"]; PR = d["prices"]
mats = {m["id"]: m for m in P["materials"]}
SHEET = 2750 * 1840
status = lambda k, i: PR[k][i]["status"]

wb = Workbook()
H = Font(bold=True, color="FFFFFF"); HF = PatternFill("solid", fgColor="3B3B3B")
REF = PatternFill("solid", fgColor="FFF2CC"); WARN = PatternFill("solid", fgColor="FCE4D6")
def sheet(name, header, rows, widths=None):
    ws = wb.create_sheet(name); ws.append(header)
    for c in ws[1]: c.font = H; c.fill = HF; c.alignment = Alignment(wrap_text=True, vertical="center")
    for r in rows: ws.append(r)
    ws.freeze_panes = "A2"
    for i, w in enumerate(widths or [], 1): ws.column_dimensions[get_column_letter(i)].width = w
    return ws

# ---- por material: líquido, comprado, custo, rateio
plans = {pl["materialId"]: pl for pl in R["plans"]}
cost_mat = {k: len(pl["sheets"]) * mats[k]["pricePerSheet"] for k, pl in plans.items()}
net_mat = {k: pl["netArea"] for k, pl in plans.items()}
bands = {b["id"]: b for b in P["edgeBands"]}

def band_m(p):
    e = p.get("edges") or {}
    return ((p["w"] if e.get("w1") else 0) + (p["w"] if e.get("w2") else 0) + (p["h"] if e.get("h1") else 0) + (p["h"] if e.get("h2") else 0)) * p["qty"] / 1000

rows = []
for p in P["pieces"]:
    m = mats[p["materialId"]]; ar = p["w"] * p["h"] * p["qty"]
    rat = cost_mat[p["materialId"]] * ar / net_mat[p["materialId"]]
    md = p.get("moduleDims") or {}
    rows.append([p.get("module"), f'{md.get("W","")}x{md.get("H","")}x{md.get("D","")}' if md else "", p["label"], p["w"], p["h"], m["thickness"], m["name"], p["qty"],
                 round(p["w"] * p["h"] / 1e6, 4), round(ar / 1e6, 4), round(ar / SHEET * 100, 2), round(rat, 2), round(band_m(p), 3),
                 "lido do PDF" if p.get("origin") == "pdf" else "derivado por regra (confirmar)", p.get("source", "")])
ws = sheet("Peças", ["Módulo / móvel", "Móvel L×A×P (mm)", "Peça", "Comprimento (mm)", "Largura (mm)", "Espessura (mm)", "Material", "Qtd", "Área unit. (m²)", "Área total (m²)", "% de 1 chapa", "Custo rateado da chapa (R$)", "Fita de borda (m)", "Origem", "Fonte"], rows,
           [46, 16, 38, 12, 12, 10, 40, 6, 11, 11, 10, 14, 11, 26, 10])
for r in ws.iter_rows(min_row=2):
    if "derivado" in str(r[13].value):
        for c in r: c.fill = WARN

# ---- consumo por material
rows = []
for k, pl in plans.items():
    m = mats[k]; ns = pl["netArea"] / 1e6
    rows.append([m["name"], m["thickness"], round(ns, 3), len(pl["sheets"]), round(pl["purchasedArea"] / 1e6, 3), round(pl["utilization"] * 100, 1), m["pricePerSheet"], round(cost_mat[k], 2), PR["materials"][k]["status"]])
ws = sheet("Consumo por material", ["Material", "Esp. (mm)", "Líquido (m²)", "Chapas a comprar", "Comprado (m²)", "Aproveitamento (%)", "Preço/chapa (R$)", "Custo (R$)", "Status do preço"], rows, [44, 9, 12, 12, 12, 12, 12, 14, 16])
ws.append(["TOTAL", "", round(sum(pl["netArea"] for pl in plans.values()) / 1e6, 3), sum(len(pl["sheets"]) for pl in plans.values()), "", "", "", round(sum(cost_mat.values()), 2), ""])

# ---- fita
rows = []
for k, v in R["edgeBandMeters"].items():
    rows.append([bands[k]["name"], v["net"], v["purchased"], bands[k]["pricePerMeter"], round(v["purchased"] * bands[k]["pricePerMeter"], 2), PR["bands"][k]["status"]])
sheet("Fita de borda", ["Fita", "Líquido (m)", "Comprar (m, +10% perda)", "Preço/m (R$)", "Custo (R$)", "Status do preço"], rows, [34, 12, 16, 12, 12, 16])

# ---- ferragens
rows = [[h["name"], h["qty"], h["unitPrice"], round(h["qty"] * h["unitPrice"], 2), "derivado por regra (confirmar)", PR["hardware"][h["id"]]["status"]] for h in R["hardware"]]
sheet("Ferragens", ["Ferragem", "Qtd", "Preço unit. (R$)", "Custo (R$)", "Origem", "Status do preço"], rows, [40, 8, 14, 12, 28, 16])

# ---- terceiros
rows = [[e["name"], e["qty"], e["unit"], e["unitPrice"], round(e["qty"] * e["unitPrice"], 2), "lido do PDF" if e["origin"] == "pdf" else "assumido (confirmar)", PR["extras"][e["id"]]["status"]] for e in P["extras"]]
sheet("Itens não-MDF", ["Item", "Qtd", "Unid.", "Preço unit. (R$)", "Custo (R$)", "Origem da quantidade", "Status do preço"], rows, [44, 9, 7, 14, 12, 24, 16])

# ---- plano de corte
rows = []
for pl in R["plans"]:
    for i, s in enumerate(pl["sheets"], 1):
        for q in s["placements"]:
            rows.append([mats[pl["materialId"]]["name"], i, q["label"], q["x"], q["y"], q["w"], q["h"], "sim" if q["rotated"] else "não"])
sheet("Plano de corte", ["Material", "Chapa nº", "Peça", "X (mm)", "Y (mm)", "Comp. X (mm)", "Larg. Y (mm)", "Girada"], rows, [40, 9, 44, 8, 8, 12, 12, 8])

# ---- orçamento
b = R["budget"]
ref_share = None
rows = [["Chapas de MDF", b["materials"]], ["Fita de borda", b["edgeBand"]], ["Ferragens", b["hardware"]], ["Itens não-MDF (vidro, espelho, LED, pés...)", b["thirdParty"]],
        ["SUBTOTAL MATERIAIS (sem mão de obra)", round(b["materials"] + b["edgeBand"] + b["hardware"] + b["thirdParty"], 2)],
        ["Mão de obra (R$/m² de peça >= 10 mm)", b["labor"]], ["Custos indiretos (12%)", b["overhead"]], ["CUSTO TOTAL", b["totalCost"]],
        ["Margem (30% sobre o preço)", b["margin"]], ["PREÇO SUGERIDO DE VENDA", b["suggestedPrice"]]]
ws = sheet("Orçamento", ["Item", "Valor (R$)"], rows, [58, 16])
ws.append([]); ws.append(["ATENÇÃO: todos os preços, a mão de obra, os indiretos e a margem são de REFERÊNCIA (status 'referencia'), não confirmados. Edite prices.json e gere de novo."])
ws.cell(ws.max_row, 1).fill = REF
for r in ws.iter_rows(min_row=2, max_row=11):
    if r[0].value and str(r[0].value).isupper(): 
        for c in r: c.font = Font(bold=True)

# ---- confirmar
rows = [[i + 1, a] for i, a in enumerate(P["assumptions"])] + [[len(P["assumptions"]) + 1 + i, i2["message"]] for i, i2 in enumerate([x for x in R["issues"] if x["severity"] == "blocking"])]
sheet("Confirmar (premissas)", ["#", "Premissa assumida ou dado ausente - CONFIRMAR"], rows, [5, 150])

del wb["Sheet"]; i = wb.sheetnames.index("Orçamento"); wb._sheets.insert(0, wb._sheets.pop(i)); wb.active = 0; wb.save(out)
print("ok", out, "| peças:", len(P["pieces"]), "| linhas de confirmação:", len(P["assumptions"]))
