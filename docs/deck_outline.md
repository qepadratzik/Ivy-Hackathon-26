# Pitch Deck Outline: Quote Memory

**Case:** 2026 Ivy AI Case Competition (Iowa State): *AI for Iowa: Improving Manufacturing Quoting with Artificial Intelligence*
**Product:** Quote Memory: Evidence-Weighted Quoting
**Format:** 9 slides for **two presenters**. Talk track about 6:30 plus a live demo of about 10:00, for about **16:30 total**,
leaving 3:30 for questions inside a 20-minute slot. For a 15-minute slot, skip Job 3 and the "Show the details"
moment (see the cut order below). Click-by-click demo: `demo/demo_script.md`. Concepts and glossary: `docs/PLAIN_ENGLISH.md`.

**Presenters:** **A** is technical and drives the demo (plays the estimator). **B** is business, tells the story, plays
the manager at the price checkpoint, and owns "why it matters."

**Ground rules for every slide**
- No industry statistics. Every number comes from our own build and is labeled: *synthetic* (from the generated shop history), *illustrative* (rates, ROI), or a *design parameter* (half-lives, sample counts). Nothing comes from real companies.
- Boone Creek Fabrication and all customers are **fictional**. All data is **synthetic**.
- Competitor claims stay general and fair (slide 8).
- Plain words on the slides: "typical cost", "how sure", "checkpoint", "shop notebook". Technical names (P10, P50, Monte Carlo) only appear if someone asks or the details switch is on.
- Visual language matches the process maps: **red = bottleneck, blue = AI, gold = human checkpoint, green = memory.**

| # | Slide | Lead | Time | Running total |
|---|---|---|---|---|
| 1 | Hook | B | 1:00 | 1:00 |
| 2 | The problem in Iowa | B | 1:00 | 2:00 |
| 3 | Current-state map | B | 1:00 | 3:00 |
| 4 | The idea and three rules | A | 1:00 | 4:00 |
| 5 | The five steps | A | 0:30 | 4:30 |
| 6 | Live demo | A + B | 10:00 | 14:30 |
| 7 | Why a shop would adopt it | B | 1:00 | 15:30 |
| 8 | Positioning | B | 0:30 | 16:00 |
| 9 | Limits, next steps, close | A then B | 0:30 | 16:30 |

**Cut order if time is short:** (1) the optional "Show the details" moment (-0:30), (2) Job 3 fast-track (-0:45),
(3) shorten the steel what-if (-0:30), (4) slide 8 positioning (-0:30). Never cut Checkpoint 1, Job 2 (it learned) or the
three rules.

---

## Slide 1: Hook (1:00), B

**On screen:** Title only: **Quote Memory: Evidence-Weighted Quoting**, with the case title underneath.

**Speaker notes:**
> [QUENTIN: 3-sentence Twisted Traction story about a quote burned by a missing detail or an old material price]

Transition: "Every small shop has a story like that. The estimator worked hard enough. The trouble is that the knowledge behind the quote lives in one person's head and a pile of old folders."

---

## Slide 2: The problem in Iowa (1:00), B

**On screen:**
- Small fab shops build the weldments, brackets, guards, and frames that go into Iowa-built ag and construction equipment
- One senior estimator carries the quoting know-how
- Customers expect fast, accurate quotes, and every miss comes straight out of margin

**Speaker notes:**
"Meet Boone Creek Fabrication, a made-up 40-person job shop in central Iowa. It builds custom brackets, guards and frames for farm and construction equipment makers. Like a lot of shops its size, it has one senior estimator who knows which jobs ran long and why, and that person is getting close to retirement. The case names the hard parts well: requests arrive incomplete or contradictory, supplier prices keep changing, and the most valuable knowledge was never written down. A chatbot doesn't fix that. The fix has to change how information moves through the whole quote."

---

## Slide 3: Current-state map (1:00), B

**On screen:** The current-state diagram from `docs/process_current.md`, with its red bottleneck nodes.

**Speaker notes:**
"Here's how Boone Creek quotes today. A request lands in the inbox and waits for the one estimator. They chase missing info by email, dig through old job folders for something similar, and build the parts list and shop steps in Excel. Then come the risky parts, in red. Welding and setup hours are guesses. First-time fixtures get forgotten. The steel price might be months old. Markup goes on by feel, the owner glances at it, and it's sent.
The biggest red box is at the bottom. When the job runs, the real hours go into the system and nobody ever compares them to the estimate. So the shop makes the same miss again next time."

---

## Slide 4: The idea and three rules (1:00), A

**On screen (large):**
> *Every number in the quote shows its sources, and how much you trust it depends on how good those sources are.*

Below it, three short lines:
1. **The AI never sets a cost or a price.** It reads and drafts. The math is ordinary arithmetic.
2. **A person decides, twice.** Checkpoint 1: the estimator approves the plan. Checkpoint 2: the manager approves the price.
3. **Nothing is silent.** Unsure means Low. Assumed means printed on the quote. Overridden means a reason is saved.

**Speaker notes:**
"That's the whole idea. A weld-hour estimate backed by two recent real jobs from nearly identical brackets, you can trust. One backed only by a rule of thumb, you can't. Quote Memory shows you which is which on every line, with High, Medium and Low, and it prices the uncertainty instead of hiding it. And three rules keep it honest: the AI only reads and drafts, a person decides twice, and nothing is silent."

---

## Slide 5: The five steps (0:30), A

**On screen:** The five-step strip (Read the request, Plan the work, Cost it, Set the price, Send the quote) over the future-state diagram from `docs/process_future.md`. The two gold checkpoints are highlighted, and a dashed green arrow runs from the checkpoints back to the **shop notebook**.

**Speaker notes:**
"These are the same seven stages the case lays out, grouped into five steps you'll see in the app. Read the request. Plan the work from the closest past job. Cost it, line by line, with the evidence. Set the price. Send the quote. Two human checkpoints sit in the middle, and anything a person changes goes into the shop notebook, which comes back as evidence on the next similar request. That dashed green arrow is how it learns."

---

## Slide 6: Live demo (10:00), A + B

**On screen:** Switch to the app. Backup slide text: **Live demo:** Job 1 (Cedar Valley Equipment, new revision of a bracket with visible welds) → Job 2 (Hawkeye Loader Works, first-time bracket) → Job 3 (Loess Hills Machinery, repeat mounting plate).

**Pre-flight (before the pitch starts):** Click **Start over**. Presentation mode is `DEMO_MODE=offline` (saved answers, no internet or key needed). Keep the backup screen recording queued.

| Beat | Time | Who | Click | Say |
|---|---|---|---|---|
| **Step 1 · Read the request** | 1:45 | A, B adds | Show the email, the "What we understood" table (each row quotes the email) and the two things to sort out. Choose **Assume and quote** on the color, then on the quantity. | "The AI only copies words, and every row shows its sentence. It caught 250 vs 200 and the missing color. Assume, and it's printed on the quote." |
| **Step 2 · Plan the work (Checkpoint 1)** | 2:00 | A | Closest past job (J-1042), what's different, then **No, we need to build a new one**, type the reason, **Approve the plan**. | "We start from what the closest job really took. The estimator decides, and his reason goes in the notebook." |
| **Step 3 · Cost it** | 1:45 | A | Open the weld line: sources, the 0.70 to 0.94 hours, the lesson from past jobs. | "Click any number and see where it came from. Welds that show always run long, the data says so." |
| **Steel what-if** | 0:45 | A clicks, B asks | Sidebar slider to **90** days, then back to 0. | "Old steel price: less sure, wider range, quote good for 15 days instead of 30." |
| **Step 4 · Set the price (Checkpoint 2)** | 1:15 | B clicks | Three prices with chance of winning and profit; **Approve the price**. | "Lower wins more, higher earns more. The manager decides." |
| **Step 5 · Send the quote** | 0:30 | B | Checklist and the quote. | "An honest, finished quote in minutes. A person presses send." |
| **Job 2 · It learned** | 1:00 | A then B | Job 2, Step 3: the green "Learned from an earlier quote" box. | "Yesterday's judgment is today's evidence." |
| **Job 3 · Fast track** | 0:45 | B | Job 3, Step 1: green Fast track badge. | "Easy quotes go out fast, so the estimator's time goes to hard ones." |
| **Show the details (optional)** | 0:30 | A | Sidebar switch. | "For anyone who wants to check our work." |

**If something breaks:** set `DEMO_MODE=offline` and keep going. If the app itself fails, play the backup recording and narrate the same beats. The 60-second fallback is in `demo/demo_script.md`.

---

## Slide 7: Why a shop would adopt it (1:00), B

**On screen:**
- **Designed to run on one shop PC:** a local model plus local search, so customer prints never leave the building. The model is a config switch (this demo uses a hosted model)
- **Starts from a spreadsheet export of past jobs**, no software swap
- **Low cost:** an existing PC plus open models
- **Illustrative ROI** box: headline from `docs/roi.md`, labeled **ILLUSTRATIVE, NOT BENCHMARKS**

**Speaker notes:**
"A 40-person shop won't rip out its software or send customer drawings to a cloud AI service. Quote Memory is designed to run on one desktop PC with an open model and read the job history the shop can already export as a spreadsheet. That matters to customers with confidential prints and to anyone handling controlled work. To be clear, that's a design advantage, not a compliance certification, and this demo uses a hosted model because our GPU machine fell through. On ROI, our one-pager uses illustrative inputs the shop can change: requests per month, estimator hours before and after, and loaded estimator cost. The bigger payoff doesn't fit in a spreadsheet: faster answers, fewer margin-killing misses, and the senior estimator's judgment saved as reusable evidence before retirement."

---

## Slide 8: Positioning (0:30), B

**On screen:**

| Player | Known for (general) |
|---|---|
| Paperless Parts | Intake and quoting workflow platform |
| Xometry | Prices jobs for its own manufacturing marketplace |
| Arzana | Custom AI builds for larger shops |
| CADDi | Drawing similarity search |
| Toolpath | CAD-based CNC estimating |

**Quote Memory:** the transparent, evidence-weighted layer for smaller shops.

**Speaker notes:**
"These are strong products, and we haven't benchmarked any of them. We're describing their general focus, not their feature lists. Our lane is narrower. We give a small fab shop a quoting layer where every number shows its sources, confidence comes from the quality of those sources, and it can run on the shop's own PC using its own history. It can sit next to whatever tools a shop already uses."

---

## Slide 9: Limits, next steps and close (0:30), A then B

**On screen:**
- **Today:** synthetic data for a fictional shop, a deliberately small shop model (5 job types, 3 materials, 5 shop steps) → **next:** a real shop's job history
- Reading drawings directly (out of scope for the prototype)
- Tune the local model on a shop's own requests
- Pilot with a CIRAS-supported Iowa manufacturer

**Speaker notes:**
A: "We're upfront about the limits. Everything today runs on synthetic data and a deliberately small shop, so the next step is a real shop's history, then reading drawings directly."
B: "We'd like to pilot with a CIRAS-supported Iowa manufacturer. To sum it up: every number shows its sources, and how much you trust it depends on how good those sources are. Thank you. We're happy to take questions."

---

**Q&A prep:** see `docs/qa.md` (cold start, hallucinated numbers, why these weights, security, plain-English questions) and the short answers in `docs/PLAIN_ENGLISH.md`.
