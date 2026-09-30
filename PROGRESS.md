# PROGRESS: Quote Memory

**Deadline:** code freeze + submission **Thu Oct 1, 2026 2:50 PM CT** (feature freeze 11:30 AM, code freeze 1:30 PM CT).
**Branch:** `claude/determined-hawking-hdkb0z` (this cloud session's designated branch; see Questions).
**Quentin: local Ollama run (`docs/LOCAL_RUN.md`) needed by ~12:30 PM CT Thu.**

## Questions for Quentin (defaults apply if no answer)
1. Is there an `ANTHROPIC_API_KEY` you want to use as an optional fallback provider? It is NOT set in the cloud env
   (presence checked only). **Default:** no Anthropic; build and test with `mock`, run live with Ollama on your PC.
2. The handoff says push to `main`; this cloud session is pinned to `claude/determined-hawking-hdkb0z`.
   **Default:** I push to that branch every phase; you can pull it directly or merge it to `main` (or tell me to open a PR).
3. Once the scaffold is pushed, please run `python -m qm.pipeline --check-ollama` on your PC (target: valid JSON, < 20 s/call).

## [Wed 00:39 CT] Phase 0: Setup & model check: DONE
- Built: repo scaffold, `.gitignore`, empty `.env.example`, secret guard (`scripts/secret_scan.py` + pre-commit/pre-push hooks, installed and tested with a dummy staged token + staged .env: both blocked; docs that only mention prefixes pass), `CLAUDE.md`, `docs/HANDOFF.md`, venv + requirements, `qm/config.py`, `qm/llm.py` (mock / ollama / anthropic providers, sha256 disk cache, portable cache key, offline mode, fixture + deterministic fallback, one retry with the validation error appended, `<think>` stripping, `think:false` with `/no_think` fallback), `python -m qm.pipeline --check-ollama`.
- Verified: `tests/test_llm.py` 14/14 pass (mock structured JSON, Ollama request/response with mocked HTTP, retry, offline never touches network, cache portability, anthropic payload, no secrets in cache). `git check-ignore -v .env` OK. ANTHROPIC_API_KEY not present in cloud env.
- Cuts/decisions: secret regexes require key-shaped suffixes (e.g. `sk-` + 16 key chars) so docs that mention prefixes don't block; timeline check at 00:50 CT Wed: ~37 h to deadline, no cuts needed yet. Demo RFQs A/B/C written (subagent, reviewed).
- Next: Phase 1 data generator + pattern tests.

