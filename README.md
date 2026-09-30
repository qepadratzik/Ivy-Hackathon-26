# Quote Memory: Evidence-Weighted Quoting

> **Every number in the quote shows its sources, and how much you trust it depends on how good those sources are.**

Built for the 2026 Ivy AI Case Competition (Iowa State): *"AI for Iowa: Improving Manufacturing Quoting with AI"*.

> **All data is synthetic.** Boone Creek Fabrication (a ~40-person metal fab job shop in central Iowa) and every
> customer, contact and email address in this repo are fictional. All rates, prices and dollar figures are illustrative.

## What it does

One RFQ flows through the case's seven stages. AI reads, searches, weights and simulates; people decide at the gates.

1. **Customer Request**: an RFQ email plus the customer's spec sheet (pick demo RFQ A/B/C or paste your own).
2. **Understand Requirements**: the model copies each field with a verbatim quote; Python verifies it, flags gaps
   and conflicts (qty 250 vs 200, missing color), triages S/M/L. *Human:* ask the customer, or assume + contingency.
3. **Determine Manufacturing Approach**: finds the closest past job, proposes its BOM + routing rescaled for this
   order, and lists what's different. *Human: Gate 1*, the estimator approves or edits the BOM + routing.
4. **Estimate Cost**: every line gets a value, a range, a confidence chip and cited evidence (past actuals, past
   quotes, supplier quotes, debriefs/NCRs, patterns, earlier overrides, shop default). Click a line to see its sources.
5. **Assess Risk & Uncertainty**: Monte Carlo (2,000 samples) gives P10/P50/P90 cost per unit, plus gap
   contingencies and a stale-material flag (steel quote > 30 days old: re-quote or 15-day quote validity).
6. **Determine Price**: a win-probability model trained on past quotes gives an expected-margin curve, a recommended
   price and range, adjusted for shop load; standard vs expedite. *Human: Gate 2*, the manager picks the price.
7. **Review & Submit Quote**: customer-ready quote (prices, lead time, validity, assumptions), Markdown/HTML download.

Overrides need a written reason (Gate 1 edits, Gate 2 prices outside the recommended range) and are saved to memory,
so the next similar RFQ shows them as evidence. A "What just changed" banner shows how every decision moves cost,
confidence and price downstream.

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

- **RFQ A (main):** Cedar Valley hitch bracket, Rev C. Qty conflict and missing color, Gate 1 fixture override,
  weld-line provenance, stale steel chain reaction, Gate 2 price and the finished quote.
- **RFQ B (learning):** Hawkeye hitch bracket, first run. The override written on A shows up as evidence.
- **RFQ C (fast-track):** Loess Hills mounting plate, repeat order. Triaged S, no gaps, all lines green.

Click-by-click script (~3.5 min, plus a 60 s fallback): [demo/demo_script.md](demo/demo_script.md). Use the sidebar's
**Reset demo state** before each run.

## Tests

`python -m pytest -q` (no model needed, about a minute): seeded patterns, retrieval analogs (Chroma and TF-IDF),
intake and gaps, the HANDOFF 7.4 worked example, pricing, the override → memory → next-RFQ loop, and a headless
Streamlit AppTest of the whole demo path, including offline mode.

## Repo layout

```
app.py              Streamlit UI: 6 sections, 2 gates, evidence drawer, change banner
qm/
  config.py         .env loading + every tunable constant
  data_gen.py       seeded synthetic shop history (python -m qm.data_gen); data_text.py: fictional text
  llm.py            call_model: mock / ollama / anthropic, disk cache, offline mode
  intake.py         RFQ email -> structured spec (copy-only LLM + quote check)
  gaps.py           gaps & conflicts, ask/assume, clarification email
  triage.py         S/M/L: fast-track vs full review
  store.py          tables + vector store (Chroma, TF-IDF fallback); retrieval.py: similar jobs and notes
  proposal.py       analog -> proposed BOM + routing, difference table
  evidence.py       evidence weighting (the core)
  patterns.py       pattern queries P1-P4
  uncertainty.py    Monte Carlo P10/P50/P90
  pricing.py        win model, expected-margin curve, recommendation
  memory.py         overrides -> memory (CSV + SQLite + vector store)
  pipeline.py       wiring, change banner, quote preview, CLI (--check-ollama, --warm)
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
| [docs/HANDOFF.md](docs/HANDOFF.md) | Build directive: mission, locked decisions, full technical and UI spec |
| [docs/assumptions.md](docs/assumptions.md) | Every constant, seeded pattern and modeling assumption |
| [docs/LOCAL_RUN.md](docs/LOCAL_RUN.md) | Running with Ollama, presentation-day modes, troubleshooting |
| [docs/process_current.md](docs/process_current.md) | Current-state quoting process map |
| [docs/process_future.md](docs/process_future.md) | Future-state process with Quote Memory |
| [docs/deck_outline.md](docs/deck_outline.md) | Pitch deck outline |
| [docs/qa.md](docs/qa.md) | Judge Q&A prep |
| [docs/roi.md](docs/roi.md) | Illustrative ROI and adoption one-pager |
| [demo/demo_script.md](demo/demo_script.md) | Live demo script |

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
- **Prototype UI.** Single-user Streamlit app with local demo memory; no ERP integration or PDF export.
