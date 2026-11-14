"""Uso: python -m ingest.readers arquivo [saida.json]   (qualquer formato suportado)"""
import sys

from . import ReaderError, read_any

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("uso: python -m ingest.readers arquivo [saida.json]")
    try:
        res = read_any(sys.argv[1])
    except ReaderError as e:
        sys.exit(f"{type(e).__name__}: {e}")
    out = res.to_json()
    if len(sys.argv) > 2:
        open(sys.argv[2], "w", encoding="utf-8").write(out)
        print(f"{res.format}: {len(res.items)} itens, {len(res.warnings)} avisos -> {sys.argv[2]}")
    else:
        print(out)
