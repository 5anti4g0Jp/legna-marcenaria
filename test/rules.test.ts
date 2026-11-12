import { describe, expect, it } from "vitest";
import { custom, expand, type CabSpec } from "../src/rules.js";

const base: CabSpec = { id: "T", nome: "teste", src: "p.0", cor: "tauari", W: 800, H: 700, D: 560 };

describe("regras construtivas", () => {
  it("corpo: 2 laterais, base, topo e fundo com dimensões derivadas", () => {
    const e = expand({ ...base, doors: [[396, 700, 2]] });
    const by = (l: string) => e.pieces.find((p) => p.label === l)!;
    expect(by("Lateral").qty).toBe(2);
    expect(by("Lateral").w).toBe(560 - 15); // profundidade recuada pela porta
    expect(by("Base").w).toBe(800 - 30);
    expect(by("Fundo").materialId).toBe("branco6");
  });
  it("portas vêm do PDF e levam fita nos 4 lados; veio vertical em madeira", () => {
    const e = expand({ ...base, doors: [[396, 700, 2]] });
    const d = e.pieces.find((p) => p.kind === "door")!;
    expect(d.origin).toBe("pdf");
    expect(d.grainAlong).toBe("h");
    expect(d.edges).toMatchObject({ w1: true, w2: true, h1: true, h2: true });
  });
  it("dobradiças por altura: 700→2, 1000→3, 2400→5 por porta", () => {
    const hinges = (h: number) => expand({ ...base, H: h, doors: [[400, h, 1]] }).hardware.find((x) => x.id === "hinge")!.qty;
    expect(hinges(700)).toBe(2);
    expect(hinges(1000)).toBe(3);
    expect(hinges(2400)).toBe(5);
  });
  it("gaveta: frente + caixa + 1 par de corrediças, comprimento padrão <= profundidade-50", () => {
    const e = expand({ ...base, D: 560, fronts: [[700, 180, 2]], doors: undefined });
    expect(e.pieces.filter((p) => p.kind === "drawer_front")[0].qty).toBe(2);
    expect(e.hardware.find((h) => h.id.startsWith("slide-"))!.qty).toBe(2);
    const slide = e.hardware.find((h) => h.id.startsWith("slide-"))!.id;
    expect(Number(slide.split("-")[1])).toBeLessThanOrEqual(560 - 15 - 50);
  });
  it("fundo maior que a chapa é emendado e registra pergunta de confirmação", () => {
    const e = expand({ ...base, W: 1960, H: 2360 });
    const fundos = e.pieces.filter((p) => p.kind === "back");
    expect(fundos.reduce((a, p) => a + p.qty, 0)).toBe(2);
    expect(Math.min(fundos[0].w, fundos[0].h)).toBeLessThanOrEqual(1820);
    expect(e.assumptions.some((a) => /emendado/.test(a))).toBe(true);
  });
  it("quantidade do módulo multiplica peças e ferragens", () => {
    const e = expand({ ...base, qty: 3, doors: [[400, 700, 1]], handle: "sinnai" });
    expect(e.pieces.find((p) => p.kind === "door")!.qty).toBe(3);
    expect(e.hardware.find((h) => h.id === "handle-sinnai")!.qty).toBe(3);
  });
  it("peça explícita de madeira sem veio informado usa veio no comprimento", () => {
    const [p] = custom({ id: "X", nome: "x", src: "p.1", W: 1, H: 1, D: 1 }, [{ label: "a", mat: "tauari18", w: 100, h: 200, src: "p.1" }]);
    expect(p.grainAlong).toBe("w");
    expect(p.origin).toBe("pdf");
  });
});
