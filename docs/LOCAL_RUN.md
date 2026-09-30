# LOCAL_RUN: running Quote Memory on Quentin's PC

> **Current plan: hosted model (Anthropic Claude Haiku 4.5).** The GPU box fell through, so use the
> "Hosted model" section right below. The Ollama steps further down are kept for a future local run.

## Hosted model (Anthropic) - do this

1. `git pull`, create the venv, `pip install -r requirements.txt` (steps 1-2 below).
2. `.env` (never committed): `MODEL_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=<your key>`, `ANTHROPIC_MODEL=claude-haiku-4-5`,
   `DEMO_MODE=live`. Use a dedicated key with a low monthly spend limit; delete it after Thursday.
3. `python -m qm.pipeline --check-model` - expect OK lines and `RFQ A as read by the model ... OK: gaps ['finish_color', 'qty_conflict']`.
   If it misreads RFQ A, set `ANTHROPIC_MODEL=claude-sonnet-5-5` and rerun.
4. `python -m qm.pipeline --warm demo/rfqs` (fills `cache/llm/`; run twice, the second run should say `cache`).
5. Commit the cache: `git add cache/llm && python scripts/secret_scan.py --staged && git commit -m "cache: warmed model outputs" && git push`.
6. **Presentation mode:** `DEMO_MODE=offline` in `.env`, then `streamlit run app.py`. No key or wifi needed on stage;
   the screen says "cached model output".

---

# Ollama (local GPU) steps, optional

**Do this by ~12:30 PM CT Thursday** so problems surface before the 1:30 PM code freeze.
Total time: ~15 minutes (plus the model download if `qwen3:8b` isn't pulled yet, ~5 GB).

The cloud build uses a `mock` model. On your PC the same app talks to **Ollama** (`qwen3:8b`,
thinking disabled). Nothing leaves your machine: the model, the embeddings and the data are all local.

---

## 1. Get the code

First time:
```bash
git clone https://github.com/qepadratzik/Ivy-Hackathon-26.git
cd Ivy-Hackathon-26
git checkout claude/determined-hawking-hdkb0z
```
Already cloned:
```bash
cd Ivy-Hackathon-26
git fetch origin
git checkout claude/determined-hawking-hdkb0z
git pull
```

## 2. Python environment (Python 3.11 or 3.12 recommended)

Windows (PowerShell):
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```
macOS / Linux:
```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```
If PowerShell blocks `Activate.ps1`: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.

## 3. Create your `.env` (never committed; it's gitignored)

Windows: `copy .env.example .env`  ·  macOS/Linux: `cp .env.example .env`

Edit `.env` so these lines read:
```
MODEL_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
DEMO_MODE=live
```
Leave `ANTHROPIC_API_KEY` empty unless you deliberately want the optional fallback.

## 4. Ollama

Make sure the Ollama app is running (tray icon), then:
```bash
ollama pull qwen3:8b
ollama list
```

## 5. Smoke test the model (connectivity + JSON + reads RFQ A correctly)
```bash
python -m qm.pipeline --check-ollama
```
Expected output (times vary):
```
OK: server reachable, model present
OK: ping returned valid JSON in 3.1s
OK: intake_extract returned valid JSON in 12.4s
RFQ A as read by the model: qty=250 lot=50 material=A36 thickness=0.375 cosmetic=True finish=powder_coat color=None due=2026-11-06
OK: gaps ['finish_color', 'qty_conflict'] (demo expects ['finish_color', 'qty_conflict'])
```
- `SLOW (>20s)`: see Troubleshooting (switch to `qwen3:4b`).
- `CHECK: gaps [...]`: the model read RFQ A differently. The app still works, but the demo script assumes
  exactly those two gaps. Use `MODEL_PROVIDER=mock` for the presentation and send Claude the printout.

## 6. Warm the cache (makes the live demo instant)
```bash
python -m qm.pipeline --warm demo/rfqs
```
This also downloads the small local embedding model (~80 MB, once). Expected:
```
Provider: ollama:qwen3:8b  mode: live
  RFQ-A: gaps=['qty_conflict', 'finish_color'] analog=J-1042 P50=$151.48 rec=$198.44 llm=['live', ...]
  RFQ-B: gaps=[] analog=J-1103 P50=$133.21 rec=$175.17 ...
  RFQ-C: gaps=[] analog=J-1118 P50=$42.62 rec=$56.26 ...
```
Run it a second time: every `llm=` entry should now say `cache` and it should take a few seconds.

## 7. Run the app
```bash
streamlit run app.py
```
Your browser opens http://localhost:8501. The sidebar should say **Model: `qwen3:8b`**, **Mode: `live`**.

## 8. Walk through the demo
Follow `demo/demo_script.md` once end to end (about 10 minutes). Click **Start over** in the
sidebar before each rehearsal and before the real presentation.

## 9. (Optional) Commit the warmed cache so offline mode has real model output
`cache/llm/*.json` contains only prompts/outputs about the synthetic RFQs. Check, then commit:
```bash
git status                                    # expect only cache/llm/*.json as new files (never .env)
git add cache/llm
python scripts/secret_scan.py --staged        # must print nothing
git commit -m "cache: warmed qwen3:8b outputs for demo RFQs"
git push
```
Install the secret guard hooks locally first (one time):
`cp scripts/pre-commit .git/hooks/pre-commit` and `cp scripts/pre-push .git/hooks/pre-push`
(Windows Git Bash works the same). Never `git add .env`.

---

## Presentation-day modes (go/no-go is your call)

| Situation | `.env` settings | What happens |
|---|---|---|
| Normal (recommended) | `MODEL_PROVIDER=ollama`, `DEMO_MODE=live` | Demo RFQs come from the warmed cache (instant); a pasted RFQ calls qwen3 live. |
| Ollama flaky / venue PC slow | `MODEL_PROVIDER=ollama`, `DEMO_MODE=offline` | Never calls the model. Uses the warmed cache, then hand-checked fixtures, then templates. |
| No Ollama at all | `MODEL_PROVIDER=mock` | Hand-checked fixture extractions + templates. Everything else (evidence, Monte Carlo, pricing, memory) is identical. |

All math (evidence weights, Monte Carlo, pricing) is deterministic Python in every mode; the model only
extracts text, drafts the clarification email and writes the one-line pattern sentences.

## Troubleshooting

- **`FAIL: cannot reach Ollama`**: start the Ollama app; check `curl http://localhost:11434/api/tags`
  (PowerShell: `irm http://localhost:11434/api/tags`). If you changed the port, update `OLLAMA_HOST`.
- **`model 'qwen3:8b' not pulled`**: `ollama pull qwen3:8b`.
- **Too slow (> 20 s per call)**: `ollama pull qwen3:4b` (~2.5 GB), set `OLLAMA_MODEL=qwen3:4b`, rerun steps 5-6.
  Or use `DEMO_MODE=offline` after warming.
- **JSON failures / weird extractions**: the app retries once with the error, then falls back to the
  fixture/template, and the UI says so ("rule-based fallback"). For the presentation use `DEMO_MODE=offline`
  (after warming) or `MODEL_PROVIDER=mock`.
- **`think` errors on an old Ollama**: handled automatically (retries with `/no_think`). Updating Ollama also fixes it.
- **`pip install` fails on `chromadb`/`onnxruntime` (Windows)**: install the rest and run anyway; the app
  falls back to local TF-IDF embeddings automatically (same demo analogs, tested):
  `pip install streamlit pandas numpy scikit-learn plotly requests pydantic python-dotenv pytest`
- **First app start is slow**: it's building the local vector index and (once) downloading the embedding
  model. Run step 6 on venue Wi-Fi beforehand, or before you leave home.
- **Something looks stuck in the demo**: sidebar **Start over**, or stop Streamlit (Ctrl+C) and
  delete the `data/memory` folder.
- **Run the tests**: `python -m pytest -q` (about a minute; no model needed).
