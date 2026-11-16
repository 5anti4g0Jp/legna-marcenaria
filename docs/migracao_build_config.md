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

## Ajustes aprovados (2026-11-16, antes do merge na `main`)
1. `config/catalogo.json`: `nome` dos 10 materiais restaurado para o nome comercial anterior (marca + espessura + dimensões, ex.: "MDF Tauari Guararapes 15 mm 2750x1840"), tirado do `prices.json` original. A marca continua também em `marca`. Nenhum preço mudou.
2. `src/rules.ts`: o aviso da rodabase usa o nome do material no catálogo em vez do id interno (`branco15`). Teste novo em `test/rules.test.ts`.

## Comparação (antes = `main` `ccbe4f4`, depois = esta branch)
`python projects/fernanda-sertorio/comparar_orcamentos.py projects/fernanda-sertorio/referencia/orcamento_pre_migracao.json projects/fernanda-sertorio/out/orcamento.json`
- Referência: `referencia/orcamento_pre_migracao.json` (saída da `main`, com preços de REFERÊNCIA inventados; não são da Legna).
- Diferenças numéricas/estruturais: **0** (220 linhas de peça, 665 unidades, 56 chapas, 10 planos de corte, ferragens, extras, 5 avisos, orçamento completo; custo total R$ 119.195,69, preço sugerido R$ 170.279,56).
- Diferenças só de texto: **7**, todas no aviso da rodabase, JUSTIFICADAS:
  - antes: "...estrutura em U assumida em MDF 15 cru."
  - agora: "...estrutura em U assumida em MDF Branco 15 mm 2750x1840."
  - motivo: as peças de rodabase usam o material `branco15` (MDF branco), não "cru"; o texto antigo descrevia um material diferente do usado no cálculo. Os nomes dos materiais voltaram a ser idênticos aos de antes.
