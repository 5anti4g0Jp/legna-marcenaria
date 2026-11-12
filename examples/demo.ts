import { run } from "../src/engine.js";
import { renderReport } from "../src/report.js";
import type { Project } from "../src/types.js";

// DADOS FICTÍCIOS de exemplo: balcão de cozinha 1200 x 870 x 560.
const edge = { w1: true, w2: true, h1: true, h2: true, bandId: "fita-branca" };
const p: Project = {
  name: "Balcão cozinha 1200 (EXEMPLO)",
  materials: [
    { id: "mdf15", name: "MDF 15 branco", thickness: 15, sheetLength: 2750, sheetWidth: 1840, pricePerSheet: 280, hasGrain: false },
    { id: "mdf6", name: "MDF 6 fundo", thickness: 6, sheetLength: 2750, sheetWidth: 1840, pricePerSheet: 120, hasGrain: false },
  ],
  edgeBands: [{ id: "fita-branca", name: "Fita 22mm branca", pricePerMeter: 1.8 }],
  pieces: [
    { id: "L", label: "Lateral", kind: "lateral", materialId: "mdf15", w: 800, h: 560, qty: 2, edges: { w1: true, bandId: "fita-branca" }, source: "p.2 corte AA" },
    { id: "B", label: "Base", kind: "base", materialId: "mdf15", w: 1170, h: 540, qty: 1, edges: { w1: true, bandId: "fita-branca" }, source: "p.2 corte AA" },
    { id: "T", label: "Travessa", kind: "other", materialId: "mdf15", w: 1170, h: 100, qty: 2, source: "p.2 vista superior" },
    { id: "P", label: "Prateleira regulável", kind: "shelf", materialId: "mdf15", w: 1166, h: 520, qty: 1, adjustable: true, edges: { w1: true, bandId: "fita-branca" }, source: "p.2 corte AA" },
    { id: "D", label: "Porta", kind: "door", materialId: "mdf15", w: 596, h: 710, qty: 2, edges: edge, source: "p.3 elevação" },
    { id: "G", label: "Frente gaveta", kind: "drawer_front", materialId: "mdf15", w: 1196, h: 140, qty: 1, edges: edge, source: "p.3 elevação" },
    { id: "F", label: "Fundo", kind: "back", materialId: "mdf6", w: 1190, h: 790, qty: 1, source: "p.2 corte AA" },
  ],
  hardware: [{ id: "parafuso", name: "Parafuso confirmat 7x50", qty: 32, unitPrice: 0.35 }],
  priceBook: { hingeUnitPrice: 6, slidePairUnitPrice: 45, handleUnitPrice: 18, shelfPinUnitPrice: 0.5 },
};
const cost = { laborPerSqm: 220, extraCosts: 120, overheadPct: 0.12, marginPct: 0.35 };
console.log(renderReport(p, run(p, cost)));
console.log("\n\n--- Mesmo projeto com uma dúvida pendente da extração ---\n");
const q = { ...p, pendingQuestions: ["Espessura do fundo não aparece no PDF (6 mm ou 3 mm?)"] };
console.log(renderReport(q, run(q, cost)));
