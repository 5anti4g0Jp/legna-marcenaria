# Legna Marcenaria - orçamentista técnico

Pipeline: **leitura de arquivos (Python)** -> *extração de peças (IA, pendente)* -> **motor de cálculo (TypeScript)** -> orçamento.

## Status por etapa

| Etapa | Situação |
|---|---|
| 1. Leitura de PDF digital/escaneado, PNG, JPG | **Pronta e testada** (`ingest/`, `tests_py/`) |
| 2. Identificação de peças/cotas/materiais por IA | Não implementada (exige chave de API) |
| 3. Consumo, ferragens, compra | Motor pronto (`src/`), regras ainda fixas no código |
| 4. Orçamento | Pronto (`src/engine.ts`), preços de referência |
| 5. DWG, DXF, TIFF, XLSX/XLS/CSV, SVG | **Não implementada: recusados explicitamente** |

## Formatos

Suportados e testados: `.pdf` (digital e escaneado), `.png`, `.jpg`/`.jpeg`.
Qualquer outro formato levanta `UnsupportedFormat`. Nada é declarado como compatível sem teste.

## Medições do OCR (desenho escaneado, simulado a partir do PDF digital como gabarito)

Recall = cotas numéricas recuperadas / cotas do gabarito. "Falsos" = números lidos que não existem.

| Página | 200 dpi | 300 dpi |
|---|---|---|
| p.1 cozinha (52 cotas) | 90% (13 falsos) | 96% (10 falsos) |
| p.6 área de serviços (32) | 100% (9) | 100% (8) |
| p.10 rack (23) | 78% (1) | 78% (3) |
| p.16 home office (22) | 95% (3) | 95% (2) |
| p.17 home office interior (35) | 97% (0) | 97% (0) |

PNG 300 dpi: 96% (10 falsos). JPG q85: 90% (19 falsos). JPG q50: 90% (15 falsos).

**Conclusão: OCR sozinho NÃO é confiável para medidas.** Perde até 22% das cotas e inventa números.
Por isso todo token de OCR carrega `source="ocr"` e `conf`, e a Etapa 2 deve tratá-lo como não confirmado
(validação cruzada por soma de cotas + confirmação humana).

Limitações conhecidas:
- Afinação do OCR (remoção de linhas coloridas de cota) medida em desenhos do SketchUp LayOut com cotas vermelhas.
  Outros softwares/estilos de desenho ainda não foram testados.
- Scan real (inclinação, sombra, ruído) é pior que scan simulado a partir de PDF limpo.
- Imagens PNG/JPG não têm escala conhecida: só números escritos valem como cota.
- Tesseract é dependência de sistema (`apt-get install tesseract-ocr tesseract-ocr-por`); não roda em função serverless comum.

## Rodar

```bash
pip install -r requirements.txt
python -m ingest.cli projeto.pdf saida.json
python -m pytest tests_py     # leitura
npx vitest run                # motor de cálculo
```
