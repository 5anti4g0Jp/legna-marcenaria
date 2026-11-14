"""CSVReader: biblioteca csv padrão, com detecção de codificação e delimitador."""
from __future__ import annotations

import csv, io
from pathlib import Path

from .base import CorruptFile, Extracted, ReadResult, UnsupportedFormat, check_file

EXTS = {".csv"}
ENCODINGS = ("utf-8-sig", "cp1252")     # cp1252 cobre também latin-1 de arquivos do Excel/Windows em pt-BR


def read(path) -> ReadResult:
    p = check_file(path, EXTS)
    raw = p.read_bytes()
    if b"\x00" in raw[:4096]:
        raise UnsupportedFormat(f"{p.name}: contém bytes nulos; não parece texto CSV")
    text, enc = None, None
    for e in ENCODINGS:
        try:
            text, enc = raw.decode(e), e; break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise CorruptFile(f"{p.name}: codificação não reconhecida")
    res = ReadResult(p.name, "csv", meta={"encoding": enc})
    if enc != "utf-8-sig":
        res.warnings.append("codificação não UTF-8 (assumido cp1252): acentos devem ser conferidos")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel; res.warnings.append("delimitador não detectado; assumida vírgula")
    res.meta["delimiter"] = dialect.delimiter
    try:
        for r, row in enumerate(csv.reader(io.StringIO(text), dialect), 1):
            for c, v in enumerate(row, 1):
                if v.strip():
                    res.items.append(Extracted(v.strip(), "cell", p.name, "csv", {"row": r, "col": c}, None, None, "csv", 1.0))
    except csv.Error as e:
        raise CorruptFile(f"{p.name}: CSV malformado ({e})") from e
    res.warnings.append("valores mantidos como TEXTO: vírgula decimal (pt-BR) não é convertida automaticamente")
    return res
