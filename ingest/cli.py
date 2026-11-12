"""Uso: python -m ingest.cli arquivo.pdf [saida.json]"""
import sys
from .reader import read, to_json, UnsupportedFormat

if __name__ == "__main__":
    try:
        doc = read(sys.argv[1])
    except UnsupportedFormat as e:
        sys.exit(f"Formato não suportado: {e}")
    out = to_json(doc)
    if len(sys.argv) > 2:
        open(sys.argv[2], "w", encoding="utf-8").write(out)
        print(f"{len(doc.pages)} página(s) -> {sys.argv[2]}")
    else:
        print(out)
