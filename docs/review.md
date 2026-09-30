# Red-team review: Quote Memory (pre-judging)

**Scope.** I ran my own isolated server (`QM_MEMORY_DIR`/`QM_CHROMA_DIR` in a scratch dir, port 8611, default `mock`
provider). I drove it with Playwright/Chromium at 1600x1000 and 1280x800: first the demo script beat by beat, then a
set of break-it tests. I re-ran the demo path and the blocker on HEAD `77048d0` (the team kept committing while I
tested). Screenshots are in my scratch dir, not the repo. I did not test Ollama live (no model here) or run `pytest`.

## Summary

- **The scripted path is solid.** Every number in `demo/demo_script.md` beats 1-7 matched to the cent: $156.35 →
  $156.62 → $166.01 → $166.85, rec $208.73 → $209.08 → $221.62 → $222.74, green 0.94→red 0.36, A36 0.97→0.21, B
  $138.16 → $138.99, C $43.31 → $56.30, green 8. No exceptions on any path I tried. Every click finished in under 1.2 s.
  A cold start takes 6-16 s.
- **One blocker:** the **Reset demo state** button leaves the browser widgets showing their old values. After a
  rehearsal, the first click of the real demo can jump to RFQ C or do nothing at all. This also breaks the script's own
  recovery move. Workaround: **Reset, then F5**.
- **Biggest credibility risk for an industry panel:** the hero override puts a **one-time fixture on the per-release
  setup line**, so the fixture is charged 5 times. The customer's email also asks for tooling to be listed separately,
  and the quote doesn't do that. On RFQ B the lesson then stacks on top of B's own one-time fixture line.
- **Plausibility with an industry eye (all labeled illustrative):**
  - These look believable for a small Iowa fab shop: burdened rates $70-150/hr; A36 at $0.88/lb and A500 at
    $1.16/lb; about 1.26 labor hr (38 min of weld) for a ~24 lb cosmetic weldment; powder coat at $8.75/part;
    markup 1.33× (about 25% gross margin); 35-day lead time including 8 days of powder coat; +12% for expedite;
    15/30-day validity.
  - An 83% win chance and a ±4% P10-P90 band on a Rev change may look optimistic. Have the answers ready (see #18).

## Findings (by severity)

### BLOCKER

**1. Reset leaves the widgets showing old values. The next click re-applies them.** (`app.py` ~L183-187, `st.session_state.clear()`)
- *Repro A:* rehearse to Beat 7 (RFQ C, section 1). Click Reset.
  - The page shows RFQ-A content, but the sidebar radio still shows **C** selected.
  - Click **Assume & quote** on the color card (Beat 1). The app **jumps to RFQ-C**.
- *Repro B:* assume the color, then Reset.
  - The color card still shows **Assume & quote** selected, but the right column says "Question for the customer"
    (the backend says ask).
  - Clicking **Assume & quote** does nothing: no rerun, **no banner**, and Beat 1 is dead.
- *Repro C:* set Shop load to 90%, then Reset. The slider still shows **90%** while the numbers use 50%. The next
  interaction re-applies 90%.
- *Also:* a stale section radio (e.g. "5 · Price") shows while section 1 content renders.
- *Why it matters:* this is the first thing done on stage, and the script's recovery move ("Wrong state → Reset → redo
  from Beat 1") fails the same way. `tests/test_app.py` can't catch it, because AppTest keeps no browser-side widget
  state.
- *Fix:*
  - Demo-day workaround: **press F5 right after Reset**. Verified: a reload gives a fresh session with defaults, and
    memory stays cleared.
  - Code fix: give every widget key a generation suffix (e.g. `key=f"rfq_pick_{gen}"`). Keep `gen` outside what the
    reset clears and increment it on reset. That way the frontend creates new widgets. Alternatively, use an `on_click`
    callback that explicitly sets `rfq_pick="RFQ-A"`, `capacity=50`, `mat_age=0`, `section=SECTIONS[0]`, and every
    `gap_*` key to `ASK`.

### HIGH

**2. The "new fixture" override is charged every release. Tooling isn't broken out. Fixture cost is double-counted on B.**
- *Repro:* Beat 2 (Quick adjust **Fit & tack: setup (hr/lot) +6** with reason "new fixture needed").
- *What happens:* it adds 6 hr to **every lot of 50**: +$9.39/unit P50, about $2,350 over 250 pcs, which is 5× the
  $480 of a one-time 6-hr build. The quote has no "one-time tooling" line, even though the RFQ email on screen says
  *"list any setup or tooling charges separately."* On B the learned note (+6 hr/lot, "value 8.54") sits next to B's
  own **Fixture build (one-time) 6.7 hr/order** line. The script points at both together.
- *Why it matters:* an estimator on the panel will ask "why is the fixture on every release?" and "why is B paying for
  the fixture twice?" It also contradicts `docs/qa.md` Q12 ("one-time items like a new fixture are their own line").
- *Fix, cheapest:* change the Beat 2 reason to a genuinely per-release cause. For example: "Rev C gusset adds a fit-up
  step; old fixture needs re-shimming every setup". Consider a smaller delta (+1.5 to 2 hr), then update the script
  numbers.
- *Fix, better (code):* on a revision change, add a `fixture.setup` (hr/order) line in `proposal.build_proposal` and put
  the +6 there. B would then learn on its own `fixture.setup` line (same `line_key`), not on per-lot setup. Also add a
  "Setup & tooling (included above)" block to `pipeline.quote_markdown`: per-release setup $, and one-time
  fixture/tooling $.

**3. The "What just changed" banner is off-screen right after the clicks the script says to watch.**
- *Repro:*
  - At 1600x1000 the Gate 1 table starts at y≈1240 and **Approve Gate 1** is at y≈1890, so the presenter must scroll.
    After approving, the banner is at y=-235 (off-screen). At 1280x800 it is y=-503.
  - At 1280x800 the Beat 1 color card sits at the fold. After clicking it the banner is at y=-95.
  - In Beat 4, if the drawer was scrolled in Beat 3, the banner is also out of view.
  - At 1280x800, the Beat 6 "Learned from an earlier quote" callout is below the fold (y≈977).
- *Why it matters:* "Watch the banner" is the chain-reaction moment, which is design goal #1. The presenter will be
  scrolling while talking.
- *Fix:*
  - Also fire `st.toast(...)` with the one-line banner text whenever `st_["banner"][rid]` changes. It is visible at any
    scroll position.
  - And/or make `.qm-banner` sticky (`position: sticky; top: 3rem; z-index: 99`).
  - Put the "What's different" table and "Other similar jobs" in expanders (or after Gate 1) so Approve sits near the
    fold.
  - Present at 80-90% browser zoom.

**4. In mock mode the screen contradicts the talk track.**
- *What the screen shows:* "extracted by `mock:mock` (**mock fixture**)", "Drafted by mock:mock (**fallback**)", and in
  the sidebar "Model: `mock fixtures` · Mode: `live`".
- *What the presenter says:* "Our local model reads the email." `mock` is the default provider, and `cache/llm/` is
  empty in the repo.
- *Why it matters:* a judge who reads the small print concludes the AI part is canned.
- *Fix:*
  - On the presentation PC run `MODEL_PROVIDER=ollama`, then `python -m qm.pipeline --warm demo/rfqs`, then
    `DEMO_MODE=offline`.
  - Check that the labels read "ollama:qwen3:8b (cached model output)" and that `cache/llm/` is non-empty.
  - If you must fall back to mock, say so out loud ("hand-checked extraction of what the model returns").

### MEDIUM

**5. Approved gates are not invalidated when upstream inputs change.**
- *Repro:* assume both gaps, approve Gate 1 and Gate 2 at $209.64 ("Ready to send"). Then set load to 100% and age to
  180, and re-open Gate 1 with +6.
- *What happens:*
  - The quote still says **"Ready to send"** at $209.64, while P50 is now $168.59, rec $235.19 and **floor $233.48**.
  - The 50-pc row stays at $209.64, but the 100/200/250 rows are recomputed with the new markup ($198.91 / $193.35 /
    $192.24).
  - The stepper shows Gate 2 done while Gate 1 is open.
- *Why it matters:* the obvious judge question is "what if cost changes after the manager signs off?"
- *Fix:* store the P50 and floor at Gate 2 approval. In `run_pipeline`, or in `sec_quote`, flag or un-approve Gate 2
  when a later P50 differs by more than 0.5%, or when the approved price is below the new floor. Re-opening Gate 1 should
  also reset `gate2_approved`.

**6. Beat 5's optional shop-load drag leaves the old price in the Gate 2 box.**
- *Repro:* on section 5, drag load to 90%. The recommended price becomes $230.25, but the **Unit price box still says
  $222.74**. That is exactly the new range's lower edge, so no warning appears.
- *What happens:* **Approve Gate 2** approves $222.74, not the recommendation the script says is pre-filled. Beat 6 then
  runs at 90% load unless someone drags it back.
- *Fix:* either drop the optional step, or add to the script "click **Use recommended**, then drag load back to 50%". In
  code, re-seed `g2_price_{rid}` whenever `pr["recommended"]` changes while Gate 2 is open.

**7. Script and screen mismatches.**
- Beat 4 says the banner shows "quote validity 30 → 15 days". It doesn't: `app.py` renders only P50/band/rec/lines, and
  `diff()["text"]` is unused.
- Beat 4 says "the steel lines show a warning: *Newest A36 quote is 95 days old…*". The ledger shows only a WARN flag. The text
  appears only in the drawer after selecting **A36 plate**, or in section 4.
- Beat 1 "tight but feasible" isn't on screen (it shows "slack +3").
- Beat 2's key sentence "New revision of a part we built: check that the fixture and programs still fit" is truncated
  in the dataframe at both widths.
- *Fix:* render validity (and removed lines) in the banner. Otherwise, edit the script to "select A36 plate in the
  drawer", and give the "Expected cost effect" column `width="large"`, or use `st.table`.

**8. Excluding a Gate 1 line is fragile.**
- *Repro:* untick **Include** on *Bolt kit*, then click Quick adjust **Apply**. The tick silently comes back. Only values
  are stored in `g1_pending`, and the editor is re-keyed.
- Excluding *Powder coat* and approving:
  - Requires a reason, but the reason **is not saved to memory** (Memory stays 0) and isn't shown.
  - The banner cause reads **"Gate 1 edits: cleared"** and doesn't name the removed line.
  - The quote still asks the customer for the powder coat color.
- *Fix:*
  - In the Apply handler, persist `excl` (e.g. `st_["g1_pending_excl"][rid]`).
  - List exclusions in "Pending changes" and in `cause_of_change`, e.g. "removed Powder coat (outside)".
  - Record exclusions via `memory.record_decision`.
  - Drop gaps whose affected lines are all excluded.

**9. A pasted RFQ gets a confident price even with no real content.**
- *Nonsense* (`asdf … DROP TABLE jobs;`):
  - The KPIs show **$60.30 recommended, 76% win chance**.
  - The analog J-0959 has similarity **0.32**, below the 0.35 bar, and is used anyway.
  - The quote prints **"Quotation: None", "To: None", "Part: None:"**.
- *Tube assembly* ("3x3x1/4 A500 tube with two 1/2" A36 end plates", zinc):
  - Material is read as A36. The analog's A500 tube line is "swapped" to **A36 plate**.
  - The analog's 1018 bar, grease zerk and machining are kept, although the RFQ never mentions them.
- *Aluminum guard* ("riveted together, **no welding**", "Finish: none (bare aluminum)"):
  - Triage says "new weldment" and the ledger keeps **Weld $17.62/unit**.
  - The finish is flagged "not stated".
  - The description is cut at the decimal point: "…part RRA-GD-0412, in 0".
- *Why it matters:* "paste your own" is the first thing a curious judge tries. "Garbage in, price out" undercuts
  "honest uncertainty."
- *Fix:*
  - When 3 or more essentials came from `fill_from_analog`, or the analog similarity is below 0.35, replace the price
    KPIs with "Not enough information to price: N assumptions", block Gate 2, and never print `None` in
    `quote_markdown`.
  - Add a difference-table row "Analog items not mentioned in the RFQ".
  - Honor "no welding" by dropping weld/grind ops.
  - Add `none|bare` to the `rule_extract` finish regex, and stop the description regex at sentence ends rather than at
    any "."

**10. Live-model latency on pasted RFQs is untested.** Every ask/assume flip changes the clarification-email prompt,
which means a new, uncached LLM call. The same happens for intake and pattern narration on a new paste. On a laptop
running qwen3:8b this could mean multi-second freezes on every click. *Fix:* for pasted RFQs, draft the email only when
its expander is opened (or on a button), and use the template otherwise. Time one paste on the demo PC before promising
it.

**11. The quote's "Release size" table mixes up totals and release sizes.** RFQ A shows rows 50 / 100 / **200** /
**250**. The 200 comes from the quantity conflict, which is a *total* quantity in releases of 50, and 250 is the order
total. A buyer reads "Release size 200 = $200.34" as one release of 200. *Fix:* in `pipeline.build_quote`, label the
table "Unit price by release size", drop the sheet quantity from it, and add a separate line: "If total is 200 pcs
(releases of 50): $X/unit".

### LOW

**12. A Gate 2 price of $0 is approved at the recommendation.** `pipeline.run_pipeline` L140 uses
`if st["gate2_price"]` (falsy for 0.0). After entering 0 plus a reason, the UI shows "approved at $221.27", but memory
records "Manager priced $0.00". *Fix:* use `is not None`, and set a sane `min_value` (e.g. 0.5 × P50) on the input.

**13. Section 4 "Cost mix per unit" renders as LaTeX.** The `$` amounts become green monospace math
(`app.py` L577 lacks `esc()`). It's the one visible glitch in the Risk tab, which the deck says to show.

**14. Jargon a non-technical judge will trip on:**
- The banner cause uses internal keys: "Gate 1 edits: **fit_tack.setup** → 8.10", "**mat.A36** → 2.00".
- "P50" appears in the KPIs and banner. The drawer says "CV 0.20" and "weight **4.9 of 3**". The evidence table header
  is "= sim × auth × recen…" (truncated).
- The stepper shows "> Determine Manufacturing Approach" while section 1 is displayed.

*Fix:* map keys to labels in `cause_of_change`. Use "typical cost (P50)", "sources disagree by ±20%", and "evidence
weight 4.9 (3+ = full)".

**15. Demo rigging is visible, and double-applying is easy.** Quick adjust pre-fills **+6.00** on Fit & tack setup for
*every* weldment (B, pasted RFQs). Clicking **Apply** twice gives +12 (2.10 → 14.10); a double-click is safe. *Fix:*
default the delta to 0 except for RFQ-A, and reset `qa_delta` after Apply.

**16. Wild BOM edits aren't sanity-checked.** Setting the A36 plate from 19.8 to 2.0 lb/unit is accepted silently. The
line stays green 0.97 (confidence is on $/lb, not quantity) with no EDIT flag in the ledger. It is also written to memory, but
BOM overrides are never used as evidence. *Fix:* warn when an edit is more than 2× or less than 0.5× the analog, show EDIT
on BOM lines, and don't claim "saved so the next quote learns" for BOM edits.

**17. The docs don't fully match the app:**
- Deck slide 5 and `process_future.md` say "**three** gates"; the README and script say two, and there is no send gate
  in the UI.
- Deck beat 5 shows the P10/P50/P90 chart; the script skips section 4.
- `process_future.md` stage 4 says you "can override a line" in the ledger (only Gate 1 can), and stage 7 promises a
  "line summary" in the quote (not there).
- The script's fallback points to `docs/screens/`, which doesn't exist yet.
- The `memory.py` docstring mentions "reasoned ask/assume flip" (there's no UI for it).

**18. Credibility answers to prepare:**
- *The ±3.9% band (P10-P90 7.8%) on a Rev-changed cosmetic weldment:* a veteran will call it tight. The answer is the
  independence limit plus the contingencies; `qa.md` Q5 covers it, so lead with it.
- *The 83% win chance at 1.33×:* explain that it comes from a repeat OEM customer's synthetic history.
- *A36 shows two different prices:* $0.886/lb in the difference table (mean of the last 3 quotes) vs $0.877/lb in the
  ledger (weighted over 12 quotes). Know why.

### NIT

**19.** Clarification email formatting: Markdown turns the numbered questions into an outdented list, with extra blank
lines and no blank line after "Hi Dana,". Render it with `<pre>` or `st.text`.

**20.** The quote is dated **Sep 30, 2026** (`config.AS_OF`), but the pitch is on Oct 1.

**21.** At 0% load, the capacity cost prints as "$-12.59". The banner colors a higher *price* red, as if it were bad
news.

**22.** The SQLite mirror ignores `QM_MEMORY_DIR` (`config.SQLITE_PATH`). An isolated test instance's Reset deletes
`M-%` rows from the shared `data/quote_memory.sqlite`. This is harmless today (memory is read from CSV).

## Things that worked well

- The numbers are deterministic and match the script exactly on HEAD `77048d0`. Ask/assume flips (repeated 3×) return
  the KPIs exactly to baseline.
- Every rerun takes 0.1-1.2 s, and there were zero exceptions: empty, whitespace and nonsense pastes, $0 price, load
  0-100%, age 180, re-opened gates, and double-clicks on Apply/Approve all held up.
- It degrades cleanly with Ollama unreachable, or offline with an empty cache: fixture/template fallback, same numbers,
  honest labels.
- The provenance drawer is strong. For J-1042 it shows "Quoted 0.46 hr/unit, actual 0.62", the date, and the
  half-life. P1 is shown with n=16. The override honestly turns red (green 0.94→red 0.36). The learning loop shows up on B with
  its reason.
- Gate 1 refuses an edit without a reason. Stale steel lowers confidence, widens the band, and switches validity to 15
  days.

## Demo-day checklist

1. Start the server at least 2 minutes early. A cold first load takes 6-16 s (embedding index).
2. Warm the cache with Ollama, then run `DEMO_MODE=offline`. Confirm the labels don't say `mock` (#4).
3. **Reset, then F5.** Verify: A is selected, 50%, 0 days, section 1, **both gap cards on "Ask"**, Memory 0 (#1).
4. After every Approve or card click, scroll to the top before saying "watch the banner". Present at 80-90% zoom (#3).
5. Beat 4: select **A36 plate** in the drawer to show the warning text. Say "15-day validity" on the Quote tab, not the
   banner (#7).
6. Skip the optional shop-load drag. If you do it, click **Use recommended** and drag back to 50% before Beat 6 (#6).
7. Rehearse the answer to "fixture every release / fixture twice on B", or change the Beat 2 reason (#2).
8. Don't take a live paste unless one has been timed on the demo PC (#9, #10).
9. Capture `docs/screens/` (the fallback relies on it) and queue the backup recording.

---

## Resolution (build owner, after the review)

| # | Finding | Status | What changed |
|---|---|---|---|
| 1 | Reset leaves widgets stale | **Fixed** | Every widget key carries a generation suffix; Reset is an `on_click` callback that clears state and bumps the generation, so the browser draws fresh widgets. Verified in Chromium: after rehearsing to C with 90% load, Reset shows A / 50% / 0 / section 1 / both gaps "Ask", and the first Assume click produces the banner. AppTest asserts the same. |
| 2 | Fixture charged every release; double count on B | **Fixed** | Revision change adds a red 0-hr *Fixture build (one-time)* line; Beat 2 sets it to 6 hr (charged once: $480 over 250 pcs). B learns on its own one-time fixture line (absolute 6 hr from memory). P2 explains the fixture line instead of inflating setup, and "no fixture quoted" debriefs don't count when a fixture line exists. Quote lists setup per release and one-time tooling separately. |
| 3 | Banner off-screen after clicks | **Fixed** | Every change also fires a toast (visible at any scroll position) with P50, price and the first changed line. Gate 1 editor height capped so Approve sits closer. |
| 4 | Mock labels contradict the talk track | **Fixed / process** | Labels now say "hand-checked extraction (mock mode …)" instead of `mock:mock`; LOCAL_RUN + demo script tell the presenter to warm with Ollama and check the label before presenting. |
| 5 | Approved gates not invalidated | **Fixed** | Gate 2 stores the P50 at approval; a >0.5% P50 move, a price below the new floor, or re-opening Gate 1 marks the approval stale (quote back to draft, "please re-approve"). |
| 6 | Price box keeps the old value | **Fixed** | The Gate 2 price box follows the recommendation whenever inputs change (until approved). |
| 7 | Script/screen mismatches | **Fixed** | Banner shows "Quote validity 30 → 15 days"; ledger warnings listed under the table; "tight but feasible" wording; difference table rendered as a full-width table (no truncation); script updated. |
| 8 | Exclusions fragile / not saved | **Fixed** | Exclusions persist through Quick adjust, appear in "Pending changes" and the banner cause, are saved to memory, and removing the coating line drops the color question. |
| 9 | Confident price from junk pastes | **Fixed** | "Not enough information to price" when the analog is below the 0.35 bar or 3+ essentials were assumed: KPIs show "not priced", Gate 2 blocked, quote says NOT PRICED, never prints "None". "No welding" drops weld ops; tube assemblies priced on A500; bare/none finish read; descriptions no longer cut at decimals; difference table lists purchased items carried over from the analog that the RFQ never mentions. |
| 10 | Live latency on pasted RFQs | **Mitigated** | Pasted RFQs use the template email instantly; the model drafts it only on "Draft it with the model". Intake still calls the model once per paste (timed on the demo PC per LOCAL_RUN). |
| 11 | Release-size table mixes totals | **Fixed** | "Unit price if released in lots of …" (release, 2× release, order total) + a separate "If the total is 200 pcs" line. |
| 12 | $0 price approved as recommendation | **Fixed** | `is not None` check; prices under half of P50 are refused. |
| 13 | Cost mix renders as LaTeX | **Fixed** | Escaped. |
| 14 | Jargon | **Fixed (mostly)** | Banner cause uses line labels; "Typical cost (P50)"; drawer says "weight 4.9; 3 or more counts as full" and "typical spread ±20%". Stepper kept as process progress (accepted). |
| 15 | Visible rigging / double apply | **Fixed** | Quick adjust pre-fills only the 6.0 hr *shop default* on an empty fixture line (0 elsewhere) and resets after Apply. |
| 16 | Wild BOM edits | **Fixed** | Warning when an edit is > 2× off the analog; EDIT shown on edited BOM lines; BOM edits logged as decisions (not claimed as evidence). |
| 17 | Docs don't match the app | **Fixed** | process_future stage 4/7, deck beats 2/6, memory docstring, LOCAL_RUN numbers; `docs/screens/` captured. "Three gates" kept: Gate 1, Gate 2 and the human who sends the quote (as in the brief). |
| 18 | Credibility answers | **Fixed** | Labor lines now 0.5-correlated (band on A 7.8% → 11.3%); qa.md Q5 and new Q25-Q28 cover the band, the 83% win chance, the two A36 prices and junk pastes. |
| 19 | Email formatting | **Fixed** | Text boxes render newlines as `<br>` inside one HTML block. |
| 20 | Quote dated Sep 30 | **Fixed** | Quote date = max(AS_OF, today). |
| 21 | Negative capacity cost / red price | **Fixed** | Shows "−$12.59 (slow shop: thinner margin OK)"; price changes in the banner are blue (neutral). |
| 22 | SQLite path ignores isolation | **Fixed** | `QM_SQLITE_PATH` env override. |
