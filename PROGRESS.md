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

## [Wed 00:45 CT] Phase 1: Data: DONE
- Built: `qm/data_gen.py` (seeded; 150 random jobs + 8 hero jobs over Oct 2024-Sep 2026, 7 fictional customers, BOM/routing with estimates + actuals, messy aliases, near-dup part numbers, missing finishes, typo'd emails, NCR/debrief docs, weekly steel quotes). Subagent wrote `data/seed_notes.json` (36 shop-floor notes tagged by pattern) + `qm/data_text.py` (email templates); reviewed.
- Verified: `tests/test_data.py` 10/10. Seed 42 stats: P1 cosmetic weld act/est 1.38 (n=16); P2 first-run no-fixture fit/tack setup 1.94x (n=14, 4+ fixture notes); P3 NCR rate 0.31 (n=13); P4 Prairie win 94% below 1.25x vs 6% at >=1.30x; P5 A36 last-6 vs first-6 months +14.6%.
- Hero jobs: J-0918 (CVE-HB-4410 Rev A, first run w/ fixture), J-0987 + J-1042 (cosmetic hitch brackets, full actuals), J-1077 (lost Prairie quote), J-1103 (first run, no fixture, setup 2.2x + fixture debrief), J-0842/J-0955/J-1118 (LHM-MP-0620 repeats for RFQ C).
- Cuts/decisions: added a `fixture` routing op (one-time, fit_tack rate) and `line_key/old_value/new_value` columns on `docs` (needed for override memory). Data CSVs are committed; SQLite + Chroma are rebuilt locally (gitignored).
- Next: Phase 2 store + retrieval.

## [Wed 00:50 CT] Phase 2: Store & retrieval: DONE
- Built: `qm/store.py` (CSV tables + demo-session memory overlay; Chroma persistent store with local MiniLM embeddings, auto-rebuilt when data changes; TF-IDF fallback if Chroma/model unavailable, forced via `QM_EMBEDDINGS=tfidf`), `qm/retrieval.py` (similar jobs, analog pick, related notes, "why matched" strings).
- Verified: `tests/test_retrieval.py` (both backends): A->J-1042, B->J-1103, C->J-1118; A's weld-line notes are cosmetic-weld debriefs; B's setup notes lead with J-1103's fixture debrief. Full suite green.
- Cuts/decisions: structured similarity gets a weld-class term (0.32 family, 0.16 material, 0.16 thickness, 0.16 qty bucket, 0.20 weld class; HANDOFF weights x0.8), because cosmetic vs standard weld is the biggest labor driver (P1). Analog pick uses recency as a soft tiebreaker (15% weight). Hero J-1103 qty set to 150.
- Next: Phase 3 intake, gaps, triage.

## [Wed 00:54 CT] Phase 3: Intake, gaps, triage: DONE
- Built: `qm/intake.py` (pydantic RFQSpec where the LLM only COPIES text + verbatim source quote + confidence; Python normalizes materials/fractions/gauges/dates/families; quote-verification guard downgrades any value whose quote isn't in the email; deterministic spec-sheet parse + merge -> conflicts; regex fallback extractor for pastes/offline misses; repeat-part / first-run / revision-change from history), `qm/gaps.py` (missing/conflict/color rules, ask vs assume with contingency, due-date feasibility, clarification email via LLM with template fallback), `qm/triage.py`. Hand-written mock fixtures for A/B/C intake.
- Verified: `tests/test_intake.py` 33 pass: A -> exactly {qty_conflict, finish_color}; "3/8 plate" vs "0.375 A-36 HR" normalizes (no conflict); B none + first run; C none + S/fast-track; live Ollama result cached then served from cache (mocked HTTP).
- Next: Phase 4 proposal, evidence engine, patterns.

