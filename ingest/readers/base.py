"""Núcleo comum dos leitores: modelo de dados, erros e verificações de arquivo.

Todo leitor devolve um ReadResult cujos itens (Extracted) preservam: arquivo de origem, formato original,
localização (página/aba/layer/entidade), coordenadas, unidade, valor, método de extração, confiança e
status de confirmação. Leitores NUNCA marcam um dado como confirmado: isso é papel da revisão humana.
"""
from __future__ import annotations

import json, os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from ingest.reader import UnsupportedFormat as _LegacyUnsupported

MAX_BYTES = int(os.environ.get("LEGNA_MAX_FILE_MB", "200")) * 1024 * 1024
STATUS_NAO_CONFIRMADO = "nao_confirmado"


class ReaderError(Exception):
    """Base de todos os erros previstos dos leitores."""


class CorruptFile(ReaderError):
    """Arquivo danificado, truncado, protegido ou ilegível."""


class UnsupportedFormat(ReaderError, _LegacyUnsupported):
    """Formato não suportado, não testado ou conteúdo que não corresponde à extensão."""


class ToolMissing(ReaderError):
    """Ferramenta externa necessária não está instalada (ex.: ODA File Converter)."""


class FileTooLarge(ReaderError):
    pass


@dataclass
class Extracted:
    value: Any
    kind: str                         # text | number | cell | dimension | entity | path | image-text
    source_file: str
    format: str                       # formato ORIGINAL: pdf, dwg, dxf, png, jpg, tiff, xlsx, xls, csv, svg
    locator: dict                     # {"page":1} | {"sheet":"A","cell":"B3"} | {"layer":"X","handle":"2F"} | {"row":1,"col":2} ...
    coords: tuple | None              # bbox (x0,y0,x1,y1) ou ponto (x,y,x,y); None se não houver geometria
    unit: str | None                  # pt | px | mm | cm | m | in | user-units | unitless | None
    method: str                       # text-layer | ocr | ezdxf | openpyxl | calamine | csv | lxml | svgpathtools | oda+ezdxf
    confidence: float | None          # 0..1; 1.0 = leitura exata (camada de texto/estrutura); None = não se aplica
    status: str = STATUS_NAO_CONFIRMADO
    extra: dict = field(default_factory=dict)


@dataclass
class ReadResult:
    file: str
    format: str
    items: list[Extracted] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str, indent=1)


def sniff(path: Path, n: int = 16) -> bytes:
    with open(path, "rb") as f:
        return f.read(n)


def check_file(path: str | Path, exts: set[str], magic: Callable[[bytes], bool] | None = None) -> Path:
    """Valida existência, tamanho, extensão e (opcional) assinatura do arquivo."""
    p = Path(path)
    if not p.is_file():
        raise CorruptFile(f"{p.name}: arquivo não encontrado")
    size = p.stat().st_size
    if size == 0:
        raise CorruptFile(f"{p.name}: arquivo vazio")
    if size > MAX_BYTES:
        raise FileTooLarge(f"{p.name}: {size / 1e6:.0f} MB excede o limite de {MAX_BYTES / 1e6:.0f} MB (LEGNA_MAX_FILE_MB)")
    if p.suffix.lower() not in exts:
        raise UnsupportedFormat(f"{p.name}: extensão {p.suffix or '(nenhuma)'} não é tratada por este leitor ({', '.join(sorted(exts))})")
    if magic is not None and not magic(sniff(p)):
        raise UnsupportedFormat(f"{p.name}: o conteúdo não corresponde à extensão {p.suffix}")
    return p


# milímetros por unidade
MM_PER = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "pt": 25.4 / 72.0, "px": 25.4 / 96.0}
