"""PDFReader: encapsula a leitura da Etapa 1 (ingest.reader), sem reescrevê-la."""
from __future__ import annotations

from collections import Counter

from ingest.reader import read as _read_legacy

from .base import CorruptFile, Extracted, ReadResult, ReaderError, check_file

EXTS = {".pdf"}


def read(path) -> ReadResult:
    p = check_file(path, EXTS, lambda h: h.startswith(b"%PDF"))
    try:
        doc = _read_legacy(p)
    except ReaderError:
        raise
    except Exception as e:  # PDF truncado, criptografado, estrutura inválida
        raise CorruptFile(f"{p.name}: PDF ilegível ({type(e).__name__}: {e})") from e
    res = ReadResult(p.name, "pdf", meta={"pages": len(doc.pages), "page_kinds": dict(Counter(pg.kind for pg in doc.pages)),
                                          "vector_paths": {pg.index: pg.n_vector_paths for pg in doc.pages}})
    for pg in doc.pages:
        for n in pg.notes:
            if "OCR" in n:
                res.warnings.append(f"p.{pg.index}: {n}")
        for t in pg.tokens:
            res.items.append(Extracted(
                value=t.text, kind="number" if t.is_number else "text", source_file=p.name, format="pdf",
                locator={"page": pg.index}, coords=(t.x0, t.y0, t.x1, t.y1), unit=pg.unit, method=t.source,
                confidence=1.0 if t.source == "text-layer" else (t.conf or 0) / 100.0, extra={"rotation": t.rotation}))
    return res
