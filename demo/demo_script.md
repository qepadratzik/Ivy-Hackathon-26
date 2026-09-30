# Demo script: Quote Memory (live demo about 10 minutes, inside a 15-20 minute pitch)

Two presenters. **Presenter A** (technical) drives the mouse and plays the **estimator**. **Presenter B** (business)
tells the story, plays the **manager** at the price checkpoint, and explains why it matters. Every "Say" line below
is plain English on purpose: if you can say it to a friend who has never seen a machine shop, you are doing it right.

Read `docs/PLAIN_ENGLISH.md` first (10 minutes). It has the glossary and the five-minute version of this story.

**Time budget for the whole pitch (target about 16:30, hard stop 20:00):**

| Part | Who | Time |
|---|---|---|
| Hook, problem, today's process, the idea (slides 1 to 5) | B then A | 4:30 |
| **Live demo** (this script, including the optional details moment) | A + B | **about 10:00** |
| Why a shop would adopt it, positioning, limits, close (slides 7 to 9) | B then A | 2:00 |
| Buffer and questions | both | 3:30 or more |

**If you only have 15 minutes:** skip Job 3, skip "Show the details" and the on-the-spot request, shorten the steel what-if. The demo drops to about 7:30.

---

## Before you go on stage (off stage, 2 minutes)

1. Start the app at least 2 minutes early: `streamlit run app.py` (the first load builds a search index, 6 to 16 seconds).
   Browser full screen, zoom 90 to 100%.
2. Presentation mode: in `.env` set `DEMO_MODE=offline` (see `docs/LOCAL_RUN.md`). It uses saved answers only, so it
   needs no internet and no key. The numbers are identical in every mode because the AI never touches the math.
3. Click **Start over** (bottom of the left sidebar). Check this starting picture:
   - **Job 1 · New bracket order (Cedar Valley)** is selected.
   - The step picker reads **1 · Read the request (2 open questions)**.
   - Top strip: **$151.48** typical cost, **$198.44** suggested price, **13 of 14 lines solid**, "needs a look: Fixture build (one-time)".
   - Sidebar: **Show the details** is off, the steel slider is at **0**, **Shop notebook: 0 saved note(s)**.
   - Step 1 says *read by ...*: with the hosted model warmed it must read **a saved copy of claude-haiku-4-5's reading**. If it
     says *no AI model* or *hand-checked backup*, the model answers were not saved on this PC: either re-run the warm step in
     `docs/LOCAL_RUN.md` or say "hand-checked copy of what the AI reads" out loud. The numbers do not change either way.
   If anything looks off, press F5 once, then **Start over** again.

Numbers below come from the synthetic data and are the same on every run. The AI only reads and drafts text, so if a
number on your screen differs from this script by more than a cent, stop and press **Start over**.

---

## Job 1: the whole quote, start to finish (about 8 minutes)

### Step 1 · Read the request (1:45)
**Screen:** Job 1, step **1 · Read the request**.

**Point at:**
- The red **Full review** badge and its reason: *the welds will show, and past jobs like this took longer than quoted;
  it is a new revision of a part we have built before.*
- Left: the customer's email. Right: **What we understood**, a table where every row has **How sure** (High / Medium /
  Low) and **Where we saw it**, a quote copied from the email.
- **Things to sort out**: *Quantity conflict: email says 250, spec sheet says 200* and *Powder coat color not specified*.
- The yellow delivery check: *tight but doable (4 days to spare)*.
- (optional, 10 s) Open **Draft email to the customer**: one email with both questions.

**Say (B):** "A customer emails a request for a hitch bracket. Today, one senior estimator reads this, digs through old
folders and guesses. Here the AI reads the email for us, but it is only allowed to copy words. Every row shows the
sentence it came from, so nothing is made up."

**Say (A):** "It also caught two problems a person might miss: the email says 250 parts but the spec sheet says 200, and
nobody said what color. We can ask the customer, or assume and keep going."

**Click (A):** on the **Powder coat color** card choose **Assume and quote**. Then on the **Quantity conflict** card
choose **Assume and quote**.

**Watch (the blue "What just changed" box and a small pop-up top right):**
- After the color: *Typical cost per part: $151.48 to $151.75 (+0.2%) ... Suggested price: $198.44 to $198.79.*
- After the quantity: *$151.75 to $152.14 (+0.3%) ... Suggested price: $198.79 to $199.31.*

**Say (B):** "When we assume, we say so on the quote and add a small safety cushion. Each choice moves the numbers on the
spot, and the box tells us exactly why."

### Step 2 · Plan the work, Checkpoint 1 (2:00)
**Click (A):** the step picker, **2 · Plan the work**.

**Point at:**
- **Closest past job: J-1042 · CVE-HB-4410 Rev B · 200 parts · we won it · we have the real hours it took.** "Very close match."
- **How this order is different from that job**: a new revision (Rev C), 250 parts in batches of 50 versus 200, and steel
  is 14% more expensive than when that job was quoted.
- The fixture box: **Does the old fixture still fit the new revision?**

**Say (A):** "The system found our closest past job, the Rev B we built in the spring, and copied its parts list and shop
steps using the hours it really took, not the hours we guessed. The customer changed the design to Rev C, so the
system asks the estimator one good question: does the old fixture, the jig that holds the parts while we weld, still fit?"

**Click (A):** **No, we need to build a new one** (the hours box fills with **6.00**, the shop's usual time). Click in
**Why?** and type: `Rev C moved the hole pattern, so the old fixture will not fit.` Then click **Approve the plan**.
(Optional, 5 s: click **Approve the plan** *before* typing the reason to show that it refuses.)

**Watch:** *because the estimator changed the plan: Fixture build (one-time) to 6. Typical cost per part: $152.14 to
$154.30 (+1.4%). Very likely between $143.11-$161.72 to $145.20-$164.02. Suggested price: $199.31 to $202.13.
Confidence changed on: Fixture build (one-time): Low to High.* The top strip now says **14 of 14 lines solid**.

**Say (B):** "This is the first of two human checkpoints. The estimator stays in charge. He said why he changed it, and that
reason just went into our **shop notebook** (open it in the left sidebar: 1 saved note). Remember it, it comes back
in a minute."

### Step 3 · Cost it (1:45)
**Click (A):** **3 · Cost it**. The right-hand panel already shows **Fit & weld: run time (per part)**.

**Point at:**
- The headline: *About $154.30 per part, very likely between $145.20 and $164.02.*
- The table: every line has a colored **How sure** (High / Medium / Low), an estimate and a cost per part. **Notes** says
  *edited*, *learned* or *lesson* where it applies. To open a line, tick the small box at the left of its row (or use the
  dropdown above the panel): the panel shows what it is **based on** ("3 past jobs, 3 shop notes, 3 past quotes").
- Right panel: **0.947 hours per part** and the sentence *we found 11 pieces of evidence ... they mostly agree, so we are
  high confidence in this number.* Open **What the shop wrote down** for the real notes.
- Scroll to **Lessons from our history**: *Visible (cosmetic) welds take longer than quoted: on 20 past jobs with visible
  welds, welding took 1.35x the quoted hours (ordinary welds: 1.02x), so this quote plans for the extra time.*
- The fixture row: **6 hours, once**, about **$2 per part** because it is spread over 250 parts.

**Say (A):** "Open any line and you see where the number came from. The last time we quoted this weld we said 0.70 hours
and it took 0.94. The system noticed that welds that show always run long, found the same thing on 20 jobs, and
plans for it. That used to live in one person's head."

**Say (B):** "And notice it never says 'trust me'. Every line says how sure it is, and why."

### What if the steel quote gets old? (0:45)
**Click (A):** left sidebar, slider **What if our steel price quote were older? (add days)** to **90**. Drag it with the mouse
(do not hold an arrow key: fast key repeats can skip the last value).

**Watch:** *because our newest steel price quote is now 90 days older. Typical cost per part: $154.30 to $155.34
(+0.7%). Very likely between $145.20-$164.02 to $145.58-$166.01. Suggested price: $202.13 to $203.50. Quote good for:
30 to 15 days. Confidence changed on: A36 plate: High to Low, A500 tube: High to Low.* In the table the two steel rows
turn red (Low).

**Say (B):** "Steel prices move. If our newest supplier price is three months old, the system trusts itself less, the range
gets wider, and the quote is only good for 15 days instead of 30. One change, everything downstream moves."

**Click (A):** slider back to **0** (the box says the steel quote is back to its real age).

### Step 4 · Set the price, Checkpoint 2 (1:15)
**Click (A):** **4 · Set the price**. **Hand the mouse to B.**

**Point at:** *Our planning cost is $159.16 per part: the typical cost ($154.30) plus a safety cushion ($4.86).* Then the
table:

| Choice | Price per part | Chance we win it | Profit per part if we win | Average profit per part quoted |
|---|---|---|---|---|
| Lower price | $193.64 | about 9 in 10 | $34.48 | $31.75 |
| **Recommended price** | **$202.13** | **about 8 in 10** | **$42.97** | **$34.74** |
| Higher price | $209.84 | about 6 in 10 | $50.68 | $31.79 |

(Profit per part if we win is the price minus the **planning cost** of $159.16, not minus the typical cost, so $202.13 minus
$159.16 is $42.97. Say it once if someone does the subtraction.)

**Say (B):** "Now the manager decides, and this is the part I like. Go low and we win more often but earn less each time. Go
high and we earn more when we win, but we win fewer. The middle price has the best average. The chance of winning comes
from how customers reacted to our past quotes. The AI does not pick a price. A person does."

**Click (B):** leave **Recommended price** selected, click **Approve the price**. (Optional, 10 s: pick **Another amount**,
type a much higher number, and point out that it demands a reason, which also goes in the notebook.)

### Step 5 · Send the quote (0:30)
**Click (A or B):** **5 · Send the quote**.

**Point at:** the checklist (*Done: Plan approved, Done: Price approved, Done: Customer questions answered (0 open)*),
the green **Ready to send**, and the quote: **$202.13** per part for batches of 50 ($197.00 for 100, $193.88 for 250), a
separate price if the total turns out to be 200, setup and the one-time **$510** fixture listed separately, **35 days**
lead time, **valid 30 days**, and the assumptions we printed (quantity per the email, black powder coat).

**Say (B):** "A customer-ready quote, with the assumptions written down, in minutes instead of days. A person still
presses send."

---

## Job 2: it learned (1:00)
**Click (A):** left sidebar, **Job 2 · Similar bracket, first time built (Hawkeye)**, then **3 · Cost it**. The right
panel opens on **Fixture build (one-time)**.

**Point at:**
- A blue note says *these are draft numbers, the estimator has not approved the plan yet*. That is expected: we are not
  approving Job 2 here.
- The blue box: *because the shop notebook now holds 1 saved note(s): this quote learned from one.*
- The green box: **Learned from an earlier quote (M-0001): Estimator note on Fixture build ... changed from 0 to 6.
  Reason: Rev C moved the hole pattern, so the old fixture will not fit.** It is counted as evidence next to real past
  fixture builds: **6.51 hours, High confidence.**
- **Lessons from our history**: *New welded parts without a fixture run long on setup: ... 1.90x the planned fit-up and
  weld setup (21 jobs) ...*
- Top strip: **13 of 14 lines solid, needs a look: Fit & weld: setup (once per batch)**.

**Say (A):** "Different customer, different part, first time we build it. The note our estimator wrote ten minutes ago
is now evidence on this quote, with his reason attached."

**Say (B):** "And it is honest about what it does not know: it flags the weld setup on a first build as the line to look
at. The typical cost barely moves here ($133.21 to $133.16) because history already agreed with him. The value is that the
reason is now saved for the next person. That is how the senior estimator's knowledge stays when he retires."

## Job 3: the easy one (0:45)
**Click (A):** **Job 3 · Repeat order (Loess Hills)**, then **1 · Read the request**.

**Point at:** green **Fast track** badge: *we have built this part before (3 earlier orders), standard tolerance, and a
small order (40 parts)*; no open questions; **8 of 8 lines solid**; typical **$42.62**, suggested **$56.26**.

**Say (B):** "Not every request needs the senior estimator. A clean repeat order is all green and goes out fast, so
his time goes to the hard jobs."

## Optional: "Show the details" (0:30)
**Click (A):** sidebar switch **Show the details**, then **3 · Cost it**.

**Point at:** the table now shows the score behind each source (*similarity x authority x recency*), and below it the
simulation: "we ran the job 2,000 times in a computer" with the low end, typical and high end marked. Step 4 shows the
profit curve.

**Say (A):** "For anyone who wants to check our work, the math is all here. Everyone else can leave it switched off."
Switch it off before you continue.

---

## Optional: "Try one of yours", an on-the-spot request (1:00 to 1:30)
Use this when a judge says "what about a different job?" or when you have time to spare. It needs no typing of emails.

**Click (A):** sidebar **Quick demo · fill in a request**. A short form opens. Pick anything the judge likes, for
example **Customer** Raccoon River Attachments, **What are we making?** Guard, **Material** 5052 aluminum sheet,
**Thickness** 1/8", **How many?** 60, **Batch size** 20, **Welding** Standard weld, **Finish** Powder, **Color** Not
stated. Click **Build this request**. (Leave **Part number** empty: that means a part we have never built.)

**Point at:** step 1 fills in at once: the customer's email and spec sheet were written from the form, the system read
them back, and because the color was "Not stated" it lists **Powder coat color not specified** as a question. Two
quick extras: tick **Make the spec sheet disagree on the quantity** before building to show the conflict catch, or type
`CVE-HB-4410 Rev D` as the part number to show "it is a new revision of a part we have built" from our history.

**Say (B):** "That's a job we made up thirty seconds ago. The same five steps run on it. Aluminum is rare in our history,
so watch step 3: it says it is less sure, which is the honest answer."

**Then:** walk the steps quickly (step 2 approve, step 3 click the aluminum line, step 4 approve). Each build gets its own
number, so a second build can learn from a note you saved on the first (for example by answering "No, we need to build a new
one" on a new revision such as `CVE-HB-4410 Rev D`).

---

## 60-second fallback (if the slot is cut or something misbehaves)
1. (10 s) Job 1, step 1: "The AI copies words from the email, with quotes. It caught 250 versus 200 and the missing color."
2. (15 s) Step 2: **No, we need to build a new one**, reason, **Approve the plan**: "the estimator decides, and his reason is saved."
3. (15 s) Step 3: fit and weld line: "every number shows its sources; welds that show run long."
4. (10 s) Steel slider to 90: "old steel price, less confidence, wider range, 15-day quote."
5. (10 s) Job 2, step 3: "it learned from the note."

If the app itself fails: play the backup screen recording, or show `docs/screens/` in order (01 to 13).

## Recovery moves
- Wrong state or a confusing box: sidebar **Start over** (F5 if anything still looks stale), then redo from Step 1.
- Plan approved by mistake: **Re-open the plan** (your choices are kept; the price approval resets, as it should).
- Do not take a live paste from a judge unless you have timed one on this PC. A pasted email with too little
  information shows "Not priced" on purpose. Pasted emails draft the reply from a template instantly.
- A slow model call means you are on a pasted request or the saved answers are missing: set `DEMO_MODE=offline`
  (after warming) or `MODEL_PROVIDER=mock` and restart Streamlit.

## One-line answers to have ready
- "Does the AI set the price?" No. The AI reads text and drafts an email. Every cost and price is ordinary arithmetic.
- "Who is responsible?" A person approves the plan and a person approves the price. Both leave a reason.
- "Is this real data?" No. The shop and customers are made up, so nothing private is involved.
- "What does the shop need?" Its past jobs as a spreadsheet export. No new software to replace.
- "Did it run on the shop's own computer?" The design is local-first, so prints never leave the building. This
  demo uses a hosted model (Claude Haiku 4.5) because our GPU machine fell through, and it only reads and drafts text.
