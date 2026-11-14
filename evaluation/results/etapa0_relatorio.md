# Etapa 0 — Linha de base do algoritmo de cotas (`ingest/dimensions.py`)

Gerado em 2026-11-14T17:05:46 · Python 3.13.18 · PyMuPDF 2.1 · algoritmo `sha256 696a8b83ee41…` (**não alterado nesta etapa**)

## 1. Resumo (PDF real, tokens revisados)

- Universo: **462** tokens numéricos em 34 páginas; **113** (24%) com rótulo revisado, nas páginas [1, 6, 10].
- Cotas revisadas: **104** (86 regulares + 18 deslocadas).
- **Confirmadas corretamente: 53 (51%)**.
- **Falsas confirmações (confirmada com intervalo errado): 3 (3%)**.
- Confirmadas sem veredito decidível: 3.
- Conflitos: **14**: **11 falsos alarmes verificados** por soma de cadeia (o valor escrito fecha a conta); **3 não decidíveis** pela imagem (valor escrito apenas ASSUMIDO correto; a geometria pode estar inconsistente com ele).
- **Cotas perdidas (sem medição): 31 (30%)**; perdidas na leitura: 0.
- Medidas em nota (ex.: `PROFUNDIDADE = 34 CM`, `12mm`): **5 de 5 não lidas**.
- Números que não são medida (K, W): 4 de 4 ignorados corretamente.
- **Associação a componentes: não implementada** no baseline (0%).

## 2. Metodologia e limitações do gabarito

- **Real:** census independente dos tokens + regras + inspeção visual de overlays do baseline. Rótulos feitos pelo assistente, **sem conferência independente**.
- Veredito de associação 'correta' vem de verificação visual global do overlay, **não token a token**. Valores escritos assumidos corretos (sem erro plantado no PDF real).
- Só 3 páginas foram revisadas; o resto do PDF entra apenas nas contagens de universo.
- **Sintético:** 60 itens em 9 desenhos gerados com resposta exata. Cobre estilos que o PDF real não tem, mas **não prova compatibilidade com Promob/AutoCAD**.

## 3. PDF real — por tipo de cota

Definições: *confirmada correta* = confirmada e intervalo certo; *falsa confirmação* = confirmada contra o intervalo errado; *conflito (falso alarme)* = marcada conflito, mas o valor escrito está certo; *perdida na leitura* = número nem virou candidato; *perdida na medição* = candidato sem medição.

**Por papel**

| Grupo | N | Confirmada correta | Falsa confirmação | Confirmada indeterminada | Conflito (tratado como falso alarme) | Perdida na leitura | Perdida na medição | Erro plantado detectado |
|---|---|---|---|---|---|---|---|---|
| cota_deslocada | 18 | 0 (0%) | 3 | 0 | 1 | 0 | 14 | 0 |
| cota_regular | 86 | 53 (62%) | 0 | 3 | 13 | 0 | 17 | 0 |

**Por orientação (cotas)**

| Grupo | N | Confirmada correta | Falsa confirmação | Confirmada indeterminada | Conflito (tratado como falso alarme) | Perdida na leitura | Perdida na medição | Erro plantado detectado |
|---|---|---|---|---|---|---|---|---|
| horizontal | 64 | 34 (53%) | 3 | 0 | 7 | 0 | 20 | 0 |
| vertical | 40 | 19 (48%) | 0 | 3 | 7 | 0 | 11 | 0 |

**Por tamanho (cotas)**

| Grupo | N | Confirmada correta | Falsa confirmação | Confirmada indeterminada | Conflito (tratado como falso alarme) | Perdida na leitura | Perdida na medição | Erro plantado detectado |
|---|---|---|---|---|---|---|---|---|
| 61-600mm | 45 | 28 (62%) | 0 | 2 | 9 | 0 | 6 | 0 |
| <=60mm | 24 | 2 (8%) | 3 | 1 | 3 | 0 | 15 | 0 |
| >600mm | 35 | 23 (66%) | 0 | 0 | 2 | 0 | 10 | 0 |

**Notas e números que não são medida**

| Papel | N | Resultado |
|---|---|---|
| medida_em_nota | 5 | nota_nao_lida=5 |
| nao_cota | 4 | ignorada_corretamente=4 |

**Por formato do número**

| Formato | N | Resultados |
|---|---|---|
| decimal | 2 | nota_nao_lida=2 |
| inteiro | 105 | confirmada_correta=53, perdida_medicao=31, conflito_falso_alarme=14, confirmada_indeterminada=3, confirmada_associacao_incorreta=3, nota_nao_lida=1 |
| misto | 2 | ignorada_corretamente=2 |
| unidade | 4 | ignorada_corretamente=2, nota_nao_lida=2 |

## 4. Escalas

- Estados do baseline nas 34 páginas: {'confirmado': 167, 'sem_medicao': 196, 'conflito': 23, 'confirmado_local': 14, 'sem_escala': 5}.
- Páginas com **mais de uma escala próxima** (divergência de 3% a 8%, causa ainda desconhecida: vistas diferentes ou viés de medida): [8, 12, 17, 23].
- **Escala espúria aceita:** {'6': [0.082]} (página → mm/pt); as cotas confirmadas contra ela são falsas confirmações.

## 5. Tempo

- PDF de 34 páginas: **0.796 s** (mediana de 3 execuções); mediana por página **18.9 ms**.

## 6. Sintético — por estilo (resposta exata)

| Grupo | N | Confirmada correta | Falsa confirmação | Confirmada indeterminada | Conflito (tratado como falso alarme) | Perdida na leitura | Perdida na medição | Erro plantado detectado |
|---|---|---|---|---|---|---|---|---|
| cad_preto_slash | 6 | 6 (100%) | 0 | 0 | 0 | 0 | 0 | 0 |
| decimais_unidades | 5 | 0 (0%) | 0 | 0 | 0 | 5 | 0 | 0 |
| deslocada_chamada | 7 | 3 (43%) | 0 | 0 | 0 | 0 | 4 | 0 |
| duas_escalas | 6 | 6 (100%) | 0 | 0 | 0 | 0 | 0 | 0 |
| erro_plantado | 8 | 4 (50%) | 1 | 0 | 0 | 0 | 0 | 3 |
| inclinada | 3 | 0 (0%) | 0 | 0 | 0 | 0 | 3 | 0 |
| lay_abaixo | 6 | 0 (0%) | 0 | 0 | 0 | 0 | 6 | 0 |
| lay_acima | 6 | 6 (100%) | 0 | 0 | 0 | 0 | 0 | 0 |
| setas_texto_na_linha | 6 | 0 (0%) | 0 | 0 | 0 | 0 | 6 | 0 |

**Por orientação**

| Grupo | N | Confirmada correta | Falsa confirmação | Confirmada indeterminada | Conflito (tratado como falso alarme) | Perdida na leitura | Perdida na medição | Erro plantado detectado |
|---|---|---|---|---|---|---|---|---|
| horizontal | 42 | 21 (50%) | 1 | 0 | 0 | 5 | 12 | 3 |
| inclinada | 3 | 0 (0%) | 0 | 0 | 0 | 0 | 3 | 0 |
| vertical | 8 | 4 (50%) | 0 | 0 | 0 | 0 | 4 | 0 |

**Por formato**

| Grupo | N | Confirmada correta | Falsa confirmação | Confirmada indeterminada | Conflito (tratado como falso alarme) | Perdida na leitura | Perdida na medição | Erro plantado detectado |
|---|---|---|---|---|---|---|---|---|
| decimal | 2 | 0 (0%) | 0 | 0 | 0 | 2 | 0 | 0 |
| inteiro | 48 | 25 (52%) | 1 | 0 | 0 | 0 | 19 | 3 |
| milhar | 1 | 0 (0%) | 0 | 0 | 0 | 1 | 0 | 0 |
| unidade | 2 | 0 (0%) | 0 | 0 | 0 | 2 | 0 | 0 |

**Números que não são cota (sintético):** Counter({'ignorada_corretamente': 5, 'falsa_deteccao_medida': 1, 'falso_candidato_sem_medicao': 1})

**Erros plantados (texto ≠ geometria)**

| Escrito | Geometria (mm) | Desvio | Resultado |
|---|---|---|---|
| 430 | 450 | -4.4% | erro_plantado_detectado |
| 100 | 1000 | -90.0% | erro_plantado_detectado |
| 746 | 764 | -2.4% | erro_plantado_detectado |
| 1010 | 1000 | +1.0% | erro_plantado_aceito |

**Escalas sintéticas**

| Desenho | Verdadeiras | Detectadas | Perdidas | Espúrias |
|---|---|---|---|---|
| lay_acima | [4.0] | [4.0] | [] | [] |
| lay_abaixo | [4.0] | [] | [4.0] | [] |
| cad_preto_slash | [4.0] | [4.0] | [] | [] |
| setas_texto_na_linha | [4.0] | [] | [4.0] | [] |
| decimais_unidades | [0.09375, 0.15625, 3.75, 5.625, 15.0] | [] | [0.09375, 0.15625, 3.75, 5.625, 15.0] | [] |
| inclinada | [4.0] | [] | [4.0] | [] |
| duas_escalas | [4.0, 6.5] | [4.0, 6.5005] | [] | [] |
| erro_plantado | [5.0] | [5.0] | [] | [] |
| deslocada_chamada | [2.0] | [2.0] | [] | [] |

## 7. Casos de erro

Total catalogado: **83** (lista completa em `etapa0_baseline.json` → `falhas`).

| N | Resultado | Causa | Exemplos |
|---|---|---|---|
| 16 | perdida_medicao | limite fixo de busca de 14 pt: linha a 14.2 pt | 1420 (p1), 760 (p1), 650 (p1), 750 (p1) |
| 14 | perdida_medicao | cota deslocada (texto fora dos riscos, com chamada) | 15 (p1), 15 (p1), 15 (p1), 15 (p1) |
| 11 | conflito_falso_alarme | baseline mediu 1825/1601 mm para 1720 etc.; valores escritos fecham por soma (200+1720+200 | 500 (p10), 200 (p10), 1720 (p10), 200 (p10) |
| 6 | perdida_medicao | desenho sintético: lay_abaixo | 2000 (lay_abaixo), 1000 (lay_abaixo), 600 (lay_abaixo), 400 (lay_abaixo) |
| 6 | perdida_medicao | desenho sintético: setas_texto_na_linha | 2000 (setas_texto_na_linha), 1000 (setas_texto_na_linha), 600 (setas_texto_na_linha), 400 (setas_texto_na_linha) |
| 5 | perdida_leitura | desenho sintético: decimais_unidades | 12,5 (decimais_unidades), 1.200 (decimais_unidades), 45cm (decimais_unidades), 7.5 (decimais_unidades) |
| 5 | nota_nao_lida | - | 12mm (p1), 34 (p6), 58,5 (p6), 58,5 (p6) |
| 4 | perdida_medicao | desenho sintético: deslocada_chamada | 15 (deslocada_chamada), 18 (deslocada_chamada), 25 (deslocada_chamada), 15 (deslocada_chamada) |
| 3 | perdida_medicao | desenho sintético: inclinada | 600 (inclinada), 800 (inclinada), 500 (inclinada) |
| 3 | confirmada_indeterminada | - | 450 (p1), 18 (p10), 200 (p10) |
| 3 | confirmada_associacao_incorreta | '15' deslocado confirmado contra a escala espúria 0,082 mm/pt | 15 (p6), 15 (p6), 15 (p6) |
| 1 | falsa_deteccao_medida | desenho sintético: lay_acima | 3 (lay_acima) |
| 1 | falso_candidato_sem_medicao | desenho sintético: lay_acima | 2 (lay_acima) |
| 1 | erro_plantado_aceito | desenho sintético: erro_plantado | 1010 (erro_plantado) |
| 1 | conflito_falso_alarme | '15' é chamada de espessura; o baseline mediu um intervalo de ~195 pt (640 mm) | 15 (p1) |
| 1 | conflito_falso_alarme | escrito 45, geometria 50 mm (+11%); não decidível pela imagem | 45 (p1) |
| 1 | conflito_falso_alarme | escrito 230, geometria 215 mm (-6%); não decidível pela imagem | 230 (p6) |
| 1 | perdida_medicao | linha paralela mais próxima a 63 pt (texto deslocado/chamada) | 370 (p10) |

## 8. O que a linha de base mostra

1. O algoritmo atual **não pode ser tratado como validação**: confirma intervalos errados e marca como conflito valores corretos.
2. As cotas **pequenas** (espessuras, ≤ 60 mm) são as que mais se perdem, e são justamente as que definem materiais.
3. Decimais, unidades, texto inclinado, texto na linha e texto abaixo da linha **não são tratados**.
4. A geometria detecta erros grandes (≥ ~2%), mas **não erros de ~1%**: 'geometricamente consistente' não é 'correto'.
5. Medidas em notas de texto (profundidades em cm) **não são lidas**; precisam de outra via de extração.

## 9. Reprodução

```bash
python -m evaluation.run_baseline --algo evaluation/baseline_etapa0/dimensions.py   # regera os resultados
python -m evaluation.report evaluation/results/etapa0_baseline.json > evaluation/results/etapa0_relatorio.md
python -m pytest tests_py/test_evaluation.py -q
```

