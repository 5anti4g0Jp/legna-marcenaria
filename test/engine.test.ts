import { describe, expect, it } from "vitest";
import { computeBudget, DEFAULT_CUTTING, edgeBandMeters, run } from "../src/engine.js";
import { nestMaterial } from "../src/nesting.js";
import { validateProject } from "../src/validate.js";
import { resolveHardware } from "../src/hardware.js";
import { renderReport } from "../src/report.js";
import type { CostConfig, Material, Piece, Project } from "../src/types.js";

const mdf: Material = { id: "mdf15", name: "MDF 15 branco", thickness: 15, sheetLength: 2750, sheetWidth: 1840, pricePerSheet: 200, hasGrain: false };
const wood: Material = { ...mdf, id: "freijo", name: "Freijó", hasGrain: true, pricePerSheet: 500 };
const cost: CostConfig = { laborPerSqm: 100, extraCosts: 50, overheadPct: 0.1, marginPct: 0.3 };
const cut = { kerf: 3, trim: 10, edgeWastePct: 0.1 };

const piece = (o: Partial<Piece> & Pick<Piece, "id" | "w" | "h">): Piece =>
  ({ label: o.id, kind: "other", materialId: "mdf15", qty: 1, ...o });

function checkLayout(mat: Material, pieces: Piece[], plan: ReturnType<typeof nestMaterial>) {
  const placed = plan.sheets.flatMap((s) => s.placements);
  expect(placed.length).toBe(pieces.reduce((a, p) => a + p.qty, 0)); // nada some nem duplica
  for (const s of plan.sheets) {
    for (const a of s.placements) {
      expect(a.x).toBeGreaterThanOrEqual(cut.trim);
      expect(a.y).toBeGreaterThanOrEqual(cut.trim);
      expect(a.x + a.w).toBeLessThanOrEqual(mat.sheetLength - cut.trim);
      expect(a.y + a.h).toBeLessThanOrEqual(mat.sheetWidth - cut.trim);
    }
    for (let i = 0; i < s.placements.length; i++)
      for (let j = i + 1; j < s.placements.length; j++) {
        const a = s.placements[i], b = s.placements[j];
        // Sem sobreposição e com folga >= kerf em pelo menos um eixo.
        const sepX = a.x + a.w + cut.kerf <= b.x || b.x + b.w + cut.kerf <= a.x;
        const sepY = a.y + a.h + cut.kerf <= b.y || b.y + b.h + cut.kerf <= a.y;
        expect(sepX || sepY).toBe(true);
      }
  }
}

describe("plano de corte", () => {
  it("uma peça cabe em 1 chapa e o líquido é exato", () => {
    const pcs = [piece({ id: "a", w: 800, h: 500, qty: 2 })];
    const plan = nestMaterial(mdf, pcs, cut);
    expect(plan.sheets.length).toBe(1);
    expect(plan.netArea).toBe(800 * 500 * 2);
    checkLayout(mdf, pcs, plan);
  });

  it("peças que não cabem em uma chapa geram 2ª chapa", () => {
    // 3 peças de 1800x2700 (quase a chapa toda) → 3 chapas
    const pcs = [piece({ id: "big", w: 2700, h: 1800, qty: 3 })];
    const plan = nestMaterial(mdf, pcs, cut);
    expect(plan.sheets.length).toBe(3);
    checkLayout(mdf, pcs, plan);
  });

  it("respeita o veio: peça com veio nunca é girada", () => {
    const pcs = [
      piece({ id: "v1", w: 1000, h: 400, qty: 6, materialId: "freijo", grainAlong: "w" }),
      piece({ id: "v2", w: 400, h: 1000, qty: 6, materialId: "freijo", grainAlong: "h" }),
    ];
    const plan = nestMaterial(wood, pcs, cut);
    checkLayout(wood, pcs, plan);
    for (const pl of plan.sheets.flatMap((s) => s.placements)) {
      expect(pl.rotated).toBe(false);
      expect(pl.w).toBe(1000); // eixo X (veio) sempre com a dimensão de 1000
      expect(pl.h).toBe(400);
    }
  });

  it("sem veio pode girar para aproveitar melhor", () => {
    // 1700x2000: h=2000 > 1820 (largura útil) → só cabe girada.
    const pcs = [piece({ id: "r", w: 1700, h: 2000 })];
    const plan = nestMaterial(mdf, pcs, cut);
    expect(plan.sheets[0].placements[0].rotated).toBe(true);
    checkLayout(mdf, pcs, plan);
  });

  it("falha com erro claro se a peça não cabe", () => {
    expect(() => nestMaterial(mdf, [piece({ id: "x", w: 3000, h: 100 })], cut)).toThrow(/não cabe/);
  });

  it("é determinístico", () => {
    const pcs = Array.from({ length: 15 }, (_, i) => piece({ id: `p${i}`, w: 300 + i * 37, h: 450 + i * 21, qty: 2 }));
    expect(JSON.stringify(nestMaterial(mdf, pcs, cut))).toBe(JSON.stringify(nestMaterial(mdf, pcs, cut)));
  });

  it("lote aleatório: sempre válido (sem sobreposição, tudo colocado)", () => {
    let seed = 42;
    const rnd = () => ((seed = (seed * 1664525 + 1013904223) % 2 ** 32) / 2 ** 32);
    for (let t = 0; t < 30; t++) {
      const pcs = Array.from({ length: 25 }, (_, i) =>
        piece({ id: `r${t}-${i}`, w: 80 + Math.floor(rnd() * 1500), h: 80 + Math.floor(rnd() * 1500), qty: 1 + Math.floor(rnd() * 3) }));
      checkLayout(mdf, pcs, nestMaterial(mdf, pcs, cut));
    }
  });
});

describe("fita de borda", () => {
  it("soma lados × quantidade e aplica perda", () => {
    const p: Project = {
      name: "t", materials: [mdf], edgeBands: [{ id: "b", name: "Branca", pricePerMeter: 2 }], hardware: [],
      pieces: [piece({ id: "a", w: 1000, h: 500, qty: 2, edges: { w1: true, h1: true, h2: true, bandId: "b" } })],
    };
    // (1000 + 500 + 500) * 2 = 4000 mm = 4 m; +10% = 4.4 → compra 5 m
    expect(edgeBandMeters(p, 0.1)).toEqual({ b: { net: 4, purchased: 5 } });
  });
});

describe("ferragens", () => {
  const base: Project = {
    name: "t", materials: [mdf], edgeBands: [], hardware: [],
    priceBook: { hingeUnitPrice: 5, slidePairUnitPrice: 40, handleUnitPrice: 15, shelfPinUnitPrice: 0.5 },
    pieces: [
      piece({ id: "d1", kind: "door", w: 400, h: 700, qty: 2 }),   // 2 dobradiças cada
      piece({ id: "d2", kind: "door", w: 400, h: 1900, qty: 1 }),  // 4
      piece({ id: "g", kind: "drawer_front", w: 500, h: 150, qty: 3 }),
      piece({ id: "s", kind: "shelf", w: 500, h: 300, qty: 2, adjustable: true }),
    ],
  };
  it("deriva por regra e marca como derivado", () => {
    const hw = Object.fromEntries(resolveHardware(base).map((h) => [h.id, h]));
    expect(hw["hinge"].qty).toBe(2 * 2 + 4);
    expect(hw["slide"].qty).toBe(3);
    expect(hw["handle"].qty).toBe(2 + 1 + 3);
    expect(hw["shelf-pin"].qty).toBe(8);
    expect(Object.values(hw).every((h) => h.derived)).toBe(true);
  });
  it("não inventa preço: sem priceBook não gera item", () => {
    expect(resolveHardware({ ...base, priceBook: undefined })).toEqual([]);
  });
  it("o que está no projeto prevalece sobre a regra", () => {
    const hw = resolveHardware({ ...base, hardware: [{ id: "hinge", name: "Dobradiça Blum", qty: 12, unitPrice: 9 }] });
    const hinges = hw.filter((h) => h.id === "hinge");
    expect(hinges).toHaveLength(1);
    expect(hinges[0].qty).toBe(12);
  });
});

describe("validação e bloqueio", () => {
  const ok: Project = { name: "t", materials: [mdf], edgeBands: [], hardware: [], pieces: [piece({ id: "a", w: 500, h: 500 })] };
  it("projeto válido não tem pendência bloqueante", () => {
    expect(validateProject(ok).filter((i) => i.severity === "blocking")).toEqual([]);
  });
  it("material com veio exige direção do veio", () => {
    const p = { ...ok, materials: [wood], pieces: [piece({ id: "a", w: 500, h: 500, materialId: "freijo" })] };
    expect(validateProject(p).some((i) => /veio/.test(i.message))).toBe(true);
  });
  it("dimensão ausente/NaN, qty inválida e material inexistente bloqueiam", () => {
    const p = { ...ok, pieces: [piece({ id: "a", w: NaN, h: 500 }), piece({ id: "b", w: 100, h: 100, qty: 0 }), piece({ id: "c", w: 100, h: 100, materialId: "x" })] };
    expect(validateProject(p).filter((i) => i.severity === "blocking").length).toBeGreaterThanOrEqual(3);
  });
  it("perguntas pendentes da extração bloqueiam o cálculo", () => {
    const r = run({ ...ok, pendingQuestions: ["Espessura do fundo não aparece no PDF"] }, cost, cut);
    expect(r.budget).toBeUndefined();
    expect(r.plans).toEqual([]);
    expect(renderReport(ok, r)).toMatch(/Pendências bloqueantes/);
  });
});

describe("orçamento", () => {
  it("fecha as contas à mão", () => {
    // 1 chapa MDF (200) + fita 5 m × 2 = 10 + ferragem 0 + mão de obra.
    const p: Project = {
      name: "t", materials: [mdf], edgeBands: [{ id: "b", name: "B", pricePerMeter: 2 }], hardware: [{ id: "x", name: "Parafusos", qty: 10, unitPrice: 1 }],
      pieces: [piece({ id: "a", w: 1000, h: 500, qty: 2, edges: { w1: true, h1: true, h2: true, bandId: "b" } })],
    };
    const r = run(p, cost, cut);
    expect(r.plans[0].sheets.length).toBe(1);
    const b = r.budget!;
    expect(b.materials).toBe(200);
    expect(b.edgeBand).toBe(10);
    expect(b.hardware).toBe(10);
    expect(b.labor).toBe(100); // 1.0 m² líquido × R$100
    const direct = 200 + 10 + 10 + 100 + 50;
    expect(b.totalCost).toBeCloseTo(direct * 1.1, 2);
    expect(b.suggestedPrice).toBeCloseTo((direct * 1.1) / 0.7, 2);
    expect(b.margin).toBeCloseTo(b.suggestedPrice - b.totalCost, 2);
  });
  it("margem de 100% ou mais não gera preço válido", () => {
    const b = computeBudget(
      { name: "t", materials: [mdf], edgeBands: [], hardware: [], pieces: [] },
      { project: "t", issues: [], plans: [], edgeBandMeters: {}, hardware: [] },
      { ...cost, marginPct: 1 },
    );
    expect(b.suggestedPrice).toBeNaN();
  });
  it("relatório distingue líquido de comprado", () => {
    const p: Project = { name: "t", materials: [mdf], edgeBands: [], hardware: [], pieces: [piece({ id: "a", w: 1000, h: 500 })] };
    const txt = renderReport(p, run(p, cost, DEFAULT_CUTTING));
    expect(txt).toMatch(/líquido 0\.500 m² · comprar 1 chapa/);
  });
});
