import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { run } from "../../src/engine.js";
import { custom, expand, type CabSpec, type Custom, type Extra } from "../../src/rules.js";
import type { ExtraItem, HardwareItem, Material, Piece, Project } from "../../src/types.js";

const prices = JSON.parse(readFileSync(new URL("./prices.json", import.meta.url), "utf8"));
const X = (id: string, qty: number, origin: "pdf" | "regra" = "pdf"): Extra => ({ id, name: prices.extras[id].name, qty: Math.round(qty * 1000) / 1000, unit: prices.extras[id].unit, origin });
const m2 = (w: number, h: number, n = 1) => (w * h * n) / 1e6;
const mod = (id: string, nome: string, src: string, W: number, H: number, D: number) => ({ id, nome, src, W, H, D });

const D_SUP = "profundidade do armário superior não informada neste desenho; assumido 34 cm (mesma da área de serviços, p.6)";
const specs: CabSpec[] = [
  // ---------- COZINHA (p.1-4) ----------
  { id: "K1", nome: "Cozinha - superior esquerdo (portas + vidro)", src: "p.1-2", cor: "tauari", W: 2200, H: 990, D: 340, top: "full", dividers: 1, shelves: 2,
    doors: [[545, 560, 4]], handle: "sinnai", extraHandles: 2, extraHinges: 4,
    assumed: [`Cozinha superior esquerdo: ${D_SUP}`, "Cozinha superior esquerdo: nº de divisórias (1) e prateleiras (2) não cotados; assumidos pelas linhas tracejadas."],
    extras: [X("vidro-canelado", m2(1100, 430, 2)), X("led", 2.2)] },
  { id: "K2", nome: "Cozinha - torre central (porta 650x2300)", src: "p.1", cor: "tauari", W: 680, H: 2330, D: 600, shelves: 4, doors: [[650, 2300, 1]], handle: "none", rodabase: true,
    assumed: ["Cozinha torre central: profundidade não informada; assumido 60 cm (como a despensa, p.5)", "Cozinha torre central: 4 prateleiras assumidas pelas linhas tracejadas (espaçamento ~450)", "Cozinha torre central: puxador = cava circular (sem ferragem)"] },
  { id: "K3", nome: "Cozinha - superior central (2 portas 375)", src: "p.1", cor: "tauari", W: 750, H: 590, D: 340, shelves: 1, doors: [[375, 560, 2]], handle: "sinnai", assumed: [`Cozinha superior central: ${D_SUP}`] },
  { id: "K4", nome: "Cozinha - torre do forno", src: "p.1", cor: "tauari", W: 750, H: 2330, D: 600, shelves: 3, doors: [[360, 560, 2]], fronts: [[720, 310, 1]], handle: "sinnai", rodabase: true,
    assumed: ["Cozinha torre do forno: profundidade não informada; assumido 60 cm", "Cozinha torre do forno: largura da frente do gavetão (720) derivada de 750 - 2x15", "Cozinha torre do forno: 3 prateleiras fixas assumidas para nicho do micro-ondas e forno (eletros fora do escopo)"] },
  { id: "K6", nome: "Cozinha - gaveteiro 760 (3 gavetas)", src: "p.1", cor: "tauari", W: 790, H: 585, D: 640, top: "rails", fronts: [[760, 195, 3]], handle: "sinnai", rodabase: true, assumed: ["Cozinha gaveteiro: profundidade 64 cm assumida (armário inferior da p.3)"] },
  { id: "K7", nome: "Cozinha - armário inferior da pia", src: "p.3-4", cor: "tijolo", W: 2198, H: 730, D: 640, top: "rails", dividers: 4, shelves: 3,
    doors: [[200, 730, 1], [492, 730, 3]], fronts: [[492, 182, 4]], handle: "sinnai", rodabase: true,
    assumed: ["Armário da pia: altura das 4 gavetas não cotada; derivada (730/4 = 182)", "Armário da pia: 'porta temperos' (200) tratada como porta comum; confirmar se é gaveta/extensível", "Armário da pia: largura externa 2198 = soma das cotas (15+200+4x492+15); confirmar vs 2200"] },
  // ---------- ÁREA DE SERVIÇOS (p.6-7) ----------
  { id: "AS1", nome: "Serviços - torre branca (porta 345x2150)", src: "p.6-7", cor: "branco", W: 375, H: 2150, D: 585, shelves: 1, doors: [[345, 2150, 1]], handle: "sinnai", rodabase: true },
  { id: "AS2", nome: "Serviços - superior esquerdo (2 portas 350)", src: "p.6-7", cor: "tauari", W: 700, H: 940, D: 340, shelves: 1, doors: [[350, 940, 2]], handle: "sinnai" },
  { id: "AS3", nome: "Serviços - superior direito branco (2 portas 330)", src: "p.6-7", cor: "branco", W: 660, H: 940, D: 340, shelves: 2, doors: [[330, 940, 2]], handle: "sinnai" },
  { id: "AS4", nome: "Serviços - inferior da pia (2 portas 340)", src: "p.6-7", cor: "tauari", W: 710, H: 750, D: 585, top: "rails", shelves: 1, doors: [[340, 750, 2]], handle: "sinnai", rodabase: true },
  { id: "AS5", nome: "Serviços - gaveta sob bancada 675x230", src: "p.6-7", cor: "branco", W: 675, H: 230, D: 585, top: "none", fronts: [[675, 230, 1]], handle: "sinnai", back: false },
  // ---------- DESPENSA (p.5) ----------
  { id: "DP", nome: "Despensa cozinha (2 portas 485x2380)", src: "p.5", cor: "tauari", W: 1000, H: 2460, D: 600, shelves: 5, doors: [[485, 2380, 2]], handle: "none", assumed: ["Despensa: puxador = cava circular (sem ferragem)"] },
  // ---------- GOURMET (p.12-13) ----------
  { id: "G1", nome: "Gourmet - inferior sálvia (4 portas 435x745)", src: "p.12-13", cor: "salvia", W: 1740, H: 745, D: 600, top: "rails", dividers: 3, shelves: 2, doors: [[435, 745, 4]], handle: "sinnai", rodabase: true, assumed: ["Gourmet inferior: profundidade não informada; assumido 60 cm", "Gourmet inferior: 3 divisórias e 2 prateleiras assumidas"] },
  { id: "G2", nome: "Gourmet - superior com portas de vidro", src: "p.12-13", cor: "tauari", W: 922, H: 820, D: 340, shelves: 2, handle: "sinnai", extraHandles: 2, extraHinges: 4, assumed: [`Gourmet superior: ${D_SUP}`],
    extras: [X("vidro-canelado", m2(461, 820, 2)), X("led", 0.922)] },
  // ---------- LAVABO (p.14-15) ----------
  { id: "LV", nome: "Gabinete lavabo (suspenso)", src: "p.14-15", cor: "tauari", t: 18, W: 1420, H: 440, D: 345, top: "rails", dividers: 1, doors: [[380, 440, 2]], handle: "none", assumed: ["Lavabo: espessura 18 mm (cota 18 no desenho)", "Lavabo: puxador = cava circular"] },
  // ---------- BANHO HOME OFFICE (p.19-20) ----------
  { id: "BHO", nome: "Banho home office - gabinete", src: "p.19-20", cor: "tauari", W: 735, H: 500, D: 340, top: "rails", doors: [[367, 500, 2]], handle: "sinnai" },
  // ---------- BANHO MASTER (p.21-22) ----------
  { id: "BM1", nome: "Banho master - gabinete", src: "p.21-22", cor: "tauari", W: 920, H: 500, D: 540, top: "rails", doors: [[460, 500, 2]], handle: "sinnai" },
  { id: "BM2", nome: "Banho master - espelheira (nichos)", src: "p.21-22", cor: "tauari", W: 690, H: 940, D: 150, shelves: 3, handle: "none", assumed: ["Espelheira: 4 nichos de 216 mm => 3 prateleiras internas"] },
  { id: "BM3", nome: "Banho master - caixa da espelheira (atrás dos espelhos)", src: "p.21-22", cor: "branco", W: 920, H: 940, D: 150, handle: "none", assumed: ["Espelheira: caixa atrás dos espelhos não detalhada; assumida em MDF branco 15 com fundo"],
    extras: [X("espelho-cristal", m2(460, 940, 2)), X("estrutura-espelho", 1, "regra")] },
  // ---------- HOME OFFICE (p.16-18) ----------
  { id: "HO1", nome: "Home office - armário 4 portas (areia)", src: "p.16-18", cor: "areia", W: 1580, H: 2400, D: 640, dividers: 1, shelves: 2, shelves25: 6,
    doors: [[396, 2400, 4]], fronts: [[750, 200, 6]], handle: "none",
    assumed: ["Home office: espessura de 25 mm indicada nas prateleiras; assumida MDF 25 mm", "Home office: puxador = tiras de MDF tauari 1100 mm (ver peças)", "Home office: gavetas internas sem puxador (atrás das portas)"] },
  { id: "HO2", nome: "Home office - gaveteiro suspenso (2 gavetas)", src: "p.16", cor: "tauari", W: 1410, H: 120, D: 500, top: "none", fronts: [[680, 120, 2]], handle: "none", assumed: ["Home office gaveteiro/tampo: profundidade não informada; assumido 50 cm", "Home office gaveteiro: 'pega por baixo' (sem puxador)"] },
  // ---------- CLOSET (p.23-25) ----------
  { id: "CL1", nome: "Closet - módulo interno 1960", src: "p.23-25", cor: "tauari", W: 1960, H: 2360, D: 620, dividers: 1, shelves: 2, shelves25: 6, fronts: [[950, 200, 6], [950, 150, 2]], handle: "none",
    assumed: ["Closet: gavetas internas sem puxador listado", "Closet: sapateiras de correr tratadas como gavetas de 150 mm"] },
  { id: "CL2", nome: "Closet espelho - módulo 1160", src: "p.26-28", cor: "tauari", W: 1160, H: 2360, D: 610, shelves25: 3, handle: "none",
    assumed: ["Closet espelho: portas de correr de espelho (2x580x2360) + trilho: item de terceiros"],
    extras: [X("espelho-cristal", m2(580, 2360, 2)), X("estrutura-espelho", 2, "regra"), X("sistema-correr", 1, "regra"), X("spot", 5)] },
];

const D = (id: string, nome: string, src: string, W: number, H: number, Dp: number) => mod(id, nome, src, W, H, Dp);
const customs: Piece[] = [
  // Estante (p.8-9): 50/100 mm laminados em MDF 25
  ...custom(D("EST", "Estante 2160x2380x480", "p.8-9", 2160, 2380, 480), [
    { label: "Topo 100mm (4 camadas 25)", mat: "tauari25", w: 2160, h: 480, qty: 4 },
    { label: "Base 100mm (4 camadas 25)", mat: "tauari25", w: 2160, h: 480, qty: 4 },
    { label: "Prateleira 50mm (2 camadas 25)", mat: "tauari25", w: 2160, h: 480, qty: 8 },
    { label: "Vertical 50mm (2 camadas 25)", mat: "tauari25", w: 396, h: 480, qty: 16 },
  ]),
  ...custom(D("RK", "Rack 2120x330x500 + prateleira", "p.10-11", 2120, 330, 500), [
    { label: "Prateleira 50mm (2 camadas 25)", mat: "tauari25", w: 2120, h: 370, qty: 2 },
    { label: "Tampo rack 18", mat: "tauari18", w: 2120, h: 500 }, { label: "Base rack 18", mat: "tauari18", w: 2120, h: 500 },
    { label: "Lateral curva 18", mat: "tauari18", w: 294, h: 500, qty: 2 },
    { label: "Divisória 18 (derivada)", mat: "tauari18", w: 294, h: 480, qty: 2, origin: "regra" },
  ]),
  ...custom(D("RKG", "Rack - gavetas", "p.10-11", 2120, 330, 500), [
    { label: "Frente gaveta 573x294", mat: "tauari18", w: 573, h: 294, qty: 3, kind: "drawer_front" },
    { label: "Gaveta lateral", mat: "branco15", w: 450, h: 244, qty: 6, grain: "none", origin: "regra", band: false },
    { label: "Gaveta frente/traseira", mat: "branco15", w: 513, h: 244, qty: 6, origin: "regra", band: false },
    { label: "Gaveta fundo", mat: "branco6", w: 543, h: 450, qty: 3, origin: "regra", band: false },
    { label: "Fundo rack (derivado)", mat: "branco6", w: 1720, h: 294, origin: "regra", band: false },
  ]),
  ...custom(D("HOX", "Home office - prateleira, tampo e puxadores", "p.16-18", 1410, 50, 350), [
    { label: "Prateleira flutuante 50mm (2x25) 1410x350", mat: "tauari25", w: 1410, h: 350, qty: 2, origin: "regra" },
    { label: "Tampo gaveteiro 25mm 1410x500", mat: "tauari25", w: 1410, h: 500 },
    { label: "Puxador-tira 1100", mat: "tauari15", w: 60, h: 1100, qty: 2, grain: "h" },
  ]),
  ...custom(D("CLP", "Closet - portas shaker (4x483x2360)", "p.23", 483, 2360, 18), [
    { label: "Montante 80x2360", mat: "tauari15", w: 80, h: 2360, qty: 8, grain: "h" },
    { label: "Travessa 323x80", mat: "tauari15", w: 323, h: 80, qty: 12 },
    { label: "Painel inferior 323x580", mat: "tauari15", w: 323, h: 580, qty: 4, grain: "h" },
    { label: "Painel de fechamento 120x2440", mat: "tauari15", w: 120, h: 2440, grain: "h" },
  ]),
  ...custom(D("CLN", "Closet espelho - nicho lateral 250", "p.26-28", 250, 2440, 610), [
    { label: "Prateleira 40mm (25+15) camada 25", mat: "tauari25", w: 250, h: 610, qty: 6 },
    { label: "Prateleira 40mm (25+15) camada 15", mat: "tauari15", w: 250, h: 610, qty: 6 },
    { label: "Vertical 40mm camada 25", mat: "tauari25", w: 2440, h: 610, origin: "regra" },
    { label: "Vertical 40mm camada 15", mat: "tauari15", w: 2440, h: 610, origin: "regra" },
  ]),
  ...custom(D("CM", "Cama de casal 1940x1440x200", "p.29", 1940, 200, 1440), [
    { label: "Lateral 25 (longa)", mat: "areia25", w: 1940, h: 200, qty: 2 },
    { label: "Lateral 25 (curta)", mat: "areia25", w: 1390, h: 200, qty: 2 },
    { label: "Tampo da cama 15 (derivado)", mat: "areia15", w: 1940, h: 1440, origin: "regra" },
  ]),
  ...custom(D("MC", "Mesa de cabeceira x2 (500x340)", "p.30", 500, 340, 350), [
    { label: "Tampo/base 18", mat: "areia18", w: 500, h: 350, qty: 4 },
    { label: "Lateral 18", mat: "areia18", w: 300, h: 350, qty: 4 },
    { label: "Prateleira/plataforma 18", mat: "areia18", w: 460, h: 330, qty: 2, origin: "regra" },
    { label: "Frente gaveta 18 (moldura)", mat: "tauari18", w: 460, h: 150, qty: 2, kind: "drawer_front" },
  ]),
  ...custom(D("ESC", "Escrivaninha 1960 + gaveteiro 600", "p.31-32", 1960, 780, 550), [
    { label: "Tampo 50mm (2x25) 1960x550", mat: "tauari25", w: 1960, h: 550, qty: 2 },
    { label: "Lateral gaveteiro 18", mat: "areia18", w: 550, h: 730, qty: 2, grain: "h", origin: "regra" },
    { label: "Base gaveteiro 18", mat: "areia18", w: 560, h: 550, origin: "regra" },
    { label: "Fundo gaveteiro 6", mat: "branco6", w: 596, h: 726, origin: "regra", band: false },
    { label: "Frente gaveta 560x178", mat: "areia18", w: 560, h: 178, qty: 4, kind: "drawer_front" },
    { label: "Gaveta lateral", mat: "branco15", w: 500, h: 128, qty: 8, origin: "regra", band: false },
    { label: "Gaveta frente/traseira", mat: "branco15", w: 490, h: 128, qty: 8, origin: "regra", band: false },
    { label: "Gaveta fundo", mat: "branco6", w: 520, h: 500, qty: 4, origin: "regra", band: false },
  ]),
  ...custom(D("CAB", "Cabeceira ripada 2590x1050", "p.33", 2590, 1050, 38), [
    { label: "Base 18", mat: "tauari18", w: 2590, h: 1050 },
    { label: "Ripa 18x20 (112 un)", mat: "tauari18", w: 20, h: 1050, qty: 112, grain: "h", band: false },
  ]),
  ...custom(D("CG", "Caminha de gato x3 (350x550x50)", "p.34", 350, 50, 550), [
    { label: "Fundo 18", mat: "areia18", w: 550, h: 350, qty: 3 },
    { label: "Moldura lateral longa 18x32", mat: "areia18", w: 550, h: 32, qty: 6 },
    { label: "Moldura lateral curta 18x32", mat: "areia18", w: 314, h: 32, qty: 6 },
  ]),
];
// peças do gaveteiro com dimensões "kind: drawer_front" já são frentes; mantêm-se como estão.

const customExtras: Extra[] = [
  X("spot", 10), X("cnc-oval", 8, "regra"), X("pezinho", 4 /*rack*/ + 4 /*cama*/ + 8 /*cabeceira x2*/, "regra"),
  X("led", 2.05), X("led", 1.41), X("led", 2.59),
  X("ripado", m2(690, 940) + m2(758, 820), "regra"),
  X("palhinha", m2(323, 1540, 4) + 0.08, "regra"), X("calha", 1), X("estofado", 3), X("puxador-madeira", 2),
];
const customHardware: { id: string; qty: number }[] = [
  { id: "handle-travertino", qty: 3 /*rack*/ + 4 /*closet*/ + 4 /*escrivaninha*/ },
  { id: "hinge", qty: 20 /*closet 4x5*/ },
  { id: "slide", qty: 3 + 4 + 2 /*rack, escrivaninha, home office mesa*/ },
];

// ---------- monta projeto ----------
const expanded = specs.map(expand);
const pieces: Piece[] = [...expanded.flatMap((e) => e.pieces), ...customs];
const allExtras = [...expanded.flatMap((e) => e.extras), ...customExtras];
const hwMap = new Map<string, { name: string; qty: number }>();
for (const e of expanded) for (const h of e.hardware) { const k = h.id.startsWith("slide-") ? "slide" : h.id; hwMap.set(k, { name: prices.hardware[k]?.name ?? h.name, qty: (hwMap.get(k)?.qty ?? 0) + h.qty }); }
for (const c of customHardware) hwMap.set(c.id, { name: prices.hardware[c.id].name, qty: (hwMap.get(c.id)?.qty ?? 0) + c.qty });

const materials: Material[] = Object.entries(prices.materials).map(([id, v]: any) => {
  const t = Number(id.match(/(\d+)$/)![1]);
  return { id, name: v.name, thickness: t, sheetLength: 2750, sheetWidth: 1840, pricePerSheet: v.price, hasGrain: id.startsWith("tauari") };
});
const edgeBands = Object.entries(prices.bands).map(([id, v]: any) => ({ id, name: v.name, pricePerMeter: v.price }));
const hardware: HardwareItem[] = [...hwMap.entries()].map(([id, v]) => ({ id, name: v.name, qty: v.qty, unitPrice: prices.hardware[id].price, derived: true }));
const extrasAgg = new Map<string, ExtraItem>();
for (const e of allExtras) {
  const cur = extrasAgg.get(e.id);
  extrasAgg.set(e.id, { id: e.id, name: prices.extras[e.id].name, unit: prices.extras[e.id].unit, unitPrice: prices.extras[e.id].price, origin: cur?.origin === "regra" || e.origin === "regra" ? "regra" : "pdf", qty: Math.round(((cur?.qty ?? 0) + e.qty) * 1000) / 1000 });
}
const assumptions = [
  "Espessura do corpo 15 mm: indício pelas cotas '15' dos desenhos (lavabo usa 18). CONFIRMAR.",
  "Fundos em MDF branco 6 mm; caixas de gaveta em MDF branco 15 mm; corrediça telescópica. CONFIRMAR.",
  "Portas sobrepostas (corpo recuado pela espessura da porta); portas com dimensões lidas do PDF.",
  "MDF Tauari tem veio: portas/laterais com veio na vertical, tampos/prateleiras na horizontal.",
  "Peças de 40/50/100 mm: laminadas em MDF 25 (e 15) - sistema construtivo não especificado. CONFIRMAR.",
  "Bancadas de pedra, vidros de box, eletrodomésticos e a instalação elétrica NÃO estão no orçamento (fora do escopo de marcenaria).",
  "Fita de LED da banho master é fornecida pela cliente (nota p.21): excluída.",
  ...expanded.flatMap((e) => e.assumptions),
];
const project: Project = { name: "Marcela e Gustavo - Detalhamento de marcenaria (Fernanda Sertório)", materials, edgeBands, pieces, hardware, extras: [...extrasAgg.values()], derivedHardware: true, assumptions } as Project & { derivedHardware: boolean };

const c = prices.cost;
const report = run(project, { laborPerSqm: c.laborPerSqm, extraCosts: c.extraCosts, overheadPct: c.overheadPct, marginPct: c.marginPct });
mkdirSync(new URL("./out/", import.meta.url), { recursive: true });
writeFileSync(new URL("./out/orcamento.json", import.meta.url), JSON.stringify({ project, report, prices }, null, 1));
const b = report.budget;
console.log("peças (linhas):", pieces.length, "| peças (unid.):", pieces.reduce((a, p) => a + p.qty, 0));
console.log("issues bloqueantes:", report.issues.filter((i) => i.severity === "blocking").map((i) => i.message));
for (const pl of report.plans) console.log(pl.materialId.padEnd(9), "líquido", (pl.netArea / 1e6).toFixed(2), "m² | chapas", pl.sheets.length, "| aprov.", (pl.utilization * 100).toFixed(0) + "%");
console.log(b);
