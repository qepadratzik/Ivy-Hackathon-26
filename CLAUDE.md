# CLAUDE.md: Quote Memory operating rules

Full brief: `docs/HANDOFF.md` (read it after any context compaction). Live status: `PROGRESS.md`.

## Quick facts
- Product: **Quote Memory: Evidence-Weighted Quoting** for the 2026 Ivy AI Case Competition (Iowa State).
- **Deadline: code freeze AND submission Thu Oct 1, 2026, 2:50 PM CT.** Feature freeze 11:30 AM CT, code freeze 1:30 PM CT.
- Quentin must do the local Ollama run (`docs/LOCAL_RUN.md`) by ~12:30 PM CT Thu.
- Dev branch for this cloud session: `claude/determined-hawking-hdkb0z` (session-mandated). Quentin pulls it on his PC.
- Cloud default `MODEL_PROVIDER=mock`. Ollama (`qwen3:8b`, `think:false`) runs only on Quentin's PC.
- Run tests: `.venv/bin/python -m pytest -q`. Run app: `.venv/bin/streamlit run app.py`.

## 2.1 Autonomy: decide without asking
- Implementation details (layout, signatures, prompts, chart styling, tests).
- Numeric constants (weights, half-lives, range formula, thresholds). Record final values in `docs/assumptions.md`.
- Library choices within the approved stack (streamlit, pandas, numpy, scikit-learn, plotly, chromadb, requests, pydantic, python-dotenv, pytest; optional anthropic).
- Cutting features via the Cut Order (HANDOFF Section 12) when behind. Log each cut in PROGRESS.md.
- Regenerating/adjusting synthetic data so patterns are discoverable and demo RFQs hit the intended analogs.
- Fixing, refactoring, adding tests.

## 2.2 Subagents
Delegate bounded, low-coupling work (text/notes, demo RFQs, pure-function tests, process maps, deck outline, Q&A, ROI, README, red-team review). Crisp spec + exact output path + acceptance criteria. **Review their output before merging.** Keep ownership of architecture, evidence/weights engine, pricing math, app state, integration.

## 2.3 Escalate to Quentin ONLY for
- Changing a Locked Decision (HANDOFF Section 3).
- Large downloads / system installs (e.g. `ollama pull`); ask first with name + size.
- Credentials or money. **Never** create, request, or paste keys. Quentin puts them in `.env`.
- Being > ~90 min behind after applying the Cut Order.
- Content only Quentin has (Twisted Traction hook story -> `[QUENTIN: ...]` placeholder).
- Final go/no-go on live model vs offline cache for the presentation.
One short message: decision needed, recommended option, default if no answer in 20 min. Keep working meanwhile.

## 2.4 Progress logging
After every phase append to PROGRESS.md:
```
## [time] Phase N: <name>: DONE | PARTIAL | BLOCKED
- Built: ...
- Verified: <which acceptance checks passed>
- Cuts/decisions: ...
- Next: ...
```
Commit at the end of every phase: `phase N: <summary>`. Chat status updates 3-5 lines.

## 2.5 Engineering principles
- **The LLM never produces a number that goes into cost or price.** Math is deterministic Python. The model only extracts, flags, drafts, explains.
- Local by default (Ollama + local embeddings); provider switchable via config.
- Demo reliability beats cleverness: every model call cached; offline mode reads only cache (falls back to mock fixtures).
- Keep it simple: plain functions, pandas DataFrames, one app state dict. No over-engineering, no async.
- Verify, don't assume: run code, tests, and Streamlit `AppTest` before calling a phase done.

## 2.6 Secrets & public repo (NON-NEGOTIABLE)
- Repo is **PUBLIC**. Never push secrets.
- `.gitignore` covers `.env`, `.env.*` (except `.env.example`), keys, venv, secrets.toml.
- `.env.example` has empty values only. Real `.env` is Quentin's, never staged.
- Hooks: `scripts/pre-commit` and `scripts/pre-push` (copied into `.git/hooks/`) run `scripts/secret_scan.py`.
  The scanner uses key-shaped regexes (e.g. `sk-` + 16 key chars) so docs that merely mention a prefix don't block.
- Review `git status` before `git add`. Never `git add -f` an ignored file.
- Before every push: `git diff --cached --stat` + `python3 scripts/secret_scan.py --range origin/<branch>..HEAD`. On a match: stop, don't push, fix, tell Quentin.
- Never print secret values anywhere (logs, PROGRESS.md, code, tests, cache, chat). Read keys only via `os.getenv`.
- `cache/llm/` may be committed; it must contain only prompts/outputs about synthetic data. Verify before committing.
- If a secret is committed: do not push, tell Quentin. If pushed: tell him to rotate the key immediately.
- All data synthetic, all names fictional (say so in README). No personal info about Quentin, teammate, Twisted Traction financials, or real customers.

## Locked decisions (do not change without asking)
Boone Creek Fabrication (fictional ~40-person Iowa fab shop); no CAD parsing; cost = BOM + routing x burdened rates;
S/M/L is an output; numbers from tables, vectors only for text; evidence-weighted ledger; Gate 1 (estimator BOM/routing)
+ Gate 2 (manager price), overrides need reasons and are saved to memory; local-first (Ollama); synthetic data labeled; Streamlit UI.
