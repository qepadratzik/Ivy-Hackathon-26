# Quote Memory in plain English

Read this once (about 10 minutes) and you can explain the whole project to anyone, technical or not. It is written for
both presenters. Nothing here needs a computer science background.

> **Everything is made up.** Boone Creek Fabrication and all its customers are fictional, and all the data is
> synthetic. That is deliberate: nothing private is involved, and we say so out loud.

---

## 1. The 30-second story

A small metal shop gets a request from a customer: "Please quote me 250 of these brackets." To answer, someone has to
work out what the job will cost and what to charge. At most small shops that someone is **one senior estimator**. He
carries the answers in his head and in old folders: "welds that show always take longer," "we forgot the fixture last
time," "steel went up again." When he is busy, quotes are slow. When he retires, the knowledge leaves with him.

**Quote Memory is a helper that remembers.** It reads the customer's email, finds the closest job the shop has done
before, works out the cost line by line, and shows **where every number came from and how sure it is**. A person
approves the plan and a person approves the price. Whenever a person changes something and says why, the reason is
saved, and the **next** similar quote uses it.

One sentence to remember:

> **Every number in the quote shows its sources, and how much you trust it depends on how good those sources are.**

---

## 2. Three rules (say these out loud in the pitch)

1. **The AI never sets a cost or a price.** The AI only *reads* the email and *drafts* a message. All the arithmetic is
   ordinary, checkable math.
2. **A person decides, twice.** Checkpoint 1: the estimator approves the plan. Checkpoint 2: the manager approves the
   price. A person also sends the quote.
3. **Nothing is silent.** If the system is unsure, it says so (High / Medium / Low). If it assumes something, the
   assumption is printed on the quote. If a person overrides it, they must say why.

---

## 3. Words you will hear (glossary)

| Word | What it means |
|---|---|
| **RFQ** (request for quote) | The customer's email asking "how much for this?" |
| **Part** | One finished item, for example one hitch bracket. Costs and prices are per part. |
| **Parts list (BOM)** | What goes into one part: steel plate, steel tube, bolts, bushings, powder coat. |
| **Shop steps (routing)** | The work done in our shop, in order: Cut, Bend, Fit & weld, Drill & tap, Inspect & pack. |
| **Setup time** | Time to get ready, paid once per batch (for example 2.6 hours to fit up and set up the weld). |
| **Run time** | Time per part once running (for example 0.94 hours of welding per bracket). |
| **Batch / release** | How many parts we make at once. Setup is spread over the batch, so small batches cost more per part. |
| **Fixture** | A jig that holds the parts in place while we weld. A new design may need a new one. It is built once, not per batch. |
| **Visible (cosmetic) weld** | A weld that customers can see, so it has to look smooth. It takes longer than an ordinary weld. |
| **Revision (Rev B, Rev C)** | A new version of the same part drawing. "Rev C" moved the holes, so the old fixture may not fit. |
| **Closest past job** | The earlier job most like this one. We start from what it really took. |
| **Evidence** | Anything that backs a number: a past job's real hours, a past quote, a supplier's price, a shop note. |
| **How sure (High / Medium / Low)** | Our confidence in a number. High means plenty of recent, agreeing evidence. Low means thin, old, or disagreeing evidence. |
| **Typical cost** | Our best single estimate of what one part costs us to make. |
| **Very likely between $A and $B** | The realistic range around the typical cost. Wider means less sure. |
| **Planning cost** | Typical cost plus a **safety cushion**, because the real cost could come in higher. We price from this. |
| **Safety cushion** | A small amount added to cover the things we are guessing. |
| **Chance we win it** | How likely the customer is to say yes at a given price, learned from how customers reacted to our past quotes. Shown as "about 8 in 10". |
| **Profit if we win / Average profit** | Price minus planning cost. Average profit multiplies that by the chance of winning. |
| **Checkpoint** | A step where a person must approve before we move on. |
| **Shop notebook** | Where the reasons people give are saved. The next similar quote reads them as evidence. |
| **Fast track / Standard review / Full review** | How much human attention a request needs. A clean repeat order is Fast track. |
| **Synthetic data** | Data we generated for a pretend shop. Real patterns, made-up jobs. |

---

## 4. The made-up shop (what the numbers are built from)

**Boone Creek Fabrication**, about 40 people in central Iowa. It builds for farm and construction equipment makers.

- **5 kinds of job:** hitch bracket, guard, frame, mounting plate, tube assembly.
- **3 materials:** A36 steel plate, A500 steel tube, 5052 aluminum sheet. (We have done almost no aluminum, so the
  aluminum price line shows a lower confidence than the steel lines. That is the system being honest.)
- **5 shop steps:** Cut, Bend, Fit & weld, Drill & tap, Inspect & pack. Powder coat is done by an outside vendor.
- **158 past jobs** over two years, 7 fictional customers, about 6 in 10 quotes won.
- **Hidden lessons in the history.** We planted these so there is something real to find. The system finds them with
  simple statistics on the past jobs (not with AI):
  - Jobs with visible welds took about **35% longer** to weld than quoted (20 jobs).
  - First-time welded parts without a fixture took about **1.9 times** the planned setup (21 jobs).
  - Bending thick plate needed rework about **3 times in 10**.
  - A couple of customers, Prairie Implement especially, mostly buy when we are cheap.
  - Steel rose about **14%** from the first six months of the history to the last six.

---

## 5. The five steps (what the screen shows and what to say)

The app walks through five steps. The picker above the content shows each step and its status, for example
*2 · Plan the work (needs approval)*. The box at the top always shows three numbers:

- **Typical cost per part**, with "very likely between $A and $B"
- **Price we suggest**, with "we would win it about 8 times in 10"
- **How sure are we?**, for example "13 of 14 lines solid"

### Step 1 · Read the request
- **You see:** the customer's email, a table of what the AI understood (each row with a quote from the email and a
  High / Medium / Low), and a list of **things to sort out**: a quantity that disagrees (250 in the email, 200 on the
  spec sheet) and a missing color.
- **Say:** "The AI reads the email but may only copy words, and every row shows the sentence it came from. It catches
  what a busy person misses. For each problem we can ask the customer or assume an answer and say so on the quote."
- **Underneath:** the model copies text into fields with a verbatim quote, and ordinary code checks the quote really
  appears in the email. Gaps come from simple rules.

### Step 2 · Plan the work (Checkpoint 1)
- **You see:** the closest past job, how this order differs from it, and one question: *Does the old fixture still fit
  the new revision?* Then the plan, a table of parts and shop steps the estimator can change.
- **Say:** "We start from what the closest job really took, not from guesses. The estimator is in charge: he says no,
  the old fixture won't fit, it takes 6 hours, and he types why. That reason goes in the notebook."
- **Underneath:** the plan copies the closest job's parts list and real hours, then applies rules for what differs
  (quantity, steel thickness, finish, new revision). Nothing is priced yet.

### Step 3 · Cost it
- **You see:** a table of every cost line with a colored High / Medium / Low, what we estimate, and what it is based on.
  Click a line to see exactly which past jobs and notes back it, and any **lesson from our history**.
- **Say:** "Nothing is a black box. Click any number and see where it came from. Last time this weld was quoted at 0.70
  hours and it took 0.94. Welds that show always run long, the data says so, and the quote plans for it."
- **Underneath:** for each line, every piece of evidence is weighted by **how similar** it is, **how trustworthy** its
  type is (real hours beat a guess), and **how recent** it is. Steel prices go stale fast, so old steel quotes count
  much less. The range comes from running the job 2,000 times in a computer with each line wobbling within its range.

### Steel what-if (sidebar)
- **Say:** "What if our steel price is three months old? Confidence drops, the range widens, and the quote is only good
  for 15 days instead of 30. One change, everything downstream moves."

### Step 4 · Set the price (Checkpoint 2)
- **You see:** three prices with the chance of winning and the profit at each, and the manager's choice.
- **Say:** "Lower wins more often but earns less. Higher earns more but wins less. The recommended one has the best
  average. The manager decides, and anything outside the recommended range needs a written reason."
- **Underneath:** a simple model learned from our past quotes how the chance of winning falls as price rises. It picks
  the price with the best average profit above a minimum margin.

### Step 5 · Send the quote
- **You see:** a checklist (plan approved, price approved, questions answered) and the customer-ready quote with
  prices by batch size, lead time, how long the price is good for, and every assumption written down.
- **Say:** "A finished, honest quote in minutes. A person presses send."

---

## 6. The three demo jobs

| Job | What it shows | Headline numbers |
|---|---|---|
| **Job 1 · Cedar Valley** (new revision of a bracket) | The whole flow: gaps, the fixture decision, evidence, stale steel, pricing, the quote | Typical cost $151.48 at the start, $154.30 after the decisions. Suggested price $202.13, about 8 in 10 to win. |
| **Job 2 · Hawkeye** (bracket, first time built) | **It learned:** the note from Job 1 shows up as evidence, with its reason | Typical cost $133.16. The weld setup is flagged as the line to check. |
| **Job 3 · Loess Hills** (repeat mounting plate) | **Fast track:** a clean repeat is all green | Typical cost $42.62, suggested price $56.26, 8 of 8 lines solid. |

**Want a different job on the spot?** In the sidebar, choose **Quick demo · fill in a request**, pick a customer, what we are
making, material, thickness, quantity, batch size, welding, finish and color, and click **Build this request**. The app writes the
customer's email and spec sheet from your choices and runs the same five steps. Two extras: leave the color on "Not stated"
to see a question get raised, or tick "Make the spec sheet disagree on the quantity" to see a conflict caught. **Paste a
customer email** still works if you would rather type a whole email.

---

## 7. Who says what (two presenters, about 16:30 plus questions)

**Presenter A (technical)** drives the mouse and plays the estimator. **Presenter B (business)** tells the story, plays
the manager at Checkpoint 2, and owns the "why it matters." Click-by-click detail: `demo/demo_script.md`. Slide
details: `docs/deck_outline.md`.

| Time | Part | Lead |
|---|---|---|
| 0:00 to 1:00 | Hook: a quote that went wrong (your own story goes in the placeholder in `docs/deck_outline.md`) | B |
| 1:00 to 2:00 | The problem in Iowa: one estimator, retirement risk | B |
| 2:00 to 3:00 | How quoting works today (the red boxes are the problems) | B |
| 3:00 to 4:30 | The idea, the three rules, the five steps | A |
| 4:30 to 6:15 | Demo Step 1: read the request | A, B adds the "why" |
| 6:15 to 8:15 | Demo Step 2: plan the work (Checkpoint 1, the fixture decision) | A |
| 8:15 to 10:00 | Demo Step 3: cost it | A |
| 10:00 to 10:45 | Steel what-if | B asks, A clicks |
| 10:45 to 12:30 | Demo Steps 4 and 5: price (B clicks Checkpoint 2) and the quote | B |
| 12:30 to 14:15 | Job 2 (it learned) and Job 3 (fast track) | A then B |
| 14:15 to 14:45 | Optional: "Show the details" | A |
| 14:45 to 16:00 | Why a shop would adopt it, who else is out there | B |
| 16:00 to 16:30 | Limits, next steps, close | A then B |
| 16:30 to 20:00 | Buffer and questions | both |

**If you run long:** drop Job 3, then the "Show the details" moment, then shorten the steel what-if. Never drop
Checkpoint 1, Job 2 (the learning), or the three rules.

**Hand-offs:** B hands A the mouse at "let's look at a real request." A hands B the mouse at Step 4 so B approves the
price as the manager. It makes the two-checkpoint point without saying it.

---

## 7b. The numbers worth memorizing

- **$151.48** typical cost at the start of Job 1, **$154.30** after the decisions.
- **6 hours** for the new fixture, charged once ($510 total, about **$2 per part**).
- **0.70 to 0.94** hours: what the weld was quoted at last time versus what it really took.
- **35%**: how much longer visible welds take (20 past jobs).
- **30 to 15 days**: how long the quote is good for when the steel price quote is 90 days old.
- **$202.13** suggested price, **about 8 in 10** chance of winning.

---

## 8. Simple questions and simple answers

**Is this just ChatGPT writing quotes?**
No. The AI only reads the email and drafts a message. The costs and prices are ordinary math on the shop's own history,
and every number shows its sources.

**What if the AI reads something wrong?**
It has to quote the sentence it got each value from, and code checks the sentence really is in the email. If it cannot
find support, the value is marked Low confidence with a warning, and if it is something we need to price, it becomes a
question for the customer.

**Who is responsible if the price is wrong?**
A person approves the plan and a person approves the price. The tool's job is to make their decision better informed,
with the evidence on screen.

**How does it "learn"?**
Not by retraining a model. Every time a person changes something and says why, the reason is saved in the shop
notebook. The next similar quote reads it as one more piece of evidence, weighted like the rest.

**What does High / Medium / Low mean?**
How much good evidence backs a number. High: plenty of recent, agreeing evidence. Low: little, old, or conflicting.

**Why only five job types, three materials and five shop steps?**
On purpose: it keeps the demo clear and matches a small shop. The method does not depend on the count. Adding a shop
step is one new row in a settings table.

**Is this real data?**
No. The shop, customers and history are synthetic, so nothing private is involved. With a real shop we would start
from its own past-job spreadsheet and check the settings against what really happened.

**Does a shop have to replace its software?**
No. It starts from a spreadsheet export of past jobs.

**Did it run on the shop's own computer?**
The design is local-first: a model on one shop PC, so customer prints never leave the building. This demo uses a hosted
model (Claude Haiku 4.5) because our GPU machine fell through. The model only reads and drafts text, so the numbers
are identical either way.

**What would you do next?**
Try it on a real shop's history, read drawings directly, and pilot with an Iowa manufacturer.
