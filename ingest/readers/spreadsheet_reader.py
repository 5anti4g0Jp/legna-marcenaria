"""SpreadsheetReader (XLSX, XLS): openpyxl para XLSX (valores em cache), python-calamine para XLS e como alternativa."""
from __future__ import annotations

import zipfile

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from python_calamine import CalamineWorkbook

from .base import CorruptFile, Extracted, ReadResult, ReaderError, check_file

EXTS = {".xlsx", ".xlsm", ".xls"}
OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _magic(ext):
    return (lambda h: h.startswith(b"PK")) if ext in (".xlsx", ".xlsm") else (lambda h: h.startswith(OLE))


def _emit(res, name, fmt, method, sheet, r, c, v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return
    res.items.append(Extracted(v, "cell", name, fmt, {"sheet": sheet, "cell": f"{get_column_letter(c)}{r}", "row": r, "col": c},
                               None, None, method, 1.0))


def _read_xlsx_openpyxl(p, res, fmt):
    wb = load_workbook(p, read_only=True, data_only=True)
    try:
        res.meta["sheets"] = wb.sheetnames
        for ws in wb.worksheets:
            for r, row in enumerate(ws.iter_rows(values_only=True), 1):
                for c, v in enumerate(row, 1):
                    _emit(res, p.name, fmt, "openpyxl", ws.title, r, c, v)
    finally:
        wb.close()


def _read_calamine(p, res, fmt):
    wb = CalamineWorkbook.from_path(str(p))
    res.meta["sheets"] = wb.sheet_names
    for name in wb.sheet_names:
        for r, row in enumerate(wb.get_sheet_by_name(name).to_python(), 1):
            for c, v in enumerate(row, 1):
                _emit(res, p.name, fmt, "calamine", name, r, c, v)


def read(path) -> ReadResult:
    from pathlib import Path
    ext = Path(path).suffix.lower()
    p = check_file(path, EXTS, _magic(ext))
    fmt = "xls" if ext == ".xls" else "xlsx"
    res = ReadResult(p.name, fmt)
    try:
        if fmt == "xls":
            _read_calamine(p, res, fmt)
        else:
            try:
                _read_xlsx_openpyxl(p, res, fmt)
            except (zipfile.BadZipFile, KeyError, ValueError, OSError):
                res.items.clear(); res.warnings.append("openpyxl falhou; tentando python-calamine")
                _read_calamine(p, res, fmt)
    except ReaderError:
        raise
    except Exception as e:
        raise CorruptFile(f"{p.name}: planilha ilegível ({type(e).__name__}: {e})") from e
    res.warnings.append("valores lidos são os calculados salvos no arquivo; fórmulas sem valor em cache aparecem vazias")
    return res
