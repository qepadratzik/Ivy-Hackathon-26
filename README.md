# Quote Memory: Evidence-Weighted Quoting

> **Every number in the quote shows its sources, and how much you trust it depends on how good those sources are.**

Built for the 2026 Ivy AI Case Competition (Iowa State): *"AI for Iowa: Improving Manufacturing Quoting with AI"*.

> **All data is synthetic.** Boone Creek Fabrication (a ~40-person metal fab job shop in central Iowa) and every
> customer, contact and email address in this repo are fictional. All rates, prices and dollar figures are illustrative.

## What it does

A guided **five-step** walk from a customer's email to a finished quote, in plain language. AI reads, searches,
weights and simulates; people decide at two checkpoints. The five steps cover the case's seven stages.

| Step in the app | Case stage(s) | What happens |
|---|---|---|
| **1 · Read the request** | 1 Customer Request, 2 Understand Requirements | The model copies each field with a verbatim quote from the email; Python verifies the quote, flags gaps and conflicts (qty 250 vs 200, missing color), and triages the job (Fast track / Standard / Full review). *Human:* ask the customer, or assume and print the assumption on the quote. |
| **2 · Plan the work** | 3 Determine Manufacturing Approach | Finds the closest past job, proposes its parts list and shop steps (using the hours it really took), and lists what is different. *Human: Checkpoint 1.* The estimator approves or edits the plan; a revision asks "does the old fixture still fit?". |
| **3 · Cost it** | 4 Estimate Cost, 5 Assess Risk and Uncertainty | Every line gets a value, a range, a High / Medium / Low confidence and its cited evidence (past actuals, past quotes, supplier quotes, shop notes, lessons from history, earlier estimator notes, shop rule of thumb). A 2,000-run simulation gives the "very likely between $A and $B" range. A stale steel quote shortens the quote's validity. |
| **4 · Set the price** | 6 Determine Price | A win model learned from past quotes gives three choices (Lower, Recommended, Higher) with the chance of winning and the profit. *Human: Checkpoint 2.* The manager approves; a price outside the range needs a reason. |
| **5 · Send the quote** | 7 Review and Submit Quote | Checklist plus a customer-ready quote (prices by batch size, lead time, validity, assumptions), Markdown/HTML download. A person sends it. |

Changes a person makes need a written reason (Checkpoint 1 edits, Checkpoint 2 prices outside the range). Reasons are
saved to the **shop notebook**, so the next similar request shows them as evidence. A "What just changed" box shows how
every decision moves the typical cost, the likely range, the suggested price and the quote validity. The sidebar switch
**Show the details** reveals the evidence scores, the simulation and the profit curve for anyone who wants to check the work.

**New here? Read [docs/PLAIN_ENGLISH.md](docs/PLAIN_ENGLISH.md) first** (10 minutes, no technical background needed).

The fictional shop is deliberately small: **5 job types** (hitch bracket, guard, frame, mounting plate, tube assembly),
**3 materials** (A36 plate, A500 tube, 5052 aluminum sheet) and **5 shop steps** (Cut, Bend, Fit and weld, Drill and tap,
Inspect and pack) plus outside powder coat.

## Design principles

- **The LLM never produces a cost or price number.** It does exactly three things: copy RFQ text into fields (each
  with a verbatim quote that Python checks), draft one clarification email, and write one-line pattern sentences.
  All math is deterministic Python; numbers come from structured tables, vector search is used only for text.
- **Local-first by design.** The shop deployment runs Ollama `qwen3:8b` (thinking disabled) plus local embeddings
  (Chroma's all-MiniLM-L6-v2, TF-IDF fallback), so customer data never leaves the machine. The model provider is one
  config line: the competition demo used the hosted `anthropic` provider (Claude Haiku 4.5) because the local GPU box
  was not available. The local path is implemented and unit-tested with mocked HTTP but was not run on real hardware.
- **Every model call is cached** (`cache/llm/`, sha256 key). `DEMO_MODE=offline` never calls a model (cache, then
  hand-checked fixtures, then templates); any model failure degrades the same way and the UI says so.
- **Evidence weighting** (details and every constant in [docs/assumptions.md](docs/assumptions.md)):

```
evidence_score = similarity × source_authority × recency_decay
source_authority: actual / supplier quote 1.0 · note / override / pattern 0.8 · past quote 0.6 · shop default 0.3
recency_decay    = 0.5 ** (age_days / half_life)      half-life: material 30 d · labor 540 d · notes 365 d
line_value       = Σ(score·value) / Σ(score)          CV = weighted_std / line_value
confidence       = min(1, Σscore / 3) × (1 − min(1, CV))
spread           = 0.10 + 0.40 × (1 − confidence)     (≤ 0.60)   range = value × (1 ± spread)
```

## Quickstart (no model needed)

The default `mock` provider uses hand-checked extractions, so the app runs without Ollama. Use Python 3.11 or 3.12.

macOS / Linux:
```bash
git clone https://github.com/qepadratzik/Ivy-Hackathon-26.git
cd Ivy-Hackathon-26
git checkout claude/determined-hawking-hdkb0z
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Windows (PowerShell):
```powershell
git clone https://github.com/qepadratzik/Ivy-Hackathon-26.git
cd Ivy-Hackathon-26
git checkout claude/determined-hawking-hdkb0z
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501. The first start builds the local vector index and downloads a ~80 MB
embedding model once; if that isn't available it falls back to TF-IDF automatically (same demo analogs, tested).
If PowerShell blocks `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` and retry.

### Run with the real local model

Full guide: [docs/LOCAL_RUN.md](docs/LOCAL_RUN.md). Copy `.env.example` to `.env` (`cp`, or `copy` on Windows) and set:
```
MODEL_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
DEMO_MODE=live
```
`MODEL_PROVIDER` is `mock` (default), `ollama` or `anthropic` (optional fallback); `DEMO_MODE=offline` is cache-only.
`.env` is gitignored and must never be committed. Then:
```bash
ollama pull qwen3:8b
python -m qm.pipeline --check-ollama      # connectivity + JSON smoke test on RFQ A
python -m qm.pipeline --warm demo/rfqs    # pre-fill the cache so the demo is instant
streamlit run app.py
```

## Demo

- **Job 1 (main):** Cedar Valley, a new revision of a hitch bracket with visible welds. Quantity conflict and missing
  color, the Checkpoint 1 fixture decision, evidence behind the weld line, a stale-steel what-if, Checkpoint 2 price
  choices and the finished quote.
- **Job 2 (it learned):** Hawkeye, a bracket we have never built. The estimator's note from Job 1 shows up as evidence.
- **Job 3 (fast track):** Loess Hills, a repeat mounting plate. Fast track, no questions, all lines solid.

- **On the spot:** sidebar **Quick demo · fill in a request** is a short form (customer, job type, material, thickness, quantity,
  batch size, welding, finish and color, tolerance, due date, optional part number, optional quantity conflict). It writes the
  customer's email and spec sheet and runs the same five steps. **Paste a customer email** takes a whole pasted email instead.

Click-by-click script for two presenters (about 10 minutes of demo inside a 15-20 minute pitch, plus a 60 second
fallback): [demo/demo_script.md](demo/demo_script.md). Click **Start over** in the sidebar before each run. Screenshots
of every beat are in `docs/screens/`.

## Tests

`python -m pytest -q` (no model needed, about a minute): seeded patterns, retrieval analogs (Chroma and TF-IDF),
intake and gaps, the HANDOFF 7.4 worked example, pricing, the estimator note → notebook → next request loop, and a
headless Streamlit AppTest of the whole demo path (all five steps, all three jobs, details switch, offline mode).

## Repo layout

```
app.py              Streamlit UI: 5 guided steps, 2 checkpoints, cost table with sources, change box
qm/
  config.py         .env loading + every tunable constant
  data_gen.py       seeded synthetic shop history (python -m qm.data_gen); data_text.py: fictional text
  llm.py            call_model: mock / ollama / anthropic, disk cache, offline mode
  intake.py         RFQ email -> structured spec (copy-only LLM + quote check)
  gaps.py           gaps & conflicts, ask/assume, clarification email
  triage.py         Fast track / Standard / Full review, with a plain reason
  plain.py          plain-language names (High/Medium/Low, 'about 8 in 10', line labels)
  quick.py          quick demo form -> customer email + spec sheet
  quote_html.py     customer-facing HTML quote (download)
  store.py          tables + vector store (Chroma, TF-IDF fallback); retrieval.py: similar jobs and notes
  proposal.py       analog -> proposed BOM + routing, difference table
  evidence.py       evidence weighting (the core)
  patterns.py       pattern queries P1-P4
  uncertainty.py    Monte Carlo cost range (P10/P50/P90 under the hood)
  pricing.py        win model, profit curve, recommendation, three price choices
  memory.py         estimator notes -> shop notebook (CSV + SQLite + vector store)
  pipeline.py       wiring, change box, quote preview, CLI (--check-model, --warm)
data/               synthetic CSVs (committed); SQLite, chroma/, memory/ are local runtime state (gitignored)
demo/               demo_script.md + rfqs/RFQ_A|B|C (.md email + .json spec sheet)
docs/               design, assumptions, run guide and pitch material (below)
tests/              pytest suite + fixtures/llm (hand-checked mock extractions)
cache/llm/          model response cache (sha256-keyed JSON)
scripts/            secret guard: secret_scan.py, pre-commit, pre-push
```

## Docs

| File | What's in it |
|---|---|
| [docs/PLAIN_ENGLISH.md](docs/PLAIN_ENGLISH.md) | **Start here.** The story, glossary, the five steps, who says what, simple Q&A |
| [docs/HANDOFF.md](docs/HANDOFF.md) | Build directive: mission, locked decisions, full technical and UI spec (original, pre-simplification wording) |
| [docs/assumptions.md](docs/assumptions.md) | Every constant, seeded pattern and modeling assumption |
| [docs/LOCAL_RUN.md](docs/LOCAL_RUN.md) | Running with Ollama, presentation-day modes, troubleshooting |
| [docs/process_current.md](docs/process_current.md) | Current-state quoting process map |
| [docs/process_future.md](docs/process_future.md) | Future-state process with Quote Memory |
| [docs/deck_outline.md](docs/deck_outline.md) | Pitch deck outline (two presenters, about 16:30) |
| [docs/qa.md](docs/qa.md) | Judge Q&A prep |
| [docs/roi.md](docs/roi.md) | Illustrative ROI and adoption one-pager |
| [demo/demo_script.md](demo/demo_script.md) | Live demo script, click by click |

## Contributing: keep secrets out

This repo is public. Never commit `.env`; only `.env.example` (all values empty) belongs here. Install the
secret-guard hooks once; they run `scripts/secret_scan.py` on staged changes (pre-commit) and outgoing commits
(pre-push) and block anything key-shaped or any `.env` file:
```bash
cp scripts/pre-commit .git/hooks/pre-commit
cp scripts/pre-push .git/hooks/pre-push
```

## Limitations

- **Synthetic data.** The history, patterns and customers are generated (seed 42); nothing is measured from a real shop.
- **Weights are tunable priors**, not fitted; with real history, calibrate them against estimate-vs-actual error.
- **Monte Carlo correlation is assumed, not fitted.** Steel lines share one shock and labor lines are 0.5-correlated;
  a real shop's estimate-vs-actual history should calibrate that.
- **No CAD/drawing parsing.** Input is RFQ email text plus a structured spec sheet; reading drawings is the next step.
- **Deliberately small shop.** 5 job types, 3 materials and 5 shop steps keep the demo clear; the method does not depend
  on the count (a new shop step is one row in `qm/config.py`). Aluminum is rare in the history, so aluminum requests show low confidence.
- **Prototype UI.** Single-user Streamlit app with local demo memory; no ERP integration or PDF export.
