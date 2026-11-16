import { loadConfig, type Config } from "./config.js";
import type { GrainAlong, Piece, PieceKind } from "./types.js";

export type Handle = "sinnai" | "travertino" | "none";
export interface Extra { id: string; name: string; qty: number; unit: string; origin: "pdf" | "regra" }

/** Descrição de um módulo (armário/gabinete). Cotas lidas do PDF entram como `pdf`; o resto vem das regras de config/fabricacao.json. */
export interface CabSpec {
  id: string; nome: string; src: string;
  /** cor base do catálogo: tauari | areia | tijolo | salvia | branco ... */
  cor: string;
  t?: number;             // espessura do corpo (padrão: config.espessuras.corpo)
  W: number; H: number; D: number;
  qty?: number;
  top?: "full" | "rails" | "none";
  base?: boolean; back?: boolean;
  dividers?: number;
  shelves?: number;       // prateleiras na espessura do corpo
  shelves25?: number;     // prateleiras na espessura "grossa" da config
  shelfDepthCut?: number; // sobrescreve o recuo de prateleira da config
  doors?: [number, number, number][];   // [w,h,qty] lidas do PDF
  fronts?: [number, number, number][];  // frentes de gaveta [w,h,qty]
  handle?: Handle;
  extraHandles?: number;
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

let cached: Config | undefined;
export const defaultConfig = (): Config => (cached ??= loadConfig());

type ModInfo = { id: string; nome: string; src: string; W: number; H: number; D: number };
function mk(spec: ModInfo, o: Partial<Piece> & Pick<Piece, "label" | "kind" | "materialId" | "w" | "h">, n = 1): Piece {
  return {
    id: `${spec.id}-${o.label}`.replace(/\s+/g, "_"), qty: n, origin: "regra", source: spec.src,
    module: spec.nome, moduleDims: { W: spec.W, H: spec.H, D: spec.D }, ...o,
  } as Piece;
}

/** Utilitários derivados da configuração. */
function helpers(cfg: Config) {
  const mats = new Map(cfg.catalogo.materiais.map((m) => [m.id, m]));
  const fab = cfg.fabricacao;
  const bandOf = (mat: string) => mats.get(mat)?.fitaId ?? `fita-${mat.replace(/\d+$/, "")}`;
  const isWood = (mat: string) => mats.get(mat)?.veio ?? false;
  const edgesFor = (tipo: string, band: string) => {
    const lados = fab.fitaPorTipo[tipo] ?? [];
    return lados.length ? { ...Object.fromEntries(lados.map((l) => [l, true])), bandId: band } : undefined;
  };
  const grain = (mat: string, tipo: string): GrainAlong => (isWood(mat) ? ((fab.veioMadeira[tipo] ?? "w") as GrainAlong) : "none");
  const hingesFor = (h: number) => fab.dobradica.porAltura.find((f) => f.alturaMax === null || h <= f.alturaMax)!.qtd;
  const hwName = (id: string) => cfg.catalogo.ferragens.find((f) => f.id === id)?.nome ?? id;
  return { mats, fab, bandOf, isWood, edgesFor, grain, hingesFor, hwName };
}

export function expand(s: CabSpec, cfg: Config = defaultConfig()): Expanded {
  const { mats, fab, bandOf, edgesFor, grain, hingesFor, hwName } = helpers(cfg);
  const e = fab.espessuras;
  const t = s.t ?? e.corpo, q = s.qty ?? 1;
  const mat = `${s.cor}${t}`, mat25 = `${s.cor}${e.prateleiraGrossa}`;
  const matFundo = `${fab.corInterna}${e.fundo}`, matCaixa = `${fab.corInterna}${e.caixaGaveta}`, matRoda = `${fab.corInterna}${e.rodabase}`;
  const band = bandOf(mat);
  const P: Piece[] = [], hw = new Map<string, HwLine>(), as: string[] = [...(s.assumed ?? [])];
  const addHw = (id: string, name: string, n: number) => { if (n > 0) hw.set(id, { id, name, qty: (hw.get(id)?.qty ?? 0) + n * q }); };
  const hasFront = !!(s.doors?.length || s.fronts?.length);
  const Dc = hasFront && fab.montagem.portaSobreposta ? s.D - t : s.D; // corpo recuado pela espessura da porta
  const Wi = s.W - 2 * t;
  const add = (o: Parameters<typeof mk>[1], n = 1) => P.push(mk(s, o, n * q));

  add({ label: "Lateral", kind: "lateral", materialId: mat, w: Dc, h: s.H, grainAlong: grain(mat, "lateral"), edges: edgesFor("lateral", band) }, 2);
  if (s.base !== false) add({ label: "Base", kind: "base", materialId: mat, w: Wi, h: Dc, grainAlong: grain(mat, "base"), edges: edgesFor("base", band) });
  const top = s.top ?? "full";
  if (top === "full") add({ label: "Topo", kind: "top", materialId: mat, w: Wi, h: Dc, grainAlong: grain(mat, "topo"), edges: edgesFor("topo", band) });
  if (top === "rails" && fab.montagem.travessas.quantidade > 0)
    add({ label: "Travessa", kind: "other", materialId: mat, w: Wi, h: fab.montagem.travessas.altura, grainAlong: grain(mat, "travessa") }, fab.montagem.travessas.quantidade);
  if (s.dividers) add({ label: "Divisória", kind: "divider", materialId: mat, w: Dc, h: s.H - 2 * t, grainAlong: grain(mat, "divisoria"), edges: edgesFor("divisoria", band) }, s.dividers);
  const cut = s.shelfDepthCut ?? fab.montagem.recuoPrateleira;
  if (s.shelves) add({ label: "Prateleira", kind: "shelf", materialId: mat, w: Wi, h: Dc - cut, grainAlong: grain(mat, "prateleira"), adjustable: s.adjustable, edges: edgesFor("prateleira", band) }, s.shelves);
  if (s.shelves25) add({ label: `Prateleira ${e.prateleiraGrossa}mm`, kind: "shelf", materialId: mat25, w: Wi, h: Dc - cut, grainAlong: grain(mat25, "prateleira"), edges: edgesFor("prateleira", bandOf(mat25)) }, s.shelves25);

  if (s.back !== false) {
    // Fundo maior que a chapa (área útil) é emendado em k partes iguais, se a config permitir.
    const bw = s.W - fab.fundo.folgaLargura, bh = s.H - fab.fundo.folgaAltura;
    const ch = mats.get(matFundo)?.chapa;
    let k = 1;
    if (ch && fab.fundo.emendarSeMaiorQueChapa) {
      const L = ch.comprimento - 2 * fab.corte.refilo, Wd = ch.largura - 2 * fab.corte.refilo;
      while (k < 6 && Math.min(bw / k, bh) > Wd) k++;
      void L;
    }
    if (k > 1) as.push(`${s.nome}: fundo ${bw}x${bh} não cabe na chapa; emendado em ${k} partes (confirmar).`);
    add({ label: k > 1 ? `Fundo (1/${k})` : "Fundo", kind: "back", materialId: matFundo, w: Math.ceil(bw / k), h: bh, grainAlong: "none" }, k);
  }

  let hinges = 0, handles = 0;
  for (const [w, h, n] of s.doors ?? []) {
    add({ label: `Porta ${w}x${h}`, kind: "door", materialId: mat, w, h, grainAlong: grain(mat, "porta"), origin: "pdf", edges: edgesFor("porta", band) }, n);
    hinges += n * hingesFor(h); handles += n;
  }
  const cd = fab.corredica;
  for (const [fw, fh, n] of s.fronts ?? []) {
    add({ label: `Frente gaveta ${fw}x${fh}`, kind: "drawer_front", materialId: mat, w: fw, h: fh, grainAlong: grain(mat, "frenteGaveta"), origin: "pdf", edges: edgesFor("frenteGaveta", band) }, n);
    handles += n;
    const L = [...cd.comprimentos].reverse().find((x) => x <= Dc - cd.folgaTraseira) ?? cd.comprimentos[0];
    const hb = Math.max(cd.alturaCaixaMin, fh - cd.alturaCaixaMenosFrente), Wb = fw - cd.larguraCaixaMenosFrente;
    const bandCx = bandOf(matCaixa);
    add({ label: `Gaveta lateral ${fw}x${fh}`, kind: "drawer_part", materialId: matCaixa, w: L, h: hb, grainAlong: "none", edges: edgesFor("lateralGaveta", bandCx) }, 2 * n);
    add({ label: `Gaveta frente/traseira ${fw}x${fh}`, kind: "drawer_part", materialId: matCaixa, w: Wb - 2 * e.caixaGaveta, h: hb, grainAlong: "none" }, 2 * n);
    add({ label: `Gaveta fundo ${fw}x${fh}`, kind: "back", materialId: matFundo, w: Wb, h: L, grainAlong: "none" }, n);
    addHw(`${cd.ferragemId}-${L}`, `${hwName(cd.ferragemId)} ${L} mm`, n);
  }
  if (s.rodabase) {
    const r = fab.montagem.rodabase;
    add({ label: "Rodabase frente", kind: "other", materialId: matRoda, w: s.W, h: r.altura, grainAlong: "none" });
    add({ label: "Rodabase lateral", kind: "other", materialId: matRoda, w: Math.max(100, s.D - r.recuoFrente), h: r.altura, grainAlong: "none" }, 2);
    as.push(`${s.nome}: rodabase ${r.altura} mm montada pela marcenaria (nota do projeto); estrutura em U assumida em ${matRoda}.`);
  }
  addHw(fab.dobradica.ferragemId, hwName(fab.dobradica.ferragemId), hinges + (s.extraHinges ?? 0));
  const hd = s.handle ?? "none";
  if (hd !== "none") addHw(`handle-${hd}`, hwName(`handle-${hd}`), handles + (s.extraHandles ?? 0));
  if (s.shelves && s.adjustable) addHw(fab.pinoPrateleira.ferragemId, hwName(fab.pinoPrateleira.ferragemId), s.shelves * fab.pinoPrateleira.porPrateleiraRegulavel);
  const extras = (s.extras ?? []).map((x) => ({ ...x, qty: x.qty * q }));
  void mats;
  return { pieces: P, hardware: [...hw.values()], extras, assumptions: as };
}

/** Peças explícitas (lidas do PDF), usando fita e veio do catálogo. */
export function custom(mod: ModInfo, list: Custom[], cfg: Config = defaultConfig()): Piece[] {
  const { bandOf, isWood, edgesFor } = helpers(cfg);
  return list.map((c) => ({
    ...mk(mod, {
      label: c.label, kind: c.kind ?? "other", materialId: c.mat, w: c.w, h: c.h, qty: c.qty ?? 1,
      grainAlong: isWood(c.mat) ? (c.grain ?? "w") : "none", origin: c.origin ?? "pdf", source: c.src,
    }),
    edges: c.band === false ? undefined : edgesFor("prateleira", bandOf(c.mat)),
  }));
}
