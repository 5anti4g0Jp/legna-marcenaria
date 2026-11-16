# Avaliação técnica complementar (IA) — 46 cartões do pkg-1.1

Você recebeu: (1) o PDF do projeto (34 páginas), (2) `legna_revisao_pkg-1.1_respostas.csv` (somente a lista dos 46 IDs; NÃO preencha este arquivo) e (3) `legna_revisao_pkg-1.1_coordenadas.csv` (onde está cada número no PDF).

## Tarefa
Para cada um dos 46 IDs, localize o número no PDF usando `pagina` e a caixa (x0,y0)-(x1,y1) do arquivo de coordenadas (pontos PDF, origem no canto superior esquerdo; y cresce para baixo; rotacao_graus 0 = horizontal, 90 = lido de baixo para cima). Há valores repetidos na mesma página (ex.: vários "15"): **a caixa é o que identifica o número**, não o texto.

1. **Papel do número** (`papel_observado`): `cota_regular` (entre os riscos/setas da cota), `cota_deslocada` (cota cujo texto fica fora dos riscos, com chamada), `nota` (medida dentro de texto de nota), `nao_medida` (código, quantidade, numeração), ou `indeterminado`.
2. **Valor** (`classificacao_valor`): `correto`, `incorreto` ou `indeterminado`, para o valor escrito. Confira no desenho e nas relações com cotas vizinhas (somas de cadeia, cotas totais). Só use `correto`/`incorreto` com evidência concreta; sem evidência suficiente, `indeterminado`. Se `incorreto`, informe em `valor_observado` o valor que o desenho sustenta.

Fora do escopo: se a linha de cota "cobre o trecho certo" (não há linha azul nem intervalo medido neste material).

## Regras
- **Não invente medidas nem deduza valores sem evidência.** Na dúvida, `indeterminado`.
- Cite a evidência: página e coordenadas (da caixa e das cotas vizinhas usadas).
- Declare limitações (ex.: resolução, texto cortado, vistas sobrepostas, não consegui localizar).
- Não há resposta esperada; você não recebeu nenhum gabarito.

## Formato de saída (um CSV, UTF-8, uma linha por ID, os 46 IDs na ordem do arquivo de coordenadas)
`id,pagina,papel_observado,classificacao_valor,valor_observado,justificativa,evidencia_pagina_coordenadas,limitacoes`

Em `evidencia_pagina_coordenadas` use o formato `p6 (x0,y0,x1,y1); vizinhas: p6 (...)=340`. Identifique-se no cabeçalho do retorno como **IA (ChatGPT), avaliação complementar**; esta avaliação não é revisão humana independente.
