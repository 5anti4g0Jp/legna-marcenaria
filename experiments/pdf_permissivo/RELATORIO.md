# Experimento: substituir o PyMuPDF (AGPL) por bibliotecas permissivas

Isolado em `experiments/pdf_permissivo/` (branch `experimento/pdf-permissivo`). **Não altera** leitores, `ingest/`, baseline, gabarito nem o algoritmo congelado (sha `696a8b83…`, verificado a cada execução). O algoritmo roda **sem PyMuPDF** nos backends alternativos (módulo vazio injetado só no carregamento). Dados: `results/comparacao.json`. Reproduzir: `python -m experiments.pdf_permissivo.compare`.

Bibliotecas e licenças (conferir antes de decidir): pdfplumber 0.11 + pdfminer.six (MIT); pypdfium2 5.x (Apache-2.0/BSD-3; PDFium BSD-3). Referência: PyMuPDF 2.1 (AGPL-3.0 ou comercial Artifex).

## Resultado (PDF real, 34 págs; gabarito/baseline v0 da Etapa 0)
| Métrica | pdfplumber/pdfminer | pypdfium2 |
|---|---|---|
| Tokens numéricos (405 no PyMuPDF): casados, perdidos, extras | 405 / 0 / 0 | 405 / 0 / 0 |
| Mesmo estado em todos os 405 tokens | 405 | 405 |
| Mesmo intervalo medido (±0,5 pt) e mesmo mm medido | 405 / 405 | 405 / 405 |
| Mesma orientação (h/v) | 405 | 405 |
| Páginas com mesma cor de cota e mesmas escalas | 34 de 34 | 34 de 34 |
| Desvio máximo de coordenada (caixa do texto) | 0,10 pt | 0,13 pt |
| **104 cotas** (86 regulares + 18 deslocadas): mesmo estado / mesmo resultado da baseline | 104 / 104 | 104 / 104 |
| 113 linhas revisadas (inclui notas): mesmo estado | 113 | 113 |
| Medições (estado medido: 73 das 104 cotas): idênticas | 73 | 73 |
| Sintético (9 estilos): mesmos estados e resultados | 9 de 9 | 9 de 9 |

Desempenho (34 págs, mediana de 2-3 execuções; varia ±15% entre execuções): PyMuPDF ≈ 0,7-0,8 s · pdfplumber ≈ 0,9-1,2 s (extração domina; algoritmo ≈ 0,04 s) · pypdfium2 ≈ 0,25 s.

## Limites (leia antes de concluir qualquer coisa)
1. **A extração alternativa é um adaptador que eu escrevi e ajustei** (agrupamento de caracteres em spans, direção do texto, cor do traço, itens `re`/`l`). Ajustei-o iterando contra **este mesmo PDF** e os sintéticos; o resultado "idêntico" é, portanto, otimista. Primeira rodada sem ajustes: 112 de 113 linhas e 6 páginas com cor/escala divergentes no pypdfium2. Erros achados e corrigidos: texto vertical/diagonal partido em caracteres; ângulo do PDFium inválido com eixo y invertido (LayOut); cor escalar no pdfplumber (apareceu só no 2º PDF).
2. **Um único estilo de PDF real** (SketchUp LayOut). O 2º PDF disponível (apresentação) não tem números: não prova nada. Promob e AutoCAD (texto em curvas, tracejados, recortes, vistas) podem quebrar o adaptador.
3. Os PDFs sintéticos foram **gerados com PyMuPDF** (como fixtures); a geração em si continuaria dependendo dele, a menos que se troque o gerador.
4. Não medi OCR/PDF escaneado (Tesseract, outro caminho) nem o restante do pipeline que usa PyMuPDF (`ingest/readers/pdf_reader.py`, `census`, ferramentas de avaliação).
5. Tempo: sem otimização; comparação indicativa.

## Conclusão
Tecnicamente **viável** para o algoritmo de cotas neste PDF, com qualquer das duas bibliotecas; **não demonstrado** para outros softwares. Critério de aceite proposto para uma troca real: (a) reproduzir a baseline (mesmos estados) em todos os PDFs reais recebidos (Promob/AutoCAD inclusos) e nos sintéticos; (b) adaptador com testes próprios e sem ajuste a um único arquivo; (c) migrar também leitor de PDF e avaliação; (d) decisão jurídica registrada. Não foi migrado nada.
