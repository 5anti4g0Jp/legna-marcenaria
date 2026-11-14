"""Log append-only com cadeia de hash (JSONL). Alterar, remover, reordenar ou inserir entradas é detectado."""
from __future__ import annotations

import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

RESERVADOS = ("seq", "em", "hash_anterior", "hash")
ZERO = "0" * 64


class LogAdulterado(Exception):
    pass


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(e: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in e.items() if k != "hash"}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class HashLog:
    def __init__(self, caminho: str | Path | None = None):
        self.caminho = Path(caminho) if caminho else None
        self.entradas: list[dict] = []
        if self.caminho and self.caminho.exists():
            self.entradas = [json.loads(l) for l in self.caminho.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.verificar()

    def verificar(self) -> None:
        anterior = ZERO
        for i, e in enumerate(self.entradas):
            if e.get("seq") != i + 1 or e.get("hash_anterior") != anterior or e.get("hash") != _hash(e):
                raise LogAdulterado(f"cadeia de hash quebrada na entrada {i + 1}")
            anterior = e["hash"]

    @property
    def cabeca(self) -> str:
        return self.entradas[-1]["hash"] if self.entradas else ZERO

    def adicionar(self, **payload) -> dict:
        if any(k in payload for k in RESERVADOS):
            raise ValueError(f"campos reservados: {RESERVADOS}")
        self.verificar()
        e = {"seq": len(self.entradas) + 1, "em": agora(), **payload, "hash_anterior": self.cabeca}
        e["hash"] = _hash(e)
        self.entradas.append(e)
        if self.caminho:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            with open(self.caminho, "a", encoding="utf-8") as f:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        return e
