# Demo script: Quote Memory (~3.5 minutes of clicks)

**Before you present (30 s, off-stage)**
1. `streamlit run app.py` at least 2 minutes early (the first load builds the embedding index, 6-16 s). Ollama running,
   cache warmed (see `docs/LOCAL_RUN.md`). Browser full screen at 90-100% zoom.
2. Sidebar: click **↺ Reset demo state**. Check: RFQ **A · Cedar Valley hitch bracket (main)** selected, *Shop load* 50%,
   *Age our newest material quote* 0, section **1 · Requirements**, both gap cards on **Ask the customer**,
   *Memory: 0 saved override(s)*. (If anything looks off, press F5 once.)
3. Check the small print says what you'll say: with Ollama the Requirements header reads "extracted by
   ollama:qwen3:8b (cached model output)". In mock mode it says "hand-checked extraction (mock mode)"; then say
   "hand-checked extraction of what the model returns".

Numbers below are what the synthetic data produces (mock, warmed cache or offline). The model never produces a cost
or price, so these numbers are identical with the live model; only the email/sentence wording can change.
Every click also pops a small **🔁 toast** (top right) with the same before → after numbers, so the change is visible
even when you've scrolled down.

---

## Beat 1: Customer request → requirements (≈35 s)
**Screen:** Section **1 · Requirements** (already open).

**Point:**
- **Gaps & conflicts**: *Quantity conflict: email says 250, spec sheet says 200* and *Powder coat color not specified*;
  the due-date line *tight but feasible (slack +3 days)*.
- Scroll: **What we understood** table: a "📧 “…”" source quote and a green **high** chip.
- Expand **✉️ Draft clarification email**: one email, both questions.
- KPI strip: *🟢16 🟡3 🔴1*: one red line already (you'll fix it in Beat 2).

**Click:** on the color card, **Assume & quote**.

**Say:** "An RFQ lands. Our local model reads the email and the customer's spec sheet, but it only *copies* text:
every field has to quote the email, and Python does the conversions. It caught a real conflict, 250 in the email vs.
200 on the spec sheet. For the color we don't need to wait: we assume black, print that on the quote, and carry a 3%
contingency on the coating line."

**Watch:** banner / toast *P50 $156.12 → $156.39 (+0.2%) · price $209.20 → $209.56 … because gap 'finish color'
switched ask → assume.*

## Beat 2: Approach + Gate 1 (≈45 s)
**Click:** section **2 · Approach (Gate 1)**.

**Point:** *Closest past job: J-1042 · CVE-HB-4410 Rev B · won · actual hours on file · similarity 0.97*. In
**What's different**: *New revision of a part we built: check that the fixture and programs still fit*; *First run:
New revision: one-time fixture line added at 0 hr for the estimator to confirm*; *Setup spread over 50 pcs instead of
200: +$6.34/unit*; *A36 price +14% since the analog was quoted*.

**Click:** **Quick adjust a line** is already on *Fixture build (one-time) (hr/order)* with **+6.00** (the shop default
for a new fixture) → **Apply**. Type in **Why?**: `new fixture needed: Rev C moved the hole pattern` → **✓ Approve Gate 1**.
(Optional, +5 s: click Approve *before* typing the reason to show it refuses.)

**Say:** "This is where human judgment stays. The system proposed last run's routing, noticed it's a new revision,
and put a red zero-hour fixture line in front of the estimator: does the old fixture still fit? He knows it doesn't,
because Rev C moved the holes. So it's six hours, **once**, not on every release, and he has to say why. That reason
goes into memory."

**Watch:** banner / toast *P50 $156.39 → $158.30 (+1.2%) · recommended price $209.56 → $212.13 · Fixture build
(one-time) 🔴0.00 → 🟢0.90*. "His number agrees with what past fixture builds cost, so the line goes green."

## Beat 3: The ledger: provenance on every number (≈30 s)
**Click:** section **3 · Cost ledger**. The drawer on the right shows **Weld: run** (0.629 hr/unit, 🟢0.80).

**Point:** the evidence table: **Pattern adjustment · P1**, **Past job (actual) · J-1042 = 0.62**, J-0964, J-0918,
shop-floor debriefs, past quotes, shop default. Score = similarity × authority × recency. Expand
**Past job (actual) · J-1042** for the original record. Scroll to the blue **P1** callout: *On 16 past cosmetic-weld
jobs, welding took 1.38x the quoted hours (standard welds: 1.03x)*.

**Say:** "Click any number and you see exactly where it came from. Our old quotes said about 0.46 hours for this weld;
the actuals came in at 0.62. Cosmetic welds always run long here. That used to live in one estimator's head. Now it's
a pattern the system finds and applies, with the receipts."

## Beat 4: Stale steel price → chain reaction (≈25 s)
**Click:** sidebar slider **Age our newest material quote by (days)** → **90**.

**Watch:** banner *P50 $158.30 → $159.47 · band 11.3% → 12.5% · price $212.13 → $213.68 · **Quote validity: 30 → 15
days** · A36 plate 🟢0.97 → 🔴0.21, A500 tube 🟢0.97 → 🔴0.18*. Under the ledger table: ⚠ *Newest A36 quote is 95 days
old: re-quote material or shorten quote validity to 15 days.*

**Say:** "What if our steel quote were three months old? Material evidence decays with a 30-day half-life, so
confidence collapses, the cost band widens, the price picks up a steel-trend escalation, and the quote validity drops
to 15 days automatically. One input, every downstream number moves."

## Beat 5: Price + Gate 2 + quote (≈40 s)
**Click:** section **5 · Price (Gate 2)**.

**Point:** the blue expected-margin curve, dotted win-chance line, green recommended band, red floor.
*Recommended $213.68 (1.34× P50 cost, win chance 82%)*. The decision-cost table: P50 + risk cushion (half the gap to
P90) + capacity cost.
(Optional, +10 s: drag **Shop load** to **90%** → price $213.68 → $220.06 and the price box follows: "when we're
slammed, we price for it." Drag it back to 50% before Beat 6.)

**Click:** **✓ Approve Gate 2** (the price box holds the recommendation). Then section **6 · Quote**.

**Say:** "The model never picks the price. Win chance comes from our own quote history, and wider uncertainty means a
bigger cushion. The owner makes the call at Gate 2; outside the range he'd need a reason. And here's the quote: unit
price by release size (50: $213.68, 100: $208.11, 250: $204.76), what 200 total would cost, setup and the one-time
$480 fixture listed separately like the buyer asked, 15-day validity because of the steel, and the open quantity
question flagged."

## Beat 6: It learns (≈30 s)
**Click:** sidebar slider **Age … material quote** back to **0**. Then sidebar **B · Hawkeye hitch bracket (first run)**,
section **3 · Cost ledger**. The drawer opens on **Fixture build (one-time)** (6.61 hr/order, 🟢0.90, flags 🧠 P2).

**Point:** banner *because memory now holds 1 saved override(s): this quote learned from one*. In the drawer: green
**🧠 Learned from an earlier quote (M-0001): … Reason: new fixture needed: Rev C moved the hole pattern**, counted as
evidence next to past fixture builds. Below the table, the **P2** callout: *first-run weldments quoted without a
fixture took 1.94x the planned fit-up setup (14 jobs), so this quote carries a one-time fixture line instead.*

**Say:** "Different customer, different part, a first run. The note our estimator wrote ten minutes ago is now
evidence on this quote, weighted like any other source, with its reason attached. That's how tacit knowledge stops
walking out the door when he retires."

## Beat 7: Fast-track (≈15 s)
**Click:** sidebar **C · Loess Hills mounting plate (repeat)**, section **1 · Requirements**.

**Point:** green badge **S · Fast-track** *(repeat of LHM-MP-0620, 3 prior runs; standard tolerance; qty 40 ≤ 50)*,
no gaps, KPI strip *🟢8 🟡0 🔴0*, *$43.41 typical cost → $56.43 recommended*.

**Say:** "Not every RFQ needs the senior estimator. A clean repeat order is fast-tracked: all green, priced in a
minute, and his time goes to the jobs that need judgment."

---

## 60-second fallback (if time is cut or something misbehaves)
1. (10 s) A · Requirements: "The model copies text with quotes; it caught 250 vs 200 and the missing color."
2. (15 s) Section 2: **Apply** (+6 on *Fixture build (one-time)*), reason `new fixture needed`, **Approve Gate 1** →
   "charged once, reason saved, the red line turns green."
3. (15 s) Section 3: weld drawer: "every number shows its sources; P1 says cosmetic welds run 38% over."
4. (10 s) Slide material age to 90: "stale steel → red, wider band, 15-day validity."
5. (10 s) Switch to B, section 3: "🧠 it learned from the override."

If the app itself fails: play the backup screen recording (Quentin records it Thursday morning), or show the
screenshots in `docs/screens/` in order (01 → 12).

## Recovery moves
- Wrong state / confusing banner → sidebar **↺ Reset demo state** (then F5 if anything still looks stale), redo from Beat 1.
- A slow model call → you're on a pasted RFQ or the cache isn't warmed; switch `.env` to `DEMO_MODE=offline`
  (after warming) or `MODEL_PROVIDER=mock` and restart Streamlit.
- Gate 1 approved by mistake → **Re-open Gate 1** (edits are kept; the price approval resets, as it should).
- Don't take a live paste from a judge unless one has been timed on the demo PC; a pasted RFQ with too little
  information shows "not priced" on purpose.

## Talking points to have ready
- "The LLM never produces a cost or a price." Extraction, one email, one-line explanations. All math is Python.
- "Runs on one PC." Local model (qwen3:8b via Ollama), local embeddings; customer prints and emails never leave the building.
- "Works from what the shop already has": past jobs, BOM/routing with estimated vs actual hours, debrief notes,
  supplier quotes, exported to CSV. No ERP replacement.
- "Humans at two gates" (approach, price), and every override needs a reason that becomes memory.
- "Honest uncertainty": confidence is weight of evidence × agreement; ranges widen when evidence is thin or stale;
  steel lines move together and labor lines are partially correlated in the simulation.
- Synthetic data, fictional names; the weights are tunable priors (see `docs/assumptions.md`).
