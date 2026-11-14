# Legna Marcenaria - orçamentista técnico

Pipeline: **leitura de arquivos (Python)** -> *extração de peças (IA, pendente)* -> **motor de cálculo (TypeScript)** -> orçamento.

## Status por etapa

| Etapa | Situação |
|---|---|
| 1. Leitura de PDF digital/escaneado, PNG, JPG | **Pronta e testada** (`ingest/`, `tests_py/`) |
| 2. Identificação de peças/cotas/materiais por IA | **Iniciada**: verificação geométrica de cotas pronta (`ingest/dimensions.py`); associação cota->peça por IA pendente |
| 3. Consumo, ferragens, compra | Motor pronto (`src/`), regras ainda fixas no código |
| 4. Orçamento | Pronto (`src/engine.ts`), preços de referência |
| Leitura técnica (branch `etapa2-tecnica`) | **Etapa 0** baseline/gabarito e **Etapa 1** seis estados + modelo rastreável concluídas (`docs/etapa1_estados_e_modelo.md`) |
| 5. DXF, TIFF, XLSX/XLS/CSV, SVG | Leitores prontos e testados na branch `ambiente-leitores` (ver `docs/ambiente.md`) |
| 5b. DWG | Leitor pronto, **não validado** (ODA File Converter indisponível) |

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

## Verificação geométrica de cotas (`ingest/dimensions.py`)

Em PDF vetorial (ex.: SketchUp LayOut), cada cota tem uma linha desenhada com o comprimento real. O módulo mede esse
comprimento no desenho e confere o número escrito: se `valor == comprimento x escala da vista`, a cota é **confirmada**.
Sem IA e sem OCR. Status: `confirmado`, `confirmado_local` (escala própria de uma vista), `conflito`, `sem_medicao`, `sem_escala`.

Medido no PDF de teste (34 págs, LayOut): 405 números lidos -> **181 confirmados (45%)**, 23 conflitos, 196 sem medição, 5 sem escala.

Limites (importante):
- **A cota escrita prevalece sobre o desenho.** A geometria só *confere*; conflito = alerta para revisão humana, nunca correção automática.
- Parte dos 23 conflitos é **falso alerta** (ex.: página 10, várias vistas em escalas diferentes). Dois falsos alertas já corrigidos
  (linha de outra cota que apenas cruza; riscos diagonais curtos), ambos cobertos por teste.
- 48% dos números não são medidos (texto fora da linha de cota, chamadas/leaders). Esses dependem de outras verificações.
- **Não detecta** erro de rótulo truncado como o "9" (era 100) da estante: isso exige conferir a soma da cadeia de cotas (não implementado).
- Só vale para geometria vetorial. PDF escaneado/imagem não tem geometria: segue só OCR + confirmação humana.
- Ainda não associa cada cota a uma peça (isso é a parte de IA da Etapa 2).
