"""Despacho por formato. Todo leitor entrega ReadResult para o núcleo de interpretação."""
from __future__ import annotations

from pathlib import Path

from . import csv_reader, dwg_reader, dxf_reader, image_reader, pdf_reader, spreadsheet_reader, svg_reader, tiff_reader
from .base import ReadResult, UnsupportedFormat

READERS = {
    ".pdf": pdf_reader, ".dwg": dwg_reader, ".dxf": dxf_reader,
    ".png": image_reader, ".jpg": image_reader, ".jpeg": image_reader,
    ".tif": tiff_reader, ".tiff": tiff_reader,
    ".xlsx": spreadsheet_reader, ".xlsm": spreadsheet_reader, ".xls": spreadsheet_reader,
    ".csv": csv_reader, ".svg": svg_reader,
}


def read_any(path) -> ReadResult:
    ext = Path(path).suffix.lower()
    if ext not in READERS:
        raise UnsupportedFormat(f"{Path(path).name}: extensão {ext or '(nenhuma)'} desconhecida. Suportadas: {', '.join(sorted(READERS))}")
    return READERS[ext].read(path)
