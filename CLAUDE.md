# Legna Marcenaria - orçamentista técnico (memória do projeto)

Objetivo: o cliente envia um projeto executivo (PDF/imagem); o sistema interpreta, lista peças, calcula
consumo/compra e gera orçamento. **Prioridade absoluta: precisão do levantamento de materiais.**

## Regras que NÃO mudam
- Nunca inventar medida, material, espessura ou preço. Faltou dado -> pergunta de confirmação.
- IA interpreta/extrai; **cálculos são do motor determinístico** (TypeScript). Regras de fabricação e preços
  são configuração editável, não código.
- Não declarar compatibilidade com formato sem testar. Na `main` (desde o merge 1): leitores testados para PDF digital/escaneado, PNG, JPG,
  DXF, TIFF, XLSX, XLS, CSV, SVG. **DWG NÃO validado** (ODA File Converter indisponível; leitor pronto, recusa com ToolMissing).
  **Compatibilidade com Promob e AutoCAD NÃO comprovada** (só há 1 projeto real, SketchUp LayOut).
- JSON é interno; o cliente nunca prepara JSON.
- Sem frontend por enquanto (backend primeiro).
- O usuário quer discordância/teste das ideias, sem bajulação; respostas diretas, em português.

## Arquitetura
- `ingest/` (Python, PyMuPDF + Tesseract): leitura -> Document JSON com tokens, coordenadas, origem (text-layer|ocr) e confiança.
- `src/` (TypeScript): `engine.ts` (pipeline), `nesting.ts` (plano de corte guilhotina multi-estratégia, veio, serra),
  `validate.ts`, `rules.ts` (módulo -> peças), `config.ts` (esquemas + validação), `report.ts`.
- `projects/fernanda-sertorio/`: projeto de teste real (34 págs, SketchUp LayOut): `build.ts` + `export_xlsx.py`.
- `evaluation/` (na `main`): baseline/gabarito da Etapa 0, fluxo de revisão independente, pacotes `pkg-1.0`/`pkg-1.1`. `ingest/technical/`: 6 estados e registro de revisões humanas.
- `config/` (somente na branch `feature/config-estrutura`, NÃO integrada): `catalogo.json`, `precos.json`, `fabricacao.json`.

## Estado (atualizado em 2026-11-16, após o merge 1)
- **`main` = `ccbe4f4`** (merge 1: `etapa2-tecnica` → `main`, fast-forward). Backup do estado anterior: branch `backup/main-pre-merge-2026-11-16` (= `0bd5a5c`).
  Testes em clone novo: **315 pytest + 27 vitest**, `tsc` ok, `projects/fernanda-sertorio/build.ts` ok (orçamento idêntico ao anterior; preços de REFERÊNCIA).
- Conteúdo da `main`: Etapa 0 (baseline+gabarito v0 em `evaluation/`), Etapa 1 (`ingest/technical/`), leitores modulares (`ingest/readers/`), cliente Anthropic (`ingest/ai/`, sem chave real),
  Docker validado, fluxo de revisão independente (registro → relatório → resolução → congelamento `rev1`, testado só com respostas SIMULADAS), pacotes de revisão `pkg-1.0` (histórico) e `pkg-1.1`.
- **Intocáveis:** algoritmo de cotas (`ingest/dimensions.py` = `evaluation/baseline_etapa0/dimensions.py`, sha `696a8b83…`), gabarito v0 (`febda860…`), baseline v0 (`6a2d8446…`), pacotes `pkg-1.0`/`pkg-1.1`.
- **Revisão independente dos 46 itens:** NENHUM CSV real recebido. Envio do `pkg-1.1`: status `preparado_aguardando_envio` (`evaluation/review_package/envios.jsonl`); falta destinatário e envio efetivo.
  A avaliação do ChatGPT (complementar, sem HTML; material em `pkg-1.1/auxiliar/`) NÃO é revisão humana independente. **`rev1` não congelada. Etapa 2 NÃO iniciada.**
- Gabarito v0: feito pelo assistente, 113 tokens (104 cotas) nas págs 1, 6, 10, SEM revisão independente. Itens sem linha azul (16) excluídos da pergunta 2 (`evaluation/review/exclusoes_q2.json`).
- **Branches** (nenhuma excluída/arquivada sem aprovação do usuário):
  - `etapa2-tecnica` = igual à `main`; `ambiente-leitores` e `etapa2-leitura-exata` já estão contidas nela (redundantes).
  - `feature/config-estrutura` (NÃO integrar sem aprovação): `config/*.json`, `src/config.ts`, `src/rules.ts` refatorado; 27 vitest ok; **quebra o `build.ts`** da main se mesclada sozinha.
  - `migracao/build-config`: config + `build.ts` migrado, ISOLADA (não mesclada na main). Orçamento: 0 diferenças numéricas, 27 de texto (nomes de 10 materiais e texto de rodabase). Ver `docs/migracao_build_config.md`.
  - `fase2/levantamento-dados`: formulário de levantamento da Legna (60 campos + 7 tabelas, `confirmado/pendente/provisorio`), NÃO ligado ao motor.
  - `experimento/pdf-permissivo`: pdfplumber/pdfminer e pypdfium2 alimentando o algoritmo congelado (104 cotas idênticas neste PDF), ISOLADO; PyMuPDF NÃO foi substituído.
  - `backup/main-pre-merge-2026-11-16`: backup da main anterior.
- **Licença:** PyMuPDF é AGPL-3.0 (ou licença comercial Artifex): decisão jurídica pendente; cotação pendente.
- Plano da leitura técnica: 0 baseline OK | 1 estados/modelo OK | 2 números (decimais/unidades) BLOQUEADA até aprovação | 3 tolerância/escalas | 4 textos deslocados | 5 vistas | 6 soma de cadeia | 7 componentes | 8 IA | 9 relatório.
- Fases combinadas (2026-11-16): 1 Validação | 2 Dados reais | 3 Arquitetura/consolidação | 4 Motor (Etapas 2-9, bloqueada) | 5 Produto (só depois de validar leitura e cálculo em projetos reais).
- OCR medido (scan simulado): 78-100% das cotas, 0-13 números falsos/página -> **OCR nunca é dado confirmado**.
- Todos os preços e a mão de obra são de REFERÊNCIA (inventados pelo assistente, status "referencia"). Nenhum é da Legna.

## ONDE PARAMOS (ponto de retomada, 2026-11-16)
Merge 1 concluído e validado. **Merge 2 (`feature/config-estrutura` → `main`) NÃO autorizado**; só a preparação isolada (`migracao/build-config`) foi autorizada e feita.
Aguardando: (a) CSV do revisor humano; (b) decisão do usuário sobre o merge 2 e sobre os nomes dos materiais/texto de rodabase; (c) PDFs reais Promob/AutoCAD e dados da Legna (formulário);
(d) decisão jurídica PyMuPDF. Não avançar para a Etapa 2, não congelar a `rev1`, não alterar gabarito/baseline/algoritmo.

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

### Decisões em aberto (usuário ainda não respondeu; proposta de config segue SEM aprovação)
1. Fornecedores: um por item (simples) ou vários para comparar cotações? **Recomendação: vários.**
2. Edição: `store.ts` com validação + CLI simples, sem tela. Pode ser assim?
3. Preço com histórico: só o atual ou também datas anteriores? **Recomendação: só o atual por enquanto.**

### Ao retomar
1. Aguardar aprovação do merge 2 (a migração do `build.ts` já está pronta em `migracao/build-config`). 2. Perguntar/confirmar as 3 decisões acima.
3. Depois: `fornecedores.json`, `store.ts` (+CLI), `ai-context.ts`; folgas/descontos/espessura de fita. 4. Manter os 315 pytest + 27 vitest verdes. 5. Só então Etapa 2 (IA) e Etapas 2-9 da leitura.

## Pendências / decisões abertas
1. Aprovar estrutura de config: fornecedores (um ou vários por item), `store.ts` + CLI, preço sem histórico.
2. Legna informar (formulário em `fase2/levantamento-dados`): espessura padrão do corpo, ferragens, mão de obra por m², preços reais; enviar 2-3 PDFs Promob/AutoCAD com ficha.
3. Etapa 2 (IA): chamadas à API Anthropic são autenticadas pela sessão neste ambiente (credencial de usuário recusada).
   Em produção (Vercel) é preciso `ANTHROPIC_API_KEY` nas variáveis de ambiente do projeto.
4. Validar a IA contra projetos reais da Legna (precisa de mais PDFs de outros softwares e scans reais).
5. Repo `5anti4g0Jp/Legna-scanner` (vazio) ainda existe: só o usuário pode apagar (proxy bloqueia). Criar repos também é bloqueado.

## Ambiente
- Tesseract precisa de `apt-get install tesseract-ocr tesseract-ocr-por`; não roda em serverless comum da Vercel -> backend de leitura em contêiner.
- Script de setup do ambiente cloud falha ao instalar `rectpack` (setuptools/install_layout); não afeta este projeto.
- Vercel: conta Hobby, 5 projetos, nenhum da Legna. GitHub: sessão só acessa repos já anexados.
