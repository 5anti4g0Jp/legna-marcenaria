# Ambiente do motor de leitura

Python **3.13**. Leitores modulares (`ingest/readers/`) que entregam dados para um núcleo comum (`ReadResult` / `Extracted`).
Cada item preserva: arquivo de origem, formato original, localização (página/aba/layer/entidade), coordenadas, unidade,
valor, método de extração, confiança e status de confirmação (sempre `nao_confirmado`: só revisão humana confirma).

## 1. Formatos e situação de validação

| Formato | Leitor | Biblioteca | Situação |
|---|---|---|---|
| PDF (digital e escaneado) | `pdf_reader` (encapsula `ingest/reader.py` da Etapa 1) | PyMuPDF + Tesseract | **Validado** (PDF real de 34 págs + escaneamento simulado) |
| PNG, JPG/JPEG | `image_reader` | Pillow + Tesseract | **Validado** (OCR) |
| TIFF/TIF, multipágina | `tiff_reader` | tifffile (+ Pillow p/ G4/LZW) | **Validado**: raw, LZW, CCITT G4, 2 páginas |
| DXF | `dxf_reader` | ezdxf | **Validado** com DXFs gerados (TEXT, MTEXT, DIMENSION, LINE, LWPOLYLINE, CIRCLE, INSERT; unidades mm/pol/sem unidade) |
| DWG | `dwg_reader` | ODA File Converter (externo) + ezdxf | **NÃO validado com o conversor real**: ver §6. Só o encanamento foi testado com um conversor simulado |
| XLSX | `spreadsheet_reader` | openpyxl (alternativa: calamine) | **Validado** |
| XLS | `spreadsheet_reader` | python-calamine | **Validado** (fixture gerada com xlwt) |
| CSV | `csv_reader` | `csv` da biblioteca padrão | **Validado** (cp1252, `;`, vírgula decimal mantida como texto) |
| SVG | `svg_reader` | lxml + svgpathtools | **Validado** (XXE bloqueado; `transform` NÃO aplicado, com aviso) |

## 2. Dependências

### Obrigatórias (`requirements/base.txt`)
| Pacote | Versão testada | Finalidade | Licença |
|---|---|---|---|
| pymupdf | 2.1 | PDF: texto, coordenadas, imagens, vetores | **AGPL-3.0 ou comercial (Artifex)** ⚠ |
| pdfplumber | 0.11.10 | PDF: tabelas/posicionamento | MIT |
| pypdf | 6.17.0 | inspeção/manipulação de PDF | BSD-3 |
| pillow | 12.3.0 | imagens | MIT-CMU |
| numpy | 2.5.3 | numérico | BSD-3 |
| pytesseract | 0.3.13 | ponte p/ Tesseract | Apache-2.0 |
| ezdxf | 1.4.5 | DXF | MIT |
| tifffile | 2026.11.12 | TIFF multipágina | BSD-3 |
| openpyxl | 3.1.5 | XLSX | MIT |
| python-calamine | 0.9.1 | XLS/XLSX | MIT |
| lxml | 6.1.3 | XML/SVG | BSD-3 |
| svgpathtools | 1.8.0 | caminhos SVG (traz scipy, svgwrite) | MIT |
| shapely | 2.2.0 | geometria 2D | BSD-3 (GEOS/LGPL embutido nas rodas) |
| opencv-python-headless | 5.0.0.93 (contêiner) | processamento de imagem | Apache-2.0 |
| anthropic | 2.8.0 | SDK Claude (usa `httpx2` 2.x, BSD-3) | Apache-2.0 |
| scipy (via svgpathtools) | 1.18.1 | matemática | BSD-3 |

### Opcionais (`requirements/optional.txt`)
pandas (BSD-3, tratamento tabular), pypdfium2 (BSD/Apache-2.0, renderização alternativa), imagecodecs (BSD-3, TIFF comprimido no tifffile).
Hoje o Pillow cobre G4/LZW, então imagecodecs **não** está instalado.

### Desenvolvimento e testes (`requirements/dev.txt`)
pytest (MIT), xlwt (BSD, só para gerar `.xls` de teste).

### Sistema
`tesseract-ocr` + `tesseract-ocr-por` (Apache-2.0). Local: 5.3.4; contêiner: 5.3.0. Idiomas verificados: `por`, `eng`, `osd`.

### Ferramentas externas
ODA File Converter (DWG): **não instalado**, ver §6. `xvfb` só se o ODA for usado (conversor usa Qt).

### Recusadas ou adiadas, e por quê
| Item | Decisão | Motivo |
|---|---|---|
| **SymPy** | Recusado | Sem caso de uso: o motor usa aritmética simples. Reavaliar se surgir álgebra simbólica |
| **FreeCAD** | Recusado | Não há pacote no apt do ambiente; pesado; ezdxf+Shapely cobrem o 2D. Reavaliar só para 3D/BIM |
| **ODA Drawings SDK** | Não avaliado | Licença paga; só se o File Converter + ezdxf se mostrarem insuficientes |
| **Blender** | Fora do motor | Conforme pedido: reservado a geometria/visualização 3D futura |
| **imagecodecs** | Adiado | Pillow resolve os casos testados |
| **opencv-python (completo)** | Não declarado | O ambiente local já tem o completo; a declaração é a variante `headless`. **Não instalar as duas no mesmo ambiente** |

## 3. Instalação
```bash
# sistema (Debian/Ubuntu)
sudo apt-get install -y tesseract-ocr tesseract-ocr-por
# Python
pip install -r requirements/base.txt -c requirements/constraints.txt
pip install -r requirements/dev.txt      # testes
```
Reprodutível: `requirements/lock-container.txt` (pip freeze do contêiner validado).

## 4. Variáveis de ambiente (`.env.example`)
`ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY_FILE` (Docker secret) | `LEGNA_AI_MODEL` | `LEGNA_MAX_FILE_MB` (200) | `LEGNA_MAX_ENTITIES` (2.000.000) |
`ODA_FILE_CONVERTER` | `LEGNA_DWG_TIMEOUT` (180 s) | `LEGNA_FIXTURES` (pasta dos PDFs reais usados em testes).
A chave **nunca** vai no código nem no git: `.env` está no `.gitignore` e `tests_py/test_no_secrets.py` varre o repositório.

## 5. Docker
```bash
# build (use --build-arg HTTPS_PROXY=... --network host em redes com proxy; certificado em docker/certs/*.crt)
docker build -f docker/Dockerfile --target runtime -t legna-leitor .
docker build -f docker/Dockerfile --target test    -t legna-leitor-test .
docker run --rm --network none --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true \
           --memory 2g --cpus 2 -v ./dados:/data:ro legna-leitor /data/projeto.pdf /tmp/saida.json
docker run --rm --network none legna-leitor-test                       # testes (PDFs reais ausentes: pulados)
docker run --rm --network none --user root -v /pasta/pdfs:/fixtures:ro legna-leitor-test   # testes completos
```
Base `python:3.13-slim-bookworm`, usuário não-root (uid 10001). `docker/docker-compose.yml`: leitor **sem rede**, FS somente-leitura,
sem capabilities, 2 GB; serviço de IA separado com a chave via secret. **Não presume serverless.**

## 6. DWG e ODA File Converter
O download do ODA não é acessível deste ambiente e a licença é proprietária. O leitor está pronto: sem o conversor, recusa com
`ToolMissing` (nunca inventa dado). Para habilitar: aceitar a licença da ODA, colocar o `.deb` em `docker/oda/` e
`--build-arg ODA_DEB=<arquivo>.deb`, ou apontar `ODA_FILE_CONVERTER`. **Até testar com DWGs reais, DWG não é suportado.**

## 7. Testes
```bash
python -m pytest tests_py -q      # Python (110)
npx vitest run                    # motor TypeScript (27)
python -m ingest.bench            # tempo e memória
```

## 8. Medições (PDF real de 34 págs, contêiner, limite 1 GB)
1136 itens em 0,79 s, pico 256 MB. Leitura isolada com FS somente-leitura e sem rede: 2,5 s incluindo a partida do contêiner.
Benchmark sintético (host): PDF 10 págs 0,02 s/179 MB; PNG A4 OCR 1,4 s/224 MB; TIFF 3 págs OCR 4,2 s/221 MB; DXF 50 mil linhas 1,7 s/275 MB;
XLSX 20 mil linhas 0,6 s/215 MB; CSV 50 mil linhas 0,4 s/275 MB.

## 9. Limitações conhecidas
- **DWG não validado** (§6). O teste com conversor simulado prova o encanamento, não o ODA.
- **OCR não é dado confiável**: recupera 78-100% das cotas e inventa números. Sempre `nao_confirmado`.
- DXF: lê só o espaço-modelo e as entidades listadas; sem HATCH, SPLINE, ELLIPSE, expansão de blocos, layouts de papel, XREF, 3D.
- SVG: `transform` não é aplicado; sem `width`+`viewBox` não há conversão para mm.
- XLS/XLSX: lê valores em cache; fórmulas sem valor salvo aparecem vazias.
- CSV: vírgula decimal mantida como texto; codificação não UTF-8 assume cp1252.
- Imagens (PNG/JPG/TIFF) não têm escala: coordenadas em pixels.
- A integração com a API foi validada com transporte simulado (sucesso, 429, 5xx, 401, 403, 400, timeout, conexão, repetição) e uma chamada real
  com chave fictícia (rejeitada com 401, corretamente traduzida). **Uma chamada bem-sucedida não foi validada: falta chave real.**
- O SDK 2.8 envia a chave como `Authorization: Bearer` e depende de `httpx2` (não `httpx`).
- TIFF corrompido pode ser aceito parcialmente pelo tifffile; páginas ilegíveis são rejeitadas, mas leitura parcial silenciosa não foi excluída.

## 10. Licenças e restrições comerciais relevantes
- ⚠ **PyMuPDF (AGPL-3.0 ou comercial)**: usar em serviço comercial acessível por rede exige abrir o código-fonte do serviço **ou comprar a licença
  da Artifex**. É o risco jurídico mais importante do projeto e precisa de decisão. Alternativa livre parcial: pypdfium2 (BSD/Apache) renderiza, mas não
  oferece a extração de vetores que a verificação de cotas usa.
- ⚠ **ODA File Converter / SDK**: licença proprietária da Open Design Alliance; revisar termos de uso comercial e redistribuição antes de embarcar.
- Demais dependências: licenças permissivas (MIT/BSD/Apache-2.0). Shapely distribui o GEOS (LGPL) nas rodas.
- Tesseract: Apache-2.0.
