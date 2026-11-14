"""Garante que nenhuma chave foi parar no repositório e que .env está protegido."""
import re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REAL_KEY = re.compile(r"sk-ant-api\d{2}-[A-Za-z0-9_\-]{30,}")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", "out"}


def _files():
    for p in ROOT.rglob("*"):
        if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS) and p.stat().st_size < 2_000_000:
            yield p


def test_nenhuma_chave_real_nos_arquivos():
    achados = []
    for p in _files():
        try:
            t = p.read_text(errors="ignore")
        except Exception:
            continue
        for m in REAL_KEY.finditer(t):
            if "FAKEKEYFORTESTS" not in m.group(0):         # única chave falsa permitida (testes)
                achados.append(f"{p.relative_to(ROOT)}")
    assert not achados, f"possível chave Anthropic em: {achados}"


def test_env_ignorado_e_exemplo_sem_valor():
    gi = (ROOT / ".gitignore").read_text()
    assert re.search(r"^\.env$", gi, re.M) and "!.env.example" in gi
    ex = (ROOT / ".env.example").read_text()
    assert re.search(r"^ANTHROPIC_API_KEY=\s*$", ex, re.M)


def test_env_nao_rastreado_pelo_git():
    import shutil, pytest
    if not shutil.which("git") or not (ROOT / ".git").exists():
        pytest.skip("git/.git ausente (ex.: dentro do contêiner)")
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert ".env" not in out and not any(f.endswith(".pem") for f in out)
