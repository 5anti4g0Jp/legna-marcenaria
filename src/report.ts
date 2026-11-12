import type { Project, Report } from "./types.js";

/** Relatório conferível peça por peça (Markdown). */
export function renderReport(p: Project, r: Report): string {
  const L: string[] = [`# Levantamento: ${r.project}`, ""];
  const blocking = r.issues.filter((i) => i.severity === "blocking");
  if (blocking.length) {
    L.push("## ⛔ Pendências bloqueantes (nada foi calculado)", ...blocking.map((i) => `- ${i.message}`), "");
    return L.join("\n");
  }
  const warn = r.issues.filter((i) => i.severity === "warning");
  if (warn.length) L.push("## ⚠ Avisos", ...warn.map((i) => `- ${i.message}`), "");

  L.push("## Peças (conferência)", "| ID | Peça | Material | w×h (mm) | Qtd | Fonte |", "|---|---|---|---|---|---|");
  for (const pc of p.pieces) L.push(`| ${pc.id} | ${pc.label} | ${pc.materialId} | ${pc.w}×${pc.h} | ${pc.qty} | ${pc.source ?? "—"} |`);

  L.push("", "## Chapas a comprar (líquido × comprado)");
  for (const pl of r.plans)
    L.push(`- ${pl.materialId}: líquido ${(pl.netArea / 1e6).toFixed(3)} m² · comprar ${pl.sheets.length} chapa(s) = ${(pl.purchasedArea / 1e6).toFixed(3)} m² · aproveitamento ${(pl.utilization * 100).toFixed(1)}%`);

  L.push("", "## Fita de borda (m)");
  for (const [id, m] of Object.entries(r.edgeBandMeters)) L.push(`- ${id}: líquido ${m.net} m · comprar ${m.purchased} m`);

  L.push("", "## Ferragens");
  for (const h of r.hardware) L.push(`- ${h.qty}× ${h.name}${h.derived ? " (derivado, confirmar)" : ""} — R$ ${(h.qty * h.unitPrice).toFixed(2)}`);

  if (r.budget) {
    const b = r.budget;
    L.push("", "## Orçamento",
      `- Chapas: R$ ${b.materials}`, `- Fita de borda: R$ ${b.edgeBand}`, `- Ferragens: R$ ${b.hardware}`,
      `- Mão de obra: R$ ${b.labor}`, `- Extras: R$ ${b.extras}`, `- Indiretos: R$ ${b.overhead}`,
      `- **Custo total: R$ ${b.totalCost}**`, `- Margem: R$ ${b.margin}`, `- **Preço sugerido: R$ ${b.suggestedPrice}**`);
  }
  return L.join("\n");
}
