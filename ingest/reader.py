"""Etapa 1 - leitura de arquivos: PDF digital, PDF escaneado, PNG e JPG/JPEG.

Gera um Document interno (JSON) com, por página: tipo (digital/escaneada), tokens de texto
com coordenadas e origem (camada de texto ou OCR), candidatos a cota e contagem de vetores.
Formatos NÃO testados (DWG, DXF, TIFF, XLSX, XLS, CSV, SVG) são recusados explicitamente.
"""
from __future__ import annotations
import io, json, re, warnings
import numpy as np
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", category=FutureWarning)
import pymupdf  # noqa: E402
import pytesseract  # noqa: E402
from PIL import Image  # noqa: E402

SUPPORTED = {".pdf": "pdf", ".png": "image", ".jpg": "image", ".jpeg": "image"}
NOT_YET = {".dwg", ".dxf", ".tif", ".tiff", ".xlsx", ".xls", ".csv", ".svg"}
OCR_DPI = 300
MIN_TEXT_TOKENS = 5           # camada de texto com >= 5 palavras é sempre preservada (nunca substituída por OCR)
MIN_IMAGE_COVERAGE = 0.25     # fração da página coberta por imagens para considerar OCR
NUM_RE = re.compile(r"^\d{1,5}([.,]\d{1,2})?$")


class UnsupportedFormat(Exception):
    pass


@dataclass
class Token:
    text: str
    x0: float; y0: float; x1: float; y1: float   # em pontos (PDF) ou pixels (imagem)
    source: str                                   # "text-layer" | "ocr"
    rotation: int = 0                             # graus; 0 = horizontal, 90 = lido de baixo p/ cima
    conf: float | None = None                     # só OCR (0-100)

    @property
    def is_number(self) -> bool:
        return bool(NUM_RE.match(self.text))


@dataclass
class Page:
    index: int                    # 1-based
    width: float; height: float
    unit: str                     # "pt" | "px"
    kind: str                     # "digital" | "escaneada"
    tokens: list[Token] = field(default_factory=list)
    n_vector_paths: int = 0
    n_images: int = 0
    notes: list[str] = field(default_factory=list)

    def numbers(self) -> list[Token]:
        return [t for t in self.tokens if t.is_number]


@dataclass
class Document:
    file: str
    format: str                   # pdf | png | jpg
    pages: list[Page]


def detect_format(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in NOT_YET:
        raise UnsupportedFormat(f"{ext}: leitura ainda não implementada nem testada (planejado para etapas seguintes).")
    if ext not in SUPPORTED:
        raise UnsupportedFormat(f"{ext}: formato desconhecido.")
    head = path.read_bytes()[:8]
    magic_ok = {".pdf": head.startswith(b"%PDF"), ".png": head.startswith(b"\x89PNG"),
                ".jpg": head[:3] == b"\xff\xd8\xff", ".jpeg": head[:3] == b"\xff\xd8\xff"}[ext]
    if not magic_ok:
        raise UnsupportedFormat(f"{path.name}: o conteúdo não corresponde à extensão {ext}.")
    return "jpg" if ext in (".jpg", ".jpeg") else ext[1:]


# ---------------------------------------------------------------- OCR
def _rotate_back(box, angle, W, H):
    """Converte bbox da imagem rotacionada (CCW angle, expand) para a imagem original."""
    x0, y0, x1, y1 = box
    pts = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
    out = []
    for xr, yr in pts:
        if angle == 90:   # CCW: original (x,y) -> (y, W-1-x)
            out.append((W - 1 - yr, xr))
        elif angle == 270:  # CCW 270: original (x,y) -> (H-1-y, x)
            out.append((yr, H - 1 - xr))
        else:
            out.append((xr, yr))
    xs, ys = [p[0] for p in out], [p[1] for p in out]
    return min(xs), min(ys), max(xs), max(ys)


def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def ocr_image(img: Image.Image, scale: float = 1.0, min_conf: float = 50.0) -> list[Token]:
    """OCR em 0/90/270 graus (cotas verticais). `scale` converte px -> unidade da página.

    Reúne os candidatos de todas as passadas e resolve sobreposições por prioridade:
    número válido > texto, depois maior confiança. Assim um lixo lido na passada horizontal
    não bloqueia a leitura correta de uma cota vertical.
    """
    # Canal de MAIOR valor por pixel: linhas coloridas de cota (vermelho/azul) viram claras e o texto
    # preto permanece escuro. Em scan cinza/preto-e-branco equivale ao próprio cinza.
    img = Image.fromarray(np.asarray(img.convert("RGB")).max(axis=2).astype("uint8"))
    W, H = img.size
    cands: list[tuple[str, tuple[float, float, float, float], float, int]] = []
    for angle in (0, 90, 270):
        im = img if angle == 0 else img.rotate(angle, expand=True)
        data = pytesseract.image_to_data(im, lang="por+eng", config="--psm 11", output_type=pytesseract.Output.DICT)
        for i, txt in enumerate(data["text"]):
            txt = (txt or "").strip()
            try:
                conf = float(data["conf"][i])
            except ValueError:
                continue
            if not txt or conf < min_conf:
                continue
            if angle != 0 and not (NUM_RE.match(txt) or len(txt) >= 3):
                continue
            box = (data["left"][i], data["top"][i], data["left"][i] + data["width"][i], data["top"][i] + data["height"][i])
            cands.append((txt, _rotate_back(box, angle, W, H), conf, angle))
    cands.sort(key=lambda c: (not NUM_RE.match(c[0]), -c[2]))
    chosen: list[tuple[str, tuple[float, float, float, float], float, int]] = []
    for c in cands:
        if all(_iou(c[1], k[1]) <= 0.3 for k in chosen):
            chosen.append(c)
    chosen.sort(key=lambda c: (c[1][1], c[1][0]))
    rot = {0: 0, 90: 270, 270: 90}
    return [Token(t, bx[0] * scale, bx[1] * scale, bx[2] * scale, bx[3] * scale, "ocr", rot[ang], conf) for t, bx, conf, ang in chosen]


# ---------------------------------------------------------------- PDF
def _text_layer_tokens(page: "pymupdf.Page") -> list[Token]:
    out: list[Token] = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            dx, dy = ln["dir"]
            rot = 0 if abs(dx) > abs(dy) else (90 if dy < 0 else 270)
            for sp in ln["spans"]:
                for w in sp["text"].split():
                    out.append(Token(w, *sp["bbox"], "text-layer", rot))
    return out


def read_pdf(path: Path) -> Document:
    doc = pymupdf.open(path)
    pages: list[Page] = []
    for i, pg in enumerate(doc, 1):
        toks = _text_layer_tokens(pg)
        n_vec = len(pg.get_drawings())
        infos = pg.get_image_info()
        n_img = len(infos)
        page_area = pg.rect.width * pg.rect.height
        coverage = min(1.0, sum(max(0, (i["bbox"][2] - i["bbox"][0]) * (i["bbox"][3] - i["bbox"][1])) for i in infos) / page_area) if page_area else 0.0
        p = Page(i, pg.rect.width, pg.rect.height, "pt", "digital", toks, n_vec, n_img)
        p.notes.append(f"cobertura de imagem: {coverage:.0%}")
        if len(toks) < MIN_TEXT_TOKENS and coverage >= MIN_IMAGE_COVERAGE:
            # sem camada de texto útil e dominada por imagem: rasteriza e aplica OCR
            pix = pg.get_pixmap(dpi=OCR_DPI)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            p.kind = "escaneada"
            p.tokens = toks + ocr_image(img, scale=72.0 / OCR_DPI)
            p.notes.append(f"OCR a {OCR_DPI} dpi (camada de texto com {len(toks)} palavras)")
        elif len(toks) < MIN_TEXT_TOKENS:
            p.notes.append("pouco texto e pouca imagem: possível desenho vetorial sem cotas/texto")
        pages.append(p)
    return Document(path.name, "pdf", pages)


def read_image(path: Path, fmt: str) -> Document:
    img = Image.open(path)
    W, H = img.size
    p = Page(1, W, H, "px", "escaneada", ocr_image(img, 1.0), 0, 1,
             ["imagem sem escala conhecida: cotas em pixels não são medidas reais; só números escritos"])
    return Document(path.name, fmt, [p])


def read(path: str | Path) -> Document:
    path = Path(path)
    fmt = detect_format(path)
    return read_pdf(path) if fmt == "pdf" else read_image(path, fmt)


def to_json(doc: Document) -> str:
    return json.dumps(asdict(doc), ensure_ascii=False, indent=1)
