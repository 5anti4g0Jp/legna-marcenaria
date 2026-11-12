import type { Issue, Project } from "./types.js";

/** Valida o projeto extraído. Nunca corrige nem inventa valores: só aponta. */
export function validateProject(p: Project): Issue[] {
  const issues: Issue[] = [];
  const add = (severity: Issue["severity"], message: string, pieceId?: string) =>
    issues.push({ severity, message, pieceId });

  const mats = new Map(p.materials.map((m) => [m.id, m]));
  const bands = new Set(p.edgeBands.map((b) => b.id));

  for (const q of p.pendingQuestions ?? []) add("blocking", `Pendente de confirmação: ${q}`);
  if (p.pieces.length === 0) add("blocking", "Nenhuma peça informada.");

  const seen = new Set<string>();
  for (const m of p.materials) {
    if (!(m.sheetLength >= m.sheetWidth && m.sheetWidth > 0))
      add("blocking", `Material ${m.id}: sheetLength deve ser >= sheetWidth e > 0.`);
    if (!(m.thickness > 0)) add("blocking", `Material ${m.id}: espessura inválida.`);
    if (!(m.pricePerSheet >= 0)) add("blocking", `Material ${m.id}: preço da chapa inválido.`);
  }

  for (const pc of p.pieces) {
    if (seen.has(pc.id)) add("blocking", `ID de peça duplicado: ${pc.id}`, pc.id);
    seen.add(pc.id);
    if (!(Number.isFinite(pc.w) && pc.w > 0 && Number.isFinite(pc.h) && pc.h > 0))
      add("blocking", `Peça ${pc.label}: dimensões ausentes ou inválidas.`, pc.id);
    if (!(Number.isInteger(pc.qty) && pc.qty > 0))
      add("blocking", `Peça ${pc.label}: quantidade inválida.`, pc.id);
    const mat = mats.get(pc.materialId);
    if (!mat) {
      add("blocking", `Peça ${pc.label}: material "${pc.materialId}" não existe.`, pc.id);
      continue;
    }
    if (mat.hasGrain && !pc.grainAlong)
      add("blocking", `Peça ${pc.label}: material com veio, direção do veio não informada.`, pc.id);
    if (pc.edges) {
      const used = pc.edges.w1 || pc.edges.w2 || pc.edges.h1 || pc.edges.h2;
      if (used && !pc.edges.bandId)
        add("blocking", `Peça ${pc.label}: lados com fita, mas fita não especificada.`, pc.id);
      if (pc.edges.bandId && !bands.has(pc.edges.bandId))
        add("blocking", `Peça ${pc.label}: fita "${pc.edges.bandId}" não existe.`, pc.id);
    }
    // Coerência: peça maior que a área útil da chapa em qualquer orientação.
    const long = Math.max(pc.w, pc.h), short = Math.min(pc.w, pc.h);
    if (long > mat.sheetLength || short > mat.sheetWidth)
      add("blocking", `Peça ${pc.label} (${pc.w}x${pc.h}) não cabe na chapa ${mat.sheetLength}x${mat.sheetWidth}.`, pc.id);
    if (pc.w < 30 || pc.h < 30)
      add("warning", `Peça ${pc.label} muito pequena (${pc.w}x${pc.h}); confirmar leitura da cota.`, pc.id);
  }
  return issues;
}
