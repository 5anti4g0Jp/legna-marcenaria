"""Modelo de saída da leitura técnica (Etapa 1): medidas rastreáveis com seis estados.

REGRAS DE SEGURANÇA (impostas pelo próprio modelo, não por convenção):
  * Uma medida geometricamente consistente NUNCA é aprovada automaticamente.
  * `aprovado` só é alcançável a partir de `pendente_revisao` e só por um ATOR HUMANO identificado.
  * Um objeto que alegue `aprovado` sem o registro da revisão humana não é sequer construído (validação).
  * A análise automática fica gravada à parte (`analise_automatica`) e NUNCA é apagada: uma decisão humana muda
    o `estado`, não apaga o que o algoritmo concluiu (isso preserva a comparação com a linha de base).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, computed_field, field_validator, model_validator

SCHEMA_VERSION = "etapa1.0"


class Estado(str, Enum):
    EXTRAIDO = "extraido"                                          # lido do documento; nenhuma verificação feita
    GEOMETRICAMENTE_CONSISTENTE = "geometricamente_consistente"    # a geometria não contradiz o valor escrito (NÃO é aprovação)
    CONFLITO = "conflito"                                          # a geometria contradiz o valor escrito, ou um humano rejeitou
    SEM_MEDICAO = "sem_medicao"                                    # não foi possível medir/verificar pela geometria
    PENDENTE_REVISAO = "pendente_revisao"                          # aguardando decisão humana
    APROVADO = "aprovado"                                          # confirmado por um humano identificado


class AtorTipo(str, Enum):
    SISTEMA = "sistema"
    HUMANO = "humano"


class TransicaoProibida(Exception):
    """Transição de estado não permitida (ou ator sem autoridade para ela)."""


E, G, C, S, P, A = (Estado.EXTRAIDO, Estado.GEOMETRICAMENTE_CONSISTENTE, Estado.CONFLITO, Estado.SEM_MEDICAO, Estado.PENDENTE_REVISAO, Estado.APROVADO)
SIS, HUM = AtorTipo.SISTEMA, AtorTipo.HUMANO

# (estado_atual, estado_novo) -> atores autorizados. `None` = criação. QUALQUER outro par é proibido.
PERMITIDAS: dict[tuple[Estado | None, Estado], frozenset[AtorTipo]] = {
    (None, E): frozenset({SIS}),
    (E, G): frozenset({SIS}), (E, C): frozenset({SIS}), (E, S): frozenset({SIS}),
    (E, P): frozenset({SIS, HUM}), (G, P): frozenset({SIS, HUM}), (C, P): frozenset({SIS, HUM}), (S, P): frozenset({SIS, HUM}),
    (P, A): frozenset({HUM}),            # ÚNICO caminho para aprovado: humano, a partir de pendente_revisao
    (P, C): frozenset({HUM}),            # rejeição humana
    (A, P): frozenset({HUM}),            # revogação humana
}


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Ator(BaseModel):
    model_config = ConfigDict(frozen=True)
    tipo: AtorTipo
    id: str = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def _id_nao_vazio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("id do ator não pode ser vazio")
        return v.strip()

    @model_validator(mode="after")
    def _humano_identificado(self):
        if self.tipo == HUM and self.id.lower() in {"sistema", "system", "auto", "automatico", "automático", "algoritmo", "ia", "ai", "claude"}:
            raise ValueError(f"'{self.id}' não é uma identificação humana válida")
        return self


class Documento(BaseModel):
    arquivo: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    paginas: int | None = None


class Evidencia(BaseModel):
    """Prova auditável de uma conclusão. `dados` guarda os números usados (escala, intervalos, desvios...)."""
    tipo: Literal["leitura", "unidade", "geometria", "conflito_geometrico", "sem_medicao", "orientacao", "revisao_humana", "observacao"]
    descricao: str
    metodo: str
    dados: dict[str, Any] = Field(default_factory=dict)
    coords: tuple[float, float, float, float] | None = None       # onde, na página, a evidência se apoia (pt, origem no topo esquerdo)


class Transicao(BaseModel):
    de: Estado | None
    para: Estado
    ator: Ator
    em: str
    motivo: str


class Revisao(BaseModel):
    revisor: str = Field(min_length=1)
    decisao: Literal["aprovado", "rejeitado"]
    em: str
    observacao: str | None = None
    valor_confirmado: str | None = None        # valor que o humano confirma (pode diferir do texto lido)

    @field_validator("revisor")
    @classmethod
    def _rev(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("revisor vazio")
        return v.strip()


class AnaliseAutomatica(BaseModel):
    """O que o algoritmo concluiu. Imutável na prática: decisões humanas NÃO a sobrescrevem."""
    estado: Estado
    estado_algoritmo: str                      # rótulo original do algoritmo (ex.: confirmado, confirmado_local, conflito, sem_medicao, sem_escala)
    algoritmo_sha256: str


class Medida(BaseModel):
    """Medida rastreável. IMUTÁVEL fora dos métodos de transição.

    O `estado` NÃO é um campo gravável: é sempre o destino da última transição do `histórico`. Histórico, evidências e
    conflitos são tuplas. Qualquer tentativa de escrever direto (ex.: `m.estado = ...`) levanta AttributeError, e as mudanças
    feitas pelos métodos são revalidadas e REVERTIDAS se violarem um invariante.
    """
    model_config = ConfigDict(revalidate_instances="always")
    id: str
    documento: Documento
    pagina: int = Field(ge=1)
    vista: str | None = None                   # não determinado nesta etapa
    componente: str | None = None              # não determinado nesta etapa
    texto_original: str                        # exatamente como aparece no documento
    valor_normalizado: float | None = None
    unidade: str | None = None
    unidade_fonte: Literal["declarada_na_pagina", "assumida", "desconhecida"] = "desconhecida"
    orientacao: Literal["horizontal", "vertical", "inclinada", "desconhecida"] = "desconhecida"
    angulo_graus: float | None = None
    coords: tuple[float, float, float, float]  # caixa do texto na página (pt, origem no topo esquerdo)
    metodo_extracao: str                       # ex.: "text-layer"
    confianca: float | None = Field(default=None, ge=0, le=1)   # confiança da LEITURA do número (não da medida)
    analise_automatica: AnaliseAutomatica | None = None
    evidencias: tuple[Evidencia, ...] = ()
    conflitos: tuple[dict[str, Any], ...] = ()
    historico: tuple[Transicao, ...] = ()
    revisao: Revisao | None = None
    _escrita: bool = PrivateAttr(default=False)

    # ---------------------------------------------------------------- estado derivado
    @computed_field  # type: ignore[prop-decorator]
    @property
    def estado(self) -> Estado:
        return self.historico[-1].para

    @model_validator(mode="before")
    @classmethod
    def _estado_serializado_deve_bater(cls, data):
        """Ao carregar JSON, o `estado` declarado precisa coincidir com o derivado do histórico (detecta adulteração)."""
        if isinstance(data, dict) and "estado" in data:
            data = dict(data); declarado = data.pop("estado"); hist = data.get("historico") or []
            if hist:
                ult = hist[-1]; destino = ult["para"] if isinstance(ult, dict) else ult.para
                if Estado(declarado) != Estado(destino):
                    raise ValueError(f"estado declarado '{declarado}' difere do último destino do histórico '{Estado(destino).value}'")
        return data

    def __setattr__(self, nome, valor):
        if nome.startswith("_") or self._escrita:
            return super().__setattr__(nome, valor)
        raise AttributeError(f"Medida é imutável: '{nome}' só pode mudar pelos métodos de transição (transitar/aprovar/rejeitar/revogar)")

    # ---------------------------------------------------------------- invariantes
    @model_validator(mode="after")
    def _invariantes(self):
        if not self.evidencias:
            raise ValueError("toda medida precisa de ao menos uma evidência (rastreabilidade)")
        if not self.historico:
            raise ValueError("toda medida precisa de histórico de transições")
        prev = None
        for t in self.historico:
            if t.de != prev:
                raise ValueError("histórico incoerente: 'de' não corresponde ao estado anterior")
            permitidos = PERMITIDAS.get((t.de, t.para))
            if permitidos is None or t.ator.tipo not in permitidos:
                raise ValueError(f"transição inválida no histórico: {t.de.value if t.de else 'criação'} -> {t.para.value} por '{t.ator.tipo.value}'")
            prev = t.para
        if self.estado == A:
            if self.revisao is None or self.revisao.decisao != "aprovado" or self.historico[-1].ator.tipo != HUM:
                raise ValueError("estado 'aprovado' exige revisão humana registrada (ator humano + revisão aprovada)")
        return self

    # ---------------------------------------------------------------- escrita controlada, com reversão
    def _mutar(self, **campos) -> None:
        antes = {k: getattr(self, k) for k in campos}
        self._escrita = True
        try:
            for k, v in campos.items():
                BaseModel.__setattr__(self, k, v)
            Medida.model_validate(self.model_dump())            # revalida TODOS os invariantes
        except Exception:
            for k, v in antes.items():
                BaseModel.__setattr__(self, k, v)               # reversão: o objeto nunca fica inválido
            raise
        finally:
            self._escrita = False

    def verificar(self) -> "Medida":
        """Revalida os invariantes a partir da forma serializada (usar antes de exportar)."""
        Medida.model_validate(self.model_dump())
        return self

    # ---------------------------------------------------------------- transições
    def _checar(self, para: Estado, ator: Ator, motivo: str) -> None:
        if not motivo.strip():
            raise TransicaoProibida("toda transição exige um motivo")
        permitidos = PERMITIDAS.get((self.estado, para))
        if permitidos is None:
            raise TransicaoProibida(f"transição {self.estado.value} -> {para.value} não é permitida")
        if ator.tipo not in permitidos:
            raise TransicaoProibida(f"ator '{ator.tipo.value}' não tem autoridade para {self.estado.value} -> {para.value}")

    def transitar(self, para: Estado, ator: Ator, motivo: str, evidencia: Evidencia | None = None, revisao: Revisao | None | str = "manter") -> "Medida":
        """Aplica uma transição validada. Levanta TransicaoProibida se o par ou o ator não forem autorizados."""
        self._checar(para, ator, motivo)
        campos = {"historico": self.historico + (Transicao(de=self.estado, para=para, ator=ator, em=agora(), motivo=motivo.strip()),)}
        if evidencia is not None:
            campos["evidencias"] = self.evidencias + (evidencia,)
        if revisao != "manter":
            campos["revisao"] = revisao
        self._mutar(**campos)
        return self

    def enfileirar_revisao(self, ator: Ator, motivo: str = "enfileirada para revisão humana") -> "Medida":
        return self.transitar(P, ator, motivo)

    def _decidir(self, destino: Estado, decisao: str, revisor: str, observacao, valor_confirmado) -> "Medida":
        ator = Ator(tipo=HUM, id=revisor)
        rev = Revisao(revisor=ator.id, decisao=decisao, em=agora(), observacao=observacao, valor_confirmado=valor_confirmado)
        return self.transitar(destino, ator, f"{decisao} por revisão humana",
                              Evidencia(tipo="revisao_humana", descricao=f"{decisao} por {ator.id}", metodo="revisao_humana",
                                        dados={"revisor": ator.id, "observacao": observacao, "valor_confirmado": valor_confirmado}), revisao=rev)

    def aprovar(self, revisor: str, observacao: str | None = None, valor_confirmado: str | None = None) -> "Medida":
        """Aprovação HUMANA. Exige estado `pendente_revisao`. O revisor fica registrado como ator e na revisão."""
        return self._decidir(A, "aprovado", revisor, observacao, valor_confirmado)

    def rejeitar(self, revisor: str, observacao: str | None = None, valor_confirmado: str | None = None) -> "Medida":
        """Rejeição HUMANA: volta a `conflito`, preservando análise e evidências."""
        return self._decidir(C, "rejeitado", revisor, observacao, valor_confirmado)

    def revogar(self, revisor: str, motivo: str) -> "Medida":
        """Um humano retira uma aprovação anterior (volta a `pendente_revisao`)."""
        ator = Ator(tipo=HUM, id=revisor)
        return self.transitar(P, ator, f"aprovação revogada: {motivo}",
                              Evidencia(tipo="revisao_humana", descricao=f"aprovação revogada por {ator.id}", metodo="revisao_humana",
                                        dados={"revisor": ator.id, "acao": "revogada", "motivo": motivo}), revisao=None)


class Algoritmo(BaseModel):
    nome: str
    arquivo: str
    sha256: str
    parametros: dict[str, Any] = Field(default_factory=dict)


class Resumo(BaseModel):
    total: int
    por_estado: dict[str, int]
    aprovadas_automaticamente: int = 0          # DEVE ser sempre 0; mantido explícito para auditoria


class Resultado(BaseModel):
    schema_version: str = SCHEMA_VERSION
    gerado_em: str
    documento: Documento
    algoritmo: Algoritmo
    medidas: list[Medida]
    resumo: Resumo
    avisos: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sem_aprovacao_automatica(self):
        if self.resumo.aprovadas_automaticamente != 0:
            raise ValueError("aprovações automáticas são proibidas")
        return self


def resumir(medidas: list[Medida]) -> Resumo:
    por = {e.value: 0 for e in Estado}
    for m in medidas:
        por[m.estado.value] += 1
    auto = sum(1 for m in medidas if any(t.para == A and t.ator.tipo != HUM for t in m.historico))
    return Resumo(total=len(medidas), por_estado=por, aprovadas_automaticamente=auto)
