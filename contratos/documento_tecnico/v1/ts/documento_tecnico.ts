/**
 * Contrato `documento_tecnico` v1 — lado TypeScript (PROTÓTIPO ISOLADO; não é importado por src/).
 *
 * Papel: (1) validar o JSON gerado pelo leitor Python (estrutura + regras de segurança que o TS precisa garantir sozinho);
 *        (2) converter para a entrada do motor, usando SOMENTE dados aprovados por humano.
 * A máquina de estados NÃO é reimplementada aqui: transições e atores autorizados são verificados pelo validador Python
 * (fonte única). O TS faz defesa em profundidade com o subconjunto abaixo e recusa o que o Python recusaria nesse subconjunto.
 */
import { createHash } from "node:crypto";
import { z } from "zod";

export const VERSAO_SUPORTADA = { major: 1, minor: 0 };
export const ESCOPO_HASH = ["projeto", "documento", "extracao", "paginas", "vistas", "modulos", "itens", "conflitos", "pendencias"] as const;
const ESTADOS = ["extraido", "geometricamente_consistente", "conflito", "sem_medicao", "pendente_revisao", "aprovado"] as const;
export type Estado = (typeof ESTADOS)[number];

export interface ErroContrato { codigo: string; caminho: string; mensagem: string }
export type ResultadoParse = { ok: true; doc: DocumentoTecnico; avisos: ErroContrato[] } | { ok: false; erros: ErroContrato[] };

// ---------------------------------------------------------------- esquema (espelha documento_tecnico.schema.json)
function esquemas(estrito: boolean) {
  const o = <T extends z.ZodRawShape>(s: T) => (estrito ? z.object(s).strict() : z.object(s).passthrough());
  const nul = <T extends z.ZodTypeAny>(t: T) => t.nullable();
  const id = z.string().regex(/^[a-z][a-z0-9_.:-]{0,79}$/);
  const sha = z.string().regex(/^[0-9a-f]{64}$/);
  const dh = z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/);
  const bbox = z.array(z.number()).length(4);
  const estado = z.enum(ESTADOS);
  const ator = o({ tipo: z.enum(["sistema", "humano"]), id: z.string().min(1) });
  const transicao = o({ de: nul(estado), para: estado, ator, em: dh, motivo: z.string().min(1) });
  const evidencia = o({
    tipo: z.enum(["leitura", "unidade", "geometria", "conflito_geometrico", "sem_medicao", "orientacao", "revisao_humana", "observacao", "ocr", "relacao_paginas", "quantidade_inferida"]),
    descricao: z.string().min(1), metodo: z.string().min(1), dados: z.record(z.unknown()).optional(), pagina: nul(z.number().int().min(1)).optional(), coords: nul(bbox).optional(),
  });
  const revisao = o({ revisor: z.string().min(1), decisao: z.enum(["aprovado", "rejeitado"]), em: dh, observacao: nul(z.string()).optional(), valor_confirmado: nul(z.string()).optional() });
  const valor = o({ numero: nul(z.number()).optional(), texto: nul(z.string()).optional(), unidade: nul(z.enum(["mm", "cm", "m", "un", "m2", "outra"])).optional(),
    unidade_fonte: z.enum(["declarada_na_pagina", "declarada_no_item", "assumida", "desconhecida", "nao_se_aplica"]) });
  const item = o({
    id, tipo: z.enum(["cota", "nota", "rotulo_componente", "material", "acabamento", "ferragem", "acessorio", "quantidade", "observacao_producao", "declaracao_unidade", "marcador_nao_preenchido"]),
    pagina: z.number().int().min(1), coords: bbox, texto_original: z.string(), valor,
    orientacao: z.enum(["horizontal", "vertical", "inclinada", "desconhecida"]).optional(), angulo_graus: nul(z.number()).optional(),
    origem: o({ metodo_extracao: z.enum(["camada_texto", "ocr", "geometria_vetorial", "inferencia_geometrica", "entrada_humana", "regra_configuracao"]),
      ocr: nul(o({ motor: z.string().min(1), versao: nul(z.string()).optional(), confianca: nul(z.number().min(0).max(1)).optional() })).optional() }),
    confianca: nul(z.number().min(0).max(1)).optional(), natureza: z.enum(["explicita", "sugerida", "inferida"]), chave_semantica: nul(z.string()).optional(),
    atributos: o({ espessura_mm: nul(z.number().positive()).optional(), espessura_fonte: z.enum(["declarada_no_documento", "cota_candidata", "confirmada_pelo_formulario_legna", "confirmada_pelo_revisor"]).optional(),
      acabamento: nul(z.string()).optional(), marca_linha: nul(z.string()).optional(), modelo: nul(z.string()).optional(),
      categoria: z.enum(["porta", "gaveta", "prateleira", "divisoria", "sapateira", "fundo", "lateral", "base", "topo", "rodabase", "painel", "outro"]).optional(),
      quantidade_item_id: nul(id).optional(), quantidade: nul(z.number().int().min(0)).optional() }).optional(),
    relacoes: z.array(o({ tipo: z.enum(["pertence_ao_modulo", "aparece_na_vista", "mede_componente", "descreve", "usa_ferragem", "usa_material", "quantidade_de", "mesma_entidade_que", "pagina_par_de"]), alvo_id: id })).optional(),
    analise_automatica: nul(o({ estado, estado_algoritmo: z.string(), algoritmo_sha256: sha })).optional(),
    evidencias: z.array(evidencia).min(1), conflitos: z.array(z.record(z.unknown())).optional(), estado, historico: z.array(transicao).min(1), revisao: nul(revisao).optional(),
  });
  const pagina = o({ numero: z.number().int().min(1), largura_pt: z.number().positive(), altura_pt: z.number().positive(), rotacao: z.union([z.literal(0), z.literal(90), z.literal(180), z.literal(270)]),
    tipo: z.enum(["desenho_tecnico", "ficha", "capa", "outro", "indeterminado"]), origem_texto: z.enum(["camada_texto", "ocr", "mista", "nenhuma"]), n_vetores: z.number().int().min(0), n_imagens: z.number().int().min(0),
    titulo_detectado: nul(z.string()).optional(), unidade_declarada: nul(z.enum(["mm", "cm", "m"])).optional(), unidade_declarada_item_id: nul(id).optional(), par_de: z.array(z.number().int().min(1)).optional() });
  const vista = o({ id, pagina: z.number().int().min(1), tipo: z.enum(["frontal", "lateral", "superior", "corte", "detalhe", "planta", "indeterminado"]), nome: nul(z.string()).optional(), bbox: nul(bbox).optional(),
    escala_mm_por_pt: nul(z.number().positive()).optional(), estado, evidencias: z.array(evidencia).optional() });
  const modulo = o({ id, nome: z.string().min(1), paginas: z.array(z.number().int().min(1)).min(1), vista_ids: z.array(id).optional(), item_ids: z.array(id).optional(),
    dimensoes: o({ largura_item_id: nul(id), altura_item_id: nul(id), profundidade_item_id: nul(id) }), origem: z.enum(["rotulo_do_documento", "revisao_humana", "geometria_vetorial"]), estado });
  const pendencia = o({ id, campo_legna: nul(z.string().min(1)), tipo: z.enum(["ausente_no_pdf", "nao_confirmado", "conflito", "inferido_sem_revisao", "unidade_nao_declarada", "ocr_sem_revisao", "sugerido_sem_confirmacao"]),
    descricao: z.string().min(1), bloqueia: z.enum(["nenhum", "calculo", "orcamento"]), item_ids: z.array(id), modulo_id: nul(id).optional(), pagina: nul(z.number().int().min(1)).optional() });
  const conflito = o({ id, chave_semantica: z.string().min(1), item_ids: z.array(id).min(2), descricao: z.string().min(1), estado: z.enum(["aberto", "resolvido"]),
    resolucao: nul(o({ revisor: z.string().min(1), item_id_vencedor: id, em: dh, observacao: nul(z.string()).optional() })).optional() });
  const porEstado = o(Object.fromEntries(ESTADOS.map((e) => [e, z.number().int().min(0)])) as Record<Estado, z.ZodNumber>);
  return o({
    $schema: z.string().optional(), contrato: o({ nome: z.literal("documento_tecnico"), versao: z.string().regex(/^\d+\.\d+\.\d+$/) }),
    marcador_exemplo: o({ ficticio: z.literal(true), aviso: z.string().min(10) }).optional(),
    projeto: o({ id, nome: nul(z.string()).optional(), software_origem: o({ nome: nul(z.string()).optional(), versao: nul(z.string()).optional(), fonte: z.enum(["metadado_do_pdf", "declarado_pela_legna", "inferido", "desconhecido"]) }) }),
    documento: o({ arquivo: z.string().min(1), sha256: sha, paginas: z.number().int().min(1), tamanho_bytes: z.number().int().min(1).optional(), tipo_conteudo: z.enum(["pdf_vetorial", "pdf_escaneado", "pdf_misto", "imagem"]), metadados_pdf: z.record(z.string()).optional() }),
    extracao: o({ gerado_em: dh, leitor: o({ nome: z.string().min(1), versao: z.string().min(1), commit: nul(z.string()).optional() }), algoritmo_cotas: o({ nome: z.string().min(1), sha256: sha }), parametros: z.record(z.unknown()).optional() }),
    paginas: z.array(pagina).min(1), vistas: z.array(vista), modulos: z.array(modulo), itens: z.array(item), conflitos: z.array(conflito), pendencias: z.array(pendencia),
    elegibilidade: o({ pronto_para_calculo: z.boolean(), orcamento_completo: z.boolean(), bloqueios: z.array(id), nota: z.string().optional() }),
    resumo: o({ total_itens: z.number().int().min(0), por_estado: porEstado, por_tipo: z.record(z.number().int().min(0)), aprovadas_automaticamente: z.literal(0) }),
    integridade: o({ canonicalizacao: z.literal("json-ordenado-v1"), hash_conteudo: sha, escopo: z.array(z.string()).optional(), gerado_por: z.string().min(1) }),
    avisos: z.array(z.string()).optional(),
  });
}
export type DocumentoTecnico = z.infer<ReturnType<typeof esquemas>>;
type Item = DocumentoTecnico["itens"][number];

// ---------------------------------------------------------------- canonicalização (idêntica à do Python: json-ordenado-v1)
function ordenar(o: unknown): unknown {
  if (Array.isArray(o)) return o.map(ordenar);
  if (o && typeof o === "object") return Object.fromEntries(Object.keys(o as object).sort().map((k) => [k, ordenar((o as Record<string, unknown>)[k])]));
  return o;
}
export const canonico = (o: unknown): string => JSON.stringify(ordenar(o));
export const hashConteudo = (d: Record<string, unknown>): string => createHash("sha256").update(canonico(Object.fromEntries(ESCOPO_HASH.map((k) => [k, d[k]])))).digest("hex");

// ---------------------------------------------------------------- validação
export function parseDocumentoTecnico(entrada: unknown, opcoes: { modo?: "producao" | "teste" } = {}): ResultadoParse {
  const modo = opcoes.modo ?? "producao"; const erros: ErroContrato[] = []; const avisos: ErroContrato[] = [];
  const raw = entrada as { contrato?: { versao?: unknown } };
  const m = /^(\d+)\.(\d+)\.(\d+)$/.exec(String(raw?.contrato?.versao ?? ""));
  if (!m) return { ok: false, erros: [{ codigo: "E-VERSAO", caminho: "/contrato/versao", mensagem: `versão inválida: ${String(raw?.contrato?.versao)}` }] };
  const [major, minor] = [Number(m[1]), Number(m[2])];
  if (major !== VERSAO_SUPORTADA.major) return { ok: false, erros: [{ codigo: "E-VERSAO", caminho: "/contrato/versao", mensagem: `major ${major} incompatível com ${VERSAO_SUPORTADA.major}.x: recusado` }] };
  const minorNovo = minor > VERSAO_SUPORTADA.minor;
  if (minorNovo) avisos.push({ codigo: "A-VERSAO-MINOR", caminho: "/contrato/versao", mensagem: "minor mais novo: campos desconhecidos ignorados; nada desconhecido pode aprovar dados" });
  const r = esquemas(!minorNovo).safeParse(entrada);
  if (!r.success) return { ok: false, erros: r.error.issues.map((i) => ({ codigo: "E-SCHEMA", caminho: "/" + i.path.join("/"), mensagem: i.message.slice(0, 200) })) };
  const d = r.data;
  if (d.marcador_exemplo && modo === "producao") erros.push({ codigo: "E-EXEMPLO", caminho: "/marcador_exemplo", mensagem: "documento de exemplo/fictício não pode ser aceito em modo produção" });
  const ids = new Set<string>();
  for (const [k, lista] of [["itens", d.itens], ["vistas", d.vistas], ["modulos", d.modulos], ["pendencias", d.pendencias], ["conflitos", d.conflitos]] as const)
    lista.forEach((x, n) => { if (ids.has(x.id)) erros.push({ codigo: "E-ID-DUP", caminho: `/${k}/${n}/id`, mensagem: `id duplicado: ${x.id}` }); ids.add(x.id); });
  const porEstado: Record<string, number> = Object.fromEntries(ESTADOS.map((e) => [e, 0])); const porTipo: Record<string, number> = {}; let auto = 0;
  d.itens.forEach((it, n) => {
    const c = `/itens/${n}`; const h = it.historico; const ult = h[h.length - 1];
    porEstado[it.estado]++; porTipo[it.tipo] = (porTipo[it.tipo] ?? 0) + 1;
    auto += h.filter((t) => t.para === "aprovado" && t.ator.tipo !== "humano").length;
    if (it.estado !== ult.para) erros.push({ codigo: "E-ESTADO-HIST", caminho: c + "/estado", mensagem: `estado '${it.estado}' difere do destino da última transição '${ult.para}'` });
    h.forEach((t, k) => { if (t.para === "aprovado" && t.ator.tipo !== "humano") erros.push({ codigo: "E-APROV-AUTO", caminho: `${c}/historico/${k}`, mensagem: "aprovação por ator não humano" }); });
    if (it.estado === "aprovado") {
      const rev = it.revisao; const ok = !!rev && rev.decisao === "aprovado" && ult.ator.tipo === "humano" && ult.ator.id === rev.revisor;
      if (!ok) erros.push({ codigo: "E-APROV-HUMANO", caminho: c, mensagem: "aprovado exige `revisao` do mesmo humano que fez a última transição" });
    }
  });
  const esperado = { total_itens: d.itens.length, por_estado: porEstado, por_tipo: porTipo, aprovadas_automaticamente: auto };
  if (canonico(d.resumo) !== canonico(esperado)) erros.push({ codigo: "E-RESUMO", caminho: "/resumo", mensagem: "resumo não corresponde aos itens" });
  const bloq = d.pendencias.filter((p) => p.bloqueia !== "nenhum").map((p) => p.id); const calc = d.pendencias.filter((p) => p.bloqueia === "calculo");
  const abertos = d.conflitos.filter((c) => c.estado === "aberto");
  const el = { pronto_para_calculo: calc.length === 0 && abertos.length === 0, orcamento_completo: bloq.length === 0 && abertos.length === 0, bloqueios: bloq };
  if (canonico({ pronto_para_calculo: d.elegibilidade.pronto_para_calculo, orcamento_completo: d.elegibilidade.orcamento_completo, bloqueios: d.elegibilidade.bloqueios }) !== canonico(el))
    erros.push({ codigo: "E-ELEG", caminho: "/elegibilidade", mensagem: "elegibilidade inconsistente com as pendências" });
  if (d.integridade.hash_conteudo !== hashConteudo(d as unknown as Record<string, unknown>)) erros.push({ codigo: "E-HASH", caminho: "/integridade/hash_conteudo", mensagem: "hash do conteúdo não confere: documento alterado após a geração" });
  return erros.length ? { ok: false, erros } : { ok: true, doc: d, avisos };
}

// ---------------------------------------------------------------- conversão para a entrada do motor
export interface ModuloEntrada {
  id: string; nome: string;
  /** Dimensões em mm, SOMENTE de itens aprovados por humano; nulas quando ausentes ou não aprovadas. Nunca preenchidas por padrão. */
  W: number | null; H: number | null; D: number | null; dimensoesFaltantes: string[];
  /** Pronto para virar `CabSpec` do motor? (precisa de W, H, D aprovados; a cor/material vem do catálogo confirmado, não do documento). */
  prontoParaCabSpec: boolean;
}
export interface EntradaMotor {
  projeto: { id: string; nome: string | null }; modulos: ModuloEntrada[];
  pendencias: { id: string; campoLegna: string | null; tipo: string; bloqueia: string; descricao: string }[];
  prontoParaCalculo: boolean;
  /** Só o lado da leitura. O motor ainda precisa combinar com preços/regras não confirmados da configuração. */
  orcamentoCompletoLeitura: boolean;
  itensNaoAprovados: Record<string, number>;
  avisos: string[];
}
const paraMm = (it: Item): number | null => {
  const txt = it.revisao?.valor_confirmado ?? undefined; const n = txt !== undefined ? Number(String(txt).replace(",", ".")) : it.valor.numero ?? null;
  if (n === null || Number.isNaN(n)) return null;
  const u = it.revisao?.valor_confirmado ? it.valor.unidade ?? "mm" : it.valor.unidade; // valor confirmado por pessoa assume a unidade do item
  return u === "mm" ? n : u === "cm" ? n * 10 : u === "m" ? n * 1000 : null;
};

export function paraEntradaMotor(doc: DocumentoTecnico): EntradaMotor {
  const itens = new Map(doc.itens.map((i) => [i.id, i]));
  const dim = (idItem: string | null | undefined): number | null => { const it = idItem ? itens.get(idItem) : undefined; return it && it.estado === "aprovado" ? paraMm(it) : null; };
  const modulos = doc.modulos.map((m): ModuloEntrada => {
    const W = dim(m.dimensoes.largura_item_id), H = dim(m.dimensoes.altura_item_id), D = dim(m.dimensoes.profundidade_item_id);
    const falt = ([["largura", W], ["altura", H], ["profundidade", D]] as const).filter(([, v]) => v === null).map(([k]) => k);
    return { id: m.id, nome: m.nome, W, H, D, dimensoesFaltantes: falt, prontoParaCabSpec: falt.length === 0 };
  });
  const naoAprov: Record<string, number> = {};
  for (const it of doc.itens) if (it.estado !== "aprovado") naoAprov[it.estado] = (naoAprov[it.estado] ?? 0) + 1;
  const avisos = ["A v1 não monta portas, gavetas nem prateleiras: isso depende de interpretação de vistas (fora do escopo desta versão)."];
  if (!doc.elegibilidade.pronto_para_calculo) avisos.push("Documento NÃO está pronto para cálculo: há pendências ou conflitos abertos.");
  return {
    projeto: { id: doc.projeto.id, nome: doc.projeto.nome ?? null }, modulos,
    pendencias: doc.pendencias.map((p) => ({ id: p.id, campoLegna: p.campo_legna, tipo: p.tipo, bloqueia: p.bloqueia, descricao: p.descricao })),
    prontoParaCalculo: doc.elegibilidade.pronto_para_calculo && modulos.every((m) => m.prontoParaCabSpec),
    orcamentoCompletoLeitura: doc.elegibilidade.orcamento_completo && modulos.every((m) => m.prontoParaCabSpec),
    itensNaoAprovados: naoAprov, avisos,
  };
}
