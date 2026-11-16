# Migração do `build.ts` para a configuração externa (branch `migracao/build-config`)

**Estado:** preparada numa branch isolada; **NÃO integrada à `main`**. Esta branch contém o merge de `feature/config-estrutura` (somente aqui) + a correção do `build.ts`.

## Por que o `build.ts` quebrava depois do merge
1. Lia `projects/fernanda-sertorio/prices.json`, removido pela branch de configuração (`ENOENT`).
2. `specs.map(expand)`: `expand(spec, cfg)` agora recebe a configuração como 2º argumento e o `Array.map` passava o **índice** nesse lugar (erro `Cannot read properties of undefined (reading 'materiais')`).

## O que mudou no `build.ts`
- Usa `defaultConfig()` (`config/catalogo.json`, `precos.json`, `fabricacao.json`) e monta a mesma visão `prices` usada antes (gravada em `out/orcamento.json`).
- Item sem preço cadastrado interrompe (`preço pendente na configuração`); nada é inventado.
- Material: espessura, tamanho de chapa e veio vêm do catálogo (antes: regex no id, 2750x1840 fixo e `startsWith("tauari")`).
- Corte (serra, refilo, perda de fita) vem de `fabricacao.corte` (valores iguais aos padrões antigos).
- `specs.map((s) => expand(s, cfg))`.
- **Nenhum preço, regra ou valor foi alterado.** `src/rules.ts` não foi tocado nesta branch além do que veio do merge.

## Comparação (antes = `main` `ccbe4f4`, depois = esta branch)
`python projects/fernanda-sertorio/comparar_orcamentos.py projects/fernanda-sertorio/referencia/orcamento_pre_migracao.json projects/fernanda-sertorio/out/orcamento.json`
- Referência: `referencia/orcamento_pre_migracao.json` (saída da `main`, com os preços de REFERÊNCIA inventados; não são preços da Legna).
- Diferenças numéricas/estruturais: **0** (220 linhas de peça, 665 unidades, 56 chapas, 10 planos de corte, ferragens, extras, 5 avisos, orçamento completo).
- Diferenças só de texto: **27** (ver abaixo). Não foram "corrigidas" para forçar igualdade.
  - 20: nome de 10 materiais (config: "MDF Tauari 15 mm"; antes: "MDF Tauari Guararapes 15 mm 2750x1840"). A marca está em `marca` no catálogo; o nome composto não foi reconstruído.
  - 7: texto da premissa de rodabase em `src/rules.ts` ("MDF 15 cru" → "branco15", o id do material).
