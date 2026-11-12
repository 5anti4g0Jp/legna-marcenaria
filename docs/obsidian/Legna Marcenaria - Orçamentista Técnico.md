---
tags: [projeto, marcenaria, orcamento, legna]
status: em-andamento
atualizado: 2026-11-12
repo: https://github.com/5anti4g0Jp/legna-marcenaria
---

# Legna Marcenaria - Orçamentista Técnico

> Sistema que lê projetos executivos (PDF/imagem) e entrega levantamento de materiais + orçamento de fabricação.
> **Prioridade: precisão.** Nunca inventar medida; faltou dado -> pedir confirmação.

## Etapas
- [x] **1. Leitura** PDF digital, PDF escaneado, PNG, JPG (testado)
- [ ] **2. Interpretação por IA** (peças, cotas, materiais)
- [x] **3. Consumo / compra** (plano de corte, veio, serra, fita, ferragens) - motor pronto
- [x] **4. Orçamento** - pronto, mas com **preços de referência**
- [ ] **5. DWG, DXF, TIFF, XLSX/XLS/CSV, SVG** (recusados até testar)

## Arquitetura
- Leitura em **Python** (PyMuPDF + Tesseract) -> JSON interno -> **motor em TypeScript** -> orçamento
- IA só interpreta; **cálculo é determinístico**; regras e preços = configuração editável
- Testes: **46** (27 vitest + 19 pytest)

## Resultados medidos
**OCR em desenho escaneado** (simulado): recupera 78-100% das cotas e inventa 0-13 números por página.
Conclusão: OCR sozinho não é dado confiável -> validação cruzada + confirmação humana.
Remover as linhas vermelhas de cota antes do OCR subiu o recall de 58% para 96% (só testado em desenhos do SketchUp LayOut).

**Projeto de teste (detalhamento LayOut, 34 págs):** 220 linhas de peça, 665 peças, ~10 tipos de MDF.
Subtotal de materiais (preços de referência): **R$ 35.419**; com mão de obra de referência: custo R$ 119.196, venda R$ 170.280 (margem 30%).
**Não confirmado:** preços, mão de obra, 44 premissas (espessura 15 mm, fundo 6 mm, profundidades ausentes, peças de 40/50/100 mm laminadas).

## Lições
- Texto digital nunca deve ser trocado por OCR (bug corrigido, teste de regressão).
- Heurística de corte única gastava 2 chapas onde 1 bastava -> motor multi-estratégia.
- Cota "9" lida no PDF era "100" (soma das alturas denunciou): validação cruzada é obrigatória.
- Apresentação de interiores (PowerPoint) **não** serve: precisa de detalhamento com elevações/cortes.

## Decisões pendentes
- [ ] Fornecedores: um ou vários por item?
- [ ] Edição de cadastros por `store.ts` + CLI (sem tela)?
- [ ] Preço só atual ou com histórico?
- [ ] Legna: espessura padrão, ferragens, mão de obra por m², preços reais

## Ambiente / bloqueios
- Branch `main` = Etapa 1; `feature/config-estrutura` = WIP da configuração (aguarda aprovação)
- Repo `Legna-scanner` (vazio) ainda existe: **apagar manualmente** (Settings > Danger Zone)
- Chave Anthropic: autenticada pela sessão no desenvolvimento; em produção, `ANTHROPIC_API_KEY` nas variáveis da Vercel
- Tesseract não roda em serverless Vercel -> leitura em contêiner

## Links
- [[Marcenaria - Preços e Ferragens]] (criar: cadastro real de preços)
- [[Legna - Projetos de Teste]] (criar: PDFs reais para validar a IA)
