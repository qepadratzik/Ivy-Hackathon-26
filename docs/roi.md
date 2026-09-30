# ILLUSTRATIVE, NOT BENCHMARKS

> **Every number on this page is a made-up round example input, or arithmetic on those inputs.** None of them are measured results, industry averages, or data from a real shop. Boone Creek Fabrication is fictional. Replace the example column with your own numbers and redo the math.

## Quote Memory: ROI and Adoption One-Pager

**What a shop gets:** a quoting assistant that runs on one PC in the building (Streamlit app + local qwen3:8b model via Ollama + local embeddings), reads CSV exports of past jobs, and shows every cost line with its sources, a confidence level, and a range. No ERP swap. Customer data never leaves the building.

---

## 1. Inputs (edit these)

| Symbol | Input | Example (made up) | Your number |
|---|---|---|---|
| N | RFQs quoted per month | 60 | |
| h0 | Estimator hours per RFQ today | 3.0 | |
| h1 | Estimator hours per RFQ with Quote Memory (an assumption until the week-2 side-by-side measures it) | 1.5 | |
| C | Loaded estimator cost, $/hr (wage + benefits + overhead) | $55 | |
| Δw | Change in win rate, percentage points | **0 (default)** | |
| V | Average order value of a won job (only used if Δw is not 0) | $10,000 | |
| m | Contribution margin on a won job (only used if Δw is not 0) | 20% | |
| M | Margin leaks avoided per month, $ (forgotten fixtures, stale steel, etc.) | **$0 (default)** | |
| H | Hardware: one local PC with a GPU (placeholder; get a real quote, or $0 if the shop already owns a suitable PC) | $2,500 | |
| S | Software: open-source app + open-weights local model | $0 license fees | |
| Ls | One-time setup labor, hours (export, column mapping, install, side-by-side trial) | 40 | |
| Lm | Ongoing upkeep, hours per month (load new jobs and actuals, review overrides) | 4 | |

The two value levers we can't support yet (win rate and avoided misses) default to **0**. The headline number counts only estimator time.

## 2. Formulas

```
Hours freed per month        F  = N x (h0 - h1)
Time value per month         A  = F x C
Win-rate value per month     W  = N x Δw x V x m          (0 by default)
Misses avoided per month     M  = your estimate            (0 by default)
Ongoing cost per month       O  = Lm x C                   (+ any software you choose to buy)
Net benefit per month        B  = A + W + M - O
One-time cost                I  = H + S + Ls x C
Payback, months              P  = I / B
First-year net               Y1 = 12 x B - I
```

## 3. Worked example (made-up inputs from the table)

| Step | Calculation | Result |
|---|---|---|
| F, hours freed | 60 x (3.0 - 1.5) | **90 hrs/month** |
| A, time value | 90 x $55 | **$4,950/month** |
| W, win-rate value | 60 x 0 x $10,000 x 20% | $0 |
| M, misses avoided | default | $0 |
| O, upkeep | 4 x $55 | $220/month |
| B, net benefit | $4,950 + $0 + $0 - $220 | **$4,730/month** |
| I, one-time cost | $2,500 + $0 + 40 x $55 | **$4,700** |
| P, payback | $4,700 / $4,730 | **about 1 month** |
| Y1, first-year net | 12 x $4,730 - $4,700 | **$52,060** |

Scale check: 90 hours a month is about half of one full-time person (40 hrs x 52 weeks / 12 ≈ 173 hrs/month).

**Sensitivity: change only h1** (all other inputs as above).

| Hours saved per RFQ | h1 | F (hrs/mo) | B (net/mo) | Payback | First-year net |
|---|---|---|---|---|---|
| 0.5 | 2.5 | 30 | $1,430 | about 3.3 months | $12,460 |
| 1.0 | 2.0 | 60 | $3,080 | about 1.5 months | $32,260 |
| 1.5 | 1.5 | 90 | $4,730 | about 1 month | $52,060 |

**Break-even:** with these made-up inputs, the tool pays back within 12 months if it saves about **11 minutes per RFQ** ((I / 12 + O) / C / N = ($392 + $220) / $55 / 60 ≈ 0.19 hr).

**Win-rate formula, for illustration only (not in any total above):** if Δw were +1 point, W = 60 x 0.01 x $10,000 x 20% = $1,200/month. Win rate could also go *down* if the tool raises prices on jobs with stale steel or hidden setup, and losing jobs that would have lost money is fine.

**Read these carefully:**
- **Freed hours are capacity, not cash.** They become money only if the estimator quotes more RFQs, answers faster, spends the time on the floor, or the shop avoids adding a second estimator.
- **h1 = 1.5 is an assumption.** The prototype has not been timed in a real shop. Week 2 of the adoption path exists to measure it.

---

## 4. Benefits the math above leaves out

- **Faster response.** On arrival, the RFQ is read into fields with source quotes, gaps and conflicts are listed, and one clarification email is drafted. Repeat parts triage to S / fast-track and can be quoted from one screen.
- **Knowledge retention when the senior estimator retires.** Every override needs a written reason and is saved as evidence, alongside debrief and NCR notes. The next estimator sees "needs new fixture, add ~6 hrs" on the next similar part, not a blank spreadsheet.
- **Fewer margin-killing misses.**
  - *Forgotten fixtures:* first-run jobs without a fixture get a one-time fixture line (prototype default: 6 hours at the illustrative $80/hr fit & tack rate, or $480).
  - *Stale steel:* any material quote older than 30 days triggers "Re-quote material or shorten quote validity to 15 days" plus a steel-trend escalation contingency.
  - *Known trouble spots:* cosmetic-weld overruns (P1), first-run setup overruns (P2), and thick-plate press brake NCRs (P3) show up as labeled evidence rows on the affected lines.
- **Consistent quotes.** The same RFQ and the same history give the same starting numbers, whoever is quoting.
- **Audit trail.** Every number shows the past job, note, or supplier quote it came from. Every override records the old value, the new value, the date, and the reason.
- **Honest risk.** Confidence chips and a P10 / P50 / P90 cost band tell the manager where the uncertainty is before the price is picked at Gate 2.
- **Data stays in the building.** Local model, local embeddings, no cloud AI service. That keeps the approach CUI/ITAR-friendly (it does not by itself make a shop compliant).

---

## 5. Adoption path

| When | What happens | Done when |
|---|---|---|
| **Week 1** | Export past jobs to CSV: jobs, BOM lines, routing ops with estimated and actual hours, debrief/NCR notes, supplier material quotes. Install on one local PC. Map columns and material aliases. | The estimator re-quotes a few past jobs and agrees the closest-job matches make sense. |
| **Week 2** | Side by side: the estimator quotes every RFQ the usual way while Quote Memory runs in parallel (its output is not sent). Log hours per RFQ both ways, where the numbers differ, and any misses it caught. | The shop has its own h0 and h1 to put in the table above. |
| **Week 3+** | Gates in production: Gate 1, the estimator approves BOM + routing; Gate 2, the manager picks the price. Overrides with reasons feed memory. Each month, load new actuals and review estimate vs. actual on won jobs. | Go / no-go decided on the shop's own numbers. |

**Pilot:** run this with a CIRAS-supported Iowa manufacturer (CIRAS is Iowa State University's Center for Industrial Research and Service). Pilot measures: estimator hours per RFQ, RFQ-to-quote turnaround, estimate-vs-actual error on won jobs, misses caught, and the estimator's own verdict.

*This page cites no industry statistics. Every input above is a made-up example to be replaced by a real shop's numbers.*
