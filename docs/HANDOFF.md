# QUOTE MEMORY: Claude Code Handoff & Build Directive

> **To Claude Code:** You own this project end to end. Read this whole file before doing anything. Then follow **Section 2 (Operating Rules)** and work through **Section 10 (Phases)** in order until every acceptance check passes. Quentin is monitoring remotely and can step in, but you make most of the judgment calls. Escalate only what Section 2.3 lists.

---

## 0. Kickoff checklist (do these first, in order)

1. **Repo:** Quentin created a fresh **PUBLIC** GitHub repo for this project. Work inside that repo. Check `git remote -v`. If no remote is set, ask Quentin for the repo URL (one message) and keep working locally meanwhile. **Before the very first commit, complete Section 2.6 (Secrets & Public Repo Rules).**
2. Copy the rules in Section 2 into `CLAUDE.md` at the repo root so they survive context compaction. Save this full file as `docs/HANDOFF.md`.
3. Create `PROGRESS.md` (format in Section 2.4).
4. **Deadline (confirmed): code freeze AND submission = Thursday Oct 1, 2026 at 2:50 PM CT.** This is hard. Internal targets: **feature freeze 11:30 AM CT**, **code freeze 1:30 PM CT** (after that, bug fixes only, no new features), leaving ~80 min for the backup recording, rehearsal, and submitting. The phase time estimates in Section 10 add up to more than the time available: **apply the Cut Order (Section 12) proactively**, don't wait until you're behind. Re-plan against the clock at the end of every phase.
5. **Model (confirmed):** primary = `qwen3:8b` via Ollama (Quentin is pulling it). Fallback if it's too slow on his hardware = `qwen3:4b` (ask before pulling). Qwen3 has a "thinking" mode: disable it for every call (`"think": false` in the Ollama request; if unsupported, add `/no_think` to the prompt) so outputs are fast and clean JSON.
6. Ask Quentin (one message, then keep working): "Is there an ANTHROPIC_API_KEY in your local `.env` I can use as a fallback provider? (Optional.)"
7. Run environment checks (Phase 0). Don't wait for answers before starting Phase 0 and Phase 1.

---

## 1. Mission

Build and ship a **working, demo-ready prototype plus a pitch package** for the **2026 Ivy AI Case Competition (Iowa State, Ivy Business Analytics and Digital Strategy Forum): "AI for Iowa: Improving Manufacturing Quoting with Artificial Intelligence."**

**Product name:** Quote Memory (subtitle: Evidence-Weighted Quoting)

**One-line pitch:** *Every number in the quote shows its sources, and how much you trust it depends on how good those sources are.*

**Hard deadline:** tomorrow night (see kickoff). The team is two people: Quentin (MIS student, full-stack dev, has real custom CNC quoting experience from his company Twisted Traction) and a teammate whose skills are unknown. You are the primary builder.

### 1.1 What the case asks (paraphrased; the judges grade against this)
- Redesign the quoting process for a **small or midsize Iowa manufacturer** using AI.
- Process chain: **Customer Request → Understand Requirements → Determine Manufacturing Approach → Estimate Cost → Assess Risk & Uncertainty → Determine Price → Review & Submit Quote.**
- Teams must identify key quote factors, key tasks, bottlenecks/uncertainties/risks, and where AI adds the most value.
- The solution must show **how information moves between stages**, **how AI changes specific tasks**, **how outputs from one stage affect later decisions**, and **where human judgment stays**.
- The case explicitly says a simple chatbot, a single-task AI, or "ask AI what price to charge" is **not** enough.
- It must handle **incomplete, inconsistent, outdated data**, changing supplier prices, and tacit (hard-to-capture) knowledge.
- Existing models and tools are allowed. It must **demonstrate how it actually works**, not describe AI in general.
- Judges are experienced industry people. There is no public rubric.

### 1.2 What wins (design north star)
1. **A visible chain reaction.** Change one input and judges watch confidence drop, the cost band widen, and the price recommendation move.
2. **Provenance on every number.** Click any line and see the exact past job, note, or supplier quote it came from.
3. **Humans at the right gates**, with overrides captured as reusable knowledge ("it learns").
4. **Realism for a small Iowa shop.** Runs locally on a PC via Ollama, works from past-job exports, no ERP swap, and customer data never leaves the building.

---

## 2. Operating Rules

### 2.1 Autonomy: you decide these without asking
- All implementation details: file layout inside the given structure, function signatures, prompt wording, chart styling, test design.
- Tuning every numeric constant (weights, half-lives, range formula, pattern thresholds), as long as you record the final values in `docs/assumptions.md`.
- Library choices **within** the approved stack (Section 5).
- Cutting features by following the **Cut Order** (Section 12) when behind schedule. Log each cut in PROGRESS.md.
- Regenerating or adjusting synthetic data so seeded patterns are discoverable and the demo RFQs retrieve the intended analogs.
- Picking the Ollama model among those already pulled, using the extraction benchmark in Phase 0.
- Fixing anything that breaks, refactoring, adding tests.

### 2.2 Subagents: delegate the less intensive work
Use subagents (the Task tool) for bounded, low-coupling work. Give each a crisp spec, the exact output path, and acceptance criteria. **Review their output yourself before merging.** You keep ownership of architecture, the evidence/weights engine, pricing math, app state, and integration.

Delegate these:
| Subagent task | Output | Acceptance |
|---|---|---|
| Write text templates + ~30 LLM-style debrief/NCR notes for the data generator | `qm/data_text.py` or `data/seed_notes.json` | Realistic shop-floor voice; each note tagged with the family, work center, and pattern it supports |
| Write the 3 demo RFQ emails + structured specs (Section 9) | `demo/rfqs/*.md` + `demo/rfqs/*.json` | Contain exactly the features listed in Section 9 |
| Write pytest tests for pure functions (weights, uncertainty, pricing, gap rules) | `tests/` | Tests run and pass; they cover edge cases (no evidence, single evidence, conflicting evidence) |
| Current-state + future-state process maps (Mermaid) | `docs/process_current.md`, `docs/process_future.md` | Follow Section 11.1; render in Markdown |
| Pitch deck outline with speaker notes | `docs/deck_outline.md` | Follow Section 11.2 |
| Judge Q&A prep | `docs/qa.md` | Follow Section 11.3 |
| ROI / adoption one-pager (illustrative numbers, clearly labeled) | `docs/roi.md` | Follow Section 11.4 |
| README + run instructions | `README.md` | A fresh clone runs by following it |
| Independent review pass ("red team the demo") near the end | `docs/review.md` | Lists concrete breakages/confusions; you fix or consciously accept each |

Run business-doc subagents **in parallel** with the build, starting after Phase 1. The teammate can own and polish those docs.

### 2.3 Escalate to Quentin ONLY for these
- Changing any **Locked Decision** (Section 3).
- Downloading large things or installing system-level software (e.g., `ollama pull` a new multi-GB model, CUDA stuff). Ask first and state the model name and approximate size.
- Anything needing credentials or spending money (API keys, paid services). **Never** create, request, or paste keys yourself; Quentin puts them in `.env`.
- Being more than ~90 minutes behind the schedule **after** applying the Cut Order.
- Content only Quentin can provide: his Twisted Traction hook story (leave `[QUENTIN: ...]` placeholders).
- Final go/no-go on live model vs. cached offline mode for the actual presentation.

When you escalate, send **one short message**: the decision needed, your recommended option, and what you'll do by default if there's no answer in 20 minutes. Then **keep working** on something unblocked.

### 2.4 Progress logging (Quentin is monitoring remotely)
Keep `PROGRESS.md` current. After every phase, append:
```
## [time] Phase N: <name>: DONE | PARTIAL | BLOCKED
- Built: ...
- Verified: <which acceptance checks passed>
- Cuts/decisions: ...
- Next: ...
```
Commit to git at the end of every phase with message `phase N: <summary>`. Keep chat status updates to 3–5 lines.

### 2.5 Engineering principles
- **The LLM never produces a number that goes into cost or price.** Math is deterministic Python. The model only extracts, flags, drafts, and explains.
- **Everything runs locally by default** (Ollama + local embeddings). The provider can be switched via config.
- **Demo reliability beats cleverness.** Every model call is cached, and there's an offline mode that reads only from cache.
- Keep it simple: plain functions, pandas DataFrames, one app state dict. No over-engineering, no unnecessary classes, no async.
- Verify, don't assume. Run the code, run the tests, run the app headless (Streamlit `AppTest`) before calling a phase done.

### 2.6 Secrets & Public Repo Rules (NON-NEGOTIABLE)
The GitHub repo is **PUBLIC**. Anything pushed is visible to the world and scraped by bots within minutes. Quentin's #1 instruction: **never push secrets.**

**Before the first commit:**
1. Create `.gitignore` containing at least:
   ```
   .env
   .env.*
   !.env.example
   .venv/
   __pycache__/
   *.pyc
   .streamlit/secrets.toml
   *.key
   *.pem
   ```
2. Create `.env.example` with **empty** values only. The real `.env` is created by Quentin locally and never staged.
3. Install a local pre-commit guard at `.git/hooks/pre-commit` (executable) that scans the **staged diff** and blocks the commit if it finds any of: a staged `.env` file (other than `.env.example`), `sk-ant-`, `sk-`, `ghp_`, `github_pat_`, `AKIA`, `-----BEGIN`, `xox`, or any line matching `(API_KEY|TOKEN|SECRET|PASSWORD)\s*=\s*\S+` outside `.env.example`. Test the hook once with a dummy staged file, then remove the dummy.
4. Run `git check-ignore -v .env` to confirm `.env` is ignored.

**On every commit/push:**
- Stage files explicitly or with `git add -A` **only after** reviewing `git status`. Never `git add -f` an ignored file.
- Before every `git push`, run `git diff --cached --stat` and a quick grep of the outgoing commits for the patterns above. If anything matches: **stop, don't push**, fix it, and tell Quentin.
- Never print secret values in logs, PROGRESS.md, code, comments, tests, cache files, or chat. Read keys only via `os.getenv` from `.env`.
- The `cache/llm/` folder may be committed (it's needed for offline mode) but must contain only prompts/outputs about the synthetic data, never headers, keys, or env values. Verify before committing it.
- If a secret is ever committed, even locally: **do not push.** Tell Quentin immediately. If it was already pushed, tell him to **rotate the key right away** (history rewriting alone doesn't make it safe).

**Public-repo hygiene:**
- All data is synthetic and all company/customer names are fictional; say so in the README.
- No personal info about Quentin, his teammate, Twisted Traction financials, or any real customer in the repo. The `[QUENTIN: ...]` hook story placeholder stays a placeholder in the repo.
- Push to `main` at the end of every phase (after the secret check) so progress is backed up.

---

## 3. Locked Decisions (do not change without asking Quentin)

1. **Fictional target company:** *Boone Creek Fabrication* (fictional), a ~40-person metal fabrication job shop in central Iowa making custom weldments, brackets, guards, frames, and tube assemblies for **ag and construction equipment OEMs** and tier-1 suppliers. Primary user: the senior estimator (single point of failure, retirement risk). Secondary user: the owner/GM who approves prices.
2. **No drawing/CAD parsing.** Input = RFQ email text + structured spec (part description, material, thickness, qty, key tolerances, weld/cosmetic requirement, finish, due date). Drawing parsing is a "next steps" slide item only.
3. **Cost backbone = BOM + routing.** BOM lines (raw material, purchased parts, outside processing) + routing ops (work center, setup hours, run hours per unit) × burdened work-center rates.
4. **S/M/L job class is an OUTPUT** (triage: fast-track vs. full review), never the input.
5. **Numbers come from structured tables. Vector search is only for text** (RFQ emails, debriefs, NCRs, override notes) and for description similarity.
6. **Evidence-weighted ledger:** every BOM/routing line gets a value, a range, a confidence, and cited evidence (formula in Section 7.4).
7. **Two human gates:** Gate 1 = estimator approves/edits the proposed BOM + routing. Gate 2 = manager selects the final price. Overrides at either gate require a written reason, which is saved back into memory.
8. **Local-first:** Ollama on Quentin's PC is the primary model provider; an Anthropic API fallback is optional.
9. **Synthetic data, openly labeled as synthetic**, with seeded patterns.
10. **Streamlit** is the UI.

---

## 4. Environment

### 4.0 Two-environment setup (READ THIS)
- **You (Claude Code) are running in a CLOUD environment.** You most likely **cannot reach Ollama**, which runs on Quentin's local PC at `localhost:11434`. Don't try to tunnel into his machine, and don't try to install or run Ollama/large models in the cloud env.
- **The GitHub repo is the bridge.** You build and test in the cloud and push. Quentin pulls on his PC, where the real model runs and where the **live demo happens**.
- **Providers (in `qm/llm.py`):**
  - `mock`: the default in the cloud. Returns deterministic, hand-written fixture outputs (`tests/fixtures/llm/*.json`) for every task on the 3 demo RFQs, plus a generic safe fallback for anything else. All tests and the `AppTest` smoke test must pass with `MODEL_PROVIDER=mock`, so the whole app is fully buildable and verifiable without any model.
  - `anthropic`: optional, for live-model testing in the cloud **only if** Quentin has set `ANTHROPIC_API_KEY` as a secret env var in the cloud environment's settings. Check with `os.getenv`; never ask him to paste it in chat or write it to any file.
  - `ollama`: used on Quentin's PC for the real demo.
- Write the Ollama provider carefully against the Ollama REST API (`/api/chat`, `format` = JSON schema, `stream: false`, `think: false`) even though you can't run it. Unit-test its request building and response parsing with mocked HTTP responses.
- **Cache portability:** `DEMO_MODE=offline` reads `cache/llm/`. Quentin generates the real cache locally by running the warm script with Ollama, then commits it (after the secret check). If he never does, offline mode falls back to the mock fixtures, so the demo still works.
- **Deliver `docs/LOCAL_RUN.md`** (Phase 8): the exact copy-paste steps for Quentin's PC:
  1. `git pull`
  2. Create the venv and `pip install -r requirements.txt`
  3. Copy `.env.example` to `.env` and set `MODEL_PROVIDER=ollama`, `OLLAMA_MODEL=qwen3:8b`
  4. `ollama pull qwen3:8b` (if not done) and make sure Ollama is running
  5. `python -m qm.pipeline --check-ollama` (a small connectivity + JSON smoke test you write)
  6. `python -m qm.pipeline --warm demo/rfqs`
  7. `streamlit run app.py`
  8. Walk through the demo script
  9. Optionally commit `cache/llm/` after the secret check

  Include troubleshooting: Ollama not running, model too slow → `qwen3:4b`, JSON failures → offline mode.
- Quentin must do the local run **by ~12:30 PM CT** so issues surface before code freeze. Remind him in PROGRESS.md and chat when Phase 7 is done.

### 4.1 Local machine
- Quentin's PC runs Ollama (default `http://localhost:11434`). He operates this Claude Code session remotely.
- Python 3.11+ in a venv at `quote-memory/.venv`.
- `.env` (you create `.env.example`; Quentin fills in secrets):
```
MODEL_PROVIDER=mock              # mock (cloud default) | anthropic | ollama (Quentin's PC)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:8b            # fallback qwen3:4b (ask before pulling)
ANTHROPIC_API_KEY=               # optional fallback; Quentin fills in
ANTHROPIC_MODEL=                 # optional; Quentin fills in
DEMO_MODE=live                   # live | offline (offline = cache only, never calls a model)
RANDOM_SEED=42
```
- Never print or log secret values.

---

## 5. Approved Stack

`streamlit`, `pandas`, `numpy`, `scikit-learn`, `plotly`, `chromadb` (default local embedding function), `requests` (Ollama REST), `pydantic` (schemas), `python-dotenv`, `pytest`. Optional: `anthropic` (fallback provider only).

**Ollama structured output:** call `/api/chat` with `format` set to the JSON schema (derived from the pydantic model) and `stream: false`, `temperature` 0–0.2. Validate with pydantic. On a validation failure, retry once with the error appended. On a second failure, fall back to the cached result or mark the fields low-confidence (never crash).

---

## 6. Repo Structure

```
quote-memory/
  CLAUDE.md                 # operating rules (copied from Section 2)
  PROGRESS.md
  README.md
  .env.example
  requirements.txt
  app.py                    # Streamlit entry
  qm/
    config.py               # env loading, constants (rates, half-lives, authorities)
    llm.py                  # call_model(task, prompt, schema) -> dict; caching; provider switch; offline mode
    data_gen.py             # synthetic data generator (seeded) + hero jobs
    data_text.py            # templates/notes (subagent)
    store.py                # load tables (pandas/SQLite), Chroma client, ingest docs
    intake.py               # RFQ -> structured spec via LLM (schema, source quotes, confidence)
    gaps.py                 # deterministic gap/conflict rules, ask-vs-assume, clarification draft
    triage.py               # S/M/L label rules
    retrieval.py            # similar jobs (structured + embedding), note retrieval
    proposal.py             # analog BOM/routing -> proposed BOM/routing + difference table
    evidence.py             # per-line evidence gathering, scoring, value/confidence/range
    patterns.py             # 4 hardcoded pattern queries + LLM one-line narration
    uncertainty.py          # Monte Carlo -> P10/P50/P90
    pricing.py              # win model, expected margin curve, recommendation, expedite option
    memory.py               # override write-back to docs table + Chroma
    pipeline.py             # run_pipeline(rfq, state) -> result dict; diff(prev, new) -> change banner
  data/                     # generated CSVs/SQLite + chroma/ (gitignore chroma if large)
  cache/llm/                # JSON cache keyed by hash(provider, model, task, prompt)
  demo/rfqs/                # RFQ_A, RFQ_B, RFQ_C (.md email + .json spec)
  demo/demo_script.md
  docs/                     # HANDOFF.md, assumptions.md, process maps, deck_outline, qa, roi, review
  tests/
```

---

## 7. Technical Specification

### 7.1 Data model

All tables are generated by `qm/data_gen.py` (seeded, deterministic) and saved as CSV + one SQLite DB.

| Table | Fields |
|---|---|
| `customers` | customer_id, name, segment (`OEM`/`tier1`/`aftermarket`), is_new (bool), notes |
| `jobs` | job_id (J-0001…), customer_id, part_family, part_number, description, material, material_raw_name (messy alias), thickness_in, qty, tolerance_class (`standard`/`tight`), cosmetic_weld (bool), finish, first_run (bool), has_fixture_line (bool), quote_date, est_cost, quoted_price, won (bool), lead_time_days |
| `bom_lines` | job_id, line_no, item_type (`raw`/`purchased`/`outside`), item, qty_per, uom, unit_cost, cost_date |
| `routing_ops` | job_id, seq, work_center, setup_hr_est, run_hr_est (per unit), setup_hr_act, run_hr_act (actuals only for won and completed jobs; ~10% of won jobs missing actuals) |
| `docs` | doc_id, job_id, doc_type (`rfq_email`/`debrief`/`ncr`/`override`), date, part_family, work_center (nullable), text |
| `material_prices` | material, price_per_lb, quote_date, supplier |
| `work_centers` | work_center, rate_per_hr, default_setup_hr, default_run_hr_per_unit |

**Scale:** ~150 jobs over ~24 months ending Sept 2026; 5 part families (`hitch_bracket`, `guard`, `frame`, `mounting_plate`, `tube_assembly`); 7 fictional customers; ~60% won.

**Work centers + illustrative burdened rates** (label as illustrative everywhere): `laser` $150, `press_brake` $95, `saw` $70, `machining` $110, `fit_tack` $80, `weld` $85, `grind` $70, `inspect_pack` $75. Outside process: `powder_coat` priced per part from a small vendor table.

**Materials:** A36 plate/sheet (dominant), A500 tube, 1018 bar, occasional 304 SS and 5052 aluminum. Steel price per lb drifts upward over the 24 months (illustrative, with a noticeable jump in the last ~6 months to reflect tariff pressure). Material aliases for messiness: "A36", "A-36 HR", "HR A36", "ASTM A36 plate".

**Fictional customers (7):** Prairie Implement Co., Cedar Valley Equipment, Hawkeye Loader Works, North Star Ag Systems, Raccoon River Attachments, Big Sioux Trailer, Loess Hills Machinery. Label all as fictional.

### 7.2 Seeded patterns (must be discoverable; tests enforce this)
| ID | Pattern | Seeding rule | Test (on generated data) |
|---|---|---|---|
| P1 | Cosmetic-weld jobs overrun weld hours | `run_hr_act / run_hr_est` for weld ≈ N(1.35, 0.08) when cosmetic_weld, else N(1.02, 0.07) | mean ratio for cosmetic in [1.25, 1.45], n ≥ 8 |
| P2 | First-run weldments without a fixture line overrun setup | fit_tack `setup_hr_act/est` ≈ 1.6–2.2 when first_run & !has_fixture_line; ~50% get a debrief note mentioning the fixture | ratio ≥ 1.5, n ≥ 5, ≥ 3 fixture notes |
| P3 | Press brake on plate ≥ 0.5" has rework | ~30% of those jobs get an NCR doc (work_center=press_brake); scrap/rework adds run hours | NCR rate in [0.2, 0.45], n ≥ 8 |
| P4 | Price-sensitive customer | Prairie Implement wins only if quoted_price/est_cost < ~1.25 (logistic, steep) | win rate < 1.25 ≥ 0.7 and ≥ 1.30 ≤ 0.25 |
| P5 | Steel prices rising | A36 price_per_lb trends up; the last 6 months are ~12–18% above the first 6 | trend test passes |

**Noise:** ~10% missing actuals, messy material aliases, 3–4 near-duplicate part numbers, a few jobs with a missing finish, occasional typos in emails. The data must look realistic, not cartoonish.

**Hero jobs (deterministic, handcrafted):** add 4–6 fixed jobs so the demo RFQs reliably retrieve the intended analogs:
- 2 won `hitch_bracket` jobs in A36 3/8" with **cosmetic weld**, full actuals, qty 100–300 (strong evidence for RFQ A's weld line).
- 1 lost `hitch_bracket` quote (quote-only evidence).
- 1 first-run weldment with a setup overrun and a debrief saying a new fixture was needed.
- 1 simple repeat `mounting_plate` job for RFQ C.
Give them memorable IDs (e.g., J-1042, J-0987, J-1103). Record them in `docs/assumptions.md`.

**Text generation:** use templates with random variation for most docs. A subagent writes ~30 debrief/NCR notes in a realistic shop-floor voice (short, casual, specific). Don't call the model at data-generation time unless offline-cached; the notes can be static JSON.

### 7.3 Pipeline stages (each returns plain dicts; `pipeline.py` wires them together)

**S1 Intake (`intake.py`).** LLM → pydantic `RFQSpec`:
```
fields: part_description, part_family, material, thickness_in, qty, release_qty,
        tolerance_class, cosmetic_weld, finish, finish_color, due_date, customer_name, notes
each field: {value, confidence: high|medium|low, source_quote: str|null}
```
The prompt must forbid inventing values. Missing = null with confidence low. Normalize material aliases in Python (a lookup table) after extraction.

**S2 Gaps & conflicts (`gaps.py`, deterministic).** Rules:
- Required field null or low confidence → gap.
- Email text vs. structured spec disagree (material, qty, finish) → conflict.
- Due date < minimum feasible lead time (from routing + outside processing) → risk.
- Finish specified but color missing → gap.

Each gap has `action: ask | assume`, a default, and for `assume` a stated assumption plus a contingency % (default 3–8% of the affected lines). The LLM drafts **one** clarification email covering all `ask` items (cached). Changing ask/assume re-runs downstream stages.

**S3 Triage (`triage.py`).** Repeat part number or close analog + standard tolerance + qty ≤ 50 → `S / fast-track`. New weldment or first-run or cosmetic → `L / full review`. Else `M`. Show the reason string.

**S4 Retrieval + proposal (`retrieval.py`, `proposal.py`).**
- Candidate jobs are filtered by part_family (and material family, if enough candidates).
- `sim = 0.5 * embed_cos(description) + 0.5 * structured_sim`, where structured_sim = 0.4·same_family + 0.2·same_material + 0.2·thickness_closeness + 0.2·qty_bucket_match.
- Analog = the top won job with actuals (fall back to the top overall).
- Proposed BOM/routing = the analog's, rescaled for qty. Deterministic difference rules: finish change → add/remove the powder_coat line; first_run & no fixture → add a "fixture (one-time)" line with default hours; cosmetic → keep the grind op.
- Produce a **difference table**: field | new RFQ | analog | expected cost effect.
- **Gate 1:** show proposed BOM/routing as an editable table (`st.data_editor`). Any edit requires a reason (text input) before continuing.

**S5 Evidence & weights (`evidence.py`).** See 7.4. Runs per routing op and per BOM line.

**S6 Patterns (`patterns.py`).** Four hardcoded pandas queries (P1–P4) are triggered only when the RFQ matches the condition. Show a pattern only if n ≥ 3. The output dict has the stat, n, the affected line, and a suggested adjustment. The LLM writes one plain-English sentence from the dict (cached). A pattern adjusts the affected line's value via a clearly labeled "pattern adjustment" evidence row with authority 0.8.

**S7 Uncertainty (`uncertainty.py`).** Per line, a triangular distribution (low, value, high) × quantities × rates. 2,000 samples, summed → total cost per unit P10/P50/P90. Add gap contingencies. Treat lines as independent (state this in assumptions).

**S8 Pricing (`pricing.py`).**
- Win model: `LogisticRegression` on synthetic quotes, with features price_to_cost_ratio, segment one-hot, is_new_customer, qty_bucket.
- For candidate prices across [1.0, 1.8] × P50 cost: `exp_margin = P(win) × (price − P50)`.
- Recommend the peak. Recommended range = prices with exp_margin ≥ 90% of the peak.
- A capacity slider (0–100% shop load) shifts the minimum acceptable margin (high load → higher floor).
- Show a standard option and an expedite option (+X% price for −Y days lead time, illustrative).
- **Gate 2:** the manager picks a price. If it's outside the recommended range, a reason is required.

**S9 Memory write-back (`memory.py`).** Every override (Gate 1 edits, Gate 2 out-of-range picks, ask/assume flips if reasoned) becomes a `docs` row with `doc_type=override`, part_family, work_center (if line-level), date=now, and the text "Estimator override on <line>: <old>→<new>. Reason: <reason>". Write it to SQLite/CSV **and** Chroma immediately. Evidence retrieval for notes includes override docs, so a similar next RFQ surfaces them.

**S10 Quote preview.** An on-screen formatted quote: line summary, unit price per qty break, lead time, validity window, **assumptions & exclusions** (from `assume` gaps and material freshness), terms. Offer a Markdown/HTML download. PDF is cut.

### 7.4 Evidence weighting (core IP; implement exactly, then tune)
```
evidence_score = similarity × source_authority × recency_decay
source_authority: actual 1.0 | note/override/pattern 0.8 | past quote (estimate) 0.6 | shop default 0.3
recency_decay = 0.5 ** (age_days / half_life)
half_life: material price 30 days | labor/setup/run hours 540 days | notes 365 days
line_value = Σ(score·value) / Σ(score)
weighted_std = sqrt(Σ(score·(value − line_value)²) / Σ(score))
CV = weighted_std / line_value
confidence = min(1, Σscore / 3) × (1 − min(1, CV))
spread = 0.10 + 0.40 × (1 − confidence)       # clamp final spread to ≤ 0.60
range = [value × (1 − spread), value × (1 + spread)]
chip: green ≥ 0.70, yellow 0.40–0.70, red < 0.40
```
- Evidence for routing ops: the same work center's values from the top-5 similar jobs (actuals if present, else estimates as "past quote"), plus the shop default, plus relevant notes/patterns (notes carry the adjustment the pattern implies, not an LLM number).
- Evidence for material: `material_prices` rows for the normalized material, most recent first. Stale quotes decay fast. If the newest price is > 30 days old, add a flag: "Re-quote material or shorten quote validity to 15 days."
- Only evidence with similarity ≥ 0.35 counts. Show a "why this matched" string for each evidence row.
- **Worked example (put in tests):** values [0.62 actual, 0.58 actual, 0.45 quote, 0.40 default], scores ≈ [0.71, 0.54, 0.47, 0.30] → value ≈ 0.537, CV ≈ 0.16, confidence ≈ 0.56, range ≈ 0.39–0.69.

### 7.5 Change banner (makes the chain reaction obvious)
`pipeline.diff(prev, new)` compares results after any change and renders: "P50 cost/unit: $X → $Y (+Z%). Band width: A% → B%. Recommended price: $P → $Q. Lines that changed confidence: …". Keep the previous result in `st.session_state`.

### 7.6 LLM layer (`llm.py`)
- `call_model(task: str, prompt: str, schema: type[BaseModel] | None) -> dict | str`
- Cache key = sha256(provider, model, task, prompt, schema name). Store in `cache/llm/`.
- `DEMO_MODE=offline` → cache only; on a miss, return a safe fallback and flag it in the UI.
- Timeout 60s, one retry. Log latency.
- Tasks: `intake_extract`, `clarification_email`, `pattern_narration`, `evidence_explain` (optional one-liner for a selected line).

### 7.7 Performance
- `st.cache_resource` for the Chroma client, the win model, and loaded tables. `st.cache_data` for pure computations keyed by inputs.
- Warm the cache for all demo RFQs via `python -m qm.pipeline --warm demo/rfqs` so the live demo is instant.

---

## 8. UI Specification (`app.py`)

- **Sidebar:** RFQ picker (A/B/C + paste box), DEMO_MODE indicator, capacity slider, "Age material quote" control (days), **Reset demo state** button (reloads base data, removes demo-session overrides from memory).
- **Header:** RFQ title, triage badge with reason, 7-stage stepper (the case's stages) highlighting progress.
- **Section 1: Requirements:** extracted fields with confidence chips and source quotes. A gaps/conflicts list with an ask/assume toggle each. Clarification email in an expander.
- **Section 2: Approach (Gate 1):** difference table vs. analog, editable BOM/routing, reason box, Approve button.
- **Section 3: Ledger:** left ~60%: table of lines (value, range, confidence chip, sources count, warning icon). Right ~40%: an **evidence drawer** for the selected line (each evidence row: source type, job/doc ID, value, similarity, authority, decay, score, "why matched", expandable original text). Pattern callouts below.
- **Section 4: Risk & cost:** P10/P50/P90 chart, contingency lines, material freshness flag.
- **Section 5: Price (Gate 2):** expected-margin curve with the recommended range shaded, standard vs. expedite, price input, reason box if out of range, Approve.
- **Section 6: Quote preview** + download.
- **Change banner** pinned under the header after any change.
- Non-technical judges must be able to follow it: plain labels ("How sure are we?", "Where this number came from"), consistent colors, no raw JSON visible (except in a debug expander).

---

## 9. Demo Assets

**RFQ A (main):** Cedar Valley Equipment (existing OEM customer). Hitch bracket weldment, A36 3/8" plate, 4 laser parts + 2 formed + 1 tube, purchased bushings/bolts, **cosmetic weld** ("visible side, no spatter, smooth"), qty 250 in releases of 50, powder coat **color not specified**, due date tight but feasible. The email mentions "3/8 plate" while the spec says "0.375 A-36 HR" (should normalize cleanly, not a conflict). Include one real conflict: the email says qty 250, the attached spec line says 200. Expected: 2 gaps (color = ask, qty conflict = ask), analog = hero cosmetic-weld job, P1 fires on the weld line, the material price is fresh.

**RFQ B (learning):** near-twin of A for a different part number, **first run, needs a fixture**. After the Gate 1 override on A (setup "needs new fixture, add ~6 hrs"), B's fit_tack setup line must show that override note as evidence.

**RFQ C (fast-track):** Loess Hills Machinery repeat mounting plate, qty 40, standard tolerance → `S / fast-track`, high confidence everywhere.

**`demo/demo_script.md`:** a beat-by-beat script (~3.5 min) with exact clicks:
1. Load A → fields + gaps → draft email → set color to "assume black, +3% contingency".
2. Difference table → approve Gate 1 **after editing fit_tack setup +6 hrs with reason "new fixture needed"**.
3. Click the weld line → evidence drawer → P1 callout.
4. Age the material quote to 90 days → watch the change banner (confidence drop, band widens, validity flag).
5. Price curve → pick a price → Gate 2 → quote preview.
6. Load B → the fixture override appears as evidence on setup.
7. Load C → fast-track in one screen.

Also include a 60-second fallback version and talking points for each beat.

---

## 10. Phases (execute in order; each has acceptance checks)

**Phase 0: Setup & model check (~45 min)**
- Scaffold the repo, venv, requirements, `.env.example`, CLAUDE.md, PROGRESS.md.
- You're in the cloud: build `qm/llm.py` with the `mock`, `anthropic`, and `ollama` providers per Section 4.0. Check for `ANTHROPIC_API_KEY` in the environment (presence only, never print it). Don't attempt to reach Quentin's Ollama.
- Write `python -m qm.pipeline --check-ollama` now so Quentin can verify his local model early. Ask him to run it once the scaffold is pushed (target: valid JSON, < 20s per call; if too slow, `qwen3:4b`).
- Complete Section 2.6 (gitignore, `.env.example`, pre-commit hook) **before the first commit**.
- ✅ Accept: `call_model` returns valid structured JSON with `MODEL_PROVIDER=mock` (and `anthropic` if a key is present); Ollama provider unit tests pass with mocked HTTP.

**Phase 1: Data (~1.5 h)**
- Implement `data_gen.py` (+ subagent text/notes), hero jobs, messiness.
- Implement the pattern tests P1–P5 and noise sanity checks. Iterate until they pass.
- ✅ Accept: `pytest tests/test_data.py` passes; `data/` populated; hero jobs present.

**Phase 2: Store & retrieval (~1 h)**
- SQLite/CSV loaders, Chroma ingest of docs, similarity function, note retrieval.
- ✅ Accept: for RFQ A's spec, the top analog is the intended hero job; the top notes include a relevant debrief. Test covers it.

**Phase 3: Intake, gaps, triage (~1.5 h)**
- Pydantic schemas, prompts, alias normalization, gap rules, clarification email, triage rules.
- ✅ Accept: RFQ A yields exactly the expected gaps/conflict; RFQ C triages to S; outputs cached.

**Phase 4: Proposal, evidence, patterns (~2 h)**
- Analog → proposal + difference table. Evidence engine per 7.4 with the worked-example test. Patterns P1–P4.
- ✅ Accept: the ledger for RFQ A has every line with a value/range/confidence/evidence; the weld line shows P1; aging the material to 90 days drops material confidence to red/yellow and raises the flag.

**Phase 5: Uncertainty & pricing (~1.5 h)**
- Monte Carlo, win model, margin curve, recommendation, expedite option, capacity effect.
- ✅ Accept: sensible P10 < P50 < P90; Prairie Implement's recommended markup is lower than others'; the capacity slider moves the recommendation.

**Phase 6: Memory write-back (~45 min)**
- ✅ Accept: an override on A's fit_tack setup appears as evidence on RFQ B's setup line (automated test); reset removes it.

**Phase 7: Streamlit UI (~2.5 h)**
- Build per Section 8. Use `st.session_state` with one state dict. Build the change banner.
- ✅ Accept: an `AppTest` smoke test runs the full RFQ A → B → C path without exceptions; manual run looks clean.

**Phase 8: Demo hardening (~1 h)**
- Warm the cache; test `DEMO_MODE=offline` end to end with Ollama stopped; reset button; demo script written and executed step by step; timing checked.
- ✅ Accept: the full demo path works offline and with `mock`; `docs/LOCAL_RUN.md` exists; Quentin has confirmed (or been asked to confirm) the demo runs on his PC with `qwen3:8b`; a run-through fits in 3.5 min of clicks.

**Phase 9: Business package (parallel subagents from Phase 1 onward; you review)**
- Process maps, deck outline, Q&A, ROI, README, assumptions doc.
- ✅ Accept: every doc exists, is consistent with the build (names, numbers, features), and has `[QUENTIN: ...]` placeholders only where personal input is needed.

**Phase 10: Final verification & handoff (~45 min)**
- Red-team review subagent → fix or accept items. Run all tests. Fresh-clone install check from the README.
- Write a final `PROGRESS.md` summary: what works, known limitations, exact demo launch commands, what Quentin must still do (record the backup video, hook story, rehearse).
- ✅ Accept: all tests green; demo works live and offline; docs complete; secret scan clean; git tagged `v1-demo` and pushed **before 2:50 PM CT**.

---

## 11. Business Deliverable Specs (for subagents)

### 11.1 Process maps (Mermaid)
- **Current state:** RFQ arrives in inbox → one senior estimator reads it → chases missing info by email → searches old job folders/ERP for similar work → builds BOM + routing in Excel → guesses weld/setup hours → looks up a possibly stale steel price → adds markup by feel → owner glance → sent. No loop comparing estimates to actuals. Mark bottlenecks in red: estimator queue/single point of failure, missing info, weld/setup guesses, stale material, forgotten fixture costs, outside-processing lead time, guessed quantity breaks, no feedback loop.
- **Future state:** the case's 7 stages, with AI roles (intake extraction, gap detection, analog retrieval, per-line evidence weighting, patterns, uncertainty band, win-probability curve) and human gates (Gate 1, Gate 2, final send), plus the override → memory loop arrow.

### 11.2 Deck outline (5–7 min + demo; ~9 slides)
1. Hook (30s): `[QUENTIN: 3-sentence Twisted Traction story about a quote burned by a missing detail or an old material price]`
2. The problem in Iowa (30s): small fab shops feeding ag/construction OEMs; one estimator; buyers expect fast quotes.
3. Current-state map (45s).
4. The idea in one line (20s).
5. Future-state flow (45s).
6. Live demo (3.5 min).
7. Why a shop would adopt it (40s): local/on-prem via Ollama, customer prints never leave the building (CUI/ITAR-friendly), works from past-job exports, no ERP swap, low cost; illustrative ROI.
8. Positioning (30s): Paperless Parts (intake/workflow platform), Xometry (prices its own marketplace), Arzana (custom AI builds for larger shops), CADDi (drawing similarity search), Toolpath (CAD-based CNC estimating). Quote Memory = the transparent, evidence-weighted, local layer for smaller shops. Keep claims about competitors general and fair.
9. Limits & next steps (20s): synthetic data now → a real shop's history; drawing/CAD parsing; fine-tuning the local SLM on a shop's own RFQs; pilot with a CIRAS-supported Iowa manufacturer.
Include speaker notes for each slide. **Don't include unsourced industry statistics.** Label every number illustrative unless it's from the case text.

### 11.3 Q&A prep (`docs/qa.md`)
At least 12 hard judge questions with 2–3 sentence answers. Must include: no history/cold start; hallucinated numbers; why not buy Paperless Parts; synthetic data; why these weights; confidentiality/security; does it replace the estimator; setup time/effort; what if suppliers change prices daily; how accurate is it; why a small model instead of a big one; how it handles a totally new part type.

### 11.4 ROI one-pager (`docs/roi.md`)
Illustrative only, with every input visible and editable: RFQs/month, estimator hours per RFQ before/after, loaded estimator cost, hardware/software cost (local PC + open models ≈ minimal), qualitative benefits (faster response, knowledge retention, fewer margin-killing misses). Big "ILLUSTRATIVE, NOT BENCHMARKS" label.

---

## 12. Cut Order (apply from the top when behind; log each cut)
1. Expedite option
2. Capacity slider effect (keep the slider hidden)
3. RFQ C / triage display (keep the triage label only)
4. Quote preview download (keep on-screen)
5. Pattern callouts beyond P1 and P2
6. `evidence_explain` LLM one-liners
7. Clarification email draft (show the list of questions instead)

**Never cut:** evidence drawer with citations, confidence chips/ranges, the chain reaction via the change banner, Gate 1 + Gate 2 with reasons, override → rerun learning, offline mode.

---

## 13. Risk Register
| Risk | Mitigation |
|---|---|
| Cloud env can't reach local Ollama | `mock` provider for all cloud building/testing; optional `anthropic`; real model runs only on Quentin's PC via `docs/LOCAL_RUN.md` |
| Ollama slow or produces bad JSON | Schema-constrained output + pydantic retry; model benchmark in Phase 0; cache + offline mode; optional Anthropic fallback if Quentin provides a key |
| Wrong analog retrieved for demo RFQs | Hero jobs + retrieval test in Phase 2 |
| Seeded patterns not detected | Pattern tests in Phase 1 gate the phase |
| Silly ranges or prices | Clamp spread ≤ 60%; sanity tests; tune on demo RFQs only |
| Streamlit state bugs | Single state dict, reset button, AppTest smoke test |
| Time overrun | Cut Order; escalate if >90 min behind after cuts |
| Secret leaked to the public repo | Section 2.6: gitignore, pre-commit hook, pre-push grep; never push on a match; rotate if pushed |
| Remote session interruptions | Commit every phase; PROGRESS.md always current; any phase can be resumed from the log |

---

## 14. Definition of Done
- [ ] `streamlit run app.py` runs the full demo path (A → override → B → C) live **and** with `DEMO_MODE=offline`.
- [ ] Every ledger line shows value, range, confidence chip, and clickable evidence with original text.
- [ ] Changing a gap choice, aging the material, or overriding a line visibly updates confidence, band, and price via the change banner.
- [ ] The override on RFQ A surfaces as evidence on RFQ B.
- [ ] All tests pass; the worked-example weighting test matches Section 7.4.
- [ ] `docs/` has the process maps, deck outline, Q&A, ROI, assumptions, demo script, review.
- [ ] README lets a fresh clone run the app.
- [ ] Final PROGRESS.md summary lists what Quentin still has to do by hand: hook story, backup screen recording, build the slides from the outline, rehearse 3× with a timer.

**Start now with Section 0.**
