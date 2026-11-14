# Pacote de revisão independente (cego)

**pkg-1.0** — gerado em 2026-11-14. **STATUS: NÃO ENVIADO; SUBSTITUÍDO por pkg-1.1** (preservado intacto como histórico).
**pkg-1.1** — gerado em 2026-11-14 por `evaluation/review_package.py`. **STATUS: aguardando aprovação do responsável para envio.**

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

---
# pkg-1.1 (vigente)

## Arquivos entregues (3, em `evaluation/review_package/pkg-1.1/entrega/`, somente leitura)
| Arquivo | Papel | SHA-256 |
|---|---|---|
| `legna_revisao_pkg-1.1_folha.html` | instrumento de resposta | `304a89bfe771df1ada823848cd75de9c6fcc4483222535ac96a92a188c9bfd51` |
| `legna_revisao_pkg-1.1_respostas.csv` | instrumento de resposta (idêntico ao do pkg-1.0) | `46892c19a7342cd7d9a0dd07a1aaa8f7fad62565d6e5921d2c6101cc714826ca` |
| `legna_revisao_pkg-1.1_projeto_referencia.pdf` | material de referência, somente leitura (cópia byte a byte do PDF avaliado) | `bb6385f7eac3d67d5c6303a3033beb5340577b1af3bef1cfac1e2a77c0dd83dc` |

Uso interno (NÃO enviar): `pkg-1.1/MANIFESTO_PACOTE.json` (sha `50efd8a1828ba52b7ba17fee531877eda0a1f487f91dd2e3b6840b079b993649`), `evaluation/review/exclusoes_q2.json` (sha `223bde0dcf7b8bec7f79207d3379d86329f177f7b80e196f179cb2757e1f33f7`).

## Alterações em relação ao pkg-1.0
1. Erro de digitação corrigido ("os riscos").
2. Instrução: nos cartões sem linha azul, pergunta 2 = "Não sei" e observação "sem linha azul".
3. Regra formal (decisão do responsável, 2026-11-14): em 16 itens sem linha azul a pergunta 2 não entra na comparação com o gabarito, nas taxas por revisor/grupo, no grupo de controle, na concordância entre revisores nem nas divergências. Registrada em `evaluation/review/exclusoes_q2.json` e aplicada por `review_report`. Perguntas 1 e 3 continuam valendo. **Gabarito v0 não alterado.**
   Itens: p1-t6, p1-t7, p1-t13, p1-t16, p1-t20, p1-t30, p1-t32, p1-t34, p1-t37, p6-t18, p6-t22, p6-t25, p6-t31, p10-t4, p10-t13, p10-t14. Detecção por pixels azuis no recorte (0 nos 16; mínimo de 86 nos demais).
4. PDF original incluído como referência (verificado: sem anotações, anexos ou termos do gabarito; nome de arquivo neutro; a página "p.N" do cartão é a página do PDF).
5. Instruções sobre o PDF; regra de consulta ajustada ("nenhum arquivo além do PDF de referência").

## Pontos a considerar
- O PDF é um projeto de cliente: confirmar autorização para compartilhar com o revisor.
- Os recortes mostram o intervalo candidato do algoritmo (necessário para a pergunta 2); isso pode ancorar o revisor.
- A ausência de linha azul agora é declarada ao revisor nos 16 itens (inevitável com a instrução pedida).
