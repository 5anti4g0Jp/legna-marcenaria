import { readFileSync } from "node:fs";
import { z } from "zod";

// ---------- esquemas ----------
const Chapa = z.object({ comprimento: z.number().positive(), largura: z.number().positive() });
export const MaterialCfg = z.object({
  id: z.string().min(1), nome: z.string().min(1), familia: z.enum(["MDF", "MDP"]),
  marca: z.string().optional(), acabamento: z.string().optional(),
  espessura: z.number().positive(), chapa: Chapa, veio: z.boolean(), fitaId: z.string().min(1),
});
const Item = z.object({ id: z.string().min(1), nome: z.string().min(1) });
export const Catalogo = z.object({
  versao: z.number(), materiais: z.array(MaterialCfg).min(1), fitas: z.array(Item.extend({ largura: z.number().positive().optional(), rolo: z.number().positive().optional() })),
  ferragens: z.array(Item.extend({ tipo: z.enum(["dobradica", "corredica", "puxador", "pino", "parafuso", "outro"]), unidade: z.string() })),
  extras: z.array(Item.extend({ unidade: z.string() })),
});
const Status = z.enum(["confirmado", "referencia", "pendente"]);
const Preco = z.object({ preco: z.number().nonnegative().nullable(), status: Status });
export const Precos = z.object({
  versao: z.number(), materiais: z.record(Preco), fitas: z.record(Preco), ferragens: z.record(Preco), extras: z.record(Preco),
  custos: z.object({ maoDeObraPorM2: z.number().nonnegative(), custosExtras: z.number().nonnegative(), indiretosPct: z.number().min(0).max(1), margemPct: z.number().min(0).lt(1), status: Status }),
}).passthrough();
const Lado = z.enum(["w1", "w2", "h1", "h2"]);
const Veio = z.enum(["w", "h", "none"]);
export const Fabricacao = z.object({
  versao: z.number(),
  corte: z.object({ serra: z.number().nonnegative(), refilo: z.number().nonnegative(), perdaFitaPct: z.number().min(0).max(1) }),
  espessuras: z.object({ corpo: z.number().positive(), prateleiraGrossa: z.number().positive(), fundo: z.number().positive(), caixaGaveta: z.number().positive(), rodabase: z.number().positive() }),
  corInterna: z.string().min(1),
  montagem: z.object({
    portaSobreposta: z.boolean(), recuoPrateleira: z.number().nonnegative(),
    travessas: z.object({ altura: z.number().positive(), quantidade: z.number().int().nonnegative() }),
    rodabase: z.object({ altura: z.number().positive(), recuoFrente: z.number().nonnegative() }),
  }),
  fundo: z.object({ tipo: z.enum(["sobreposto", "rebaixado"]), folgaLargura: z.number().nonnegative(), folgaAltura: z.number().nonnegative(), emendarSeMaiorQueChapa: z.boolean() }),
  dobradica: z.object({ ferragemId: z.string(), porAltura: z.array(z.object({ alturaMax: z.number().positive().nullable(), qtd: z.number().int().positive() })).min(1) }),
  corredica: z.object({
    ferragemId: z.string(), comprimentos: z.array(z.number().positive()).min(1), folgaTraseira: z.number().nonnegative(),
    alturaCaixaMenosFrente: z.number().nonnegative(), alturaCaixaMin: z.number().positive(), larguraCaixaMenosFrente: z.number().nonnegative(),
  }),
  pinoPrateleira: z.object({ ferragemId: z.string(), porPrateleiraRegulavel: z.number().int().nonnegative() }),
  fitaPorTipo: z.record(z.array(Lado)),
  veioMadeira: z.record(Veio),
}).passthrough();

export type Catalogo = z.infer<typeof Catalogo>;
export type Precos = z.infer<typeof Precos>;
export type Fabricacao = z.infer<typeof Fabricacao>;
export interface Config { catalogo: Catalogo; precos: Precos; fabricacao: Fabricacao }

export class ConfigError extends Error {
  constructor(public problemas: string[]) { super(`Configuração inválida:\n- ${problemas.join("\n- ")}`); }
}

const TIPOS_FITA = ["porta", "frenteGaveta", "lateral", "base", "topo", "prateleira", "divisoria", "lateralGaveta"];
const TIPOS_VEIO = ["porta", "frenteGaveta", "lateral", "divisoria", "base", "topo", "prateleira", "travessa"];

/** Verificações cruzadas entre os três arquivos. Retorna a lista de problemas (vazia = ok). */
export function crossCheck(c: Config): string[] {
  const p: string[] = [];
  const dup = (nome: string, ids: string[]) => { const d = ids.filter((x, i) => ids.indexOf(x) !== i); if (d.length) p.push(`${nome}: ids duplicados: ${[...new Set(d)].join(", ")}`); };
  const { catalogo: cat, precos: pr, fabricacao: fab } = c;
  dup("materiais", cat.materiais.map((m) => m.id)); dup("fitas", cat.fitas.map((m) => m.id));
  dup("ferragens", cat.ferragens.map((m) => m.id)); dup("extras", cat.extras.map((m) => m.id));
  const fitas = new Set(cat.fitas.map((f) => f.id)), ferr = new Set(cat.ferragens.map((f) => f.id)), mats = new Set(cat.materiais.map((m) => m.id));
  for (const m of cat.materiais) if (!fitas.has(m.fitaId)) p.push(`material ${m.id}: fita "${m.fitaId}" não existe no catálogo`);
  for (const [k, v] of [["dobradica", fab.dobradica.ferragemId], ["corredica", fab.corredica.ferragemId], ["pinoPrateleira", fab.pinoPrateleira.ferragemId]] as const)
    if (!ferr.has(v)) p.push(`fabricação.${k}: ferragem "${v}" não existe no catálogo`);
  for (const t of fab.dobradica.porAltura.slice(0, -1)) if (t.alturaMax === null) p.push("fabricação.dobradica: só a última faixa pode ter alturaMax nulo");
  const fx = fab.dobradica.porAltura;
  if (fx[fx.length - 1].alturaMax !== null) p.push("fabricação.dobradica: a última faixa deve ter alturaMax nulo (cobre portas mais altas)");
  const al = fx.map((f) => f.alturaMax).filter((x): x is number => x !== null);
  if (al.some((v, i) => i > 0 && v <= al[i - 1])) p.push("fabricação.dobradica: faixas de altura devem ser estritamente crescentes");
  const cp = fab.corredica.comprimentos;
  if (cp.some((v, i) => i > 0 && v <= cp[i - 1])) p.push("fabricação.corredica.comprimentos: deve ser crescente e sem repetição");
  const e = fab.espessuras;
  for (const [nome, esp] of [["fundo", e.fundo], ["caixaGaveta", e.caixaGaveta], ["rodabase", e.rodabase]] as const)
    if (!mats.has(`${fab.corInterna}${esp}`)) p.push(`fabricação.espessuras.${nome}: material "${fab.corInterna}${esp}" não existe no catálogo`);
  for (const t of TIPOS_FITA) if (!(t in fab.fitaPorTipo)) p.push(`fabricação.fitaPorTipo: falta o tipo "${t}"`);
  for (const t of TIPOS_VEIO) if (!(t in fab.veioMadeira)) p.push(`fabricação.veioMadeira: falta o tipo "${t}"`);
  for (const [cat_, ids] of [["materiais", cat.materiais.map((m) => m.id)], ["fitas", [...fitas]], ["ferragens", [...ferr]], ["extras", cat.extras.map((x) => x.id)]] as const) {
    const tabela = (pr as Record<string, Record<string, unknown>>)[cat_];
    for (const k of Object.keys(tabela)) if (!ids.includes(k)) p.push(`preços.${cat_}: "${k}" não existe no catálogo`);
  }
  return p;
}

/** Itens do catálogo sem preço cadastrado, com preço nulo ou não confirmado. */
export function priceStatus(c: Config) {
  const out: { categoria: string; id: string; nome: string; status: "confirmado" | "referencia" | "pendente" }[] = [];
  const pr = c.precos as unknown as Record<string, Record<string, { preco: number | null; status: string }>>;
  for (const cat of ["materiais", "fitas", "ferragens", "extras"] as const)
    for (const it of c.catalogo[cat]) {
      const e = pr[cat][it.id];
      const st = !e || e.preco === null ? "pendente" : (e.status as "confirmado" | "referencia" | "pendente");
      out.push({ categoria: cat, id: it.id, nome: it.nome, status: e && e.preco !== null && e.status === "pendente" ? "pendente" : st });
    }
  return out;
}

export function parseConfig(raw: { catalogo: unknown; precos: unknown; fabricacao: unknown }): Config {
  const problemas: string[] = [];
  const parse = <T>(nome: string, schema: z.ZodType<T>, v: unknown): T | undefined => {
    const r = schema.safeParse(v);
    if (r.success) return r.data;
    for (const i of r.error.issues) problemas.push(`${nome}.${i.path.join(".") || "(raiz)"}: ${i.message}`);
    return undefined;
  };
  const catalogo = parse("catálogo", Catalogo, raw.catalogo), precos = parse("preços", Precos, raw.precos), fabricacao = parse("fabricação", Fabricacao, raw.fabricacao);
  if (problemas.length || !catalogo || !precos || !fabricacao) throw new ConfigError(problemas);
  const cfg = { catalogo, precos, fabricacao };
  const cruzados = crossCheck(cfg);
  if (cruzados.length) throw new ConfigError(cruzados);
  return cfg;
}

export function loadConfig(dir: string | URL = new URL("../config/", import.meta.url)): Config {
  const base = typeof dir === "string" ? new URL(dir.endsWith("/") ? dir : dir + "/", "file://") : dir;
  const ler = (f: string) => JSON.parse(readFileSync(new URL(f, base), "utf8"));
  return parseConfig({ catalogo: ler("catalogo.json"), precos: ler("precos.json"), fabricacao: ler("fabricacao.json") });
}
