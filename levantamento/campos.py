"""Definição do levantamento de dados da Legna (Fase 2). FONTE ÚNICA do formulário e do validador.

REGRA: este arquivo define PERGUNTAS, tipos e opções de resposta. Não contém NENHUM valor comercial (preço, espessura, folga, percentual...): todo valor vem da Legna.
Os campos já nascem com status `pendente`.

Status:
  confirmado  valor informado pela Legna, com fonte, data e quem confirmou. Único status que o sistema pode usar como dado real.
  pendente    sem valor (ainda não informado). Bloqueia o que depende dele; o sistema pergunta, não inventa.
  provisorio  estimativa MARCADA (com justificativa) para permitir testes. Nunca aparece como preço/medida real e nunca entra em orçamento ao cliente.
"""
from __future__ import annotations

STATUS = ("confirmado", "pendente", "provisorio")
TIPOS = ("texto", "numero", "inteiro", "percentual", "moeda_brl", "sim_nao", "lista", "data")
CRITICIDADE = ("bloqueia_orcamento", "importante", "opcional")
COMUNS = ["status", "valor", "fonte", "data_fonte", "confirmado_por", "justificativa_provisorio", "observacao"]

OPC_MATERIAL = ["MDF", "MDP", "MDF ultra/ultrafino", "compensado", "madeira maciça", "vidro", "espelho", "outro"]
OPC_SIMNAO = ["sim", "nao"]


def C(id, secao, rotulo, ajuda, tipo, unidade="", crit="importante", alimenta="orcamento", opcoes=None):
    assert tipo in TIPOS and crit in CRITICIDADE
    return {"id": id, "secao": secao, "rotulo": rotulo, "ajuda": ajuda, "tipo": tipo, "unidade": unidade, "criticidade": crit, "alimenta": alimenta, "opcoes": opcoes or []}


# ------------------------------------------------------------------------------------------------ campos únicos
CAMPOS = [
    # 1. Empresa e projetos recebidos
    C("emp.razao_social", "1 Empresa", "Razão social", "Nome jurídico (para o orçamento).", "texto", crit="opcional", alimenta="documento"),
    C("emp.responsavel", "1 Empresa", "Responsável pelas informações deste levantamento", "Pessoa que responde e confirma os dados.", "texto", crit="bloqueia_orcamento", alimenta="rastreabilidade"),
    C("emp.contato", "1 Empresa", "E-mail ou telefone do responsável", "Para tirar dúvidas.", "texto", crit="importante", alimenta="rastreabilidade"),
    C("emp.softwares", "1 Empresa", "Softwares usados para gerar projetos executivos", "Liste todos, com versão (ex.: nome e ano). Quem gera cada tipo de projeto?", "texto", crit="bloqueia_orcamento", alimenta="leitura"),
    C("emp.formato_entrega", "1 Empresa", "Formato com que o projeto chega ao orçamento", "PDF digital, PDF impresso/escaneado, DWG, DXF, imagem...", "texto", crit="bloqueia_orcamento", alimenta="leitura"),
    C("emp.exporta_texto_como_texto", "1 Empresa", "O PDF mantém o texto selecionável (não convertido em curvas)?", "Abra o PDF e tente selecionar um número de cota.", "sim_nao", crit="bloqueia_orcamento", alimenta="leitura", opcoes=OPC_SIMNAO),
    C("emp.unidade_desenho", "1 Empresa", "Unidade das cotas no desenho", "mm, cm ou outra; se varia por software, descreva.", "texto", crit="bloqueia_orcamento", alimenta="leitura"),
    C("emp.convencao_cotas", "1 Empresa", "Como as cotas são escritas", "Decimais (vírgula/ponto), com ou sem unidade, cotas de espessura, chamadas (leader)...", "texto", crit="importante", alimenta="leitura"),
    C("emp.tipos_movel", "1 Empresa", "Tipos de móvel que a Legna produz", "Cozinha, armário, painel, bancada, closet...", "texto", crit="importante", alimenta="regras"),

    # 2. Parâmetros de corte e aproveitamento
    C("cor.espessura_serra", "2 Corte", "Espessura do corte da serra (kerf)", "Perda de material em cada corte.", "numero", "mm", "bloqueia_orcamento", "corte"),
    C("cor.refilo", "2 Corte", "Refilo (aparo) nas bordas da chapa", "Quanto se descarta em cada borda antes de cortar.", "numero", "mm", "bloqueia_orcamento", "corte"),
    C("cor.sobra_minima", "2 Corte", "Menor sobra que a Legna reaproveita", "Abaixo disso a sobra é descartada.", "numero", "mm", "importante", "corte"),
    C("cor.respeita_veio", "2 Corte", "Peças com veio devem respeitar o sentido do veio?", "Define se o plano de corte pode girar as peças.", "sim_nao", crit="bloqueia_orcamento", alimenta="corte", opcoes=OPC_SIMNAO),
    C("cor.corte_na_chapa_inteira", "2 Corte", "A compra considera chapas inteiras?", "Ou a Legna compra meia chapa/cortes sob medida?", "texto", crit="bloqueia_orcamento", alimenta="compra"),
    C("cor.perda_extra", "2 Corte", "Perda extra de material adotada (além do plano de corte)", "Margem de segurança, se houver.", "percentual", "%", "importante", "compra"),
    C("cor.tolerancia_corte", "2 Corte", "Tolerância de corte aceita", "Variação máxima aceitável nas peças.", "numero", "mm", "opcional", "qualidade"),

    # 3. Espessuras padrão por peça (valor em mm, por tipo de peça)
    C("esp.corpo", "3 Espessuras padrão", "Corpo do módulo (laterais, base, topo)", "Espessura usada por padrão.", "numero", "mm", "bloqueia_orcamento", "regras"),
    C("esp.prateleira", "3 Espessuras padrão", "Prateleira", "", "numero", "mm", "bloqueia_orcamento", "regras"),
    C("esp.divisoria", "3 Espessuras padrão", "Divisória", "", "numero", "mm", "importante", "regras"),
    C("esp.porta", "3 Espessuras padrão", "Porta", "", "numero", "mm", "bloqueia_orcamento", "regras"),
    C("esp.fundo", "3 Espessuras padrão", "Fundo do módulo", "", "numero", "mm", "bloqueia_orcamento", "regras"),
    C("esp.gaveta_frente", "3 Espessuras padrão", "Frente de gaveta", "", "numero", "mm", "importante", "regras"),
    C("esp.gaveta_lateral", "3 Espessuras padrão", "Lateral e frente/traseira da caixa da gaveta", "", "numero", "mm", "importante", "regras"),
    C("esp.gaveta_fundo", "3 Espessuras padrão", "Fundo da gaveta", "", "numero", "mm", "importante", "regras"),
    C("esp.painel_ou_tampo", "3 Espessuras padrão", "Painéis, tampos e peças em espessura dobrada/laminada", "Descreva quando se usa 25, 30, 50 mm etc. e como é montado.", "texto", crit="importante", alimenta="regras"),

    # 4. Folgas e descontos (portas, gavetas, prateleiras, fundo)
    C("fol.porta_lateral", "4 Folgas e descontos", "Porta: folga lateral", "Diferença entre o vão e a porta, por lado.", "numero", "mm", "bloqueia_orcamento", "regras"),
    C("fol.porta_topo_base", "4 Folgas e descontos", "Porta: folga superior/inferior", "", "numero", "mm", "bloqueia_orcamento", "regras"),
    C("fol.porta_entre", "4 Folgas e descontos", "Porta: folga entre portas", "", "numero", "mm", "bloqueia_orcamento", "regras"),
    C("fol.porta_sobreposicao", "4 Folgas e descontos", "Porta: tipo de aplicação", "Sobreposta, embutida, meia-sobreposta... e a sobreposição em mm.", "texto", crit="bloqueia_orcamento", alimenta="regras"),
    C("fol.prateleira_recuo", "4 Folgas e descontos", "Prateleira: recuo em relação à profundidade do módulo", "", "numero", "mm", "importante", "regras"),
    C("fol.prateleira_folga_lateral", "4 Folgas e descontos", "Prateleira: folga lateral", "", "numero", "mm", "importante", "regras"),
    C("fol.fundo_encaixe", "4 Folgas e descontos", "Fundo: como é fixado e quanto se desconta", "Rasgo, rebaixo, colado/parafusado nas costas; descontos na largura e na altura.", "texto", crit="bloqueia_orcamento", alimenta="regras"),
    C("fol.gaveta_lateral", "4 Folgas e descontos", "Gaveta: folga lateral para a corrediça", "", "numero", "mm", "importante", "regras"),
    C("fol.gaveta_altura", "4 Folgas e descontos", "Gaveta: regra de altura da caixa em relação à frente", "", "texto", crit="importante", alimenta="regras"),
    C("fol.gaveta_profundidade", "4 Folgas e descontos", "Gaveta: regra de profundidade da caixa", "Como se escolhe o comprimento a partir da profundidade do módulo.", "texto", crit="importante", alimenta="regras"),
    C("fol.rodape_regra", "4 Folgas e descontos", "Rodapé/rodabase: altura e como é construído", "", "texto", crit="importante", alimenta="regras"),

    # 5. Regras de fabricação
    C("fab.dobradicas_regra", "5 Regras de fabricação", "Quantidade de dobradiças por porta", "Por faixa de altura (ex.: até X mm = N). Informe a tabela completa.", "texto", crit="bloqueia_orcamento", alimenta="regras"),
    C("fab.puxador_regra", "5 Regras de fabricação", "Puxadores por porta e por gaveta", "Quantidade e posição.", "texto", crit="importante", alimenta="regras"),
    C("fab.corredica_regra", "5 Regras de fabricação", "Escolha do comprimento da corrediça", "Comprimentos disponíveis e como se escolhe.", "texto", crit="importante", alimenta="regras"),
    C("fab.pinos_prateleira", "5 Regras de fabricação", "Pinos por prateleira regulável", "", "inteiro", "un", "importante", "regras"),
    C("fab.fita_bordas", "5 Regras de fabricação", "Quais bordas levam fita, por tipo de peça", "Descreva por peça (laterais, base, topo, prateleiras, portas, fundo...).", "texto", crit="bloqueia_orcamento", alimenta="regras"),
    C("fab.fita_desperdicio", "5 Regras de fabricação", "Desperdício de fita de borda na compra", "", "percentual", "%", "bloqueia_orcamento", "compra"),
    C("fab.fundo_divisao", "5 Regras de fabricação", "Fundo maior que a chapa: como é emendado", "", "texto", crit="importante", alimenta="regras"),
    C("fab.usinagens", "5 Regras de fabricação", "Usinagens especiais (CNC, rebaixos, furos) e como são cobradas", "", "texto", crit="importante", alimenta="orcamento"),
    C("fab.montagem_local", "5 Regras de fabricação", "O que é montado na marcenaria e o que é montado no cliente", "", "texto", crit="importante", alimenta="orcamento"),

    # 6. Mão de obra
    C("mo.criterio", "6 Mão de obra", "Critério de cobrança da mão de obra", "Por m² de peça, por hora, por módulo, por etapa...", "texto", crit="bloqueia_orcamento", alimenta="orcamento"),
    C("mo.valor", "6 Mão de obra", "Valor da mão de obra no critério acima", "Informe a unidade (ex.: R$ por m²).", "moeda_brl", "R$", "bloqueia_orcamento", "orcamento"),
    C("mo.base_calculo", "6 Mão de obra", "Sobre qual área/quantidade incide", "Área líquida das peças? Inclui fundos finos? Gavetas?", "texto", crit="bloqueia_orcamento", alimenta="orcamento"),
    C("mo.etapas", "6 Mão de obra", "Etapas cobradas (corte, fita, usinagem, montagem, acabamento, instalação)", "Quais entram e se têm valor próprio.", "texto", crit="importante", alimenta="orcamento"),
    C("mo.instalacao", "6 Mão de obra", "Instalação no cliente: como é cobrada", "", "texto", crit="importante", alimenta="orcamento"),

    # 7. Custos indiretos, margem e condições
    C("fin.indiretos_pct", "7 Custos, margem e condições", "Custos indiretos (overhead) sobre o custo direto", "", "percentual", "%", "bloqueia_orcamento", "orcamento"),
    C("fin.margem_pct", "7 Custos, margem e condições", "Margem desejada sobre o preço", "Informe se é margem sobre preço ou markup sobre custo.", "percentual", "%", "bloqueia_orcamento", "orcamento"),
    C("fin.impostos", "7 Custos, margem e condições", "Impostos e como entram no preço", "", "texto", crit="importante", alimenta="orcamento"),
    C("fin.frete_entrega", "7 Custos, margem e condições", "Frete e entrega: como são cobrados", "", "texto", crit="importante", alimenta="orcamento"),
    C("fin.validade_orcamento", "7 Custos, margem e condições", "Validade do orçamento", "", "inteiro", "dias", "importante", "documento"),
    C("fin.pagamento", "7 Custos, margem e condições", "Condições de pagamento padrão", "", "texto", crit="opcional", alimenta="documento"),
    C("fin.prazo_producao", "7 Custos, margem e condições", "Prazo de produção padrão", "", "texto", crit="opcional", alimenta="documento"),
    C("fin.garantia", "7 Custos, margem e condições", "Garantia oferecida", "", "texto", crit="opcional", alimenta="documento"),

    # 8. Precisão e aceite
    C("prec.tolerancia_orcamento", "8 Precisão e aceite", "Diferença máxima aceitável entre o orçamento e o consumo real", "Define o critério de aceite do sistema (ex.: 3%?). A Legna decide.", "percentual", "%", "bloqueia_orcamento", "aceite"),
    C("prec.projetos_de_validacao", "8 Precisão e aceite", "Projetos já executados que podem servir de conferência (com lista de corte real)", "Quantos e quais; a lista de corte e o consumo real de chapas.", "texto", crit="bloqueia_orcamento", alimenta="validacao"),
]

# ------------------------------------------------------------------------------------------------ tabelas (uma linha por item; N linhas em branco)
def T(nome, titulo, ajuda, colunas):
    return {"nome": nome, "titulo": titulo, "ajuda": ajuda, "colunas": colunas}


def col(id, rotulo, tipo, unidade="", obrig=True, opcoes=None, ajuda=""):
    assert tipo in TIPOS
    return {"id": id, "rotulo": rotulo, "tipo": tipo, "unidade": unidade, "obrigatoria": obrig, "opcoes": opcoes or [], "ajuda": ajuda}


TABELAS = [
    T("materiais", "Chapas e materiais de corpo", "Uma linha por combinação (material, espessura, cor/acabamento, fornecedor). Preço por chapa inteira.", [
        col("tipo", "Tipo de material", "lista", opcoes=OPC_MATERIAL), col("fabricante_linha", "Fabricante / linha", "texto"), col("cor_acabamento", "Cor / acabamento", "texto"),
        col("espessura_mm", "Espessura", "numero", "mm"), col("largura_chapa_mm", "Largura da chapa", "numero", "mm"), col("comprimento_chapa_mm", "Comprimento da chapa", "numero", "mm"),
        col("tem_veio", "Tem veio (sentido importa)?", "sim_nao", opcoes=OPC_SIMNAO), col("preco_chapa", "Preço por chapa", "moeda_brl", "R$"), col("fornecedor", "Fornecedor", "texto"),
        col("data_preco", "Data do preço", "data")]),
    T("fitas", "Fitas de borda", "Uma linha por cor/acabamento e medida.", [
        col("cor_acabamento", "Cor / acabamento", "texto"), col("largura_mm", "Largura", "numero", "mm"), col("espessura_mm", "Espessura", "numero", "mm"),
        col("unidade_venda", "Unidade de venda (rolo/metro) e tamanho do rolo", "texto"), col("preco_unitario", "Preço por metro", "moeda_brl", "R$/m"), col("fornecedor", "Fornecedor", "texto"), col("data_preco", "Data do preço", "data")]),
    T("ferragens", "Ferragens", "Dobradiças, corrediças, puxadores, pinos, sistemas de correr, etc. Uma linha por item comprado.", [
        col("categoria", "Categoria", "texto"), col("descricao", "Descrição (modelo/medida)", "texto"), col("unidade", "Unidade de compra", "texto"), col("preco_unitario", "Preço por unidade", "moeda_brl", "R$"),
        col("fornecedor", "Fornecedor", "texto"), col("data_preco", "Data do preço", "data"), col("regra_uso", "Quando é usada (regra)", "texto", obrig=False)]),
    T("terceirizados", "Itens de terceiros e especiais", "Vidro, espelho, palhinha, LED, pedra, estofado, serviços de CNC... Uma linha por item.", [
        col("descricao", "Descrição", "texto"), col("unidade", "Unidade de cobrança (m², un, m...)", "texto"), col("preco_unitario", "Preço por unidade", "moeda_brl", "R$"),
        col("fornecedor", "Fornecedor / prestador", "texto"), col("data_preco", "Data do preço", "data")]),
    T("fornecedores", "Fornecedores", "Quem fornece o quê (para comparar cotações).", [
        col("nome", "Fornecedor", "texto"), col("fornece", "O que fornece", "texto"), col("contato", "Contato", "texto", obrig=False), col("prazo_dias", "Prazo de entrega", "inteiro", "dias", obrig=False),
        col("pedido_minimo", "Pedido mínimo", "texto", obrig=False)]),
    T("regra_dobradica", "Dobradiças por altura da porta (tabela)", "Uma linha por faixa de altura. Preencha 'até' em mm e a quantidade por porta.", [
        col("altura_ate_mm", "Altura da porta até", "numero", "mm"), col("qtd_por_porta", "Dobradiças por porta", "inteiro", "un")]),
    T("regra_corredica", "Corrediças: comprimentos disponíveis", "Uma linha por comprimento vendido.", [
        col("comprimento_mm", "Comprimento", "numero", "mm"), col("tipo", "Tipo (telescópica, oculta...)", "texto"), col("capacidade_kg", "Capacidade", "numero", "kg", obrig=False)]),
]
LINHAS_TABELA = 30
