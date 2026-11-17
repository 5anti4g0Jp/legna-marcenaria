# Contrato `documento_tecnico` — versão 1.0.0 (PROPOSTA, não integrada à `main`)

Ponte formal entre o **leitor Python** (`ingest/`) e o **motor de cálculo TypeScript** (`src/`). Esta etapa entrega só a **especificação, exemplo fictício, validadores isolados e testes**. Nada de `ingest/`, `src/`, baseline, gabarito ou pacotes foi alterado. O leitor completo **não** foi implementado.

## Arquivos (`contratos/documento_tecnico/`)
| Arquivo | Função |
|---|---|
| `v1/documento_tecnico.schema.json` | Esquema JSON (Draft 2020-12): estrutura, campos obrigatórios/opcionais, enums |
| `v1/validar.py` | Validador Python: esquema + 20+ regras semânticas. **Reusa** `ingest.technical.model.PERMITIDAS` (não duplica a máquina de estados) |
| `v1/ts/documento_tecnico.ts` | Protótipo TS: esquema `zod`, subconjunto de segurança, hash idêntico ao do Python, conversão para a entrada do motor |
| `v1/campos_dependentes_legna.json` | 41 campos que o PDF não traz (ou traz só em parte) e dependem da Legna, ligados ao formulário comercial |
| `v1/exemplo_ficticio.json` | Exemplo **FICTÍCIO** (marcado `marcador_exemplo`; recusado em modo produção) |
| `v1/gerar_fixtures.py` + `v1/fixtures/` | 25 casos inválidos + 1 válido (minor novo), cada um quebra UMA regra; `manifest.json` |
| `tests_py/test_contrato_documento_tecnico.py`, `v1/ts/documento_tecnico.test.ts` | 45 testes Python + 18 TS (incl. paridade e hash idêntico nas duas linguagens) |

## 1. Estrutura do documento
```
contrato{nome,versao} · marcador_exemplo? · projeto{id,software_origem} · documento{arquivo,sha256,paginas,tipo_conteudo,...}
extracao{gerado_em,leitor,algoritmo_cotas{sha256}} · paginas[] · vistas[] · modulos[] · itens[] · conflitos[] · pendencias[]
elegibilidade{pronto_para_calculo,orcamento_completo,bloqueios} · resumo · integridade{hash_conteudo} · avisos?
```
- **`itens[]`** é o coração: UM formato para tudo que sai do PDF (`tipo`: cota, nota, rotulo_componente, material, acabamento, ferragem, acessorio, quantidade, observacao_producao, declaracao_unidade, marcador_nao_preenchido). Cada item carrega: página + coordenadas, `texto_original`, `valor` (número/texto/unidade/fonte da unidade), `origem` (método; OCR com motor e confiança), `confianca`, **`natureza`** (`explicita` | `sugerida` | `inferida`), `chave_semantica`, `relacoes`, `analise_automatica`, `evidencias[]`, `estado` + `historico[]` + `revisao` (humano).
- **`natureza`** materializa "sugerido ≠ confirmado": `MDF SUGERIDO` entra como `sugerida`; quantidade deduzida da geometria entra como `inferida`.
- **`vistas[]`** e **`modulos[]`** existem, mas a v1 aceita `vista.tipo = "indeterminado"`: a interpretação de vistas ainda não existe, e o contrato não finge que existe.
- **`pendencias[]`** (derivada pelo leitor) referencia o registro `campos_dependentes_legna.json` (`campo_legna`), ou é `null` quando a pendência é de revisão (conflito, inferido, OCR).
- **`integridade.hash_conteudo`**: SHA-256 da canonicalização `json-ordenado-v1` (chaves ordenadas, sem espaços, inteiros sem `.0`; sem notação exponencial). Detecta alteração após a validação; **não prova autoria**.

## 2. Regras de validação (código → regra)
| Código | Regra | Python | TS |
|---|---|---|---|
| E-VERSAO | major diferente de 1 ou versão inválida: recusa sem leitura parcial | ✔ | ✔ |
| E-SCHEMA | campo obrigatório ausente, tipo/enum errado, campo desconhecido (na versão atual) | ✔ | ✔ |
| E-EXEMPLO | documento com `marcador_exemplo` recusado em modo produção | ✔ | ✔ |
| E-ID-DUP / E-REF / E-PAG | ids únicos; referências existem; páginas consistentes | ✔ | só ID-DUP |
| E-ESTADO-HIST | `estado` = destino da última transição | ✔ | ✔ |
| E-TRANSICAO | cada transição está em `PERMITIDAS` e o ator tem autoridade | ✔ | — (fonte única) |
| E-APROV-HUMANO / E-APROV-AUTO | `aprovado` só com revisão do mesmo humano que fez a última transição + evidência `revisao_humana`; nunca por sistema | ✔ | parcial |
| E-OCR-CONF | OCR sempre com confiança informada | ✔ | — |
| E-NAT-REV | item `sugerida`/`inferida` só é aprovado com o **valor confirmado pela pessoa** | ✔ | — |
| E-INFERIDA-EVID | `inferida` exige evidência de geometria com coordenadas | ✔ | — |
| E-ESPESSURA | espessura informada exige fonte (não existe "assumida"); material sem espessura **exige pendência** `mat.espessura` | ✔ | — |
| E-SUGERIDO | material sugerido não confirmado exige pendência `mat.especificacao_confirmada` | ✔ | — |
| E-FERRAGEM-PEND | porta/gaveta sem ferragem ligada exige pendência (`ferr.dobradica`/`ferr.corredica`) | ✔ | — |
| E-UNIDADE | item aprovado com unidade assumida/desconhecida; página com cotas sem unidade declarada exige pendência `doc.unidade_desenho` | ✔ | — |
| E-CONFLITO-ENTRADA / E-CONFLITO-APROV | itens em conflito constam em `conflitos`; mesma `chave_semantica` com valores diferentes nunca tem dois aprovados; conflito aberto não tem aprovado | ✔ | — |
| E-PEND-REVISAO | item OCR/inferido não aprovado exige pendência de revisão | ✔ | — |
| E-PEND-CAMPO / E-PEND-BLOQ | `campo_legna` existe no registro; pendência crítica não pode ser rebaixada | ✔ | — |
| E-RESUMO / E-ELEG / E-HASH | derivados (resumo, elegibilidade, hash) conferem | ✔ | ✔ |

**Princípio de duas camadas:** o TS faz defesa em profundidade com o subconjunto acima (✔ ou parcial) e **confia no Python** para o resto; as fixtures com `esperado_ts = null` documentam explicitamente o que o TS não reverifica. Um documento só deve chegar ao TS depois de passar no validador Python.

## 3. Compatibilidade de versões e erros
- **SemVer.** *Major* diferente → recusa (`E-VERSAO`). *Minor* maior que o suportado → aceita **com aviso** `A-VERSAO-MINOR` e ignora campos desconhecidos; campo desconhecido nunca aprova nada. *Patch* → ignorado. Na versão suportada, campos desconhecidos são **erro** (esquema estrito).
- **Campos ausentes:** obrigatório ausente → `E-SCHEMA` com caminho JSON Pointer; opcional ausente → tratado como `null`/vazio; informação ausente **no PDF** → nunca vira valor: vira `pendencia`.
- **Formato de erro** (igual nas duas linguagens): `{codigo, caminho, mensagem}`; as regras semânticas só rodam se o esquema passou.

## 4. Mapeamento Python → JSON → TypeScript
| Python (`ingest/technical/model.py`) | JSON (`itens[]`) | TS |
|---|---|---|
| `Medida.id/pagina/coords/texto_original` | `id/pagina/coords/texto_original` | `Item` (zod) |
| `valor_normalizado`, `unidade`, `unidade_fonte` | `valor.numero/unidade/unidade_fonte` | `paraMm()` |
| `metodo_extracao` ("text-layer", "ocr") | `origem.metodo_extracao` (`camada_texto`, `ocr`) + `origem.ocr` | — |
| `confianca`, `orientacao`, `angulo_graus` | idem | — |
| `analise_automatica` | `analise_automatica` (não é apagada pela decisão humana) | — |
| `evidencias` (`Evidencia`) | `evidencias[]` (+ tipos `ocr`, `quantidade_inferida`, `relacao_paginas`) | — |
| `historico` / `estado` (derivado) / `revisao` | `historico[]` / `estado` / `revisao` | verificado (subconjunto) |
| `Documento{arquivo,sha256,paginas}` | `documento` (global, não por item) | `projeto/documento` |
| `Resultado.resumo` | `resumo` (recalculado) | conferido |
| `vista`, `componente` (hoje `None`) | `relacoes[]` (`aparece_na_vista`, `pertence_ao_modulo`) | — |

**Entrada do motor (TS):** `paraEntradaMotor(doc)` devolve `EntradaMotor { projeto, modulos[W,H,D em mm], pendencias, prontoParaCalculo, orcamentoCompletoLeitura, itensNaoAprovados, avisos }`.
- Só entram **itens `aprovado`**; `valor_confirmado` da pessoa prevalece sobre o texto lido; cm/m convertidos para mm; unidade ausente ⇒ dimensão nula (nunca "assume mm").
- Módulo só vira `CabSpec` quando W, H e D estão aprovados (`prontoParaCabSpec`); **`cor`/material vem do catálogo confirmado, não do documento**.
- A v1 **não monta portas, gavetas nem prateleiras** (depende de interpretação de vistas): fica fora e é avisado em `avisos`.
- `orcamentoCompletoLeitura` cobre só a leitura. O orçamento final só é "completo" se **também** os preços e regras de fabricação estiverem confirmados na configuração.

## 5. Informações pendentes e conflitantes
- **Pendente:** toda informação ausente do PDF que o cálculo precisa gera `pendencia` (`bloqueia`: `calculo` | `orcamento` | `nenhum`) ligada a um id do registro `campos_dependentes_legna.json` (que aponta para o formulário comercial: `Campos:<id>` ou `tabela:<aba>.<coluna>`). `elegibilidade` é **derivada**: qualquer pendência `calculo` ⇒ `pronto_para_calculo=false`; qualquer `calculo|orcamento` ou conflito aberto ⇒ `orcamento_completo=false`.
- **Conflito:** valores diferentes para a mesma `chave_semantica` ficam todos em `conflito` e listados em `conflitos[]`. Só se resolve com decisão humana: um vencedor `aprovado`, os demais rejeitados (`conflito`), `estado: resolvido` com `resolucao`. Conflito aberto bloqueia o cálculo.
- **Registro de campos:** 41 campos em 10 categorias (espessuras, materiais, ferragens, fitas de borda, parafusos e acessórios, regras de fabricação, folgas e tolerâncias, preços e fornecedores, documento). **Lacunas do formulário atual** (declaradas, não escondidas): `acess.parafusos_cavilhas` (o formulário não pergunta regra de parafusos/fixações) e `mat.superficie_aplicacao` (qual material em qual peça; vem do render, resolve-se na revisão humana).

## 6. Testes de contrato (implementados)
Esquema válido e igual aos seis estados do Python · fonte única da máquina de estados (o validador não redefine `PERMITIDAS`; o TS não a contém) · exemplo válido em teste e recusado em produção · uma fixture por regra (26) com os códigos esperados · fixtures reproduzíveis do exemplo · hash canônico igual em Python e TS · compatibilidade de versões · formato de erro · registro de campos (categorias pedidas, sem valores comerciais, lacunas declaradas, referências ao formulário — verificadas contra a branch `fase2/levantamento-dados`) · conversão para o motor só com itens aprovados. Verificação por mutação: desligar duas regras do validador faz a suíte falhar.
**Propostos para depois:** (a) o produtor Python emitir o documento a partir de `Resultado` e passar no validador; (b) round-trip Python → JSON → TS → relatório do motor; (c) documentos reais de Promob/AutoCAD como casos de regressão; (d) fuzz de entradas malformadas; (e) teste de compatibilidade entre versões quando existir a 1.1.

## 7. Riscos de integração
1. **Duas implementações do esquema** (JSON Schema e zod): podem divergir. Mitigação: testes de paridade e do mesmo conjunto de estados/enums; ideal futuro: gerar o zod a partir do JSON Schema.
2. **Canonicalização do hash:** ponto sensível (números, Unicode, notação exponencial). A v1 proíbe exponencial e normaliza `800.0`→`800`; qualquer outro emissor (não Python) precisa seguir `json-ordenado-v1`. O hash não autentica.
3. **TS confia no Python** para transições e regras de dados; documento que não passou no validador Python não deve chegar ao motor. Pendente: garantir isso no fluxo (o carimbo `integridade` sozinho não prova que foi validado).
4. **Contrato à frente do leitor:** o leitor atual só produz cotas. Texto, rótulos, materiais e ferragens ainda não têm produtor; os exemplos mostram o formato, não uma capacidade existente.
5. **`rules.ts`/`fabricacao.json`** preenchem padrões assumidos sem registrar o status da regra: o orçamento só poderá marcar "incompleto" por regra assumida quando a configuração ganhar status por grupo de regras (mudança de produção, não feita).
6. **Base de evidência estreita:** campos e categorias vêm de 1 projeto real (SketchUp LayOut); Promob/AutoCAD podem exigir novos tipos de item (v1.x ou 2.0).
7. **Nomes/dados de cliente** em `projeto.nome` e `documento.arquivo`: o contrato não os anonimiza; decidir política antes de persistir documentos reais.
8. **`unidade_fonte` e cm/mm:** notas em cm e cotas em mm na mesma página são normalizadas pelo `valor.unidade`; erro de unidade só é pego por revisão humana.
