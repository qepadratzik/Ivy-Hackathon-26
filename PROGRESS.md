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

## [Wed 01:05 CT] Phase 4: Proposal, evidence, patterns: DONE
- Built: `qm/proposal.py` (analog BOM/routing using actual hours, material/thickness swap, finish add/remove, first-run fixture rule, cosmetic keeps grind, difference table incl. revision-change and steel-price drift rows), `qm/evidence.py` (Section 7.4 exactly; per-line rows for past jobs, shop default, supplier quotes, vendor table, notes sized by their job's act/est ratio, override notes as deltas, pattern rows; notes gated by line driver e.g. cosmetic notes never move a standard-weld line), `qm/patterns.py` (P1-P4, n>=3, LLM one-liner with template fallback).
- Verified: worked example (0.537 / CV 0.16 / conf 0.56 / 0.39-0.69) passes; RFQ A ledger 19 lines all with value/range/confidence/evidence; weld line carries P1; aging material 90 days: A36 green 0.97 -> red 0.21, flag + validity 30 -> 15 days.
## [Wed 01:05 CT] Phase 5: Uncertainty & pricing: DONE
- Built: `qm/uncertainty.py` (2,000-sample triangular Monte Carlo, per-line seeded streams, steel lines share one market shock, gap + escalation contingencies), `qm/pricing.py` (logistic win model with standardized ratio + segment/new/qty-bucket/customer one-hots; exp margin vs risk-adjusted cost P50 + 0.5(P90-P50); capacity = floor + labor opportunity cost; expedite +12% / -7 days; Gate 2 range check; per-release-size prices).
- Verified: P10 < P50 < P90 (A: ~150/156/162); Prairie markup 1.23x vs Cedar 1.34x; capacity 10% -> 100% moves A from ~$207 to ~$217.
- Decisions: material prices raised to realistic small-shop levels (A36 ~$0.86/lb now) and regenerated; capacity has a continuous opportunity-cost term (a pure floor only moved the price above ~85% load).
## [Wed 01:05 CT] Phase 6: Memory write-back: DONE
- Built: `qm/memory.py` (override -> docs row in data/memory CSV + SQLite + vector store immediately; decisions for Gate 2 / reasoned flips; replace-per-RFQ; reset).
- Verified: automated test: A's fit/tack setup override (+6 hr, "new fixture needed") appears on B's fit/tack setup as a counted evidence row and raises B's value; unrelated RFQ C unaffected; reset removes it. `pipeline.run_pipeline` + `diff` (change banner) + quote preview in place. 86 tests green.
- Next: Phase 7 Streamlit UI.

## [Wed 01:21 CT] Phase 7: Streamlit UI: DONE
- Built: `app.py` per Section 8: sidebar (RFQ picker A/B/C + paste box, shop-load slider, "age newest material quote" slider, model/mode indicator, memory panel, Reset), header (triage badge + reason, 7-stage stepper, KPI strip), change banner with cause ("what just changed ... because ..."), sections 1-6 (gaps with Ask/Assume + contingency, fields with confidence chips + verbatim source quotes, clarification email; analog card + diff table + editable BOM/routing + quick-adjust + required reason + Gate 1; ledger table + evidence drawer with score = sim x authority x recency and original text, pattern callouts, "learned from an earlier quote" callout; Monte Carlo histogram + uncertainty drivers + contingencies + material freshness; expected-margin/win-chance curve with range, floor, decision-cost breakdown, standard vs expedite, Gate 2 with out-of-range reason; quote preview + Markdown/HTML download). `.streamlit/config.toml` (light theme, minimal toolbar).
- Verified: `tests/test_app.py` AppTest runs the full A -> Gate 1 override -> weld drawer/P1 -> age 90 d -> Gate 2 -> quote -> B (sees A's override as evidence) -> C (fast-track) -> reset path, plus every section for every RFQ and a pasted RFQ, no exceptions. Real-browser walk-through (Playwright + Chromium) screenshots reviewed; fixed $-as-LaTeX rendering, clipped header, cramped tables, chart label overlap.
- Fix: an RFQ's own saved override is no longer re-counted as "memory" evidence on itself. Tests now isolate memory via `tests/conftest.py`.
- **Quentin: please do the local Ollama run (docs/LOCAL_RUN.md, coming in Phase 8) by ~12:30 PM CT Thu.**
- Next: Phase 8 demo hardening (offline mode test, LOCAL_RUN.md, demo script).

## [Wed 01:28 CT] Phase 8: Demo hardening: DONE (pending Quentin's local run)
- Built: `docs/LOCAL_RUN.md` (Windows + macOS steps, .env, ollama pull, `--check-ollama` now also prints how the live model read RFQ A and whether the demo's 2 gaps match, `--warm`, run, commit cache after secret scan, presentation-day mode table, troubleshooting incl. chromadb-install fallback), `demo/demo_script.md` (7 beats with exact clicks, on-screen numbers, talking points, 60-second fallback, recovery moves), `docs/assumptions.md` (every constant + modeling decision). Relaxed quote verification for paraphrased quotes (verified-approx -> medium) so a live small model doesn't create spurious gaps. Git hooks now find python/py on Windows.
- Verified: AppTest with `MODEL_PROVIDER=ollama` and Ollama unreachable in both `DEMO_MODE=offline` (zero network calls) and `live` (degrades to fixtures/templates): full path, no exceptions. `--warm` and `--check-ollama` (clean FAIL when Ollama is down) run. Reset button tested. Full suite green (~280 tests).
- Cuts/decisions: `evidence_explain` LLM one-liner cut (Cut Order #6); the drawer uses a deterministic explanation sentence. Nothing else cut.
- **Quentin: run docs/LOCAL_RUN.md on your PC (steps 1-7, ~15 min) by ~12:30 PM CT Thu and tell me what `--check-ollama` prints.**
- Next: README (subagent), business-doc review (Phase 9), red-team + fresh-clone check (Phase 10).

## [Wed 01:33 CT] Phase 9: Business package: DONE
- Built (subagents, reviewed + corrected by me): `docs/process_current.md` (8 red bottlenecks + table), `docs/process_future.md` (7 stages, AI roles, gates, memory loop + stage table), `docs/deck_outline.md` (9 slides, 4:20 talk + 3:30 demo, speaker notes, `[QUENTIN: ...]` hook placeholder), `docs/qa.md` (24 judge questions + honest limits + constants), `docs/roi.md` (ILLUSTRATIVE; editable inputs, formulas, worked example, sensitivity, adoption path), `README.md`.
- Verified: numbers/features match the build (P1 1.38x, P2 1.94x, P5 +15%, expedite +12%/-7 d, authorities/half-lives, gates); fixed statements that drifted (steel lines are correlated in the Monte Carlo, capacity adds an opportunity cost, win model includes customer history, offline fallback is a rule-based extractor). Only placeholder: the hook story.
- Also: Gate 2 "Use recommended" fixed (callback), past Gate 2 decisions surface on similar quotes, Ollama schema now requires every field, plain-English pattern sentences for mock/offline mode.
- Next: Phase 10 red-team review (running), fresh-clone check (running), final screenshots, tag v1-demo.

## [Wed 01:37 CT] Phase 10: Final verification: IN PROGRESS
- Done: fresh clone from GitHub + `pip install -r requirements.txt` + full suite = green (exit 0). Thin/nonsense pasted RFQs now produce sane numbers (missing essentials assumed from the closest past job, each flagged as a gap). SQLite mirror built from CSVs on first load. `scripts/screenshots.py` ready for `docs/screens/`.
- Running: independent red-team review (browser walk of the demo script + break-it tests) -> `docs/review.md`.
- Next: fix/accept review items, capture `docs/screens/`, final summary, tag `v1-demo`.
- Timeline: ~36 h ahead of the Thu 2:50 PM CT deadline; no cuts beyond `evidence_explain`.

## [Wed 02:18 CT] Phase 10: Red-team review addressed
- Review (`docs/review.md`, 22 findings: 1 blocker, 3 high) with a resolution table at the end. All fixed except #10 (mitigated) and two conscious "accepts" (stepper shows process progress; "three gates" = Gate 1, Gate 2, the human who sends).
- **Blocker fixed:** Reset now regenerates every widget (generation-suffixed keys + on_click reset). Verified in real Chromium and in AppTest.
- **Demo change (Beat 2):** on a revision change the system adds a red 0-hr *Fixture build (one-time)* line ("confirm the old fixture still fits"); the estimator sets 6 hr with the reason -> charged once (80 over 250 pcs, listed as tooling on the quote), line turns green. B learns on its own one-time fixture line (callout). Before, the +6 hr sat on per-release setup (charged 5x) and double-counted on B. `demo/demo_script.md` rewritten with the new on-screen numbers.
- Also: toast on every change, banner shows validity changes, stale Gate 2 approvals invalidated, Gate 2 price follows the recommendation, exclusions saved, "not priced" for junk pastes, no-welding RFQs, tube assemblies on A500, labor lines 0.5-correlated in the Monte Carlo (A band 7.8% -> 11.3%), release-size table + setup/tooling block on the quote, jargon cleanup.
- `docs/screens/` captured (13 PNGs of the demo beats) for slides and the fallback. Full suite green.

---

# FINAL SUMMARY (v1-demo)

**Status:** every phase's acceptance checks pass in the cloud build (mock provider + offline mode). Full test suite
green (~290 tests incl. headless AppTest of the whole demo path, offline/unreachable-Ollama runs, and a fresh-clone
install check). Branch `claude/determined-hawking-hdkb0z`. **Tag `v1-demo`: this cloud session's git proxy
rejects tag pushes (HTTP 403, policy), so please create it from your PC:**
`git fetch origin && git tag -a v1-demo origin/claude/determined-hawking-hdkb0z -m "Quote Memory demo" && git push origin v1-demo`
(or GitHub > Releases > "Draft a new release" > new tag `v1-demo` on that branch).

**What works**
- 7-stage flow with 2 human gates: intake (copy-only LLM + verbatim-quote check) → gaps/conflicts with ask/assume +
  contingency + one clarification email → triage S/M/L → closest past job + difference table → Gate 1 (edit/remove
  lines, reason required, saved to memory) → evidence-weighted ledger (Section 7.4 exactly; drawer shows every source,
  its similarity × authority × recency and the original record) → patterns P1-P4 (+P5 steel trend) → Monte Carlo
  P10/P50/P90 → win-probability curve, capacity, expedite → Gate 2 (reason if out of range) → quote preview
  (release-size prices, setup & tooling, assumptions, validity) with Markdown/HTML download.
- Chain reaction: every change shows a "What just changed" banner + toast (P50, band, price, validity, lines that
  changed confidence, and why). Memory loop: A's fixture override appears as learned evidence on B.
- Local-first: Ollama qwen3:8b (`think:false`), local embeddings (Chroma MiniLM, TF-IDF fallback), every call cached,
  `DEMO_MODE=offline` never calls a model.

**Launch (Quentin's PC)**: see `docs/LOCAL_RUN.md`
```
git checkout claude/determined-hawking-hdkb0z && git pull
python -m venv .venv && (activate) && pip install -r requirements.txt
copy .env.example .env   # MODEL_PROVIDER=ollama, OLLAMA_MODEL=qwen3:8b, DEMO_MODE=live
ollama pull qwen3:8b
python -m qm.pipeline --check-ollama
python -m qm.pipeline --warm demo/rfqs
streamlit run app.py
```
No model? `MODEL_PROVIDER=mock` (default) runs the identical demo with hand-checked extractions.

**Known limitations** (all stated in `docs/qa.md` / `docs/assumptions.md`): synthetic data; weights and correlations are
tunable priors, not fitted; win model trained on synthetic quotes; no CAD/drawing parsing; single-user prototype UI;
live-model extraction quality of qwen3:8b not yet verified on the demo PC (hence the `--check-ollama` step).

**What Quentin (and teammate) still must do by hand**
1. **By ~12:30 PM CT Thu:** run `docs/LOCAL_RUN.md` steps 1-7 on the demo PC; send Claude the `--check-ollama` output.
   Decide live vs offline for the presentation (Section 2.3 go/no-go is yours).
2. Write the Twisted Traction hook story (slide 1 placeholder `[QUENTIN: ...]` in `docs/deck_outline.md`).
3. Build the slides from `docs/deck_outline.md` (use `docs/screens/` for demo stills; process maps in `docs/process_*.md`).
4. Record the backup screen recording of `demo/demo_script.md`.
5. Rehearse the demo 3× with a timer (Reset → F5 check before each run), and read `docs/qa.md`.
6. Create the `v1-demo` tag (command above), then submit before 2:50 PM CT Thu.
## [Wed 09:38 CT] Model plan change: hosted Anthropic (Claude Haiku 4.5)
- GPU box unavailable -> demo model is the hosted `anthropic` provider (allowed fallback; locked decisions unchanged). Provider now uses the official SDK, default `claude-haiku-4-5`, no temperature (Sonnet/Opus 5.5 reject it). `python -m qm.pipeline --check-model` works for any provider. Docs reworded so nothing claims the demo ran locally. Tests green.
- **Quentin next:** get a dedicated API key (low spend limit) -> put it in `.env` (or the cloud env var `ANTHROPIC_API_KEY`, then a new session) -> `docs/LOCAL_RUN.md` "Hosted model" steps -> commit warmed `cache/llm` -> demo with `DEMO_MODE=offline`.

## [Wed 11:23 CT] Emoji purge
- Removed every emoji and pictographic symbol (including check marks) from the UI (`app.py`), scripts, docs and the regenerated `docs/screens/`. Confidence chips are now text ("green 0.97"), flags are EDIT / LEARNED / WARN, buttons are plain ("Approve Gate 1", "Reset demo state"). Arrows and math symbols kept. Tests green.

## [Wed 12:05 CT] Phase S1: Simplify the shop: DONE
- Built: a deliberately small fictional shop so the demo and the story are easy. 5 job types (hitch bracket, guard, frame, mounting plate, tube assembly), 3 materials (A36 plate, A500 tube, 5052 aluminum sheet), 5 shop steps (Cut, Bend, Fit and weld, Drill and tap, Inspect and pack) plus outside powder coat and a one-time fixture line. Removed: laser/saw, grind, fit-tack, 1018, 304 stainless, zinc. Data regenerated (158 jobs, seed 42); patterns P1-P5 still verified (P1 1.35x n=20, P2 1.90x n=21, P3 30%, P4 100% vs 0%, P5 +14%).
- Verified: full pytest green; RFQ A/B/C still pick J-1042 / J-1103 / J-1118 with Chroma and TF-IDF.
- Cuts/decisions: purchased and outside half-lives 180 -> 365 days and TOP_K_JOBS 5 -> 6 (merging processes had left too many yellow lines); aluminum is rare in the history (1 job) so aluminum requests show low confidence on purpose; the rule-based email reader now also finds "material, then thickness" phrasing.
- Next: S2.

## [Wed 12:05 CT] Phase S2: Guided plain-language UI: DONE
- Built: `app.py` rewritten as 5 steps (Read the request, Plan the work, Cost it, Set the price, Send the quote). Checkpoint 1 (estimator approves the plan, with a "does the old fixture still fit?" question) and Checkpoint 2 (manager approves the price from three choices: Lower / Recommended / Higher with chance of winning and profit). Confidence is High / Medium / Low, ranges read "very likely between $A and $B", "Memory" is the "Shop notebook", and a sidebar "Show the details" switch reveals evidence scores, the simulation and the profit curve. Shop-load and expedite controls are gone from the UI (still in the engine). New `qm/plain.py`, `pricing.price_options`, plain `triage["plain"]` reasons.
- Verified: pytest green (app tests rewritten: full demo path, paste box, details switch, offline/unreachable-model modes, price choices, price-needs-plan-first); real-browser walk with screenshots (`docs/screens/01..13`).
- Cuts/decisions: price approval is blocked until the plan is approved; re-opening the plan keeps the estimator's answer and reason.
- Next: S3 docs, S4 final checks.
