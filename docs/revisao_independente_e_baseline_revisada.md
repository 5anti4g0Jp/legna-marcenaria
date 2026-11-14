# Revisão independente e baseline revisada (rev1, rev2…)

Estado: infraestrutura pronta e testada com respostas **simuladas**. **Nenhuma revisão real foi feita ainda.** A baseline vigente continua sendo a v0 (feita pelo assistente, sem revisão independente).

## Fluxo (cada passo só grava, nunca altera o que veio antes)
1. **Folha**: `evaluation/review/folha_conferencia_baseline_etapa0.html` (46 itens, cega) + CSV modelo.
2. **Registrar** respostas: `evaluation.review_record.registrar(csv)` — exige 1 revisor humano identificado, ids da folha, valores válidos; copia byte a byte (somente leitura) e encadeia hash em `review/respostas/MANIFEST.jsonl`. Recusa duplicado e gabarito alterado.
3. **Comparar**: `evaluation.review_report.gerar/render` — concordância por revisor e por pergunta, grupo de controle (limiar 0,75), kappa entre revisores, divergências (`discorda_do_gabarito`, `revisor_nao_sei`, `gabarito_indeterminado_com_resposta`, `revisores_discordam`). Gabarito indeterminado + "não sei" é coerente e não é divergência.
4. **Resolver**: `evaluation.resolutions.resolver(...)` — decisor humano, evidência ≥ 20 caracteres e tipificada, valor anterior preservado, log com cadeia de hash. Só itens da folha.
5. **Congelar**: `evaluation.freeze_baseline.congelar(versao="rev1", congelado_por=...)` — recusa sem respostas, com divergência sem resolução ou versão existente. Gera gabarito revN, reavaliação com o algoritmo congelado, `diff_vs_v0.md`, MANIFEST de hashes (somente leitura). `verificar_versao` detecta adulteração de qualquer artefato.

## Limites
- Só os 46 itens são conferidos; o restante do gabarito segue sem revisão independente (registrado em `limitacoes`).
- Identidade do revisor é declarada, não autenticada.
- Algoritmo (`696a8b83…`) e métricas da v0 não mudam.
