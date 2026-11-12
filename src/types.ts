// Todas as medidas em milímetros. Valores monetários em BRL.

export type PieceKind =
  | "lateral" | "base" | "top" | "shelf" | "divider"
  | "door" | "drawer_front" | "drawer_part" | "back" | "other";

/** Direção do veio da peça: qual dimensão da peça (w ou h) deve ficar paralela ao veio da chapa. */
export type GrainAlong = "w" | "h" | "none";

export interface Material {
  id: string;
  name: string;
  thickness: number;
  /** Maior dimensão da chapa comercial (o veio corre ao longo dela). */
  sheetLength: number;
  sheetWidth: number;
  pricePerSheet: number;
  /** true = material com veio (peças não podem girar livremente). */
  hasGrain: boolean;
}

export interface EdgeBand {
  id: string;
  name: string;
  pricePerMeter: number;
}

export interface EdgeSpec {
  /** Lados da peça que levam fita. w = dimensão w, h = dimensão h. */
  w1?: boolean; w2?: boolean; h1?: boolean; h2?: boolean;
  bandId?: string;
}

export interface Piece {
  id: string;
  label: string;
  kind: PieceKind;
  materialId: string;
  w: number;
  h: number;
  qty: number;
  grainAlong?: GrainAlong;
  edges?: EdgeSpec;
  /** Para prateleiras: se regulável, gera pinos de prateleira. */
  adjustable?: boolean;
  /** Referência de onde a peça foi lida (ex.: "p.3 vista frontal"). */
  source?: string;
  /** pdf = dimensão lida do projeto; regra = derivada por regra construtiva (confirmar). */
  origin?: "pdf" | "regra";
  /** Módulo/móvel de origem e suas dimensões externas (L×A×P) para conferência. */
  module?: string;
  moduleDims?: { W: number; H: number; D: number };
}

/** Itens que não saem das chapas de MDF (vidro, espelho, LED, pés, palhinha...). */
export interface ExtraItem {
  id: string;
  name: string;
  qty: number;
  unit: string;
  unitPrice: number;
  /** pdf = quantidade lida do projeto; regra = calculada/assumida. */
  origin: "pdf" | "regra";
}

export interface HardwareItem {
  id: string;
  name: string;
  qty: number;
  unitPrice: number;
  /** true = gerado por regra, não lido do projeto. Exige confirmação. */
  derived?: boolean;
}

export interface PriceBook {
  hingeUnitPrice?: number;
  slidePairUnitPrice?: number;
  handleUnitPrice?: number;
  shelfPinUnitPrice?: number;
}

export interface CostConfig {
  /** Custo de mão de obra e fabricação por m² de peça líquida. */
  laborPerSqm: number;
  /** Custos fixos adicionais (frete, embalagem, instalação...). */
  extraCosts: number;
  /** Percentual de custos indiretos sobre o custo direto (0.1 = 10%). */
  overheadPct: number;
  /** Margem de lucro sobre o PREÇO de venda (0.3 => preço = custo / 0.7). */
  marginPct: number;
}

export interface CuttingConfig {
  kerf: number;       // espessura do corte da serra
  trim: number;       // refilo por borda da chapa
  edgeWastePct: number; // perda de fita de borda (0.1 = 10%)
}

export interface Project {
  name: string;
  materials: Material[];
  edgeBands: EdgeBand[];
  pieces: Piece[];
  /** Ferragens explicitamente listadas no projeto. */
  hardware: HardwareItem[];
  priceBook?: PriceBook;
  derivedHardware?: boolean;
  extras?: ExtraItem[];
  /** Pontos que a extração não conseguiu ler e aguardam confirmação. */
  pendingQuestions?: string[];
  /** Perguntas de confirmação geradas por premissas assumidas (não bloqueiam; listadas no relatório). */
  assumptions?: string[];
}

export type IssueSeverity = "blocking" | "warning";
export interface Issue {
  severity: IssueSeverity;
  pieceId?: string;
  message: string;
}

export interface Placement {
  pieceId: string;
  label: string;
  x: number; y: number;
  w: number; h: number;
  rotated: boolean;
}
export interface SheetLayout {
  materialId: string;
  placements: Placement[];
  usedArea: number;
}
export interface MaterialPlan {
  materialId: string;
  sheets: SheetLayout[];
  netArea: number;       // soma das peças (mm²)
  purchasedArea: number; // sheets * área da chapa (mm²)
  utilization: number;   // net / purchased
}

export interface Budget {
  materials: number;
  edgeBand: number;
  hardware: number;
  thirdParty: number;
  labor: number;
  extras: number;
  overhead: number;
  totalCost: number;
  margin: number;
  suggestedPrice: number;
}

export interface Report {
  project: string;
  issues: Issue[];
  plans: MaterialPlan[];
  edgeBandMeters: Record<string, { net: number; purchased: number }>;
  hardware: HardwareItem[];
  extras?: ExtraItem[];
  budget?: Budget;
}
