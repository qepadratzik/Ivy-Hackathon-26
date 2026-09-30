# Demo script: Quote Memory (~3.5 minutes of clicks)

**Before you present (30 s, off-stage)**
1. `streamlit run app.py` (Ollama running, cache warmed; see `docs/LOCAL_RUN.md`). Browser at 100-110% zoom, full screen.
2. Sidebar: click **↺ Reset demo state**. Check: RFQ **A · Cedar Valley hitch bracket (main)** selected, *Shop load* 50%,
   *Age our newest material quote* 0, section **1 · Requirements**, *Memory: 0 saved override(s)*.
3. Have `demo/rfqs/RFQ_A.md` open in another tab only as a backup.

Numbers below are what the synthetic data produces today (mock or warmed cache). If the live model is used,
the costs/prices are the same (the model never produces numbers); only the wording of the email/sentences changes.

---

## Beat 1: Customer request → requirements (≈35 s)
**Screen:** Section **1 · Requirements** (already open).

**Click / point:**
- Point at the two cards under **Gaps & conflicts**: *Quantity conflict: email says 250, spec sheet says 200* and
  *Powder coat color not specified*. Point at the due-date line (*slack +3 days: tight but feasible*).
- Scroll a little: the **What we understood** table. Point at one "📧 “…”" quote and a green **high** chip.
- Expand **✉️ Draft clarification email**: one email, both questions.
- On the color card click **Assume & quote**.

**Say:** "An RFQ lands. Our local model reads the email and the customer's spec sheet, but it only *copies* text:
every field has to quote the email, and Python does the conversions. It caught a real conflict: 250 in the email,
200 on the spec sheet. For the color we don't need to wait: we assume black, print that on the quote, and carry a
3% contingency on the coating line."

**Watch:** the blue **What just changed** banner: *P50 $156.35 → $156.62 (+0.2%) … because gap 'finish color'
switched ask → assume.* "Every decision ripples downstream, and the banner shows you exactly how."

## Beat 2: Approach + Gate 1 (≈45 s)
**Click:** section **2 · Approach (Gate 1)**.

**Point:** *Closest past job: J-1042 · CVE-HB-4410 Rev B · won · actual hours on file · similarity 0.97*.
In **What's different**: *New revision of a part we built: check that the fixture and programs still fit*,
*Setup spread over 50 pcs instead of 200: +$6.34/unit*, *A36 price +14% since the analog was quoted*.

**Click:** **Quick adjust a line** is already on *Fit & tack: setup (hr/lot)* with **+6.00** → **Apply**.
Type in **Why?**: `new fixture needed: Rev C moved the hole pattern` → **✓ Approve Gate 1**.
(Optional, +5 s: click Approve *before* typing the reason to show it refuses.)

**Say:** "This is where human judgment stays. The system proposed last run's routing, and it flagged the revision
change. Our estimator knows Rev C moved the holes, so the old fixture won't fit: six more hours of fit-up. He has
to say why, and that reason goes into memory."

**Watch:** banner *P50 $156.62 → $166.01 (+6.0%) · recommended price $209.08 → $221.62 · Fit & tack: setup
🟢0.94 → 🔴0.36*. "The system takes his number, but it's honest: history doesn't back it yet, so confidence is red."

## Beat 3: The ledger: provenance on every number (≈30 s)
**Click:** section **3 · Cost ledger**. The drawer on the right already shows **Weld: run** (0.629 hr/unit, 🟢0.80).

**Point:** the evidence table: **Pattern adjustment · P1**, **Past job (actual) · J-1042 = 0.62**, J-0964, J-0918,
shop-floor debriefs, past quotes, shop default. Each score = similarity × authority × recency.
Expand **Past job (actual) · J-1042** to show the original record. Point at the blue **P1** callout below the table:
*cosmetic-weld jobs ran 1.38× their quoted weld run hours (n=16)*.

**Say:** "Click any number and you see exactly where it came from. Our old quotes said about 0.46 hours for this
weld; the actuals came in at 0.62. Cosmetic welds always run long here. That used to live in one estimator's head.
Now it's a pattern the system finds and applies, with the receipts."

## Beat 4: Stale steel price → chain reaction (≈25 s)
**Click:** sidebar slider **Age our newest material quote by (days)** → **90**.

**Watch:** banner *A36 plate 🟢0.97 → 🔴0.21, A500 tube 🟢0.97 → 🔴0.18 · band 7.9% → 9.9% · price $221.62 →
$222.74 · quote validity 30 → 15 days*. In the ledger the steel lines show ⚠ *Newest A36 quote is 95 days old:
re-quote material or shorten quote validity to 15 days.*

**Say:** "What if our steel quote were three months old? Material evidence decays with a 30-day half-life, so
confidence collapses, the cost band widens, the price picks up a steel-trend escalation, and the quote validity
drops to 15 days automatically. That's the chain reaction: one input, every downstream number moves."

## Beat 5: Price + Gate 2 + quote (≈40 s)
**Click:** section **5 · Price (Gate 2)**.

**Point:** the blue expected-margin curve, dotted win-chance line, green recommended band, red floor.
*Recommended $222.74 (1.33× P50, win chance 83%)*. The decision-cost table: P50 + risk cushion (half the gap to P90)
+ capacity cost.
(Optional, +10 s: drag **Shop load** to **90%** → price $222.74 → $230.25: "when we're slammed, we price for it.")

**Click:** **✓ Approve Gate 2** (price is pre-filled with the recommendation). Then section **6 · Quote**.

**Say:** "The model never picks the price. Win chance comes from our own quote history, and wider uncertainty
means a bigger cushion. The owner makes the call at Gate 2; outside the range he'd have to give a reason. And here's
the customer-ready quote: price per release size, lead time, 15-day validity because of the steel, every
assumption printed, and the open quantity question flagged."

## Beat 6: It learns (≈30 s)
**Click:** sidebar slider **Age … material quote** back to **0**. Then sidebar **B · Hawkeye hitch bracket (first run)**,
section **3 · Cost ledger**, drawer **Where this number came from** → **Fit & tack: setup**.

**Point:** banner *memory now holds 1 saved override(s): this quote learned from one · Fit & tack: setup
🟡0.63 → 🟡0.45 · P50 $138.16 → $138.99*. In the drawer: green **🧠 Learned from an earlier quote (M-0001):
… Reason: new fixture needed: Rev C moved the hole pattern**. Also the **P2** pattern row and the
**Fixture build (one-time)** line the first-run rule added.

**Say:** "Different customer, different part number, a first run. The note our estimator wrote ten minutes ago is now
evidence on this quote, weighted like any other source, with its reason attached. That's how tacit knowledge stops
walking out the door when he retires."

## Beat 7: Fast-track (≈15 s)
**Click:** sidebar **C · Loess Hills mounting plate (repeat)**, section **1 · Requirements**.

**Point:** green badge **S · Fast-track** *(repeat of LHM-MP-0620, 3 prior runs; standard tolerance; qty 40 ≤ 50)*,
no gaps, KPI strip *🟢8 🟡0 🔴0*, *$43.31 P50 → $56.30 recommended*.

**Say:** "Not every RFQ needs the senior estimator. A clean repeat order is fast-tracked: all green, priced in a
minute, and his time goes to the jobs that need judgment."

---

## 60-second fallback (if time is cut or something misbehaves)
1. (10 s) A · Requirements: "The model copies text with quotes; it caught 250 vs 200 and the missing color."
2. (15 s) Section 2: Quick adjust **+6** on *Fit & tack: setup*, reason `new fixture needed`, **Approve Gate 1** →
   point at the banner: "+6% cost, confidence red, reason saved."
3. (15 s) Section 3: weld drawer: "every number shows its sources; P1 says cosmetic welds run 38% over."
4. (10 s) Slide material age to 90: "stale steel → red, wider band, 15-day validity."
5. (10 s) Switch to B, drawer *Fit & tack: setup*: "🧠 it learned from the override."

If the app itself fails: play the backup screen recording (Quentin records it Thursday morning), or show the
screenshots in `docs/screens/` in order.

## Recovery moves
- Wrong state / confusing banner → sidebar **↺ Reset demo state**, then redo from Beat 1 (takes ~2 s).
- A slow model call → you're on a pasted RFQ or the cache isn't warmed; switch `.env` to `DEMO_MODE=offline`
  (after warming) or `MODEL_PROVIDER=mock` and restart Streamlit.
- Gate 1 approved by mistake → **Re-open Gate 1** (edits are kept).

## Talking points to have ready
- "The LLM never produces a cost or a price." Extraction, one email, one-line explanations. All math is Python.
- "Runs on one PC." Local model (qwen3:8b via Ollama), local embeddings; customer prints and emails never leave the building.
- "Works from what the shop already has": past jobs, BOM/routing with estimated vs actual hours, debrief notes,
  supplier quotes, exported to CSV. No ERP replacement.
- "Humans at two gates" (approach, price), and every override needs a reason that becomes memory.
- "Honest uncertainty": confidence is weight of evidence × agreement; ranges widen when evidence is thin or stale.
- Synthetic data, fictional names; the weights are tunable priors (see `docs/assumptions.md`).
