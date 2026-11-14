# Projetos reais (Promob e AutoCAD): o que preciso receber

**Status:** nenhum arquivo de Promob ou AutoCAD foi recebido. Hoje o único projeto técnico real é do **SketchUp LayOut** (confirmado pelo metadado `Creator: LayOut in SketchUp Pro 2023`). Ele **não** representa os outros programas.

## 1. Princípios

1. **Nada será chamado de "compatível com Promob" ou "com AutoCAD"** até passar nos critérios da seção 6, com arquivos reais cuja origem tenha sido conferida.
2. **A origem é evidência, não prova.** O metadado do PDF/DXF é registrado e comparado com a ficha, mas pode ter sido regravado por outro programa. A confirmação final é de quem gerou o arquivo.
3. **Resultados por software, separados.** Não se generaliza de um estilo para outro.
4. Exemplos públicos da internet **não** contam como prova de compatibilidade, a menos que a origem seja confirmada (e mesmo assim entram como "teste adicional", não como validação).

## 2. Arquivos de cada projeto (por software)

| # | Arquivo | Obrigatório? | Para que serve |
|---|---|---|---|
| A | **PDF do projeto executivo como a Legna recebe/envia hoje** (sem reexportar, sem escanear) | **Sim** | Teste principal: leitura de texto, cotas, vistas e escalas |
| B | **DXF do mesmo projeto, mesma revisão** (e DWG, se houver) | **Sim** | Referência **exata** das cotas (entidades `DIMENSION` trazem a medida) e teste dos leitores CAD |
| C | **Lista de peças / plano de corte do mesmo projeto** (CSV, XLS, XLSX ou XML, conforme o software exporta) | **Sim** | É a "resposta certa" para validar o levantamento de peças nas etapas futuras |
| D | **Versão impressa e escaneada** do PDF (200 a 300 dpi) | Desejável | Teste de OCR no estilo real de desenho |
| E | **Lista de corte da produção real** (o que a marcenaria de fato cortou) | Muito valioso | Gabarito independente para o orçamento final |
| F | Arquivo nativo (`.promob`, `.dwg` original) | Opcional | Só consulta; **não será lido** |

**Importante:** A, B e C devem ser da **mesma revisão** do projeto. Não misturar versões.

## 3. Informações de cada projeto (ficha)

Modelo: `evaluation/intake/ficha_projeto_template.csv` (uma linha por arquivo). **Campo desconhecido fica vazio; não será presumido.**

- `software` e `versao_software` (ex.: "Promob Plus 2024", "AutoCAD 2023") e **quem gerou** o arquivo.
- `como_exportado`: caminho de menu ou impressora usada e as opções relevantes. Perguntas-chave:
  - O PDF foi exportado pelo próprio programa ou impresso por "Microsoft Print to PDF"/outro PDF virtual?
  - O **texto** foi mantido como texto ou convertido em curvas? (muda se existe camada de texto)
  - Cores ou monocromático?
- `unidade` do desenho (mm ou cm) e `escala_plotagem` por folha/viewport.
- `estilo_cotas`: seta ou risco, casas decimais, separador (vírgula ou ponto), unidade escrita ou omitida.
- `tipo_movel`, `folhas`, `material_padrao`, `espessura_padrao_mm`, `ferragens`.
- `tem_lista_producao_real` (sim/não).
- `autorizado_uso` e `anonimizado` (sim/não): **dados de cliente final** (nome, endereço) devem ser removidos ou autorizados.
- `sha256` do arquivo (opcional): permite conferir que o arquivo recebido é o enviado.

## 4. Diversidade desejada

Pelo menos, **por software**: 1 projeto simples (um armário) e 1 complexo (cozinha ou closet); idealmente, 1 com portas de correr ou gavetas internas e 1 com cotas de espessura. Se existir, 1 com cotas em cm ou com decimais.

Mínimo viável para começar a medir: **1 projeto completo (A+B+C) por software**. Para falar em compatibilidade: **2 projetos por software**.

## 5. Riscos técnicos a testar (hipóteses, **não** fatos verificados)

Não tenho Promob nem AutoCAD aqui; o que segue é o que costuma acontecer e **precisa ser confirmado com os arquivos reais**:

**AutoCAD**
- O PDF plotado pode ter o **texto convertido em curvas** (sem camada de texto). Sem texto, o leitor atual não vê as cotas; seria preciso OCR (não confiável para medida) ou o DXF. A ferramenta de recebimento já sinaliza esse caso.
- Cotas **pretas**, no mesmo traço do desenho: o algoritmo atual detecta cotas por cor, e isso foi testado só com cotas vermelhas (LayOut) e em um desenho sintético.
- **Escala por viewport** na mesma folha, e estilo de cota com texto **sobre** a linha ou com setas (ambos falharam no teste sintético da Etapa 0).
- No DXF, as entidades `DIMENSION` guardam a medida real: referência exata para conferir o PDF.
- **DWG não é lido neste ambiente.** Preciso do DXF.

**Promob**
- Não sei como ele exporta PDF e listas; podem existir vistas renderizadas (imagem) em vez de vetor, cotas automáticas por vista, textos em português com decimais e unidades e planilhas de peças com colunas próprias.
- Preciso ver **o que a Legna realmente usa** para decidir onde investir (PDF, planilha ou DXF).

## 6. Critérios para declarar compatibilidade (por software)

1. Origem conferida (metadado + ficha + confirmação de quem gerou).
2. Mínimo de **2 projetos** do software, todos com A+B+C.
3. Gabarito de cotas **revisado por humano independente** (mesmo processo da baseline).
4. Métricas medidas e publicadas por tipo de cota: acertos, perdidas, falsas confirmações, conflitos, tempo.
5. Limiares **definidos antes** de medir (decisão conjunta), para não ajustar a régua ao resultado.
6. Falhas conhecidas documentadas (inclusive as que não conseguimos resolver).

## 7. Como os arquivos serão usados

```bash
# 1) recebimento: confere formato, hash, metadados, texto x curvas, unidade, lista de peças, e compara com a ficha
python -m evaluation.intake_check ./projetos_recebidos --ficha ficha.csv --saida recebimento.md
# 2) baseline do algoritmo congelado sobre os novos arquivos (sem alterá-lo)
# 3) gabarito do novo projeto, revisado por humano
```
A saída do recebimento **não** afirma compatibilidade: é só o diagnóstico de entrada.

## 8. O que NÃO preciso

Senhas, arquivos de licença, modelos 3D, bibliotecas de blocos, nem dados de clientes finais sem autorização.

## 9. Checklist para a Legna

- [ ] PDF executivo original (A) de ao menos 1 projeto Promob e 1 AutoCAD
- [ ] DXF do mesmo projeto e revisão (B)
- [ ] Lista de peças/plano de corte do mesmo projeto (C)
- [ ] Ficha preenchida (`software`, `versao_software`, `como_exportado`, `unidade`, `escala_plotagem`)
- [ ] Autorização de uso e anonimização confirmadas
- [ ] (opcional) PDF escaneado (D) e lista de corte da produção (E)
