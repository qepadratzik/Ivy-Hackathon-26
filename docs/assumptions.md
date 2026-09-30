# Assumptions & tuned constants

Everything here is **illustrative**: synthetic data for a fictional shop (Boone Creek Fabrication). All constants
live in `qm/config.py` unless noted; change them there. The values are tunable priors, not fitted estimates.
With a real shop's history, the authorities and half-lives would be checked against estimate-vs-actual error.
The shop and the app were simplified in the final week; see "Simplification (final week)" at the end.

## Company, data, dates
| Item | Value |
|---|---|
| Shop | Boone Creek Fabrication (fictional), ~40 people, central Iowa, weldments/brackets/guards/frames/tube assemblies |
| Scope | 5 job types (hitch bracket, guard, frame, mounting plate, tube assembly), 3 materials (A36 steel plate, A500 steel tube, 5052 aluminum sheet), 5 in-house processes plus 1 outside process (powder coat) |
| "Today" for all recency math | 2026-09-30 (`config.AS_OF`, fixed so tests are reproducible) |
| History | 158 seeded jobs (150 random + 8 hero jobs), Oct 2024 to Sep 2026, seed 42 (`qm/data_gen.py`) |
| Customers (all fictional) | Prairie Implement Co. (OEM, price-sensitive), Cedar Valley Equipment (OEM), Hawkeye Loader Works (OEM), North Star Ag Systems (tier 1), Raccoon River Attachments (aftermarket), Big Sioux Trailer (tier 1, new 2026), Loess Hills Machinery (aftermarket) |
| Win rate in history | ~61% |
| Missing actuals | exactly 10% of completed won jobs (random, not heroes) |
| Noise | several material aliases per grade (A36 has 5, A500 has 4, 5052 has 3), 4 near-duplicate part numbers, 3 missing finishes, typos in ~15% of emails |
| Cost/price units | `est_cost` and `quoted_price` are **per unit**; setup hours are per lot (release) |

### Hero jobs (fixed so the demo RFQs retrieve the intended closest past jobs)
| Job | What | Why it exists |
|---|---|---|
| J-0918 | CVE-HB-4410 **Rev A**, Cedar Valley, cosmetic, first run **with** a fixture line, won, actuals | earlier rev of RFQ A's part |
| J-1042 | CVE-HB-4410 **Rev B**, Cedar Valley, A36 3/8", qty 200, cosmetic, won, full actuals (weld setup 2.5 est → 2.6 act, weld run 0.70 est → 0.94 act) | **RFQ A's closest past job** |
| J-0987 | HLW-HB-2207, Hawkeye, A36 3/8", qty 150, cosmetic, won, full actuals | second cosmetic hitch bracket |
| J-1077 | PIC-HB-5120, Prairie, cosmetic, **lost** at 1.38×, no actuals | quote-only evidence |
| J-1103 | NSA-HB-118, North Star, first run, **no** fixture line, weld setup 2.5 est → 5.3 act, debrief "nobody quoted a fixture" | **RFQ B's closest past job** |
| J-0842, J-0955, J-1118 | LHM-MP-0620 mounting plate, Loess Hills, 1/2" A36, three won runs with actuals | **RFQ C's closest past job** (J-1118) |

### Seeded patterns (verified by `tests/test_data.py`, seed 42)
| ID | Rule | Measured |
|---|---|---|
| P1 | weld run act/est ~ N(1.35, 0.08) if cosmetic, else N(1.02, 0.07) | 1.35× (n=20) vs 1.02× |
| P2 | weld setup (fit-up included) act/est ~ U(1.6, 2.2) if first run and no fixture line; ~55% get a fixture debrief | 1.90× (n=21; 14 shop notes mention building a fixture) |
| P3 | 30% of completed Bend (press brake) jobs on plate ≥ 0.5" get an NCR; those run ×1.25-1.45 | 30% (n=20) |
| P4 | Prairie: P(win) = logistic(-40 × (ratio - 1.265)); others logistic(-12 × (ratio - 1.38/1.42)) | 100% win < 1.25× (n=15) vs 0% ≥ 1.30× (n=14) |
| P5 | steel index: +5% over 18 months, then a tariff jump to +12..19% | A36 last 6 months about +14% vs first 6 |

## Shop model
| Item | Value |
|---|---|
| Burdened rates $/hr (illustrative) | Cut 120, Bend (press brake) 95, Fit & weld 85 (fit-up, tack, weld and clean-up in one process), Drill & tap (machining) 110, Inspect & pack 75 |
| Fixture build (one-time line) | 6.0 hr shop default at the weld rate ($85/hr = $510), spread over the **order** quantity |
| Outside process | Powder coat only. Vendor table small $4.50, medium $8.75, large $26.00 per part (dated 2026-07-01), 8 days vendor turnaround. Finish is powder coat or none |
| Material base prices (Oct 2024, $/lb) | A36 0.74, A500 0.98 (both follow the steel index); 5052 aluminum 3.45 (flat ±2%) |
| Supplier quote cadence | A36 and A500 weekly, 5052 monthly; 3 fictional steel suppliers (±2-3%) |
| Aluminum in the history | 1 of 158 jobs, on purpose: an aluminum RFQ shows thin evidence and Low confidence, which demonstrates the honest-uncertainty behavior |
| Lead time | min days = ceil(first-release shop hours / 6 hr/day) work days → ×7/5 calendar + 5 material + 5 queue + 8 powder coat |

## Retrieval (similar past jobs)
`sim = 0.5 × embed_cos(description) + 0.5 × structured_sim`

`structured_sim = 0.32·same_family + 0.16·same_material + 0.16·thickness_closeness + 0.16·qty_bucket_match + 0.20·same_weld_class`

- HANDOFF weights (0.4/0.2/0.2/0.2) scaled by 0.8 to add **weld class**, because cosmetic vs standard weld is the
  largest labor driver in this history (P1). Without it, RFQ B (standard weld) matched a cosmetic job.
- thickness_closeness = 1 − |t1 − t2| / max(t1, t2); qty buckets ≤25 / 26-100 / 101-300 / >300 (adjacent bucket = 0.5).
- Candidates are filtered to the same part family, and to the same material family (steel = A36 and A500, aluminum =
  5052) if ≥ 5 remain.
- Closest past job (the engine's "analog") = most similar **won job with actuals**, score = sim × (0.85 + 0.15 × labor recency decay).
- Embeddings: Chroma's default local model (all-MiniLM-L6-v2, ONNX, ~80 MB, downloaded once). Automatic
  TF-IDF fallback if unavailable; the tests check both backends pick the same closest past jobs.
- Notes (debriefs, NCRs, estimator notes): `sim = 0.5 × embed_cos + 0.5 × (0.6·same_family + 0.4·same_work_center)`.

## Evidence weighting (HANDOFF 7.4, implemented exactly)
| Constant | Value |
|---|---|
| Authority | actual 1.0 · supplier quote 1.0 · note / estimator note (override) / pattern 0.8 · past quote (estimate) 0.6 · shop default 0.3 |
| Half-lives (days) | material price 30 · labor/setup/run hours 540 · notes & estimator notes 365 · purchased parts 365 · outside processing 365 |
| Similarity threshold | 0.35 (rows below are shown but score 0) |
| Evidence per line | top 6 similar jobs having that op/item + shop default + ≤ 3 notes + ≤ 3 estimator notes + patterns; material = 12 newest supplier quotes |
| Confidence | min(1, Σscore / 3) × (1 − min(1, CV)) |
| Spread | 0.10 + 0.40 × (1 − confidence), clamped ≤ 0.60 |
| Chips | green ≥ 0.70 · yellow 0.40-0.70 · red < 0.40 (shown in the app as High / Medium / Low confidence) |
| Stale material | newest quote > 30 days → flag "re-quote material or shorten quote validity to 15 days" + escalation contingency = max(0, monthly trend of the last 180 days) × age/30.44 |

Decisions on top of 7.4 (all deterministic, no LLM numbers):
- A job contributes its **actual** hours if recorded, otherwise its estimate (as a "past quote").
- **Pattern rows** = estimate-level base × data-derived ratio. The estimate-level base is the weighted mean of the
  similar jobs' *estimates* + shop default, because the ratio is actual/estimate (applying it to actuals would double count).
- **Debrief/NCR rows** = estimate-level base × that note's own job act/est ratio for the line; notes whose job has
  no actuals are shown as context only. Notes only count when their job matches the RFQ on the line's driver
  (weld run: cosmetic match; weld setup and fixture: first-run + fixture match; Bend: ≥ 0.5" plate match).
- **Estimator-note rows (the shop notebook; `override` in the engine)** = this line's structured base + (new − old)
  from the earlier edit. An RFQ never counts its own saved note (its Checkpoint 1 value is already locked).
- **Checkpoint 1 edits** lock the line value; confidence is still computed from all evidence around the locked value,
  so an edit that history doesn't support shows up Low/Medium (honest, and the reason is saved).

## Patterns (S6)
Shown only if n ≥ 3 and the RFQ matches the condition: P1 cosmetic weld → weld run; P2 first-run weldment → weld
setup; P3 plate ≥ 0.5" → Bend run (expected multiplier = NCR rate × NCR ratio + (1 − rate) × normal ratio);
P4 customer with ≥ 3 quotes on each side of 1.25× whose win rate is ≥ 70% below and ≤ 25% at ≥ 1.30× (pricing
callout only; the win model already carries it). P5 (steel trend) drives the stale-material escalation.
In the app these appear as "Lessons from our history".

## Gaps (S2)
| Gap | Default | If assumed |
|---|---|---|
| Quantity conflict (email vs spec sheet) | ask | quote the email quantity, show the other as a price break; +5% on setup lines |
| Material / thickness conflict | ask | quote per the email; +8% on material lines |
| Finish conflict | ask | quote per the email; +5% on outside lines |
| Powder coat color missing | ask | assume black (stock); +3% on outside lines |
| Required field missing or low confidence (quote not found) | ask | closest-past-job value; +5% (material +8%) |
| Due date < minimum lead time | ask | accept with overtime; +6% on labor lines |
The LLM drafts one clarification email covering every "ask" item (template fallback).

## Uncertainty (S7)
- Each line ~ Triangular(low, value, high) × its multiplier ($/unit); 2,000 samples; per-line seeded streams so
  unrelated edits don't reshuffle other lines.
- Gaussian copula: **steel lines share one market shock** (perfectly correlated); **labor lines share a "bad week on
  the floor" factor** with pairwise correlation 0.5 (`config.LABOR_CORRELATION`); purchased and outside lines are
  independent. The correlations are assumed priors, not fitted.
- Gap contingencies and material escalation are added as fixed dollars per unit.
- Plain-language names in the app: P10 = "low end", P50 = "typical cost", P90 = "high end"; "very likely between $A and
  $B" is the P10 to P90 range. The histogram and the raw Monte Carlo view sit behind the "Show the details" switch.

## Pricing (S8)
| Item | Value |
|---|---|
| Win model | LogisticRegression (C = 1.0) on 158 past quotes; features: (price/cost − 1.30)/0.10, segment one-hot, is_new_customer, qty bucket one-hot, **customer one-hot** (price sensitivity is customer-specific here, P4) |
| Candidate prices | 1.0-1.8 × P50 (161 points; extended up if the floor would fall off the grid) |
| Risk-adjusted cost | P50 + 0.5 × (P90 − P50): wider uncertainty → more cushion (makes the suggested price move when confidence drops). Shown in the app as the "planning cost" (typical cost + a safety cushion) |
| Capacity | Engine: opportunity cost on labor −10% at 0% load, 0 at 50%, +30% at 100% (linear); floor = minimum margin over risk-adjusted cost 4% / 10% / 22% / 35% at 0 / 50 / 80 / 100% load. **The app fixes load at the neutral 50%** (no opportunity cost, 10% floor); the shop-load slider is not shown |
| Decision | exp_margin = P(win) × (price − decision cost); recommend the peak above the floor; range = prices with ≥ 90% of the peak |
| Three choices (app) | Lower price = low end of the range, Recommended price = the peak, Higher price = high end of the range. Each shows chance of winning ("about 8 in 10"), profit per part if we win (price − planning cost) and average profit (chance × profit) |
| Expedite | +12% price for 7 days less lead time (illustrative). Engine only; not offered in the app |
| Quote validity | 30 days; 15 days when any steel quote is > 30 days old |
| Release-size prices | setup lines re-spread over the release size; the one-time fixture stays spread over the order |

Resulting suggested markups on RFQ A's typical cost (same cost, different customer): Cedar Valley 1.31×, Hawkeye 1.32×,
**Prairie 1.26×** (lowest of these three).

## LLM usage
- Tasks: `intake_extract` (copy text + verbatim quote + confidence), `clarification_email`, `pattern_narration`.
  `evidence_explain` was cut (Cut Order #6): the evidence panel uses a deterministic sentence instead.
- The model never produces a number used in cost or price. Quote verification: exact match → verified; all words
  present (paraphrase) → verified, confidence capped at medium; otherwise → low confidence → gap.
- Where the model runs: the shop design is local-first (Ollama `qwen3:8b` + local embeddings). The competition demo
  uses a hosted model (Claude Haiku 4.5, `anthropic` provider) presented from a warmed cache; the provider is one config
  line and the cost and price math is identical either way.
- Ollama: `/api/chat`, `format` = JSON schema (refs inlined), `stream: false`, `think: false` (falls back to `/no_think`),
  temperature 0.1, timeout 60 s, one retry with the validation error appended, then fixture/template fallback.
- Cache key = sha256(provider, model, task, system prompt + prompt, schema); offline mode also accepts a cache hit
  from another provider for the same prompt, then fixtures, then templates.

## Changes after the red-team review (docs/review.md)
- **Revision change → one-time fixture check line.** When the RFQ is a new revision of a part we built and the closest
  past job had no fixture line, the plan adds *Fixture build (one-time)* at **0 hr**, shown as a question ("Does the old
  fixture still fit the new revision?") with Low confidence until answered. Yes keeps it at 0; No fills the 6.0 hr shop
  default (editable), and a reason is required. The reason is saved to the shop notebook as an estimator note.
  One-time lines are spread over the **order** quantity, never per release.
- **Estimator-note memory on one-time lines** carries the absolute value (e.g. "a new fixture took 6 hr"); on per-release /
  per-unit lines it carries the delta (new − old) applied to the next quote's evidence base.
- **P2 with a fixture line**: when the quote already carries a fixture line, P2 becomes an explanation on that line
  (no numeric row), and "no fixture was quoted" debriefs no longer inflate weld setup (no double count). If the
  estimator removes the fixture line, P2 goes back onto weld setup as a ×1.90 pattern row.
- **Not enough information to price**: if the closest past job is below the 0.35 similarity bar, or 3+ essentials had
  to be assumed from it, the quote says NOT PRICED and the price cannot be approved (Checkpoint 2 is blocked). Missing
  essentials are otherwise filled from the closest past job and listed as assumptions/gaps.
- **"No welding"** in the RFQ removes the Fit & weld and fixture steps from the plan and the part is not treated as a
  weldment. Tube assemblies are priced on A500 tube when the RFQ mentions tube.
- **Stale Checkpoint 2**: an approved price is invalidated if the typical cost (P50) later moves more than 0.5%, the price
  falls below the new floor, or Checkpoint 1 is re-opened.
- **Quote**: unit price by release size (release, 2× release, order total), a separate line for the conflicting total
  (e.g. 200 pcs), and a "Setup & tooling" block (setup per release, one-time fixture) as buyers ask.
- **Pasted RFQs** draft the clarification email from the template instantly; the model drafts it only on request.

## Simplification (final week)
Why: a 15-20 minute slot and non-technical presenters and judges. A smaller shop and plainer screens are easier to
demo and to explain. The method (evidence scores, confidence, ranges, checkpoints, notebook) does not depend on how
many materials, processes or job types there are; adding a process is one entry in `config.WORK_CENTERS` (plus its label).

| What changed | Before | Now |
|---|---|---|
| Materials | A36, A500, 1018 steel, 304 stainless, 5052 aluminum | A36, A500, 5052 aluminum only (1018 and 304 stainless removed) |
| In-house processes | 8 (laser, press brake, saw, machining, fit/tack, weld, grind, inspect/pack) | 5 (Cut, Bend, Fit & weld, Drill & tap, Inspect & pack); laser and saw merged into Cut; fit-up and grind folded into Fit & weld |
| Outside process | powder coat and zinc plating | powder coat only (zinc plating removed) |
| Fixture rate | fit/tack rate ($80/hr, $480) | weld rate ($85/hr, $510) |
| Half-lives, purchased parts and outside processing | 180 days | 365 days |
| Similar jobs per evidence line | 5 | 6 |
| Screens | six technical sections (Requirements, Approach, Cost ledger, Risk, Price, Quote) under a 7-stage bar | five guided steps: Read the request, Plan the work, Cost it, Set the price, Send the quote |
| Price screen | one recommended price, shop-load slider, expedite option | three choices (Lower, Recommended, Higher), each with chance of winning and profit |
| Words | Gate 1 / Gate 2, memory, analog, ledger, override | Checkpoint 1 / Checkpoint 2, shop notebook, closest past job, cost table, estimator note |

Still in the engine but no longer on the screens: the shop-load (capacity) slider and the expedite option. The raw Monte
Carlo histogram, the evidence score columns and the price curve are not in the default view; they sit behind the "Show the
details" switch. Engine field names such as `gate1_approved` are unchanged in code. The two checkpoints plus a person sending the quote are still the three
human decisions. All weights, authorities, retrieval weights, the win model and the risk-adjusted cost are unchanged.
