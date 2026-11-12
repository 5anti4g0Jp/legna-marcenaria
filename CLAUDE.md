# Legna Marcenaria - orçamentista técnico (memória do projeto)

Objetivo: o cliente envia um projeto executivo (PDF/imagem); o sistema interpreta, lista peças, calcula
consumo/compra e gera orçamento. **Prioridade absoluta: precisão do levantamento de materiais.**

## Regras que NÃO mudam
- Nunca inventar medida, material, espessura ou preço. Faltou dado -> pergunta de confirmação.
- IA interpreta/extrai; **cálculos são do motor determinístico** (TypeScript). Regras de fabricação e preços
  são configuração editável, não código.
- Não declarar compatibilidade com formato sem testar. Suportados e testados: PDF digital, PDF escaneado, PNG, JPG.
  DWG/DXF/TIFF/XLSX/XLS/CSV/SVG: recusados explicitamente (etapas futuras).
- JSON é interno; o cliente nunca prepara JSON.
- Sem frontend por enquanto (backend primeiro).
- O usuário quer discordância/teste das ideias, sem bajulação; respostas diretas, em português.

## Arquitetura
- `ingest/` (Python, PyMuPDF + Tesseract): leitura -> Document JSON com tokens, coordenadas, origem (text-layer|ocr) e confiança.
- `src/` (TypeScript): `engine.ts` (pipeline), `nesting.ts` (plano de corte guilhotina multi-estratégia, veio, serra),
  `validate.ts`, `rules.ts` (módulo -> peças), `config.ts` (esquemas + validação), `report.ts`.
- `projects/fernanda-sertorio/`: projeto de teste real (34 págs, SketchUp LayOut): `build.ts` + `export_xlsx.py`.
- `config/` (somente na branch `feature/config-estrutura`): `catalogo.json`, `precos.json`, `fabricacao.json`.

## Estado (2026-11-12)
- `main` = Etapa 1 pronta (leitura). **46 testes**: 27 vitest (`npx vitest run`) + 19 pytest (`python -m pytest tests_py`).
- `feature/config-estrutura` = WIP da configuração externa; `build.ts` quebrado nessa branch (lê prices.json removido).
  Aguarda aprovação da estrutura (fornecedores, store.ts, ai-context.ts).
- Etapas: 1 leitura OK | 2 extração por IA pendente | 3 consumo/compra OK no motor | 4 orçamento OK (preços de referência) | 5 DWG/DXF/etc. pendente.
- OCR medido (scan simulado): 78-100% das cotas, 0-13 números falsos/página -> **OCR nunca é dado confirmado**.
- Todos os preços e a mão de obra são de REFERÊNCIA (inventados pelo assistente, status "referencia"). Nenhum é da Legna.

## ONDE PARAMOS (ponto de retomada, 2026-11-12)
Última ação: apresentei a **estrutura de configuração proposta** e o inventário do que já existia. **Nada foi implementado além do WIP**;
aguardando o usuário responder 3 decisões. Não avançar sem a resposta. Backend apenas, sem frontend, sem mexer em `ingest/`.

### Estrutura proposta (aguardando aprovação)
```
config/
  catalogo.json       materiais (MDF/MDP/outros), cores+acabamentos, chapas comerciais, fitas (largura+espessura),
                      ferragens (dobradiça, corrediça, puxador...)
  fornecedores.json   NOVO: fornecedor, contato, prazo
  precos.json         preço por item + fornecedor + data + status (confirmado/referencia/pendente)
  fabricacao.json     regras por peça: portas, gavetas, prateleiras, divisórias, fundos, folgas, descontos técnicos,
                      usinagem, serra/refilo
src/
  config.ts           esquemas + validação + verificações cruzadas   (já iniciado, branch feature/config-estrutura)
  store.ts            NOVO: cadastrar/editar/remover com validação, gravando nos JSON (e CLI simples)
  rules.ts            expande módulos em peças lendo a config        (já iniciado)
  ai-context.ts       NOVO: gera o contexto de regras que a IA recebe na Etapa 2
```
Inventário (já existia, evitar duplicar): tipos em `src/types.ts` (manter); `HINGE_RULES`/pinos em `src/hardware.ts` e
`DEFAULT_CUTTING` em `src/engine.ts` (duplicam a config, migrar); `build.ts` tem tamanho de chapa 2750x1840, "veio = nome começa com tauari"
e peças de gaveta digitadas à mão (migrar). Lacunas: fornecedores, folgas/descontos de porta, espessura da fita, cadastro de
cores/acabamentos, "outros materiais" (vidro/espelho/palhinha) sem a mesma estrutura, edição validada.

### Preparação para a IA (Etapa 2)
A IA recebe o catálogo e as regras como contexto e devolve **apenas o que leu do desenho** (medidas, nomes de material, nº de portas).
Um **passo determinístico casa o nome lido com um item do catálogo**. Sem correspondência segura -> vira pergunta de confirmação.
**A IA nunca cria ids nem preços.** Os cálculos continuam só no motor.

### Decisões em aberto (usuário ainda não respondeu)
1. Fornecedores: um por item (simples) ou vários para comparar cotações? **Recomendação: vários.**
2. Edição: `store.ts` com validação + CLI simples, sem tela. Pode ser assim?
3. Preço com histórico: só o atual ou também datas anteriores? **Recomendação: só o atual por enquanto.**

### Ao retomar
1. Perguntar/confirmar as 3 decisões. 2. Migrar `projects/fernanda-sertorio/build.ts` para a config (está quebrado na branch).
3. Criar `fornecedores.json`, `store.ts` (+CLI), `ai-context.ts`; adicionar folgas/descontos/espessura de fita à config.
4. Testes automatizados para cadastros e cálculos; manter os 46 testes da Etapa 1 verdes. 5. Só então Etapa 2 (IA).

## Pendências / decisões abertas
1. Aprovar estrutura de config: fornecedores (um ou vários por item), `store.ts` + CLI, preço sem histórico.
2. Legna informar: espessura padrão do corpo, ferragens (dobradiça/corrediça), mão de obra por m², preços reais.
3. Etapa 2 (IA): chamadas à API Anthropic são autenticadas pela sessão neste ambiente (credencial de usuário recusada).
   Em produção (Vercel) é preciso `ANTHROPIC_API_KEY` nas variáveis de ambiente do projeto.
4. Validar a IA contra projetos reais da Legna (precisa de mais PDFs de outros softwares e scans reais).
5. Repo `5anti4g0Jp/Legna-scanner` (vazio) ainda existe: só o usuário pode apagar (proxy bloqueia). Criar repos também é bloqueado.

## Ambiente
- Tesseract precisa de `apt-get install tesseract-ocr tesseract-ocr-por`; não roda em serverless comum da Vercel -> backend de leitura em contêiner.
- Script de setup do ambiente cloud falha ao instalar `rectpack` (setuptools/install_layout); não afeta este projeto.
- Vercel: conta Hobby, 5 projetos, nenhum da Legna. GitHub: sessão só acessa repos já anexados.
