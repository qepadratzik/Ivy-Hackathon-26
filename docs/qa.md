# Judge Q&A Prep: Quote Memory (Evidence-Weighted Quoting)

Prep sheet for the 2026 Ivy AI Case Competition, "AI for Iowa: Improving Manufacturing Quoting with Artificial Intelligence."
Boone Creek Fabrication, its customers, and all data in the prototype are **fictional and synthetic**. Every dollar figure is **illustrative**.

## How to answer

- Say the 2-3 sentence answer, then stop. If there is a matching demo moment (**Show:**), offer to click to it.
- Say "synthetic" and "illustrative" out loud. Never state an accuracy percentage, a win-rate lift, or an industry statistic.
- Never say "ITAR compliant" or "CMMC compliant." Say "keeps the data in the building, which makes compliance easier."
- Talk about competitors only in general, fair terms. We are not trying to out-feature mature products.
- If we don't know: "We haven't measured that yet. Here is how the pilot would measure it."

---

## 1. Trust in the numbers

**Q1. How do you stop the AI from hallucinating numbers?**
The language model never produces a cost or a price. It only extracts RFQ fields (each with the verbatim sentence it came from and a confidence level), drafts one clarification email, and writes one-sentence pattern explanations; every hour and dollar is computed by plain Python from the shop's own tables. If a field isn't in the RFQ, the model must leave it blank, and the gap rules flag it, like RFQ A's email saying 250 pieces while the attached spec says 200.
**Show:** Requirements section: source quotes next to each field, and the quantity conflict.

**Q2. How accurate is it?**
We won't quote an accuracy number, because on synthetic data it would be meaningless; our tests only prove the system recovers the patterns we seeded, such as the cosmetic-weld overrun and the first-run fixture overrun. What it gives you today is an honest self-assessment: every line has a confidence level and a range that widens when evidence is thin, old, or disagrees. In a pilot, the metric is estimate-versus-actual error on won jobs, measured side by side with the shop's estimator.

**Q3. Why these weights? Where do 1.0 / 0.8 / 0.6 / 0.3 and the half-lives come from?**
They are tunable priors, not fitted values: the ordering is shop common sense (an actual beats a note, a note beats an old estimate, an estimate beats a rule of thumb), and the half-lives match how fast things change (material prices 30 days, labor hours 540 days, notes 365 days). Every constant lives in one config file and is documented in our assumptions. With a real shop's history we would backtest: re-quote last year's won jobs using only what was known at the time, and tune the weights to minimize estimate-versus-actual error.

**Q4. What does "confidence" mean? Is 0.56 a probability?**
No, it's a 0-to-1 evidence-quality index, not a statistical probability. It multiplies how much weighted evidence there is (it saturates at a total score of 3, roughly three strong, recent, closely matching actuals) by how much that evidence agrees (1 minus the coefficient of variation). It drives the green/yellow/red chip and the width of the range, so the less we know, the wider the band.

**Q5. Your P10/P90 band looks tight (about ±6% on RFQ A). Are you treating every line as independent?**
No. Steel lines share one market shock, and labor lines share a "bad week on the floor" factor (pairwise correlation 0.5), so weld, fit-up and grind run long together. The band is still fairly tight because most lines on RFQ A are backed by several recent actuals that agree; lines with thin or stale evidence get ranges up to ±60%, and stale steel widens the band on screen. The correlation is an assumed prior today; with a real shop's estimate-versus-actual history we would fit it, and real bands may well come out wider.

**Q6. Isn't this just "ask AI what price to charge"?**
No. The recommended price comes from a logistic win-probability model on the shop's past won and lost quotes (synthetic today), and it maximizes P(win) x (price minus risk-adjusted cost), where risk-adjusted cost is P50 plus half the gap up to P90. The manager picks the final price at Gate 2, a capacity slider raises the minimum margin (and adds an opportunity cost on labor hours) when the shop is busy, and a price outside the recommended range needs a written reason.
**Show:** Price section: the expected-margin curve; the price-sensitive customer (Prairie Implement, fictional) gets a lower recommended markup.

---

## 2. Data: cold start, change, and mess

**Q7. What if a shop has no history? (cold start)**
On day one every line falls back to shop defaults (rule-of-thumb hours at burdened rates, authority 0.3), so the ledger shows red, low confidence and wide ranges instead of fake precision. It sharpens as evidence builds up: past estimates count at 0.6 and actual hours from completed jobs at 1.0, so every job the shop runs improves the next quote. Current supplier material quotes work from the first week, but until there is real won/lost history the manager should price from the cost band rather than trust the win curve.

**Q8. How does it handle a totally new part type?**
If no past job clears the similarity bar (0.35), the labor lines fall back to shop defaults, triage marks it L / full review, and the ledger shows red confidence and wide bands, which pushes the risk-adjusted cost and the recommended price up. Material still prices from current supplier quotes, because those are keyed to the material, not the part family. The estimator builds the routing at Gate 1, and once the job runs, its actual hours become the first real evidence for that family.

**Q9. What if suppliers change prices daily?**
Material evidence decays with a 30-day half-life, so a month-old price counts half as much as a fresh one, and any material quote older than 30 days triggers "Re-quote material or shorten quote validity to 15 days" plus a steel-trend escalation contingency. A new supplier quote is just a new row in the table, and the next run re-prices every affected line with no model involved. For truly daily volatility, the business answer is a short validity window or an escalation clause, and the tool tells you when you need one.
**Show:** Demo beat 4: age the material quote to 90 days and watch confidence drop, the band widen, and the validity flag appear.

**Q10. Our real data is a mess: missing actual hours, "A-36 HR" vs. "A36", typos in emails.**
The synthetic data was built messy on purpose: about 10% of won jobs lack actuals, material names come in several aliases, and some emails have typos. Aliases are normalized with a plain lookup table, missing actuals fall back to the estimate at lower authority, and disagreements between the email and the spec are flagged, never silently resolved. Cleaning up actual hours is still the biggest setup task, and we'd tell a pilot shop that up front.

**Q11. Your data is synthetic. Why should we believe any of this?**
Don't believe the numbers; we label them illustrative everywhere. What the synthetic data proves is the mechanics: seeded patterns are found, every number cites its evidence, confidence drops when evidence goes stale, and an override on one quote comes back as evidence on the next. We used synthetic data because a public repo can't hold a real shop's financials or customer prints, and the next step is loading a real Iowa shop's exports and measuring against its actuals.

**Q12. How does it handle quantity breaks and releases?**
Setup hours are kept separate from per-unit run hours, so the unit price at each quantity break comes from arithmetic (setup spread over the lot, plus run cost) rather than a guessed discount curve, and one-time items like a new fixture are their own line. The quote preview shows a unit price per quantity break, and quantity bucket is a factor in both analog matching and the win model. Release size matters (RFQ A is 250 pieces in releases of 50), so release quantity is an extracted field, and the quote shows the unit price for several release sizes so the buyer sees what bigger releases save.

---

## 3. People and process

**Q13. Does it replace the estimator?**
No. It takes over the lookup work (reading the RFQ, listing missing info, finding similar jobs, checking the latest steel price), while the estimator approves the BOM and routing at Gate 1 and the manager sets the price at Gate 2. The bigger point is succession: the senior estimator's judgment is captured as written override reasons, so whoever quotes after them sees that reasoning as evidence.

**Q14. What if the estimator's override is wrong?**
An override is evidence, not truth: it enters at authority 0.8, below actual hours at 1.0, and it fades with a 365-day half-life. Once that job runs, its actual hours come back and outweigh the override on the next similar quote. Every override is a dated record with the old value, the new value, and the written reason, so a manager can audit it and remove it.
**Show:** Demo beat 6: the fixture override from RFQ A appears as a labeled evidence row on RFQ B.

**Q15. How do you avoid learning bad habits?**
It learns from what actually happened on the floor, not from what was quoted: old estimates count at 0.6, actuals at 1.0, and a pattern only shows once it has at least three jobs behind it. The patterns are bad-habit detectors: P1 exists because cosmetic welds keep running over their estimates, and P2 because first-run jobs keep missing the fixture. Requiring a written reason for every override also makes lazy overrides visible.

**Q16. Won't estimators just rubber-stamp Gate 1?**
The gate points them at what matters: red and yellow lines, and a difference table showing how this RFQ differs from the closest past job, so a real review takes minutes instead of a rebuild. Triage sends repeat parts to fast-track and first-run, cosmetic, or new weldments to full review. We can't force careful review, but a monthly estimate-versus-actual check on won jobs makes rubber-stamping visible.

---

## 4. Security, deployment, and cost

**Q17. Confidentiality and security: can we use this on CUI or ITAR work?**
In the shop configuration everything runs on one PC (this demo used a hosted model instead, because our GPU machine fell through; it is one config line and the math is identical). The shop version runs on one PC (the Streamlit app, the qwen3:8b model through Ollama, and the embeddings), so customer prints and RFQs never leave the building and no cloud AI service sees them; after install it can run with no internet connection. That makes it CUI/ITAR-friendly, but it doesn't make a shop compliant by itself: the PC still sits inside the shop's existing controls, such as access control and, for CUI, its NIST SP 800-171 / CMMC program. The code can be pointed at a cloud model for development, but that is off by default and should stay off for controlled work.

**Q18. Why a small local model instead of a big one?**
The model's jobs are narrow: pull fields out of an email with a verbatim quote, draft one email, write one sentence, and a bigger model wouldn't improve the cost math because the model doesn't do the math. Local means no per-token fees, no data leaving the building, and it keeps working when the internet doesn't; every extraction shows its source sentence, so the estimator can catch a misread in seconds. The model provider is a config setting, so a shop that wants a larger local model can swap it without touching the pricing logic.

**Q19. What happens when the model is down?**
The quote still gets built, because every cost and price number is deterministic Python that never calls the model. All model calls are cached and there is an offline mode, which is how this demo can run with no model at all; on a cache miss a rule-based extractor and email templates take over, clearly flagged, and the estimator checks the fields as usual. The worst case is losing the intake time savings, not losing the quote.

**Q20. How much setup is this? Do we have to replace our ERP?**
No ERP swap: it reads CSV exports of past jobs, BOM lines, routing operations with estimated and actual hours, debrief/NCR notes, and supplier material quotes. Our proposed plan is about three weeks: week 1 export and install on one PC, week 2 run side by side with the estimator, week 3 onward use the gates live. The real effort is cleaning the export (column mapping, material aliases, actual hours), not installing the software.

**Q21. What does it cost?**
The software stack is open source and the model is open-weights, so there are no per-seat or per-token fees, and the hardware is one local PC with a GPU, which a shop may already own. The real cost is people time for the data export, setup, and the side-by-side trial. `docs/roi.md` has an editable calculation with made-up round inputs that a shop replaces with its own numbers.

---

## 5. Market and scope

**Q22. Why not just buy Paperless Parts?**
A shop that is happy with an established quoting platform like Paperless Parts may not need us, and we aren't trying to out-feature a mature product. Our focus is narrower: an evidence layer where every number cites the past job, note, or supplier quote it came from, with a confidence level, running on a PC in the shop from CSV exports. It can sit alongside an existing quoting or ERP workflow rather than replace it.

**Q23. There are plenty of AI quoting tools. What is actually new here?**
The market already has quoting and workflow platforms, marketplaces that price work for their own network, CAD-based estimators, and drawing-similarity search, and we don't claim to beat them at their own jobs. What's different is the combination for a small shop: provenance on every number, confidence that honestly drops when evidence is thin or stale, and human overrides captured with reasons that come back as evidence, all running locally. We don't parse drawings yet, and that's the first gap a competitor would point to.

**Q24. Most RFQs come with a PDF print. Why don't you read drawings?**
We scoped it out on purpose: the input is the RFQ email plus a structured spec (material, thickness, quantity, tolerance, weld, finish, due date) that the estimator confirms. Drawing/CAD parsing is on the roadmap, along with fine-tuning the local model on a shop's own RFQs. Even then, drawing data would feed the same evidence ledger, so the provenance and confidence logic stays the same.

---

## Extra answers from our red-team review

**Q25. Why is the new fixture charged once, not on every release?**
Because it is built once. The system keeps one-time tooling on its own "Fixture build (one-time)" line, spread over the whole order (6 hr × $80 = $480 over 250 pcs), while per-release setup is spread over each release of 50. The quote lists setup per release and the one-time fixture separately, as the buyer asked.

**Q26. An 83% win chance at 1.34× seems high.**
It's what the synthetic history says for Cedar Valley, a repeat OEM customer that accepted markups up to about 1.4× in our generated data; a price-sensitive customer like Prairie Implement gets a lower recommended markup (about 1.23×). With real data the curve is only as good as the shop's won/lost records, which is why the manager still decides at Gate 2.

**Q27. The A36 price is $0.886/lb in the difference table but $0.877/lb in the ledger. Which is it?**
Both are honest: the difference table shows a simple average of the three latest supplier quotes (for comparing with the analog's date), while the ledger weights twelve quotes by recency with a 30-day half-life. The ledger value is the one used in the cost.

**Q28. What if a judge pastes a nonsense or very thin RFQ?**
The system fills gaps from the closest past job, lists every assumption as a question, and if too much is missing (or nothing in history is similar) it refuses to price: the quote says "NOT PRICED: not enough information" and Gate 2 is blocked.

## Honest limits (say these before a judge does)

- **Synthetic data, fictional shop.** Nothing has been validated against a real shop's actuals yet.
- **Prototype.** A single-PC demo, not hardened production software.
- **Weights and half-lives are tunable priors, not fitted.** A real history would let us backtest and tune them.
- **The Monte Carlo correlations are assumed** (steel fully shared, labor 0.5), not fitted from real estimate-vs-actual history.
- **The win model is trained on synthetic quotes.** Real shops often don't record why they lost, and the curve is only as good as that history.
- **No drawing/CAD parsing.**
- **Extraction can misread.** Source quotes and Gate 1 are the check.
- **Memory can carry a wrong override** until actual hours outweigh it.

## Constants you can cite (prototype values, all tunable)

| Item | Value |
|---|---|
| Evidence score | similarity x source authority x recency decay |
| Source authority | actual 1.0; note / override / pattern 0.8; past quote 0.6; shop default 0.3 |
| Recency half-life | material 30 days; labor hours 540 days; notes 365 days |
| Similarity bar | evidence counts only at similarity >= 0.35 |
| Confidence | min(1, total score / 3) x (1 - coefficient of variation) |
| Range | +/- (10% + 40% x (1 - confidence)), capped at 60% |
| Chip colors | green >= 0.70; yellow 0.40-0.70; red < 0.40 |
| Stale material | quote older than 30 days: "Re-quote material or shorten quote validity to 15 days" + steel-trend escalation contingency |
| Patterns | P1 cosmetic-weld overrun; P2 first-run fixture/setup overrun; P3 thick-plate press brake NCRs; P4 price-sensitive customer; P5 rising steel; shown only with n >= 3 |
| Risk band | Monte Carlo, 2,000 samples: P10 / P50 / P90 |
| Recommended price | maximizes P(win) x (price - risk-adjusted cost); risk-adjusted cost = P50 + 50% of (P90 - P50) |
| Human gates | Gate 1: estimator approves BOM + routing; Gate 2: manager picks price; every override needs a written reason |
