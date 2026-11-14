"""ImageReader (PNG, JPG/JPEG): OCR sobre a imagem. Imagem não tem escala: coordenadas em pixels."""
from __future__ import annotations

from PIL import Image, UnidentifiedImageError

from ingest.reader import ocr_image

from .base import CorruptFile, Extracted, ReadResult, UnsupportedFormat, check_file

EXTS = {".png", ".jpg", ".jpeg"}


def _magic(ext: str):
    def ok(h: bytes) -> bool:
        return h.startswith(b"\x89PNG") if ext == ".png" else h[:3] == b"\xff\xd8\xff"
    return ok


def read(path) -> ReadResult:
    from pathlib import Path
    ext = Path(path).suffix.lower()
    p = check_file(path, EXTS, _magic(ext))
    fmt = "png" if ext == ".png" else "jpg"
    try:
        with Image.open(p) as im:
            im.verify()                      # detecta truncamento/corrupção
        img = Image.open(p); img.load()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, ValueError) as e:
        raise CorruptFile(f"{p.name}: imagem ilegível ({type(e).__name__}: {e})") from e
    res = ReadResult(p.name, fmt, meta={"size_px": img.size, "dpi": img.info.get("dpi")})
    res.warnings.append("imagem sem escala conhecida: coordenadas em pixels; só números escritos valem como cota")
    for t in ocr_image(img, 1.0):
        res.items.append(Extracted(t.text, "number" if t.is_number else "text", p.name, fmt, {"page": 1},
                                   (t.x0, t.y0, t.x1, t.y1), "px", "ocr", (t.conf or 0) / 100.0, extra={"rotation": t.rotation}))
    return res
