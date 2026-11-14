"""DWGReader: DWG -> DXF com o ODA File Converter (ferramenta externa, proprietária) e leitura via DXFReader.

O conversor NÃO é redistribuído aqui. Defina ODA_FILE_CONVERTER com o caminho do executável (ou deixe no PATH).
Em Linux sem display é necessário `xvfb-run` (o conversor usa Qt). Sem o conversor, o leitor recusa o arquivo
com ToolMissing, nunca devolve dados inventados.
"""
from __future__ import annotations

import os, shutil, subprocess, tempfile
from pathlib import Path

import ezdxf

from . import dxf_reader
from .base import CorruptFile, ReadResult, ReaderError, ToolMissing, check_file

EXTS = {".dwg"}
VERSIONS = {b"AC1009": "R12", b"AC1012": "R13", b"AC1014": "R14", b"AC1015": "2000", b"AC1018": "2004",
            b"AC1021": "2007", b"AC1024": "2010", b"AC1027": "2013", b"AC1032": "2018"}
TIMEOUT_S = int(os.environ.get("LEGNA_DWG_TIMEOUT", "180"))


def find_converter() -> str | None:
    c = os.environ.get("ODA_FILE_CONVERTER")
    if c and Path(c).exists():
        return c
    return shutil.which("ODAFileConverter")


def dwg_version(path: Path) -> str | None:
    return VERSIONS.get(path.read_bytes()[:6])


def read(path) -> ReadResult:
    p = check_file(path, EXTS, lambda h: h[:6] in VERSIONS)
    conv = find_converter()
    if not conv:
        raise ToolMissing("ODA File Converter não encontrado. Instale-o (opendesign.com, aceitando a licença) e defina "
                          "ODA_FILE_CONVERTER, ou coloque ODAFileConverter no PATH. DWG não pode ser lido sem conversão.")
    with tempfile.TemporaryDirectory(prefix="dwg_in_") as tin, tempfile.TemporaryDirectory(prefix="dwg_out_") as tout:
        shutil.copy(p, Path(tin) / p.name)
        cmd = [conv, tin, tout, "ACAD2018", "DXF", "0", "1", p.name]
        if shutil.which("xvfb-run") and not os.environ.get("DISPLAY"):
            cmd = ["xvfb-run", "-a"] + cmd
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired as e:
            raise CorruptFile(f"{p.name}: conversão excedeu {TIMEOUT_S}s") from e
        out = Path(tout) / (p.stem + ".dxf")
        if proc.returncode != 0 or not out.exists():
            raise CorruptFile(f"{p.name}: o conversor não gerou DXF (código {proc.returncode}): {(proc.stderr or proc.stdout)[:300]}")
        try:
            doc = ezdxf.readfile(out)
        except (ezdxf.DXFError, OSError, UnicodeDecodeError, ValueError) as e:
            raise CorruptFile(f"{p.name}: DXF gerado ilegível: {e}") from e
        res = dxf_reader.read_doc(doc, p.name, fmt="dwg", method="oda+ezdxf")
    res.meta["dwg_version"] = dwg_version(p)
    res.warnings.append("lido via conversão DWG->DXF (ODA File Converter); entidades sem equivalente DXF podem ter sido perdidas")
    return res
