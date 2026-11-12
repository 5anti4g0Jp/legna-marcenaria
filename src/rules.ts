import { HINGE_RULES, SHELF_PINS_PER_ADJUSTABLE_SHELF } from "./hardware.js";
import type { GrainAlong, Piece, PieceKind } from "./types.js";

export type Handle = "sinnai" | "travertino" | "none";
export interface Extra { id: string; name: string; qty: number; unit: string; origin: "pdf" | "regra" }
export interface Door { w: number; h: number; qty: number }

/** Descrição de um módulo (armário/gabinete). Cotas de PDF entram como `pdf`; o resto é regra. */
export interface CabSpec {
  id: string; nome: string; src: string;
  /** cor base: tauari | areia | tijolo | salvia | branco */
  cor: string;
  t?: number;             // espessura do corpo (padrão 15)
  W: number; H: number; D: number;
  qty?: number;
  top?: "full" | "rails" | "none";
  base?: boolean; back?: boolean;
  dividers?: number;
  shelves?: number;       // prateleiras na espessura do corpo
  shelves25?: number;     // prateleiras em 25 mm
  shelfDepthCut?: number; // recuo da prateleira (padrão 20)
  doors?: [number, number, number][];   // [w,h,qty] lidas do PDF
  fronts?: [number, number, number][];  // frentes de gaveta [w,h,qty]
  handle?: Handle;
  extraHandles?: number;  // puxadores adicionais (ex.: portas de vidro)
  extraHinges?: number;
  rodabase?: boolean;
  adjustable?: boolean;
  assumed?: string[];     // premissas assumidas neste módulo
  extras?: Extra[];
}

export interface Custom {
  label: string; kind?: PieceKind; mat: string; w: number; h: number; qty?: number;
  grain?: GrainAlong; band?: boolean; src: string; origin?: "pdf" | "regra";
}

export interface HwLine { id: string; name: string; qty: number }
export interface Expanded { pieces: Piece[]; hardware: HwLine[]; extras: Extra[]; assumptions: string[] }

const SLIDES = [250, 300, 350, 400, 450, 500, 550];
const bandOf = (mat: string) => `fita-${mat.replace(/\d+$/, "")}`;
const isWood = (mat: string) => mat.startsWith("tauari");

function mk(spec: { id: string; nome: string; src: string; W: number; H: number; D: number }, o: Partial<Piece> & Pick<Piece, "label" | "kind" | "materialId" | "w" | "h">, n = 1): Piece {
  return {
    id: `${spec.id}-${o.label}`.replace(/\s+/g, "_"), qty: n, origin: "regra", source: spec.src,
    module: spec.nome, moduleDims: { W: spec.W, H: spec.H, D: spec.D }, ...o,
  } as Piece;
}

export function expand(s: CabSpec): Expanded {
  const t = s.t ?? 15, q = s.qty ?? 1;
  const mat = `${s.cor}${t}`, mat25 = `${s.cor}25`, wood = isWood(s.cor);
  const g = (a: GrainAlong): GrainAlong => (wood ? a : "none");
  const band = bandOf(mat);
  const P: Piece[] = [], hw = new Map<string, HwLine>(), as: string[] = [...(s.assumed ?? [])];
  const addHw = (id: string, name: string, n: number) => { if (n > 0) hw.set(id, { id, name, qty: (hw.get(id)?.qty ?? 0) + n * q }); };
  const hasFront = !!(s.doors?.length || s.fronts?.length);
  const Dc = hasFront ? s.D - t : s.D;               // corpo recuado pela espessura da porta
  const Wi = s.W - 2 * t;
  const add = (o: Parameters<typeof mk>[1], n = 1) => P.push(mk(s, o, n * q));

  add({ label: "Lateral", kind: "lateral", materialId: mat, w: Dc, h: s.H, grainAlong: g("h"), edges: { h1: true, bandId: band } }, 2);
  if (s.base !== false) add({ label: "Base", kind: "base", materialId: mat, w: Wi, h: Dc, grainAlong: g("w"), edges: { w1: true, bandId: band } });
  const top = s.top ?? "full";
  if (top === "full") add({ label: "Topo", kind: "top", materialId: mat, w: Wi, h: Dc, grainAlong: g("w"), edges: { w1: true, bandId: band } });
  if (top === "rails") add({ label: "Travessa", kind: "other", materialId: mat, w: Wi, h: 100, grainAlong: g("w") }, 2);
  if (s.dividers) add({ label: "Divisória", kind: "divider", materialId: mat, w: Dc, h: s.H - 2 * t, grainAlong: g("h"), edges: { h1: true, bandId: band } }, s.dividers);
  const cut = s.shelfDepthCut ?? 20;
  if (s.shelves) add({ label: "Prateleira", kind: "shelf", materialId: mat, w: Wi - (s.dividers ? 0 : 0), h: Dc - cut, grainAlong: g("w"), adjustable: s.adjustable, edges: { w1: true, bandId: band } }, s.shelves);
  if (s.shelves25) add({ label: "Prateleira 25mm", kind: "shelf", materialId: mat25, w: Wi, h: Dc - cut, grainAlong: g("w"), edges: { w1: true, bandId: bandOf(mat25) } }, s.shelves25);
  if (s.back !== false) {
    // Fundo maior que a chapa (usável 2730x1820) é emendado em k partes iguais.
    const bw = s.W - 4, bh = s.H - 4;
    let k = 1;
    while (Math.min(bw / k, bh) > 1820 && Math.max(bw / k, bh) <= 2730 || (Math.min(bw / k, bh) > 1820 && k < 6)) k++;
    if (k > 1) as.push(`${s.nome}: fundo ${bw}x${bh} não cabe na chapa; emendado em ${k} partes (confirmar).`);
    add({ label: k > 1 ? `Fundo (1/${k})` : "Fundo", kind: "back", materialId: "branco6", w: Math.ceil(bw / k), h: bh, grainAlong: "none" }, k);
  }

  let hinges = 0, handles = 0;
  for (const [w, h, n] of s.doors ?? []) {
    add({ label: `Porta ${w}x${h}`, kind: "door", materialId: mat, w, h, grainAlong: g("h"), origin: "pdf", edges: { w1: true, w2: true, h1: true, h2: true, bandId: band } }, n);
    hinges += n * HINGE_RULES.find((r) => h <= r.maxHeight)!.hinges; handles += n;
  }
  for (const [fw, fh, n] of s.fronts ?? []) {
    add({ label: `Frente gaveta ${fw}x${fh}`, kind: "drawer_front", materialId: mat, w: fw, h: fh, grainAlong: g("w"), origin: "pdf", edges: { w1: true, w2: true, h1: true, h2: true, bandId: band } }, n);
    handles += n;
    const L = [...SLIDES].reverse().find((x) => x <= Dc - 50) ?? 250;
    const hb = Math.max(80, fh - 50), Wb = fw - 40;
    add({ label: `Gaveta lateral ${fw}x${fh}`, kind: "drawer_part", materialId: "branco15", w: L, h: hb, grainAlong: "none", edges: { w1: true, bandId: "fita-branco" } }, 2 * n);
    add({ label: `Gaveta frente/traseira ${fw}x${fh}`, kind: "drawer_part", materialId: "branco15", w: Wb - 30, h: hb, grainAlong: "none" }, 2 * n);
    add({ label: `Gaveta fundo ${fw}x${fh}`, kind: "back", materialId: "branco6", w: Wb, h: L, grainAlong: "none" }, n);
    addHw(`slide-${L}`, `Corrediça telescópica ${L} mm (par)`, n);
  }
  if (s.rodabase) {
    add({ label: "Rodabase frente", kind: "other", materialId: "branco15", w: s.W, h: 150, grainAlong: "none" });
    add({ label: "Rodabase lateral", kind: "other", materialId: "branco15", w: Math.max(100, s.D - 100), h: 150, grainAlong: "none" }, 2);
    as.push(`${s.nome}: rodabase 150 mm montada pela marcenaria (nota do projeto); estrutura em U assumida em MDF 15 cru.`);
  }
  addHw("hinge", "Dobradiça com amortecimento", hinges + (s.extraHinges ?? 0));
  const hd = s.handle ?? "none";
  if (hd !== "none") addHw(`handle-${hd}`, hd === "sinnai" ? "Puxador Sinnai Il-808 25mm grafite" : "Puxador mármore travertino", handles + (s.extraHandles ?? 0));
  if (s.shelves && s.adjustable) addHw("shelf-pin", "Pino de prateleira", s.shelves * SHELF_PINS_PER_ADJUSTABLE_SHELF);
  const extras = (s.extras ?? []).map((e) => ({ ...e, qty: e.qty * q }));
  return { pieces: P, hardware: [...hw.values()], extras, assumptions: as };
}

/** Peças explícitas (lidas do PDF). `layers` laminam para atingir espessuras grandes (ex.: 50 = 2×25). */
export function custom(mod: { id: string; nome: string; src: string; W: number; H: number; D: number }, list: Custom[]): Piece[] {
  return list.map((c) => mk(mod, {
    label: c.label, kind: c.kind ?? "other", materialId: c.mat, w: c.w, h: c.h, qty: c.qty ?? 1,
    grainAlong: isWood(c.mat) ? (c.grain ?? "w") : "none", origin: c.origin ?? "pdf", source: c.src,
    edges: c.band === false ? undefined : { w1: true, bandId: bandOf(c.mat) },
  }));
}
