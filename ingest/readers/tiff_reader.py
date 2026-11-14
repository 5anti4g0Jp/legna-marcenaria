"""TIFFReader: TIFF/TIF, inclusive multipágina. tifffile primeiro; Pillow como alternativa para compressões
que o tifffile só decodifica com `imagecodecs` (ex.: CCITT G4, comuns em scans)."""
from __future__ import annotations

import numpy as np
import tifffile
from PIL import Image, UnidentifiedImageError

from ingest.reader import ocr_image

from .base import CorruptFile, Extracted, ReadResult, ReaderError, check_file

EXTS = {".tif", ".tiff"}
MAGIC = (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")


def _to_pil(arr: np.ndarray) -> Image.Image:
    a = np.asarray(arr)
    if a.ndim == 3 and a.shape[0] in (3, 4) and a.shape[-1] > 4:
        a = np.moveaxis(a, 0, -1)
    if a.dtype == bool:
        a = a.astype("uint8") * 255
    elif a.dtype != np.uint8:
        a = (a.astype("float64") / max(float(a.max()), 1.0) * 255).astype("uint8")
    if a.ndim == 3 and a.shape[-1] == 4:
        a = a[..., :3]
    return Image.fromarray(a)


def _frames_tifffile(p):
    with tifffile.TiffFile(p) as tf:
        for i, page in enumerate(tf.pages):
            xr = page.tags.get("XResolution")
            dpi = None
            if xr is not None:
                n, d = xr.value
                dpi = n / d if d else None
            yield i, _to_pil(page.asarray()), dpi


def _frames_pillow(p):
    with Image.open(p) as im:
        n = getattr(im, "n_frames", 1)
        for i in range(n):
            im.seek(i)
            d = im.info.get("dpi")
            yield i, im.convert("L").copy(), (d[0] if d else None)


def read(path) -> ReadResult:
    p = check_file(path, EXTS, lambda h: h.startswith(MAGIC))
    res = ReadResult(p.name, "tiff", meta={"frames": 0, "dpi": {}})
    try:
        try:
            frames = list(_frames_tifffile(p))
            res.meta["decoder"] = "tifffile"
        except (ImportError, ValueError, NotImplementedError) as e:
            # só cai para o Pillow quando FALTA O CODEC (imagecodecs); qualquer outra falha é arquivo danificado
            if isinstance(e, ImportError) or "imagecodecs" in str(e):
                res.warnings.append(f"tifffile sem codec para esta compressão ({type(e).__name__}); usando Pillow")
                frames = list(_frames_pillow(p)); res.meta["decoder"] = "pillow"
            else:
                raise
    except ReaderError:
        raise
    except Exception as e:   # tifffile.TiffFileError, erros do Pillow (TypeError, OSError...), estrutura inválida
        raise CorruptFile(f"{p.name}: TIFF ilegível ({type(e).__name__}: {e})") from e
    if not frames:
        raise CorruptFile(f"{p.name}: TIFF sem nenhuma página legível (cabeçalho ou deslocamentos inválidos)")
    for i, img, dpi in frames:
        res.meta["dpi"][i + 1] = dpi
        for t in ocr_image(img, 1.0):
            res.items.append(Extracted(t.text, "number" if t.is_number else "text", p.name, "tiff", {"page": i + 1},
                                       (t.x0, t.y0, t.x1, t.y1), "px", "ocr", (t.conf or 0) / 100.0, extra={"rotation": t.rotation}))
    res.meta["frames"] = len(frames)
    res.warnings.append("TIFF sem escala garantida: coordenadas em pixels (dpi no meta, quando existir)")
    return res
