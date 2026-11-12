import type { CuttingConfig, Material, MaterialPlan, Piece, Placement, SheetLayout } from "./types.js";

interface Rect { x: number; y: number; w: number; h: number }
interface Item { piece: Piece; w: number; h: number; canRotate: boolean }
type SortKey = "area" | "long" | "w" | "h";
type Split = "A" | "B" | "largest" | "smallest";
type Score = "bssf" | "blsf" | "baf";

/**
 * Plano de corte por guilhotina, com veio e kerf.
 * Heurística determinística multi-estratégia: roda várias combinações de ordenação,
 * critério de encaixe e regra de divisão, e fica com a que usa menos chapas
 * (desempate: sobras mais concentradas). Não garante o ótimo matemático, mas é sempre válida.
 * Convenção: eixo X da chapa = comprimento (sentido do veio). Peça com grainAlong "w"
 * fica com w no eixo X; "h" fica com h no eixo X.
 * Kerf: consumido apenas ENTRE peças vizinhas; uma peça cabe se sua dimensão <= retângulo livre.
 */
export function nestMaterial(mat: Material, pieces: Piece[], cfg: CuttingConfig): MaterialPlan {
  const usableL = mat.sheetLength - 2 * cfg.trim;
  const usableW = mat.sheetWidth - 2 * cfg.trim;

  const items: Item[] = [];
  for (const p of pieces) {
    for (let i = 0; i < p.qty; i++) {
      let w = p.w, h = p.h, canRotate = true;
      if (mat.hasGrain && p.grainAlong && p.grainAlong !== "none") {
        canRotate = false;
        if (p.grainAlong === "h") { w = p.h; h = p.w; }
      }
      items.push({ piece: p, w, h, canRotate });
    }
  }
  for (const it of items) {
    const ok = (it.canRotate ? [false, true] : [false]).some(
      (rot) => (rot ? it.h : it.w) <= usableL && (rot ? it.w : it.h) <= usableW);
    if (!ok)
      throw new Error(`Peça ${it.piece.label} (${it.piece.w}x${it.piece.h}) não cabe na área útil ${usableL}x${usableW} da chapa ${mat.id}.`);
  }

  const sorts: SortKey[] = ["area", "long", "w", "h"];
  const splits: Split[] = ["largest", "A", "B", "smallest"];
  const scores: Score[] = ["bssf", "blsf", "baf"];
  let bestSheets: SheetLayout[] | null = null;
  let bestKey: [number, number] = [Infinity, Infinity];
  for (const so of sorts) for (const sp of splits) for (const sc of scores) {
    const sheets = pack(items, so, sp, sc, usableL, usableW, cfg, mat.id);
    // menos chapas; depois maior concentração de uso (soma dos quadrados do uso, negativa p/ minimizar)
    const key: [number, number] = [sheets.length, -sheets.reduce((a, s) => a + s.usedArea ** 2, 0)];
    if (key[0] < bestKey[0] || (key[0] === bestKey[0] && key[1] < bestKey[1])) { bestKey = key; bestSheets = sheets; }
  }
  const sheets = bestSheets!;

  const netArea = items.reduce((a, i) => a + i.piece.w * i.piece.h, 0);
  const purchasedArea = sheets.length * mat.sheetLength * mat.sheetWidth;
  return { materialId: mat.id, sheets, netArea, purchasedArea, utilization: purchasedArea ? netArea / purchasedArea : 0 };
}

function pack(
  items: Item[], sortKey: SortKey, split: Split, score: Score,
  usableL: number, usableW: number, cfg: CuttingConfig, materialId: string,
): SheetLayout[] {
  const k = cfg.kerf;
  const keyOf = (i: Item) =>
    sortKey === "area" ? i.w * i.h : sortKey === "long" ? Math.max(i.w, i.h) : sortKey === "w" ? i.w : i.h;
  const sorted = [...items].sort((a, b) => keyOf(b) - keyOf(a) || b.w * b.h - a.w * a.h || a.piece.id.localeCompare(b.piece.id));

  const sheets: { free: Rect[]; layout: SheetLayout }[] = [];
  const newSheet = () => sheets.push({
    free: [{ x: cfg.trim, y: cfg.trim, w: usableL, h: usableW }],
    layout: { materialId, placements: [], usedArea: 0 },
  });

  for (const it of sorted) {
    const orients = it.canRotate ? [false, true] : [false];
    const fits = (r: Rect, rot: boolean) => (rot ? it.h : it.w) <= r.w && (rot ? it.w : it.h) <= r.h;
    const scoreOf = (r: Rect, rot: boolean): number => {
      const pw = rot ? it.h : it.w, ph = rot ? it.w : it.h;
      const dw = r.w - pw, dh = r.h - ph;
      return score === "bssf" ? Math.min(dw, dh) : score === "blsf" ? Math.max(dw, dh) : r.w * r.h - pw * ph;
    };
    let best: { s: number; r: number; rot: boolean; sc: number } | null = null;
    for (let si = 0; si < sheets.length; si++)
      sheets[si].free.forEach((r, ri) => {
        for (const rot of orients) if (fits(r, rot)) {
          const sc = scoreOf(r, rot);
          if (!best || sc < best.sc) best = { s: si, r: ri, rot, sc };
        }
      });
    if (!best) {
      newSheet();
      const base = sheets[sheets.length - 1].free[0];
      const rot = orients.find((o) => fits(base, o))!; // garantido pela checagem prévia
      best = { s: sheets.length - 1, r: 0, rot, sc: 0 };
    }
    const sheet = sheets[best.s];
    const r = sheet.free[best.r];
    const pw = best.rot ? it.h : it.w, ph = best.rot ? it.w : it.h;
    sheet.layout.placements.push({ pieceId: it.piece.id, label: it.piece.label, x: r.x, y: r.y, w: pw, h: ph, rotated: best.rot });
    sheet.layout.usedArea += pw * ph;

    const cw = pw + k, ch = ph + k;
    const rw = r.w - cw, rh = r.h - ch;
    const mk = (x: number, y: number, w: number, h: number): Rect[] => (w > 0 && h > 0 ? [{ x, y, w, h }] : []);
    const optA = [...mk(r.x + cw, r.y, rw, r.h), ...mk(r.x, r.y + ch, pw, rh)];   // corte vertical primeiro
    const optB = [...mk(r.x, r.y + ch, r.w, rh), ...mk(r.x + cw, r.y, rw, ph)];   // corte horizontal primeiro
    const largest = (o: Rect[]) => o.reduce((m, q) => Math.max(m, q.w * q.h), 0);
    const chosen =
      split === "A" ? optA : split === "B" ? optB
      : split === "largest" ? (largest(optA) >= largest(optB) ? optA : optB)
      : (largest(optA) <= largest(optB) ? optA : optB);
    sheet.free.splice(best.r, 1, ...chosen);
  }
  return sheets.map((s) => s.layout);
}
