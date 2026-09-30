# Judge Q&A Prep: Quote Memory (Evidence-Weighted Quoting)

Prep sheet for the 2026 Ivy AI Case Competition, "AI for Iowa: Improving Manufacturing Quoting with Artificial Intelligence."
Boone Creek Fabrication, its customers, and all data in the prototype are **fictional and synthetic**. Every dollar figure is **illustrative**.

## How to answer

- Say the 2-3 sentence answer, then stop. If there is a matching demo moment (**Show:**), offer to click to it.
- Say "synthetic" and "illustrative" out loud. Never state an accuracy percentage, a win-rate lift, or an industry statistic.
- Never say "ITAR compliant" or "CMMC compliant." Say "keeps the data in the building, which makes compliance easier."
- Talk about competitors only in general, fair terms. We are not trying to out-feature mature products.
- If we don't know: "We haven't measured that yet. Here is how the pilot would measure it."
- Use the words on screen: Checkpoint 1 and 2, shop notebook, closest past job, typical cost, High / Medium / Low confidence.

---

## 1. Trust in the numbers

**Q1. How do you stop the AI from hallucinating numbers?**
The language model never produces a cost or a price. It only extracts RFQ fields (each with the verbatim sentence it came from and a confidence level), drafts one clarification email, and writes one-sentence pattern explanations; every hour and dollar is computed by plain Python from the shop's own tables. If a field isn't in the RFQ, the model must leave it blank, and the gap rules flag it, like RFQ A's email saying 250 pieces while the attached spec says 200.
**Show:** Step 1 (Read the request): source quotes next to each field, and the quantity conflict.

**Q2. How accurate is it?**
We won't quote an accuracy number, because on synthetic data it would be meaningless; our tests only prove the system recovers the patterns we seeded, such as the cosmetic-weld overrun and the first-run fixture overrun. What it gives you today is an honest self-assessment: every line has a confidence level and a range that widens when evidence is thin, old, or disagrees. In a pilot, the metric is estimate-versus-actual error on won jobs, measured side by side with the shop's estimator.

**Q3. Why these weights? Where do 1.0 / 0.8 / 0.6 / 0.3 and the half-lives come from?**
They are tunable priors, not fitted values: the ordering is shop common sense (an actual beats a note, a note beats an old estimate, an estimate beats a rule of thumb), and the half-lives match how fast things change (material prices 30 days, labor hours 540 days, notes 365 days). Every constant lives in one config file and is documented in our assumptions. With a real shop's history we would backtest: re-quote last year's won jobs using only what was known at the time, and tune the weights to minimize estimate-versus-actual error.

**Q4. What does "confidence" mean? Is 0.56 a probability?**
No, it's a 0-to-1 evidence-quality index, not a statistical probability. It multiplies how much weighted evidence there is (it saturates at a total score of 3, roughly three strong, recent, closely matching actuals) by how much that evidence agrees (1 minus the coefficient of variation). It drives the High / Medium / Low chip (green/yellow/red) and the width of the range, so the less we know, the wider the range.

**Q5. Your "very likely between" range (P10 to P90) looks tight (about ±6% around the typical cost on RFQ A). Are you treating every line as independent?**
No. Steel lines share one market shock, and labor lines share a "bad week on the floor" factor (pairwise correlation 0.5), so cutting, bending and welding run long together. The range is still fairly tight because most lines on RFQ A are backed by several recent actuals that agree; lines with thin or stale evidence get ranges up to ±60%, and stale steel widens the range on screen. The correlation is an assumed prior today; with a real shop's estimate-versus-actual history we would fit it, and real ranges may well come out wider.

**Q6. Isn't this just "ask AI what price to charge"?**
No. The recommended price comes from a logistic win-probability model on the shop's past won and lost quotes (synthetic today), and it maximizes chance of winning x (price minus planning cost), where planning cost (the risk-adjusted cost) is the typical cost plus half the gap up to the high-end cost (P50 plus half the gap up to P90). The manager picks the final price at Checkpoint 2 from three choices (lower, recommended, higher) or another amount, and a price outside the recommended range needs a written reason.
**Show:** Step 4 (Set the price): the three choices and their chance of winning; with "Show the details" on, the profit curve. The price-sensitive customer (Prairie Implement, fictional) gets a lower recommended markup.

---

## 2. Data: cold start, change, and mess

**Q7. What if a shop has no history? (cold start)**
On day one every line falls back to shop defaults (rule-of-thumb hours at burdened rates, authority 0.3), so the cost table shows Low confidence (red) and wide ranges instead of fake precision. It sharpens as evidence builds up: past estimates count at 0.6 and actual hours from completed jobs at 1.0, so every job the shop runs improves the next quote. Current supplier material quotes work from the first week, but until there is real won/lost history the manager should price from the cost range rather than trust the win chance.

**Q8. How does it handle a totally new part type?**
Two cases. If even the closest past job falls below the similarity bar (0.35), the quote says NOT PRICED and asks for more information (see Q28). If only loosely similar jobs exist, the thin-evidence lines lean on shop defaults, the cost table shows Low confidence and wide ranges, which pushes the planning cost and the suggested price up, and triage marks the job Full review. Material still prices from current supplier quotes, because those are keyed to the material, not the part type. The estimator builds the plan at Checkpoint 1, and once the job runs, its actual hours become the first real evidence for that type of part.

**Q9. What if suppliers change prices daily?**
Material evidence decays with a 30-day half-life, so a month-old price counts half as much as a fresh one, and any material quote older than 30 days triggers "Re-quote material or shorten quote validity to 15 days" plus a steel-trend escalation contingency. A new supplier quote is just a new row in the table, and the next run re-prices every affected line with no model involved. For truly daily volatility, the business answer is a short validity window or an escalation clause, and the tool tells you when you need one.
**Show:** the "What if our steel price quote were older?" slider in the sidebar: set it to 90 days and watch confidence drop, the range widen, and the quote validity go from 30 to 15 days.

**Q10. Our real data is a mess: missing actual hours, "A-36 HR" vs. "A36", typos in emails.**
The synthetic data was built messy on purpose: about 10% of won jobs lack actuals, material names come in several aliases, and some emails have typos. Aliases are normalized with a plain lookup table, missing actuals fall back to the estimate at lower authority, and disagreements between the email and the spec are flagged, never silently resolved. Cleaning up actual hours is still the biggest setup task, and we'd tell a pilot shop that up front.

**Q11. Your data is synthetic. Why should we believe any of this?**
Don't believe the numbers; we label them illustrative everywhere. What the synthetic data proves is the mechanics: seeded patterns are found, every number cites its evidence, confidence drops when evidence goes stale, and an override on one quote comes back as evidence on the next. We used synthetic data because a public repo can't hold a real shop's financials or customer prints, and the next step is loading a real Iowa shop's exports and measuring against its actuals.

**Q12. How does it handle quantity breaks and releases?**
Setup hours are kept separate from per-unit run hours, so the unit price at each quantity break comes from arithmetic (setup spread over the lot, plus run cost) rather than a guessed discount curve, and one-time items like a new fixture are their own line. The quote preview shows a unit price per quantity break, and quantity bucket is a factor in both analog matching and the win model. Release size matters (RFQ A is 250 pieces in releases of 50), so release quantity is an extracted field, and the quote shows the unit price for several release sizes so the buyer sees what bigger releases save.

---

## 3. People and process

**Q13. Does it replace the estimator?**
No. It takes over the lookup work (reading the RFQ, listing missing info, finding similar jobs, checking the latest steel price), while the estimator approves the BOM and routing at Checkpoint 1 and the manager approves the price at Checkpoint 2. The bigger point is succession: the senior estimator's judgment is captured as written reasons in the shop notebook, so whoever quotes after them sees that reasoning as evidence.

**Q14. What if the estimator's change (override) is wrong?**
An estimator note is evidence, not truth: it enters at authority 0.8, below actual hours at 1.0, and it fades with a 365-day half-life. Once that job runs, its actual hours come back and outweigh the note on the next similar quote. Every note is a dated record with the old value, the new value, and the written reason, all readable in the shop notebook, so a manager can audit it.
**Show:** Job 2: the fixture note saved on Job 1 (RFQ A) appears as an "Estimator note" evidence row on the Fixture build line (step 3).

**Q15. How do you avoid learning bad habits?**
It learns from what actually happened on the floor, not from what was quoted: old estimates count at 0.6, actuals at 1.0, and a pattern only shows once it has at least three jobs behind it. The patterns are bad-habit detectors: P1 exists because cosmetic welds keep running over their estimates, and P2 because first-run jobs keep missing the fixture. Requiring a written reason for every change also makes lazy changes visible.

**Q16. Won't estimators just rubber-stamp Checkpoint 1?**
The checkpoint points them at what matters: Low and Medium confidence lines, and a "how this order is different" table showing how this RFQ differs from the closest past job, so a real review takes minutes instead of a rebuild. Triage sends repeat parts to fast-track and first-run, cosmetic, or new weldments to full review. We can't force careful review, but a monthly estimate-versus-actual check on won jobs makes rubber-stamping visible.

---

## 4. Security, deployment, and cost

**Q17. Confidentiality and security: can we use this on CUI or ITAR work?**
In the shop configuration everything runs on one PC (this demo used a hosted model instead, because our GPU machine fell through; it is one config line, the demo is shown from a warmed cache, all demo data is synthetic, and the math is identical). The shop version runs on one PC (the Streamlit app, the qwen3:8b model through Ollama, and the embeddings), so customer prints and RFQs never leave the building and no cloud AI service sees them; after install it can run with no internet connection. That makes it CUI/ITAR-friendly, but it doesn't make a shop compliant by itself: the PC still sits inside the shop's existing controls, such as access control and, for CUI, its NIST SP 800-171 / CMMC program. The code can be pointed at a cloud model for development, but that is off by default and should stay off for controlled work.

**Q18. Why a small local model instead of a big one?**
The model's jobs are narrow: pull fields out of an email with a verbatim quote, draft one email, write one sentence, and a bigger model wouldn't improve the cost math because the model doesn't do the math. Local means no per-token fees, no data leaving the building, and it keeps working when the internet doesn't; every extraction shows its source sentence, so the estimator can catch a misread in seconds. The model provider is a config setting, so a shop that wants a larger local model can swap it without touching the pricing logic.

**Q19. What happens when the model is down?**
The quote still gets built, because every cost and price number is deterministic Python that never calls the model. All model calls are cached and there is an offline mode, which is how this demo can run with no model at all; on a cache miss a rule-based extractor and email templates take over, clearly flagged, and the estimator checks the fields as usual. The worst case is losing the intake time savings, not losing the quote.

**Q20. How much setup is this? Do we have to replace our ERP?**
No ERP swap: it reads CSV exports of past jobs, BOM lines, routing operations with estimated and actual hours, debrief/NCR notes, and supplier material quotes. Our proposed plan is about three weeks: week 1 export and install on one PC, week 2 run side by side with the estimator, week 3 onward use the checkpoints live. The real effort is cleaning the export (column mapping, material aliases, actual hours), not installing the software.

**Q21. What does it cost?**
The software stack is open source and the model is open-weights, so there are no per-seat or per-token fees, and the hardware is one local PC with a GPU, which a shop may already own. The real cost is people time for the data export, setup, and the side-by-side trial. `docs/roi.md` has an editable calculation with made-up round inputs that a shop replaces with its own numbers.

---

## 5. Market and scope

**Q22. Why not just buy Paperless Parts?**
A shop that is happy with an established quoting platform like Paperless Parts may not need us, and we aren't trying to out-feature a mature product. Our focus is narrower: an evidence layer where every number cites the past job, note, or supplier quote it came from, with a confidence level, running on a PC in the shop from CSV exports. It can sit alongside an existing quoting or ERP workflow rather than replace it.

**Q23. There are plenty of AI quoting tools. What is actually new here?**
The market already has quoting and workflow platforms, marketplaces that price work for their own network, CAD-based estimators, and drawing-similarity search, and we don't claim to beat them at their own jobs. What's different is the combination for a small shop: provenance on every number, confidence that honestly drops when evidence is thin or stale, and human changes captured with reasons (estimator notes) that come back as evidence, all designed to run locally. We don't parse drawings yet, and that's the first gap a competitor would point to.

**Q24. Most RFQs come with a PDF print. Why don't you read drawings?**
We scoped it out on purpose: the input is the RFQ email plus a structured spec (material, thickness, quantity, tolerance, weld, finish, due date) that the estimator confirms. Drawing/CAD parsing is on the roadmap, along with fine-tuning the local model on a shop's own RFQs. Even then, drawing data would feed the same evidence weighting, so the provenance and confidence logic stays the same.

---

## Extra answers from our red-team review

**Q25. Why is the new fixture charged once, not on every release?**
Because it is built once. The system keeps one-time tooling on its own "Fixture build (one-time)" line, spread over the whole order (6 hr × $85 = $510 over 250 pcs), while per-release setup is spread over each release of 50. The quote lists setup per release and the one-time fixture separately, as the buyer asked.

**Q26. An 81% win chance (about 8 in 10) at a 1.31× markup seems high.**
It's what the synthetic history says for Cedar Valley, a repeat OEM customer that accepted markups up to about 1.4× in our generated data; a price-sensitive customer like Prairie Implement gets a lower recommended markup (about 1.26× on the same cost). With real data the curve is only as good as the shop's won/lost records, which is why the manager still decides at Checkpoint 2.

**Q27. The A36 price is $0.886/lb in the "how this order is different" table but $0.877/lb in the cost table. Which is it?**
Both are honest: the difference table shows a simple average of the three latest supplier quotes (for comparing with the closest past job's date), while the cost table weights twelve quotes by recency with a 30-day half-life. The cost table value is the one used in the cost.

**Q28. What if a judge pastes a nonsense or very thin RFQ?**
The system fills gaps from the closest past job, lists every assumption as a question, and if too much is missing (or nothing in history is similar) it refuses to price: the quote says "NOT PRICED: not enough information" and the price cannot be approved (Checkpoint 2 is blocked).

## Questions a non-technical judge might ask

**Q29. Why only five job types, three materials and five processes?**
It is deliberate scope for a 15-20 minute demo and a small shop: with fewer moving parts, every number on screen can be explained in a sentence. The method does not depend on the count. The same evidence weighting, confidence and checkpoints apply to any number of materials or processes, and adding a process is one row in the config file (a name and a burdened rate). The catch is honest: with more materials and job types, each one has fewer past jobs behind it, so confidence starts lower until history builds up. The aluminum request already shows this on purpose: aluminum is rare in the synthetic history, so it gets thin evidence and Low confidence.

**Q30. What does "High / Medium / Low confidence" mean?**
It says how much to trust one number. High means several recent, closely matching past jobs or supplier quotes agree. Medium means there is some evidence, or it partly disagrees. Low means very little, old, or conflicting evidence, so treat the number as a guess and look at it first. It is the 0-to-1 evidence-quality index from Q4 (High is 0.70 or more, Medium is 0.40 to 0.70, Low is below 0.40), not a probability, and it sets the width of the range: the lower the confidence, the wider the range.
**Show:** Step 3 (Cost it): the "How sure" column, then click a row to see where the number came from.

**Q31. Who is responsible if the price is wrong?**
A person. The estimator approves the plan (Checkpoint 1), the manager approves the price (Checkpoint 2), and a person sends the quote; the quote is not marked ready to send until both checkpoints are approved. The tool shows its evidence for every number and records every change with a reason, so a decision can be reviewed afterwards. The AI never sets a number: it only reads the email and drafts text. It is decision support that shows its work, not an autopilot.

---

## Honest limits (say these before a judge does)

- **Synthetic data, fictional shop.** Nothing has been validated against a real shop's actuals yet.
- **Prototype.** A single-PC demo, not hardened production software.
- **Simplified shop.** 5 job types, 3 materials and 5 processes keep the demo clear; a real shop has more variety, and thinner history per item.
- **Weights and half-lives are tunable priors, not fitted.** A real history would let us backtest and tune them.
- **The Monte Carlo correlations are assumed** (steel fully shared, labor 0.5), not fitted from real estimate-vs-actual history.
- **The win model is trained on synthetic quotes.** Real shops often don't record why they lost, and the curve is only as good as that history.
- **No drawing/CAD parsing.**
- **Extraction can misread.** Source quotes and Checkpoint 1 are the check.
- **The shop notebook can carry a wrong estimator note** until actual hours outweigh it.

## Constants you can cite (prototype values, all tunable)

| Item | Value |
|---|---|
| Evidence score | similarity x source authority x recency decay |
| Source authority | actual 1.0; note / override / pattern 0.8; past quote 0.6; shop default 0.3 |
| Recency half-life | material 30 days; labor hours 540 days; notes 365 days; purchased parts and outside work 365 days |
| Similarity bar | evidence counts only at similarity >= 0.35 |
| Confidence | min(1, total score / 3) x (1 - coefficient of variation) |
| Range | +/- (10% + 40% x (1 - confidence)), capped at 60% |
| Chip colors | green >= 0.70; yellow 0.40-0.70; red < 0.40 (shown as High / Medium / Low confidence) |
| Stale material | quote older than 30 days: "Re-quote material or shorten quote validity to 15 days" + steel-trend escalation contingency |
| Patterns | P1 cosmetic-weld overrun; P2 first-run fixture/setup overrun; P3 thick-plate Bend (press brake) NCRs; P4 price-sensitive customer; P5 rising steel; shown only with n >= 3 |
| Risk range | Monte Carlo, 2,000 samples: typical cost (P50) and "very likely between" range (P10 to P90) |
| Recommended price | maximizes P(win) x (price - risk-adjusted cost); risk-adjusted cost ("planning cost") = P50 + 50% of (P90 - P50); the app offers three choices: lower, recommended, higher |
| Human checkpoints | Checkpoint 1: estimator approves the plan (BOM + routing); Checkpoint 2: manager approves the price; a person sends the quote; every override (a change, or a price outside the range) needs a written reason |
