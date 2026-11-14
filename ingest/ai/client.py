"""Integração com a API da Anthropic (SDK oficial).

Segurança: a chave vem SOMENTE de variável de ambiente (ANTHROPIC_API_KEY) ou de um arquivo de segredo
(ANTHROPIC_API_KEY_FILE, ex.: Docker secret). Nunca é escrita em código, log ou mensagem de erro.
Erros do SDK são traduzidos para AIError com `kind` e `retryable`, para o chamador decidir o que fazer.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import anthropic

DEFAULT_MODEL = os.environ.get("LEGNA_AI_MODEL", "claude-sonnet-5-5")
_KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{6,}")


class MissingCredential(Exception):
    pass


class AIError(Exception):
    def __init__(self, kind: str, message: str, retryable: bool, retry_after: float | None = None, status: int | None = None):
        super().__init__(f"[{kind}] {message}")
        self.kind, self.retryable, self.retry_after, self.status = kind, retryable, retry_after, status


def redact(text: str) -> str:
    return _KEY_RE.sub("sk-ant-***", text)


def load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key and os.environ.get("ANTHROPIC_API_KEY_FILE"):
        f = Path(os.environ["ANTHROPIC_API_KEY_FILE"])
        if f.is_file():
            key = f.read_text().strip()
    if not key:
        raise MissingCredential("ANTHROPIC_API_KEY não definida (nem ANTHROPIC_API_KEY_FILE). Configure no ambiente; nunca no código ou no GitHub.")
    return key


def make_client(*, http_client=None, max_retries: int = 3, timeout: float = 60.0) -> anthropic.Anthropic:
    kw = {"api_key": load_api_key(), "max_retries": max_retries, "timeout": timeout}
    if http_client is not None:
        kw["http_client"] = http_client
    return anthropic.Anthropic(**kw)


def _retry_after(e) -> float | None:
    try:
        v = e.response.headers.get("retry-after")
        return float(v) if v else None
    except Exception:
        return None


def complete(client: anthropic.Anthropic, *, messages: list[dict], system: str | None = None, model: str = DEFAULT_MODEL, max_tokens: int = 1024):
    """Chamada simples a messages.create com tradução de erros."""
    try:
        kw = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            kw["system"] = system
        return client.messages.create(**kw)
    except anthropic.AuthenticationError as e:
        raise AIError("auth", "credencial rejeitada (401). Verifique ANTHROPIC_API_KEY.", False, status=401) from None
    except anthropic.PermissionDeniedError as e:
        raise AIError("permission", "sem permissão para este recurso (403).", False, status=403) from None
    except anthropic.RateLimitError as e:
        raise AIError("rate_limit", "limite de requisições atingido (429).", True, _retry_after(e), 429) from None
    except anthropic.APITimeoutError:
        raise AIError("timeout", "a API não respondeu a tempo.", True) from None
    except anthropic.APIConnectionError:
        raise AIError("connection", "falha de conexão com a API.", True) from None
    except anthropic.BadRequestError as e:
        raise AIError("bad_request", redact(str(e))[:300], False, status=400) from None
    except anthropic.APIStatusError as e:
        code = getattr(e, "status_code", None)
        raise AIError("server" if (code or 500) >= 500 else "api", redact(str(e))[:300], (code or 500) >= 500, _retry_after(e), code) from None
