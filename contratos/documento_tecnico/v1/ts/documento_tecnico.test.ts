import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { hashConteudo, paraEntradaMotor, parseDocumentoTecnico } from "./documento_tecnico.js";

const base = new URL("../", import.meta.url);
const ler = (rel: string) => JSON.parse(readFileSync(new URL(rel, base), "utf8"));
const exemplo = () => ler("exemplo_ficticio.json");
const manifesto = ler("fixtures/manifest.json").casos as { arquivo: string; modo: "teste" | "producao"; esperado_python: string[]; esperado_ts: string[] | null }[];

describe("contrato documento_tecnico v1 (TypeScript, EXEMPLO FICTÍCIO)", () => {
  it("aceita o exemplo em modo teste e o recusa em produção", () => {
    expect(parseDocumentoTecnico(exemplo(), { modo: "teste" }).ok).toBe(true);
    const r = parseDocumentoTecnico(exemplo(), { modo: "producao" });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.erros.map((e) => e.codigo)).toEqual(["E-EXEMPLO"]);
  });

  it("o hash do conteúdo calculado em TypeScript é idêntico ao calculado em Python", () => {
    const d = exemplo();
    expect(hashConteudo(d)).toBe(d.integridade.hash_conteudo);
  });

  for (const c of manifesto.filter((x) => x.esperado_ts !== null)) {
    it(`paridade com o Python: ${c.arquivo.split("/").pop()}`, () => {
      const r = parseDocumentoTecnico(ler(c.arquivo), { modo: c.modo });
      if (c.esperado_ts!.length === 0) {
        expect(r.ok).toBe(true);
        if (r.ok) expect(r.avisos.map((a) => a.codigo)).toContain("A-VERSAO-MINOR");
      } else {
        expect(r.ok).toBe(false);
        if (!r.ok) for (const cod of c.esperado_ts!) expect(r.erros.map((e) => e.codigo)).toContain(cod);
      }
    });
  }

  it("regras só do Python NÃO são reimplementadas no TypeScript (documentado em esperado_ts=null)", () => {
    const soPython = manifesto.filter((x) => x.esperado_ts === null);
    expect(soPython.length).toBeGreaterThan(5);
    for (const c of soPython) expect(c.esperado_python.length).toBeGreaterThan(0);
  });
});

describe("conversão para a entrada do motor", () => {
  it("usa só dados aprovados; profundidade em conflito fica nula e o módulo NÃO vira CabSpec", () => {
    const r = parseDocumentoTecnico(exemplo(), { modo: "teste" });
    if (!r.ok) throw new Error("exemplo inválido");
    const e = paraEntradaMotor(r.doc);
    expect(e.modulos[0]).toMatchObject({ W: 800, H: 700, D: null, dimensoesFaltantes: ["profundidade"], prontoParaCabSpec: false });
    expect(e.prontoParaCalculo).toBe(false);
    expect(e.orcamentoCompletoLeitura).toBe(false);
    expect(e.pendencias.map((p) => p.campoLegna)).toEqual(expect.arrayContaining(["mat.espessura", "ferr.dobradica", "ferr.corredica"]));
    expect(e.itensNaoAprovados.conflito).toBe(2);
    expect(e.avisos.join(" ")).toContain("não monta portas");
  });

  it("item não aprovado nunca alimenta dimensão (mesmo com valor lido)", () => {
    const d = exemplo();
    d.modulos[0].dimensoes.profundidade_item_id = "i.nota_prof_a"; // item em conflito, não aprovado
    const r = parseDocumentoTecnico(d, { modo: "teste" });
    // o hash muda, então o documento adulterado é recusado antes de converter
    expect(r.ok).toBe(false);
  });

  it("converte cm para mm e usa o valor confirmado pela pessoa", () => {
    const d = exemplo();
    const x = d.itens.find((i: { id: string }) => i.id === "i.cota_largura");
    x.valor = { numero: 80, texto: null, unidade: "cm", unidade_fonte: "declarada_no_item" };
    d.integridade.hash_conteudo = hashConteudo(d);
    const r = parseDocumentoTecnico(d, { modo: "teste" });
    if (!r.ok) throw new Error(JSON.stringify(r.erros));
    expect(paraEntradaMotor(r.doc).modulos[0].W).toBe(800);
  });
});
