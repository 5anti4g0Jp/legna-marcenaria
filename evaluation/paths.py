"""Caminhos do fluxo de revisão/versionamento. Parametrizáveis (testes usam diretórios temporários)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

EV = Path(__file__).resolve().parent


@dataclass
class Caminhos:
    base: Path = EV

    @property
    def gt_v0(self): return self.base / "groundtruth" / "real_fernanda.json"
    @property
    def resultado_v0(self): return self.base / "results" / "etapa0_baseline.json"
    @property
    def algoritmo(self): return self.base / "baseline_etapa0" / "dimensions.py"
    @property
    def itens(self): return self.base / "review" / "itens_selecionados.json"
    @property
    def respostas(self): return self.base / "review" / "respostas"
    @property
    def manifesto_respostas(self): return self.respostas / "MANIFEST.jsonl"
    @property
    def resolucoes(self): return self.base / "groundtruth" / "resolucoes.jsonl"
    @property
    def versoes_log(self): return self.base / "groundtruth" / "versions.jsonl"
    @property
    def versoes_dir(self): return self.base / "groundtruth" / "versoes"
    @property
    def sintetico_manifest(self): return self.base / "groundtruth" / "synthetic_manifest.json"
    @property
    def exclusoes_q2(self): return self.base / "review" / "exclusoes_q2.json"
