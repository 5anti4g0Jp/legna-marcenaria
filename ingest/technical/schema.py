"""JSON Schema do resultado (gerado do próprio modelo, para não divergir)."""
import json
from pathlib import Path

from .model import Resultado

CAMINHO = Path(__file__).resolve().parent / "schema" / "resultado.schema.json"


def gerar() -> dict:
    return Resultado.model_json_schema(mode="serialization")


def gravar() -> Path:
    CAMINHO.parent.mkdir(exist_ok=True)
    CAMINHO.write_text(json.dumps(gerar(), ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return CAMINHO


if __name__ == "__main__":
    print(gravar())
