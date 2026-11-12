import type { CuttingConfig, Material, MaterialPlan, Piece, Placement, SheetLayout } from "./types.js";

interface Rect { x: number; y: number; w: number; h: number }
interface Item { piece: Piece; w: number; h: number; canRotate: boolean }

/**
 * Plano de corte por guilhotina (best-short-side-fit), com veio e kerf.
 * Heurística determinística: não garante o ótimo matemático, mas é sempre válida.
 * Convenção: eixo X da chapa = comprimento (sentido do veio). Peça com grainAlong "w"
 * fica com w no eixo X; "h" fica com h no eixo X.
 * Kerf: consumido apenas ENTRE peças vizinhas (a peça ocupa w+kerf no eixo, a sobra é
 * medida depois disso). Uma peça só cabe se w <= retângulo livre.
 */
export function nestMaterial(mat: Material, pieces: Piece[], cfg: CuttingConfig): MaterialPlan {
  const usableL = mat.sheetLength - 2 * cfg.trim;
  const usableW = mat.sheetWidth - 2 * cfg.trim;
  const k = cfg.kerf;

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
  items.sort((a, b) => b.w * b.h - a.w * a.h || a.piece.id.localeCompare(b.piece.id));

  const sheets: { free: Rect[]; layout: SheetLayout }[] = [];
  const newSheet = () => {
    sheets.push({
      free: [{ x: cfg.trim, y: cfg.trim, w: usableL, h: usableW }],
      layout: { materialId: mat.id, placements: [], usedArea: 0 },
    });
  };

  for (const it of items) {
    const orients = it.canRotate ? [false, true] : [false];
    let best: { s: number; r: number; rot: boolean; score: number } | null = null;
    for (let si = 0; si < sheets.length; si++) {
      sheets[si].free.forEach((r, ri) => {
        for (const rot of orients) {
          const pw = rot ? it.h : it.w, ph = rot ? it.w : it.h;
          if (pw <= r.w && ph <= r.h) {
            const score = Math.min(r.w - pw, r.h - ph);
            if (!best || score < best.score) best = { s: si, r: ri, rot, score };
          }
        }
      });
    }
    if (!best) {
      const fits = orients.some((rot) => (rot ? it.h : it.w) <= usableL && (rot ? it.w : it.h) <= usableW);
      if (!fits)
        throw new Error(`Peça ${it.piece.label} (${it.piece.w}x${it.piece.h}) não cabe na área útil ${usableL}x${usableW} da chapa ${mat.id}.`);
      newSheet();
      const si = sheets.length - 1;
      const rot = orients.find((o) => (o ? it.h : it.w) <= usableL && (o ? it.w : it.h) <= usableW)!;
      best = { s: si, r: 0, rot, score: 0 };
    }
    const { s, r: ri, rot } = best;
    const sheet = sheets[s];
    const r = sheet.free[ri];
    const pw = rot ? it.h : it.w, ph = rot ? it.w : it.h;
    sheet.layout.placements.push({ pieceId: it.piece.id, label: it.piece.label, x: r.x, y: r.y, w: pw, h: ph, rotated: rot });
    sheet.layout.usedArea += pw * ph;

    // Sobras após consumir peça + kerf. Duas divisões guilhotina possíveis; escolhe a
    // que deixa o maior retângulo contíguo.
    const cw = pw + k, ch = ph + k;
    const rw = r.w - cw, rh = r.h - ch;
    const mk = (x: number, y: number, w: number, h: number): Rect[] => (w > 0 && h > 0 ? [{ x, y, w, h }] : []);
    const optA = [ // corte vertical primeiro: faixa direita full-height + faixa abaixo só da peça
      ...mk(r.x + cw, r.y, rw, r.h),
      ...mk(r.x, r.y + ch, pw, rh), // largura = pw (não cw): o kerf fica entre esta faixa e a da direita
    ];
    const optB = [ // corte horizontal primeiro: faixa abaixo full-width + faixa direita só da peça
      ...mk(r.x, r.y + ch, r.w, rh),
      ...mk(r.x + cw, r.y, rw, ph), // altura = ph (não ch): o kerf fica entre esta faixa e a de baixo
    ];
    const largest = (o: Rect[]) => o.reduce((m, q) => Math.max(m, q.w * q.h), 0);
    const chosen = largest(optA) >= largest(optB) ? optA : optB;
    sheet.free.splice(ri, 1, ...chosen);
  }

  const netArea = items.reduce((a, i) => a + i.piece.w * i.piece.h, 0);
  const purchasedArea = sheets.length * mat.sheetLength * mat.sheetWidth;
  return {
    materialId: mat.id,
    sheets: sheets.map((s) => s.layout),
    netArea,
    purchasedArea,
    utilization: purchasedArea ? netArea / purchasedArea : 0,
  };
}
