"""Adaptador: converte o resultado da Etapa 1 em objetos no formato do baseline (Dimension) para reusar as MESMAS métricas
e o MESMO gabarito da Etapa 0. Usa a análise automática preservada (não o estado atual), então decisões humanas não mudam a comparação."""
from __future__ import annotations

from types import SimpleNamespace

PRIMEIRO_AXIO = {"horizontal": "h", "vertical": "v"}


def dims_from_resultado(resultado, pagina: int | None = None) -> list:
    out = []
    for m in resultado.medidas:
        if pagina is not None and m.pagina != pagina:
            continue
        dados = next((e.dados for e in m.evidencias if e.tipo in ("geometria", "conflito_geometrico", "sem_medicao")), {})
        iv = dados.get("intervalo_pt")
        out.append(SimpleNamespace(
            text=m.texto_original, bbox=m.coords, status=m.analise_automatica.estado_algoritmo, orient=dados.get("eixo_assumido_pelo_algoritmo"),
            length_pt=dados.get("comprimento_pt"), interval_pt=tuple(iv) if iv else None, scale=dados.get("escala_mm_por_pt"),
            measured_mm=dados.get("valor_geometrico_mm"), suggestion_mm=dados.get("sugestao_mm"), value=m.valor_normalizado))
    return out
