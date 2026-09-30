"""LLM layer: mock provider, cache, offline mode, and Ollama/Anthropic request/response handling
(HTTP is mocked; no model is needed)."""
import json

import pytest
from pydantic import BaseModel

from qm import llm


class Tiny(BaseModel):
    part: str | None = None
    qty: int | None = None


class Inner(BaseModel):
    value: str | None = None


class Outer(BaseModel):
    a: Inner = Inner()
    b: list[Inner] = []


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("QM_CACHE_DIR", str(tmp_path / "cache"))
    fx = tmp_path / "fixtures"
    fx.mkdir()
    (fx / "tiny.json").write_text(json.dumps(
        {"task": "intake_extract", "match": ["HB-12"], "output": {"part": "HB-12", "qty": 250}}))
    monkeypatch.setenv("QM_FIXTURE_DIR", str(fx))
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    monkeypatch.setenv("DEMO_MODE", "live")
    yield


class FakeResp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code, self._body, self.text = status, body or {}, text

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code}")


def test_mock_fixture_returns_valid_structured_json():
    out, meta = llm.call_model_meta("intake_extract", "RFQ for HB-12 please", Tiny)
    assert out == {"part": "HB-12", "qty": 250}
    assert meta["source"] == "fixture"
    assert Tiny.model_validate(out)


def test_mock_without_fixture_uses_caller_fallback_then_safe_default():
    out, meta = llm.call_model_meta("intake_extract", "something else", Tiny, fallback=lambda: {"part": "X"})
    assert out == {"part": "X"} and meta["source"] == "fallback"
    out2 = llm.call_model("intake_extract", "something else", Tiny)
    assert out2 == {"part": None, "qty": None}
    assert llm.call_model("clarification_email", "hi") == ""


def test_fallback_that_raises_never_crashes():
    def boom():
        raise ValueError("x")
    assert llm.call_model("intake_extract", "zzz", Tiny, fallback=boom) == {"part": None, "qty": None}


def test_inline_refs_flattens_nested_schema():
    flat = llm.inline_refs(Outer.model_json_schema())
    assert "$defs" not in json.dumps(flat) and "$ref" not in json.dumps(flat)
    assert flat["properties"]["a"]["properties"]["value"]


def test_build_ollama_payload_has_schema_think_false_no_stream():
    p = llm.build_ollama_payload("intake_extract", "hello", Tiny, "qwen3:8b")
    assert p["model"] == "qwen3:8b" and p["stream"] is False and p["think"] is False
    assert p["format"]["properties"]["qty"]
    assert p["messages"][0]["role"] == "system" and p["messages"][1]["content"] == "hello"
    assert 0 <= p["options"]["temperature"] <= 0.2
    p2 = llm.build_ollama_payload("intake_extract", "hello", Tiny, "qwen3:8b", think_supported=False)
    assert "think" not in p2 and p2["messages"][1]["content"].endswith("/no_think")


def test_extract_json_strips_think_and_fences():
    assert llm.extract_json('<think>hmm</think>\n{"a": 1}') == {"a": 1}
    assert llm.extract_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert llm.extract_json('Sure! {"a": 3} done') == {"a": 3}


def test_ollama_live_call_parses_caches_and_serves_cache(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    calls = []

    def fake_post(url, json=None, timeout=None, **kw):
        calls.append((url, json))
        return FakeResp(body={"message": {"content": '{"part": "HB-99", "qty": 5}'}, "done": True})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    out, meta = llm.call_model_meta("intake_extract", "RFQ HB-99 qty 5", Tiny)
    assert out == {"part": "HB-99", "qty": 5} and meta["source"] == "live"
    assert calls[0][0].endswith("/api/chat") and calls[0][1]["think"] is False
    out2, meta2 = llm.call_model_meta("intake_extract", "RFQ HB-99 qty 5", Tiny)
    assert out2 == out and meta2["source"] == "cache" and len(calls) == 1


def test_ollama_invalid_json_retries_once_with_error(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    replies = iter(['{"part": "HB-1", "qty": "lots"}', '{"part": "HB-1", "qty": 7}'])
    prompts = []

    def fake_post(url, json=None, timeout=None, **kw):
        prompts.append(json["messages"][1]["content"])
        return FakeResp(body={"message": {"content": next(replies)}})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    out, meta = llm.call_model_meta("intake_extract", "RFQ HB-1", Tiny)
    assert out == {"part": "HB-1", "qty": 7} and meta["source"] == "live"
    assert "previous reply was invalid" in prompts[1]


def test_ollama_two_failures_fall_back_without_crashing(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResp(body={"message": {"content": "not json"}}))
    out, meta = llm.call_model_meta("intake_extract", "RFQ for HB-12", Tiny)
    assert meta["source"] == "fixture" and out["part"] == "HB-12" and meta["error"]


def test_ollama_think_unsupported_falls_back_to_no_think(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    seen = []

    def fake_post(url, json=None, timeout=None, **kw):
        seen.append(json)
        if "think" in json:
            return FakeResp(status=400, text='{"error":"invalid think value"}')
        return FakeResp(body={"message": {"content": '{"part": "Z", "qty": 1}'}})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    out, _ = llm.call_model_meta("intake_extract", "RFQ Z", Tiny)
    assert out == {"part": "Z", "qty": 1} and "think" not in seen[-1]


def test_offline_mode_never_calls_network(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("DEMO_MODE", "offline")

    def no_network(*a, **k):
        raise AssertionError("network called in offline mode")

    monkeypatch.setattr(llm.requests, "post", no_network)
    out, meta = llm.call_model_meta("intake_extract", "RFQ for HB-12", Tiny)
    assert meta["source"] == "fixture" and out["qty"] == 250
    out2, meta2 = llm.call_model_meta("intake_extract", "unknown rfq", Tiny, fallback={"part": "fb"})
    assert meta2["source"] == "fallback" and out2 == {"part": "fb"} and "offline" in meta2["error"]


def test_offline_uses_cache_warmed_by_another_provider(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setattr(llm.requests, "post",
                        lambda *a, **k: FakeResp(body={"message": {"content": '{"part": "W", "qty": 3}'}}))
    llm.call_model_meta("intake_extract", "warm me", Tiny)
    monkeypatch.setenv("MODEL_PROVIDER", "anthropic")
    monkeypatch.setenv("DEMO_MODE", "offline")
    out, meta = llm.call_model_meta("intake_extract", "warm me", Tiny)
    assert out == {"part": "W", "qty": 3} and meta["source"] == "cache"


def test_anthropic_payload_and_parse(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-not-a-key")
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        seen.update(url=url, headers=headers, json=json)
        return FakeResp(body={"content": [{"type": "text", "text": '{"part": "A", "qty": 2}'}]})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    out, meta = llm.call_model_meta("intake_extract", "RFQ A", Tiny)
    assert out == {"part": "A", "qty": 2} and meta["source"] == "live"
    assert seen["url"].endswith("/v1/messages") and "JSON schema" in seen["json"]["messages"][0]["content"]


def test_cache_files_never_contain_env_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-secret-value-123")
    monkeypatch.setattr(llm.requests, "post",
                        lambda *a, **k: FakeResp(body={"content": [{"type": "text", "text": '{"part": "S"}'}]}))
    llm.call_model_meta("intake_extract", "RFQ S", Tiny)
    for f in (tmp_path / "cache").glob("*.json"):
        assert "dummy-secret-value-123" not in f.read_text()
