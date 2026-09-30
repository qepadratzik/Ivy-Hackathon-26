"""LLM layer: one function, three providers, a disk cache, and an offline mode.

    call_model(task, prompt, schema=None, fallback=None) -> dict | str

Rules (HANDOFF 2.5 / 7.6):
- The model only extracts, drafts and explains. It never produces a cost or price number.
- Every live result is cached in cache/llm/<sha256>.json.
- DEMO_MODE=offline never calls a model: cache -> mock fixture -> caller's deterministic fallback.
- Any failure degrades to the fixture/fallback and is flagged in `meta`; it never raises.

Providers: mock (default, deterministic fixtures), ollama (Quentin's PC), anthropic (optional).
Secrets are read with os.getenv at call time and are never logged, cached or returned.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests
from pydantic import BaseModel, ValidationError

from qm import config

log = logging.getLogger("qm.llm")

SYSTEM_PROMPTS = {
    "intake_extract": (
        "You extract structured fields from a manufacturing RFQ (request for quote) for a metal "
        "fabrication job shop. Only report what the text actually says. NEVER invent, guess or "
        "compute values. If a field is not stated, return value null with confidence \"low\" and "
        "source_quote null. source_quote must be copied verbatim from the input text. "
        "Reply with JSON only."
    ),
    "clarification_email": (
        "You write short, polite, plain-text clarification emails from a job-shop estimator to a "
        "customer buyer. Ask only the listed questions, as a numbered list. No prices, no numbers "
        "that are not in the input. Under 140 words."
    ),
    "pattern_narration": (
        "You turn a statistic about a machine shop's past jobs into ONE plain-English sentence "
        "for a non-technical manager. Use only the numbers given. No new numbers. Max 35 words."
    ),
    "evidence_explain": (
        "You explain in ONE plain-English sentence why a cost line in a quote has the confidence "
        "it has, using only the facts given. No new numbers. Max 35 words."
    ),
}


# ---------------------------------------------------------------- provider/runtime settings
def current_provider() -> str:
    return (os.getenv("MODEL_PROVIDER") or config.MODEL_PROVIDER or "mock").strip().lower()


def current_model(provider: str | None = None) -> str:
    provider = provider or current_provider()
    if provider == "ollama":
        return (os.getenv("OLLAMA_MODEL") or config.OLLAMA_MODEL).strip()
    if provider == "anthropic":
        return (os.getenv("ANTHROPIC_MODEL") or config.ANTHROPIC_MODEL).strip()
    return "mock"


def demo_mode() -> str:
    return (os.getenv("DEMO_MODE") or config.DEMO_MODE or "live").strip().lower()


def ollama_host() -> str:
    return (os.getenv("OLLAMA_HOST") or config.OLLAMA_HOST).strip().rstrip("/")


# ---------------------------------------------------------------- cache
def _sha(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()


def cache_key(provider: str, model: str, task: str, prompt: str, schema_name: str) -> str:
    return _sha(provider, model, task, SYSTEM_PROMPTS.get(task, ""), prompt, schema_name)


def portable_key(task: str, prompt: str, schema_name: str) -> str:
    """Provider-independent key so an Ollama-warmed cache also serves offline runs anywhere."""
    return _sha(task, prompt, schema_name)


def _cache_dir() -> Path:
    d = Path(os.getenv("QM_CACHE_DIR") or config.CACHE_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_read(key: str) -> dict | None:
    f = _cache_dir() / f"{key}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _cache_find_portable(pkey: str) -> dict | None:
    for f in sorted(_cache_dir().glob("*.json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if rec.get("portable_key") == pkey:
            return rec
    return None


def _cache_write(key: str, record: dict) -> None:
    f = _cache_dir() / f"{key}.json"
    f.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- fixtures (mock provider)
def _load_fixtures() -> list[dict]:
    out = []
    fdir = Path(os.getenv("QM_FIXTURE_DIR") or config.FIXTURE_DIR)
    if fdir.exists():
        for f in sorted(fdir.glob("*.json")):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
                rec["_file"] = f.name
                out.append(rec)
            except Exception:
                log.warning("bad fixture %s", f.name)
    return out


def _fixture_for(task: str, prompt: str) -> dict | None:
    for rec in _load_fixtures():
        if rec.get("task") != task:
            continue
        matches = rec.get("match") or []
        if isinstance(matches, str):
            matches = [matches]
        if matches and all(m in prompt for m in matches):
            return rec
    return None


def _safe_default(schema: type[BaseModel] | None) -> Any:
    if schema is None:
        return ""
    try:
        return schema().model_dump()
    except Exception:
        return {}


def _resolve_fallback(fallback: Any, schema: type[BaseModel] | None) -> Any:
    if callable(fallback):
        try:
            return fallback()
        except Exception as e:  # never crash on a fallback
            log.warning("fallback raised: %s", e)
            return _safe_default(schema)
    if fallback is not None:
        return fallback
    return _safe_default(schema)


# ---------------------------------------------------------------- JSON helpers
def inline_refs(schema: dict) -> dict:
    """Inline $ref/$defs so small local models (and Ollama's grammar builder) get a flat schema."""
    defs = schema.get("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                merged = {k: v for k, v in node.items() if k != "$ref"}
                target = walk(dict(defs.get(name, {})))
                target.update(merged)
                return target
            return {k: walk(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(schema)


def require_all(schema: dict) -> dict:
    """Mark every property required (recursively). Pydantic leaves defaulted fields optional, which lets a
    grammar-constrained small model return {}; requiring them makes it emit every field (null allowed)."""
    if isinstance(schema, dict):
        out = {k: require_all(v) for k, v in schema.items()}
        if isinstance(out.get("properties"), dict):
            out["required"] = list(out["properties"])
        return out
    if isinstance(schema, list):
        return [require_all(x) for x in schema]
    return schema


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def extract_json(text: str) -> Any:
    """Parse JSON from a model reply, tolerating <think> blocks and ``` fences."""
    text = _THINK_RE.sub("", text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _validate(raw_text: str, schema: type[BaseModel] | None) -> Any:
    if schema is None:
        return _THINK_RE.sub("", raw_text or "").strip()
    data = extract_json(raw_text)
    return schema.model_validate(data).model_dump()


# ---------------------------------------------------------------- providers
def build_ollama_payload(task: str, prompt: str, schema: type[BaseModel] | None, model: str,
                         think_supported: bool = True) -> dict:
    user = prompt if think_supported else prompt + "\n/no_think"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS.get(task, "Be concise.")},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": config.LLM_TEMPERATURE},
    }
    if think_supported:
        payload["think"] = False
    if schema is not None:
        payload["format"] = require_all(inline_refs(schema.model_json_schema()))
    return payload


def _ollama_raw(task: str, prompt: str, schema, model: str, timeout: float) -> str:
    url = f"{ollama_host()}/api/chat"
    payload = build_ollama_payload(task, prompt, schema, model, think_supported=True)
    r = requests.post(url, json=payload, timeout=timeout)
    if r.status_code == 400 and "think" in (r.text or "").lower():
        # Older Ollama builds reject the `think` field: fall back to the /no_think prompt switch.
        payload = build_ollama_payload(task, prompt, schema, model, think_supported=False)
        r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    body = r.json()
    return (body.get("message") or {}).get("content", "")


def build_anthropic_payload(task: str, prompt: str, schema: type[BaseModel] | None, model: str) -> dict:
    user = prompt
    if schema is not None:
        user += (
            "\n\nReturn ONLY a JSON object that validates against this JSON schema "
            "(no prose, no code fences):\n" + json.dumps(inline_refs(schema.model_json_schema()))
        )
    return {
        "model": model,
        "max_tokens": 2048,
        "temperature": config.LLM_TEMPERATURE,
        "system": SYSTEM_PROMPTS.get(task, "Be concise."),
        "messages": [{"role": "user", "content": user}],
    }


def _anthropic_raw(task: str, prompt: str, schema, model: str, timeout: float) -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json=build_anthropic_payload(task, prompt, schema, model),
        timeout=timeout,
    )
    r.raise_for_status()
    body = r.json()
    return "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")


def _live_call(provider: str, model: str, task: str, prompt: str, schema, timeout: float) -> Any:
    """Call the provider; one retry on network error or schema-validation failure."""
    fn = _ollama_raw if provider == "ollama" else _anthropic_raw
    attempt_prompt = prompt
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            raw = fn(task, attempt_prompt, schema, model, timeout)
            return _validate(raw, schema)
        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            last_err = e
            attempt_prompt = (
                prompt + f"\n\nYour previous reply was invalid: {str(e)[:400]}\n"
                "Reply again with valid JSON only."
            )
        except requests.RequestException as e:
            last_err = e
        log.warning("llm %s attempt %d failed: %s", task, attempt + 1, type(last_err).__name__)
    raise RuntimeError(f"{type(last_err).__name__}: {str(last_err)[:200]}")


# ---------------------------------------------------------------- public API
def call_model_meta(task: str, prompt: str, schema: type[BaseModel] | None = None,
                    fallback: Any = None, force_live: bool = False) -> tuple[Any, dict]:
    """Returns (output, meta). meta['source'] in live|cache|fixture|fallback."""
    provider = current_provider()
    model = current_model(provider)
    schema_name = schema.__name__ if schema is not None else "text"
    key = cache_key(provider, model, task, prompt, schema_name)
    pkey = portable_key(task, prompt, schema_name)
    meta = {"task": task, "provider": provider, "model": model, "source": None,
            "latency_s": 0.0, "error": None, "cache_key": key[:12]}

    def from_fixture_or_fallback(reason: str | None) -> tuple[Any, dict]:
        fx = _fixture_for(task, prompt)
        if fx is not None:
            out = fx["output"]
            if schema is not None:
                try:
                    out = schema.model_validate(out).model_dump()
                except ValidationError:
                    pass
            meta.update(source="fixture", error=reason)
            return out, meta
        meta.update(source="fallback", error=reason)
        return _resolve_fallback(fallback, schema), meta

    mode = demo_mode()
    if provider == "mock":
        return from_fixture_or_fallback(None)

    if not force_live:
        rec = _cache_read(key)
        if rec is not None:
            meta.update(source="cache", latency_s=rec.get("latency_s", 0.0))
            return rec["output"], meta

    if mode == "offline":
        rec = _cache_find_portable(pkey)
        if rec is not None:
            meta.update(source="cache", latency_s=rec.get("latency_s", 0.0),
                        error=f"cache from {rec.get('provider')}:{rec.get('model')}")
            return rec["output"], meta
        return from_fixture_or_fallback("offline cache miss")

    t0 = time.time()
    try:
        out = _live_call(provider, model, task, prompt, schema, config.LLM_TIMEOUT_S)
    except Exception as e:
        meta["latency_s"] = round(time.time() - t0, 2)
        log.warning("llm %s failed after %.1fs -> fallback", task, meta["latency_s"])
        rec = _cache_find_portable(pkey)
        if rec is not None:
            meta.update(source="cache", error=f"live failed ({str(e)[:80]}); used cache")
            return rec["output"], meta
        return from_fixture_or_fallback(f"live failed: {str(e)[:120]}")
    latency = round(time.time() - t0, 2)
    log.info("llm %s via %s:%s in %.2fs", task, provider, model, latency)
    meta.update(source="live", latency_s=latency)
    _cache_write(key, {
        "key": key, "portable_key": pkey, "provider": provider, "model": model, "task": task,
        "schema": schema_name, "prompt": prompt, "output": out, "latency_s": latency,
        "created": datetime.now().isoformat(timespec="seconds"),
    })
    return out, meta


def call_model(task: str, prompt: str, schema: type[BaseModel] | None = None,
               fallback: Any = None) -> Any:
    return call_model_meta(task, prompt, schema, fallback)[0]


# ---------------------------------------------------------------- Ollama smoke test
class _PingSchema(BaseModel):
    part: str | None = None
    qty: int | None = None
    material: str | None = None


def check_ollama(extra_prompt: str | None = None) -> bool:
    """Connectivity + JSON smoke test for Quentin's PC. Prints a short report, returns ok."""
    host, model = ollama_host(), current_model("ollama")
    print(f"Ollama host: {host}   model: {model}")
    try:
        tags = requests.get(f"{host}/api/tags", timeout=10).json()
    except Exception as e:
        print(f"FAIL: cannot reach Ollama ({type(e).__name__}). Is the Ollama app running?")
        return False
    names = [m.get("name", "") for m in tags.get("models", [])]
    if not any(n == model or n.startswith(model + ":") or n.split(":")[0] == model for n in names):
        print(f"FAIL: model {model!r} not pulled. Available: {', '.join(names) or '(none)'}")
        print(f"      Run: ollama pull {model}")
        return False
    print("OK: server reachable, model present")
    ok = True
    tests = [("ping", "Extract: 'Need 250 pcs of hitch bracket HB-12 in 3/8 A36 plate.'", _PingSchema)]
    if extra_prompt:
        from qm.intake import RFQSpec  # local import to avoid a cycle
        tests.append(("intake_extract", extra_prompt, RFQSpec))
    for name, prompt, schema in tests:
        t0 = time.time()
        try:
            out = _live_call("ollama", model, "intake_extract", prompt, schema, config.LLM_TIMEOUT_S)
            dt = time.time() - t0
            verdict = "OK" if dt < 20 else "SLOW (>20s: consider qwen3:4b)"
            print(f"{verdict}: {name} returned valid JSON in {dt:.1f}s")
            if name == "ping":
                print(f"      -> {out}")
            ok = ok and dt < 60
        except Exception as e:
            print(f"FAIL: {name}: {str(e)[:200]}")
            ok = False
    return ok
