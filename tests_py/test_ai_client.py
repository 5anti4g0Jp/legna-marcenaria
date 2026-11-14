"""Cliente Anthropic: nenhuma chamada real à rede; o transporte HTTP é simulado (httpx.MockTransport)."""
import json
import httpx2 as httpx
import pytest

from ingest.ai import client as ai

KEY = "sk-ant-api03-FAKEKEYFORTESTS000000000000"
OK = {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5", "content": [{"type": "text", "text": "ok"}],
      "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}
MSG = [{"role": "user", "content": "oi"}]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.delenv("ANTHROPIC_API_KEY_FILE", raising=False)


def _client(handler, retries=0):
    return ai.make_client(http_client=httpx.Client(transport=httpx.MockTransport(handler)), max_retries=retries)


def test_sucesso_e_chave_enviada_so_no_cabecalho():
    seen = {}

    def h(req):
        seen["key"] = req.headers.get("x-api-key") or req.headers.get("authorization", "").removeprefix("Bearer ")   # SDK 2.8 usa Authorization: Bearer
        seen["body"] = req.content.decode()
        return httpx.Response(200, json=OK)
    r = ai.complete(_client(h), messages=MSG)
    assert r.content[0].text == "ok" and seen["key"] == KEY and KEY not in seen["body"]


def test_sem_credencial_falha_com_mensagem_clara(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(ai.MissingCredential, match="ANTHROPIC_API_KEY"):
        ai.make_client()


def test_chave_via_arquivo_de_segredo(monkeypatch, tmp_path):
    f = tmp_path / "secret"; f.write_text(KEY + "\n")
    monkeypatch.delenv("ANTHROPIC_API_KEY"); monkeypatch.setenv("ANTHROPIC_API_KEY_FILE", str(f))
    assert ai.load_api_key() == KEY


@pytest.mark.parametrize("status,kind,retry", [(429, "rate_limit", True), (500, "server", True), (529, "server", True),
                                               (401, "auth", False), (403, "permission", False), (400, "bad_request", False)])
def test_erros_http_traduzidos(status, kind, retry):
    def h(req):
        return httpx.Response(status, json={"type": "error", "error": {"type": "x", "message": f"falha com {KEY}"}}, headers={"retry-after": "7"})
    with pytest.raises(ai.AIError) as e:
        ai.complete(_client(h), messages=MSG)
    assert e.value.kind == kind and e.value.retryable is retry and e.value.status == status
    assert KEY not in str(e.value) and KEY not in repr(e.value)            # a chave nunca vaza em erros
    if status == 429:
        assert e.value.retry_after == 7.0


def test_falha_de_conexao_e_timeout():
    def conn(req): raise httpx.ConnectError("recusada", request=req)
    def tmo(req): raise httpx.ReadTimeout("lento", request=req)
    with pytest.raises(ai.AIError) as e1:
        ai.complete(_client(conn), messages=MSG)
    with pytest.raises(ai.AIError) as e2:
        ai.complete(_client(tmo), messages=MSG)
    assert (e1.value.kind, e1.value.retryable) == ("connection", True) and (e2.value.kind, e2.value.retryable) == ("timeout", True)


def test_sdk_repete_em_erro_transitorio_e_recupera():
    calls = []

    def h(req):
        calls.append(1)
        return httpx.Response(500, json={"type": "error", "error": {"type": "api_error", "message": "x"}}) if len(calls) < 3 else httpx.Response(200, json=OK)
    r = ai.complete(_client(h, retries=3), messages=MSG)
    assert r.content[0].text == "ok" and len(calls) == 3


def test_redact():
    assert KEY not in ai.redact(f"erro {KEY} fim") and "sk-ant-***" in ai.redact(f"erro {KEY}")
