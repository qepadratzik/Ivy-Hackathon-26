# Assumptions & tuned constants

Everything here is **illustrative**: synthetic data for a fictional shop (Boone Creek Fabrication). All constants
live in `qm/config.py` unless noted; change them there. The values are tunable priors, not fitted estimates.
With a real shop's history, the authorities and half-lives would be checked against estimate-vs-actual error.

## Company, data, dates
| Item | Value |
|---|---|
| Shop | Boone Creek Fabrication (fictional), ~40 people, central Iowa, weldments/brackets/guards/frames/tube assemblies |
| "Today" for all recency math | 2026-09-30 (`config.AS_OF`, fixed so tests are reproducible) |
| History | 150 seeded random jobs + 8 hero jobs, Oct 2024 to Sep 2026, seed 42 (`qm/data_gen.py`) |
| Customers (all fictional) | Prairie Implement Co. (OEM, price-sensitive), Cedar Valley Equipment (OEM), Hawkeye Loader Works (OEM), North Star Ag Systems (tier 1), Raccoon River Attachments (aftermarket), Big Sioux Trailer (tier 1, new 2026), Loess Hills Machinery (aftermarket) |
| Win rate in history | ~56% |
| Missing actuals | exactly 10% of completed won jobs (random, not heroes) |
| Noise | 3-5 material aliases per grade, 4 near-duplicate part numbers, 3 missing finishes, typos in ~15% of emails |
| Cost/price units | `est_cost` and `quoted_price` are **per unit**; setup hours are per lot (release) |

### Hero jobs (fixed so the demo RFQs retrieve the intended analogs)
| Job | What | Why it exists |
|---|---|---|
| J-0918 | CVE-HB-4410 **Rev A**, Cedar Valley, cosmetic, first run **with** a fixture line, won, actuals | earlier rev of RFQ A's part |
| J-1042 | CVE-HB-4410 **Rev B**, Cedar Valley, A36 3/8", qty 200, cosmetic, won, full actuals (weld 0.46 est → 0.62 act) | **RFQ A's analog** |
| J-0987 | HLW-HB-2207, Hawkeye, A36 3/8", qty 150, cosmetic, won, full actuals | second cosmetic hitch bracket |
| J-1077 | PIC-HB-5120, Prairie, cosmetic, **lost** at 1.38× | quote-only evidence |
| J-1103 | NSA-HB-118, North Star, first run, **no** fixture line, fit/tack setup 2.0 est → 4.4 act, debrief "nobody quoted a fixture" | **RFQ B's analog** |
| J-0842, J-0955, J-1118 | LHM-MP-0620 mounting plate, Loess Hills, 1/2" A36, three won runs with actuals | **RFQ C's analog** (J-1118) |

### Seeded patterns (verified by `tests/test_data.py`, seed 42)
| ID | Rule | Measured |
|---|---|---|
| P1 | weld run act/est ~ N(1.35, 0.08) if cosmetic, else N(1.02, 0.07) | 1.38× (n=16) vs 1.03× |
| P2 | fit/tack setup act/est ~ U(1.6, 2.2) if first run and no fixture line; ~55% get a fixture debrief | 1.94× (n=14) |
| P3 | 30% of completed press-brake jobs on plate ≥ 0.5" get an NCR; those run ×1.25-1.45 | 31% (n=13) |
| P4 | Prairie: P(win) = logistic(-40 × (ratio - 1.265)); others logistic(-12 × (ratio - 1.38/1.42)) | 94% win < 1.25× vs 6% ≥ 1.30× |
| P5 | steel index: +5% over 18 months, then a tariff jump to +12..19% | last 6 months +14.6% vs first 6 |

## Shop model
| Item | Value |
|---|---|
| Burdened rates $/hr (illustrative) | laser 150, press_brake 95, saw 70, machining 110, fit_tack 80, weld 85, grind 70, inspect_pack 75 |
| Fixture build (one-time line) | 6.0 hr shop default at the fit_tack rate ($80), amortized over the **order** quantity |
| Powder coat vendor table | small $4.50, medium $8.75, large $26.00 per part (dated 2026-07-01); zinc $2.10/$4.25/$12.00 |
| Steel base prices (Oct 2024, $/lb) | A36 0.74, A500 0.98, 1018 1.05 (all follow the steel index); 304 SS 3.10, 5052 Al 3.45 (flat ±2%) |
| Supplier quote cadence | A36 and A500 weekly, 1018 biweekly, SS/Al monthly; 3 fictional steel suppliers (±2-3%) |
| Lead time | min days = ceil(first-release shop hours / 6 hr/day) work days → ×7/5 calendar + 5 material + 5 queue + 8 powder coat |

## Retrieval (similar past jobs)
`sim = 0.5 × embed_cos(description) + 0.5 × structured_sim`

`structured_sim = 0.32·same_family + 0.16·same_material + 0.16·thickness_closeness + 0.16·qty_bucket_match + 0.20·same_weld_class`

- HANDOFF weights (0.4/0.2/0.2/0.2) scaled by 0.8 to add **weld class**, because cosmetic vs standard weld is the
  largest labor driver in this history (P1). Without it, RFQ B (standard weld) matched a cosmetic job.
- thickness_closeness = 1 − |t1 − t2| / max(t1, t2); qty buckets ≤25 / 26-100 / 101-300 / >300 (adjacent bucket = 0.5).
- Candidates are filtered to the same part family, and to the same material family (carbon/stainless/aluminum) if ≥ 5 remain.
- Analog = most similar **won job with actuals**, score = sim × (0.85 + 0.15 × labor recency decay).
- Embeddings: Chroma's default local model (all-MiniLM-L6-v2, ONNX, ~80 MB, downloaded once). Automatic
  TF-IDF fallback if unavailable; the tests check both backends pick the same analogs.
- Notes (debriefs/NCRs/overrides): `sim = 0.5 × embed_cos + 0.5 × (0.6·same_family + 0.4·same_work_center)`.

## Evidence weighting (HANDOFF 7.4, implemented exactly)
| Constant | Value |
|---|---|
| Authority | actual 1.0 · supplier quote 1.0 · note / override / pattern 0.8 · past quote (estimate) 0.6 · shop default 0.3 |
| Half-lives (days) | material price 30 · labor/setup/run hours 540 · notes & overrides 365 · purchased parts 180 · outside processing 180 |
| Similarity threshold | 0.35 (rows below are shown but score 0) |
| Evidence per line | top 5 similar jobs having that op/item + shop default + ≤ 3 notes + ≤ 3 override notes + patterns; material = 12 newest supplier quotes |
| Confidence | min(1, Σscore / 3) × (1 − min(1, CV)) |
| Spread | 0.10 + 0.40 × (1 − confidence), clamped ≤ 0.60 |
| Chips | green ≥ 0.70 · yellow 0.40-0.70 · red < 0.40 |
| Stale material | newest quote > 30 days → flag "re-quote material or shorten quote validity to 15 days" + escalation contingency = max(0, monthly trend of the last 180 days) × age/30.44 |

Decisions on top of 7.4 (all deterministic, no LLM numbers):
- A job contributes its **actual** hours if recorded, otherwise its estimate (as a "past quote").
- **Pattern rows** = estimate-level base × data-derived ratio. The estimate-level base is the weighted mean of the
  similar jobs' *estimates* + shop default, because the ratio is actual/estimate (applying it to actuals would double count).
- **Debrief/NCR rows** = estimate-level base × that note's own job act/est ratio for the line; notes whose job has
  no actuals are shown as context only. Notes only count when their job matches the RFQ on the line's driver
  (weld/grind: cosmetic match; fit/tack setup: first-run + fixture match; press brake: ≥ 0.5" plate match).
- **Override rows (memory)** = this line's structured base + (new − old) from the earlier override. An RFQ never
  counts its own saved override (its Gate 1 value is already locked).
- **Gate 1 edits** lock the line value; confidence is still computed from all evidence around the locked value,
  so an override that history doesn't support shows up yellow/red (honest, and the reason is saved).

## Patterns (S6)
Shown only if n ≥ 3 and the RFQ matches the condition: P1 cosmetic weld → weld run; P2 first-run weldment → fit/tack
setup; P3 plate ≥ 0.5" → press brake run (expected multiplier = NCR rate × NCR ratio + (1 − rate) × normal ratio);
P4 customer with ≥ 3 quotes on each side of 1.25× whose win rate is ≥ 70% below and ≤ 25% at ≥ 1.30× (pricing
callout only; the win model already carries it). P5 (steel trend) drives the stale-material escalation.

## Gaps (S2)
| Gap | Default | If assumed |
|---|---|---|
| Quantity conflict (email vs spec sheet) | ask | quote the email quantity, show the other as a price break; +5% on setup lines |
| Material / thickness conflict | ask | quote per the email; +8% on material lines |
| Finish conflict | ask | quote per the email; +5% on outside lines |
| Powder coat color missing | ask | assume black (stock); +3% on outside lines |
| Required field missing or low confidence (quote not found) | ask | analog value; +5% (material +8%) |
| Due date < minimum lead time | ask | accept with overtime; +6% on labor lines |
The LLM drafts one clarification email covering every "ask" item (template fallback).

## Uncertainty (S7)
- Each line ~ Triangular(low, value, high) × its multiplier ($/unit); 2,000 samples; per-line seeded streams so
  unrelated edits don't reshuffle other lines.
- **Steel lines share one random stream** (one market shock, perfectly correlated). All other lines are
  **independent**; this understates correlated risk (e.g. every labor op running long on a bad week), so real
  bands would be somewhat wider.
- Gap contingencies and material escalation are added as fixed dollars per unit.

## Pricing (S8)
| Item | Value |
|---|---|
| Win model | LogisticRegression (C = 1.0) on 158 past quotes; features: (price/cost − 1.30)/0.10, segment one-hot, is_new_customer, qty bucket one-hot, **customer one-hot** (price sensitivity is customer-specific here, P4) |
| Candidate prices | 1.0-1.8 × P50 (161 points; extended up if the floor would fall off the grid) |
| Risk-adjusted cost | P50 + 0.5 × (P90 − P50): wider uncertainty → more cushion (makes the recommendation move when confidence drops) |
| Capacity | opportunity cost on labor: −10% at 0% load, 0 at 50%, +30% at 100% (linear); floor = minimum margin over risk-adjusted cost: 4% / 10% / 22% / 35% at 0 / 50 / 80 / 100% load |
| Decision | exp_margin = P(win) × (price − decision cost); recommend the peak above the floor; range = ≥ 90% of the peak |
| Expedite | +12% price for 7 days less lead time (illustrative) |
| Quote validity | 30 days; 15 days when any steel quote is > 30 days old |
| Release-size prices | setup lines re-spread over the release size; the one-time fixture stays spread over the order |

Resulting recommended markups on RFQ A's cost: Cedar Valley 1.33×, Hawkeye 1.29×, **Prairie 1.23×** (lowest).

## LLM usage
- Tasks: `intake_extract` (copy text + verbatim quote + confidence), `clarification_email`, `pattern_narration`.
  `evidence_explain` was cut (Cut Order #6): the drawer uses a deterministic sentence instead.
- The model never produces a number used in cost or price. Quote verification: exact match → verified; all words
  present (paraphrase) → verified, confidence capped at medium; otherwise → low confidence → gap.
- Ollama: `/api/chat`, `format` = JSON schema (refs inlined), `stream: false`, `think: false` (falls back to `/no_think`),
  temperature 0.1, timeout 60 s, one retry with the validation error appended, then fixture/template fallback.
- Cache key = sha256(provider, model, task, system prompt + prompt, schema); offline mode also accepts a cache hit
  from another provider for the same prompt, then fixtures, then templates.
