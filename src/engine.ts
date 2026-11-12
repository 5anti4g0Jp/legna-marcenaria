import { resolveHardware } from "./hardware.js";
import { nestMaterial } from "./nesting.js";
import type { Budget, CostConfig, CuttingConfig, Project, Report } from "./types.js";
import { validateProject } from "./validate.js";

export const DEFAULT_CUTTING: CuttingConfig = { kerf: 4, trim: 10, edgeWastePct: 0.1 };

export function edgeBandMeters(p: Project, wastePct: number) {
  const net: Record<string, number> = {};
  for (const pc of p.pieces) {
    const e = pc.edges;
    if (!e?.bandId) continue;
    const mm = ((e.w1 ? pc.w : 0) + (e.w2 ? pc.w : 0) + (e.h1 ? pc.h : 0) + (e.h2 ? pc.h : 0)) * pc.qty;
    net[e.bandId] = (net[e.bandId] ?? 0) + mm / 1000;
  }
  const out: Record<string, { net: number; purchased: number }> = {};
  for (const [id, m] of Object.entries(net))
    out[id] = { net: round2(m), purchased: Math.ceil(m * (1 + wastePct)) };
  return out;
}

export function computeBudget(p: Project, r: Omit<Report, "budget">, cost: CostConfig): Budget {
  const matPrice = new Map(p.materials.map((m) => [m.id, m.pricePerSheet]));
  const bandPrice = new Map(p.edgeBands.map((b) => [b.id, b.pricePerMeter]));
  const materials = r.plans.reduce((a, pl) => a + pl.sheets.length * (matPrice.get(pl.materialId) ?? 0), 0);
  const edgeBand = Object.entries(r.edgeBandMeters).reduce((a, [id, m]) => a + m.purchased * (bandPrice.get(id) ?? 0), 0);
  const hardware = r.hardware.reduce((a, h) => a + h.qty * h.unitPrice, 0);
  const netSqm = r.plans.reduce((a, pl) => a + pl.netArea, 0) / 1e6;
  const labor = netSqm * cost.laborPerSqm;
  const direct = materials + edgeBand + hardware + labor + cost.extraCosts;
  const overhead = direct * cost.overheadPct;
  const totalCost = direct + overhead;
  const suggestedPrice = cost.marginPct < 1 ? totalCost / (1 - cost.marginPct) : NaN;
  return {
    materials: round2(materials), edgeBand: round2(edgeBand), hardware: round2(hardware),
    labor: round2(labor), extras: round2(cost.extraCosts), overhead: round2(overhead),
    totalCost: round2(totalCost), margin: round2(suggestedPrice - totalCost), suggestedPrice: round2(suggestedPrice),
  };
}

/**
 * Pipeline determinístico. Se houver pendência bloqueante, NÃO calcula plano nem orçamento:
 * devolve só as issues, para o usuário confirmar.
 */
export function run(p: Project, cost: CostConfig, cutting: CuttingConfig = DEFAULT_CUTTING): Report {
  const issues = validateProject(p);
  if (issues.some((i) => i.severity === "blocking"))
    return { project: p.name, issues, plans: [], edgeBandMeters: {}, hardware: [] };

  const plans = p.materials
    .map((m) => ({ m, pcs: p.pieces.filter((x) => x.materialId === m.id) }))
    .filter((x) => x.pcs.length > 0)
    .map((x) => nestMaterial(x.m, x.pcs, cutting));
  const hw = resolveHardware(p);
  for (const h of hw.filter((h) => h.derived))
    issues.push({ severity: "warning", message: `Ferragem derivada por regra (confirmar): ${h.qty}x ${h.name}.` });

  const partial = { project: p.name, issues, plans, edgeBandMeters: edgeBandMeters(p, cutting.edgeWastePct), hardware: hw };
  return { ...partial, budget: computeBudget(p, partial, cost) };
}

const round2 = (n: number) => Math.round(n * 100) / 100;
