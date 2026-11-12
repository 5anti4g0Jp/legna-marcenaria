import type { HardwareItem, Project } from "./types.js";

/** Regra construtiva usual: nº de dobradiças por altura da porta (mm). Configurável. */
export const HINGE_RULES: { maxHeight: number; hinges: number }[] = [
  { maxHeight: 900, hinges: 2 },
  { maxHeight: 1600, hinges: 3 },
  { maxHeight: 2000, hinges: 4 },
  { maxHeight: Infinity, hinges: 5 },
];
export const SHELF_PINS_PER_ADJUSTABLE_SHELF = 4;

/**
 * Ferragens: o que está listado no projeto sempre prevalece. Itens derivados por regra
 * (dobradiças, corrediças, puxadores, pinos) só são gerados se o preço estiver no
 * priceBook E o projeto não listar item equivalente. Todo item derivado é marcado
 * `derived: true` e precisa de confirmação no relatório.
 */
export function resolveHardware(p: Project): HardwareItem[] {
  const out: HardwareItem[] = [...p.hardware];
  const has = (id: string) => p.hardware.some((h) => h.id === id);
  const pb = p.priceBook ?? {};

  let hinges = 0, slides = 0, handles = 0, pins = 0;
  for (const pc of p.pieces) {
    if (pc.kind === "door") {
      const height = Math.max(pc.w, pc.h);
      hinges += pc.qty * HINGE_RULES.find((r) => height <= r.maxHeight)!.hinges;
      handles += pc.qty;
    } else if (pc.kind === "drawer_front") {
      slides += pc.qty;
      handles += pc.qty;
    } else if (pc.kind === "shelf" && pc.adjustable) {
      pins += pc.qty * SHELF_PINS_PER_ADJUSTABLE_SHELF;
    }
  }
  const derive = (id: string, name: string, qty: number, price: number | undefined) => {
    if (qty > 0 && price !== undefined && !has(id))
      out.push({ id, name, qty, unitPrice: price, derived: true });
  };
  derive("hinge", "Dobradiça", hinges, pb.hingeUnitPrice);
  derive("slide", "Par de corrediças", slides, pb.slidePairUnitPrice);
  derive("handle", "Puxador", handles, pb.handleUnitPrice);
  derive("shelf-pin", "Pino de prateleira", pins, pb.shelfPinUnitPrice);
  return out;
}
