# Levantamento de dados da Legna (Fase 2)

**Estado:** formulário pronto e testado; **nenhum dado foi preenchido**. Tudo nasce `pendente`. Nada aqui é preço ou regra da Legna: os preços de referência antigos (inventados pelo assistente) **não foram copiados** para o formulário.

## Arquivos
- `levantamento/campos.py`: perguntas, tipos, unidades e criticidade (fonte única). Sem valores comerciais.
- `levantamento/formulario_levantamento_legna.xlsx`: o que a Legna recebe. Abas: LEIA-ME, **Campos** (60 itens únicos, 28 que bloqueiam o orçamento), **materiais**, **fitas**, **ferragens**, **terceirizados**, **fornecedores**, **regra_dobradica**, **regra_corredica** (tabelas, 30 linhas cada).
- `levantamento/formulario.py`: `gerar`, `validar`, `exportar`.

## Os três status
| Status | Exige | O sistema faz |
|---|---|---|
| `confirmado` | valor + fonte + data da fonte + quem confirmou (pessoa) | usa como dado real |
| `pendente` | valor **vazio** | pergunta, não inventa; bloqueia o que depende dele |
| `provisorio` | valor + justificativa | só para testes; marcado `uso_comercial: false`; **nunca** em orçamento |

Validações: tipo (número, inteiro, % até 100, moeda ≥ 0, data, lista/sim-não), data de fonte não futura, confirmação por pessoa (recusa "sistema", "IA", "assistente"...), linhas de tabela com colunas obrigatórias, `id` dos campos intocado.

## Uso
```bash
python -m levantamento.formulario gerar levantamento/formulario_levantamento_legna.xlsx
python -m levantamento.formulario validar arquivo_preenchido.xlsx      # resumo, erros, "pronto_para_orcamento"
python -m levantamento.formulario exportar arquivo_preenchido.xlsx saida.json   # confirmados + provisórios separados
```
`pronto_para_orcamento` só é verdadeiro quando não há erro, os 28 campos críticos estão **confirmados** e existe ao menos uma linha confirmada em materiais, fitas, ferragens e regra_dobradica.

## Limites
- É um levantamento; **não está ligado** ao motor nem à configuração (`config/`): a ligação vem depois da aprovação da estrutura e da consolidação.
- A lista de perguntas é minha; a Legna pode ter regras que não perguntei (campo texto livre "observação" em cada linha).
- xlsx preenchido à mão aceita erros de digitação; por isso existe o validador.
