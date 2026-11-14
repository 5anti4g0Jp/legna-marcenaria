# Pacote de revisão independente (cego)

**pkg-1.0** — gerado em 2026-11-14 por `evaluation/review_package.py`. **STATUS: NÃO ENVIADO.** Aguardando conferência do responsável (ver "Defeitos conhecidos").

## Conteúdo entregue ao revisor (somente 2 arquivos, em `evaluation/review_package/pkg-1.0/entrega/`)
| Arquivo | SHA-256 |
|---|---|
| `legna_revisao_pkg-1.0_folha.html` | `8d345e85f371c62d3e706088c0de564b4ad23479a59db1b23ff98676cb909a5e` |
| `legna_revisao_pkg-1.0_respostas.csv` | `46892c19a7342cd7d9a0dd07a1aaa8f7fad62565d6e5921d2c6101cc714826ca` |

`MANIFESTO_PACOTE.json` (uso interno, fora de `entrega/`) registra versão, hashes, os 46 IDs e os hashes das fontes. Arquivos somente leitura. Pacotes são imutáveis: correção = novo pacote (pkg-1.1).

## O que foi removido da folha original (que NÃO era cega)
Rótulo do gabarito e resultado do algoritmo (estavam em `<details>`, apenas recolhidos), nomes/legenda de grupos (incluindo "controle: o gabarito considera correta"), hashes do algoritmo e do PDF, nome do arquivo/cliente do PDF, botão JSON, coluna `grupos` (mantida vazia; o registro exige o cabeçalho). A ordem agrupada por categoria foi trocada por página/índice. Os 46 IDs são os originais.

## Defeitos conhecidos de pkg-1.0
1. **16 dos 46 cartões não têm linha azul** (o algoritmo não mediu intervalo): p1-t6, p1-t7, p1-t13, p1-t16, p1-t20, p1-t30, p1-t32, p1-t34, p1-t37, p6-t18, p6-t22, p6-t25, p6-t31, p10-t4, p10-t13, p10-t14. A pergunta 2 não se aplica a eles, e o gabarito v0 diz `sim` para todos. Um revisor honesto responderia "Não"/"Não sei", o que apareceria como divergência e distorceria o grupo de controle. A ausência da linha também revela ao revisor quais itens o algoritmo não mediu.
2. Erro de digitação nas instruções ("não consegui ver o riscos").
3. O PDF original não está incluído (Q3 pede conferir "pelo contexto e soma das vizinhas"); depende de decisão do responsável.

## Limites
Revisor declarado, não autenticado. Os recortes mostram o intervalo candidato do algoritmo (necessário para a pergunta 2), o que pode ancorar o revisor.
