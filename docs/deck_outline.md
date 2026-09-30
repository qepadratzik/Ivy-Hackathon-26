# Pitch Deck Outline: Quote Memory

**Case:** 2026 Ivy AI Case Competition (Iowa State): *AI for Iowa: Improving Manufacturing Quoting with Artificial Intelligence*
**Product:** Quote Memory: Evidence-Weighted Quoting
**Format:** 9 slides. Talk track about 4:20, plus a 3:30 live demo, for about **7:50 total**. If the slot runs short, use the 60-second demo fallback in `demo/demo_script.md` (about 5:20 total).

**Ground rules for every slide**
- No industry statistics. Every number comes from our own build and is labeled: *synthetic* (from the generated shop history), *illustrative* (rates, ROI, expedite), or a *design parameter* (half-lives, sample counts). Nothing comes from real companies.
- Boone Creek Fabrication and all customers are **fictional**. All data is **synthetic**.
- Competitor claims stay general and fair (slide 8).
- Visual language matches the process maps: **red = bottleneck, blue = AI, gold = human gate, green = memory.**

| # | Slide | Time | Running total |
|---|---|---|---|
| 1 | Hook | 0:30 | 0:30 |
| 2 | The problem in Iowa | 0:30 | 1:00 |
| 3 | Current-state map | 0:45 | 1:45 |
| 4 | The idea in one line | 0:20 | 2:05 |
| 5 | Future-state flow | 0:45 | 2:50 |
| 6 | Live demo | 3:30 | 6:20 |
| 7 | Why a shop would adopt it | 0:40 | 7:00 |
| 8 | Positioning | 0:30 | 7:30 |
| 9 | Limits & next steps | 0:20 | 7:50 |

---

## Slide 1: Hook (0:30)

**On screen:** Title only: **Quote Memory: Evidence-Weighted Quoting**, with the case title underneath.

**Speaker notes:**
> [QUENTIN: 3-sentence Twisted Traction story about a quote burned by a missing detail or an old material price]

Transition: "Every small shop has a story like that. The estimator worked hard enough. The trouble is that the knowledge behind the quote lives in one person's head and a pile of old folders."

---

## Slide 2: The problem in Iowa (0:30)

**On screen:**
- Small fab shops build the weldments, brackets, guards, and frames that go into Iowa-built ag and construction equipment
- One senior estimator carries the quoting know-how
- OEM buyers expect fast, accurate quotes, and every miss comes straight out of margin

**Speaker notes:**
"Meet Boone Creek Fabrication, a fictional 40-person job shop in central Iowa. It builds custom weldments, brackets, and tube assemblies for ag and construction OEMs. Like a lot of shops its size, it has one senior estimator who knows which jobs ran long and why, and that person is getting close to retirement. The case names the hard parts well: RFQs arrive incomplete or contradictory, supplier prices keep changing, and the most valuable knowledge was never written down. A chatbot doesn't fix that. The fix has to change how information moves through the whole quote."

---

## Slide 3: Current-state map (0:45)

**On screen:** The current-state diagram from `docs/process_current.md`, with its 8 red bottleneck nodes.

**Speaker notes:**
"Here's how Boone Creek quotes today. An RFQ lands in the inbox and waits for the one estimator. They chase missing info by email, dig through old job folders for something similar, and build the BOM and routing in Excel. Then come the risky parts, in red. Weld and setup hours are guesses. First-run fixtures get forgotten. The steel price might be months old. Powder coat lead time is assumed. Quantity breaks are set by feel. Markup goes on, the owner glances at it, and it's sent.
The biggest red box is at the bottom. When the job runs, the actual hours go into the ERP and nobody ever compares them to the estimate. So the shop makes the same miss again next time."

---

## Slide 4: The idea in one line (0:20)

**On screen (large):**
> *Every number in the quote shows its sources, and how much you trust it depends on how good those sources are.*

Small line underneath: `evidence score = similarity × source authority × recency`

**Speaker notes:**
"That's the whole idea. Take a weld-hour estimate backed by two recent actuals from nearly identical brackets: you can trust it. One backed only by a shop rule of thumb, you can't. Quote Memory shows you which is which on every line, with green, yellow, and red, and it prices the uncertainty instead of hiding it."

---

## Slide 5: Future-state flow (0:45)

**On screen:** The future-state diagram from `docs/process_future.md`: the case's 7 stages, blue AI roles, gold human gates, and the dashed learning loop.

**Speaker notes:**
"These are the same seven stages the case lays out. AI reads the RFQ and quotes the exact sentence behind every field. It flags gaps and conflicts and drafts the clarification email. It triages the job, finds the closest past job, and proposes a BOM and routing. Then it weighs the evidence line by line, adds patterns it found in the shop's history, simulates a cost band, and draws a win-probability curve.
Two things matter most. First, **the language model never produces a cost or price number.** It only extracts, drafts, and explains. All the math is plain, auditable code. Second, **people decide at three gates:** the estimator approves the BOM and routing, the manager picks the price, and a person sends the quote. Any override needs a reason. That reason goes into memory and shows up as evidence on the next similar RFQ. That's how it learns."

---

## Slide 6: Live demo (3:30)

**On screen:** Switch to the app. Backup slide text: **Live demo:** RFQ A (Cedar Valley Equipment, cosmetic-weld hitch bracket) → RFQ B (Hawkeye Loader Works, first-run near-twin) → RFQ C (Loess Hills Machinery, repeat mounting plate).

**Speaker notes, pre-flight (before the pitch starts):** Click **Reset demo state**. Check the DEMO_MODE indicator. If the local model is slow, run in **offline mode**: every model call is cached, so the demo works with no model at all. Keep the backup screen recording queued.

| Beat | Time | Click | Say |
|---|---|---|---|
| **1. Requirements** | 0:00–0:35 | Load **RFQ A**. Show extracted fields with confidence chips and source quotes. Point out that "3/8 plate" and "0.375 A-36 HR" normalize to the same material with no false alarm. Show the **2 gaps**: powder coat color missing, and qty 250 in the email vs. 200 on the spec. Open the drafted clarification email. Flip color to **"assume black, +3% contingency."** | "It never guesses silently. It either asks, or it writes down the assumption and prices it." |
| **2. Approach, Gate 1** | 0:35–1:05 | Triage badge (**L / full review**, cosmetic weld). Show the difference table vs. the closest past cosmetic-weld hitch bracket. The system flagged the revision change with a red **one-time fixture line at 0 hr**; set it to **6 hrs** (charged once, not per release), reason **"new fixture needed: Rev C moved the hole pattern,"** then **Approve Gate 1**: the line turns green. | "The estimator stays in charge. The edit needs a reason, and that reason is now memory." |
| **3. Evidence** | 1:05–1:35 | Click the **weld line** to open the evidence drawer: source type, job ID, similarity, authority, recency, score, "why matched," and the original text. Show the **P1 callout**. | "Click any number and see where it came from. In our synthetic history, cosmetic-weld jobs ran about 35–40% over quoted weld hours, so it shows up as a labeled adjustment, not a hidden fudge factor." |
| **4. Chain reaction** | 1:35–2:10 | Sidebar: **age the material quote to 90 days.** Read the **change banner**: material confidence drops, the cost band widens, the recommended price moves up, and the flag *"Re-quote material or shorten quote validity to 15 days"* appears. | "One stale input, and the whole quote tells you it trusts itself less. It prices that risk instead of hiding it." |
| **5. Price, Gate 2** | 2:10–2:45 | P10/P50/P90 chart, then the expected-margin curve with the recommended range shaded. Mention the shop-load slider and the expedite option (**illustrative: +12% for 1 week faster**). Pick a price, **approve Gate 2**, and open the **quote preview** (price per release, validity, assumptions and exclusions). | "The AI recommends. The manager decides. More uncertainty means more cushion." |
| **6. It learns** | 2:45–3:10 | Load **RFQ B** (first run, near-twin). The ledger opens on B's **one-time fixture line** (added by the first-run rule): the **"new fixture needed" override from RFQ A** shows up as 🧠 evidence next to past fixture builds, and P2 explains why the line is there. | "Yesterday's judgment is today's evidence. That's how the senior estimator's know-how stays in the building." |
| **7. Fast-track** | 3:10–3:30 | Load **RFQ C** (repeat mounting plate, qty 40): **S / fast-track**, green across the board, one screen. | "Easy quotes go out fast, so the estimator's time goes to the hard ones." |

**If something breaks:** switch to offline mode and keep going. If the app itself fails, play the backup recording and narrate the same beats.

---

## Slide 7: Why a shop would adopt it (0:40)

**On screen:**
- **Runs on a shop PC:** local model (qwen3:8b via Ollama) + local embeddings
- **Customer prints and RFQs never leave the building**, which suits CUI/ITAR-sensitive work
- **Starts from past-job CSV exports**, no ERP swap
- **Low cost:** an existing PC + open models
- **Illustrative ROI** box: headline from `docs/roi.md`, labeled **ILLUSTRATIVE, NOT BENCHMARKS**

**Speaker notes:**
"A 40-person shop won't rip out its ERP or send customer drawings to a cloud AI service. Quote Memory runs on one desktop PC with an open model and reads the job history the shop can already export as CSVs. Nothing leaves the building. That matters to OEM customers with confidential prints and to anyone handling CUI or ITAR-controlled work. To be clear, that's a design advantage, not a compliance certification. On ROI, our one-pager uses illustrative inputs the shop can change: RFQs per month, estimator hours per RFQ before and after, and loaded estimator cost. The bigger payoff doesn't fit in a spreadsheet: faster responses, fewer margin-killing misses, and the senior estimator's judgment saved as reusable evidence before retirement."

---

## Slide 8: Positioning (0:30)

**On screen:**

| Player | Known for (general) |
|---|---|
| Paperless Parts | Intake and quoting workflow platform |
| Xometry | Prices jobs for its own manufacturing marketplace |
| Arzana | Custom AI builds for larger shops |
| CADDi | Drawing similarity search |
| Toolpath | CAD-based CNC estimating |

**Quote Memory:** the transparent, evidence-weighted, local layer for smaller shops.

**Speaker notes:**
"These are strong products, and we haven't benchmarked any of them. We're describing their general focus, not their feature lists. Our lane is narrower. We give a small fab shop a quoting layer where every number shows its sources, confidence comes from the quality of those sources, and everything runs on the shop's own PC using its own history. It can sit next to whatever workflow tools a shop already uses."

---

## Slide 9: Limits & next steps (0:20)

**On screen:**
- **Today:** synthetic data for a fictional shop → **next:** a real shop's job history
- Drawing/CAD parsing (out of scope for the prototype)
- Fine-tune the local model on a shop's own RFQs
- Pilot with a CIRAS-supported Iowa manufacturer

**Speaker notes:**
"We're upfront about the limits. Everything today runs on synthetic data, so the next step is a real shop's history. After that, reading drawings directly and tuning the local model on the shop's own RFQs. We'd like to pilot with a CIRAS-supported Iowa manufacturer. To sum it up: every number shows its sources, and how much you trust it depends on how good those sources are. Thank you. We're happy to take questions."

---

**Q&A prep:** see `docs/qa.md` (cold start, hallucinated numbers, why these weights, security, and more).
