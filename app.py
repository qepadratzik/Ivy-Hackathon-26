"""Quote Memory (Streamlit UI): a guided 5-step walk from a customer's email to a finished quote.

    streamlit run app.py

Plain language on purpose: the numbers, sources and charts are all there, but the "Show the details"
switch in the sidebar keeps them out of the way until someone asks. All data is synthetic; Boone Creek
Fabrication and every customer are fictional. One state dict lives in st.session_state["qm"]; the
pipeline is a pure function of it.
"""
from __future__ import annotations

import html
import json
from collections import Counter

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from qm import config, intake, llm, memory, pipeline, plain, pricing, quick, quote_html, store
from qm.data_gen import frac

st.set_page_config(page_title="Quote Memory", layout="wide", initial_sidebar_state="expanded")

GREEN, YELLOW, RED, GREY, BLUE = "#1e8e3e", "#c98a00", "#d93025", "#6b7280", "#1a5fb4"
CHIP = {"green": GREEN, "yellow": YELLOW, "red": RED}
SOFT = {"green": "#e7f5ec", "yellow": "#fff6e0", "red": "#fdeceb"}
ASK, ASSUME = "Ask the customer", "Assume and quote"
FIX_YES, FIX_NO = "Yes, the old fixture still fits", "No, we need to build a new one"
STEPS = ["1 · Read the request", "2 · Plan the work", "3 · Cost it", "4 · Set the price", "5 · Send the quote"]
JOB_LABELS = {"RFQ-A": "Job 1 · New bracket order (Cedar Valley)",
              "RFQ-B": "Job 2 · Similar bracket, first time built (Hawkeye)",
              "RFQ-C": "Job 3 · Repeat order (Loess Hills)", "QUICK": "Quick demo · fill in a request",
              "PASTE": "Paste a customer email"}
CAT_ORDER = {"material": 0, "purchased": 1, "outside": 2, "labor": 3}
CAT_LABEL = {"material": "Material", "purchased": "Bought-in parts", "outside": "Outside work", "labor": "Shop time"}
SRC_PLURAL = {"actual": ("past job", "past jobs"), "past_quote": ("past quote", "past quotes"),
              "note": ("shop note", "shop notes"), "override": ("estimator note", "estimator notes"),
              "pattern": ("lesson", "lessons"), "supplier_quote": ("supplier price", "supplier prices"),
              "shop_default": ("shop rule of thumb", "shop rules of thumb")}
FIELD_CHIP = {"high": "green", "medium": "yellow", "low": "red"}

st.markdown(f"""
<style>
.block-container {{padding-top: 2.6rem; padding-bottom: 3rem;}}
.qm-kpis {{display:flex; gap:12px; flex-wrap:wrap; margin:0.4rem 0 0.6rem 0;}}
.qm-kpis div {{flex:1; min-width:200px; border:1px solid #e4e7ec; border-radius:10px; padding:10px 14px; background:white;}}
.qm-kpis span {{display:block; color:#667085; font-size:0.82rem;}}
.qm-kpis b {{font-size:1.65rem; color:#101828;}}
.qm-kpis i {{font-style:normal; color:#667085; font-size:0.85rem;}}
.qm-title {{font-size:1.4rem; font-weight:700; margin:0; line-height:1.3;}}
.qm-chip {{display:inline-block; padding:1px 9px; border-radius:10px; color:white; font-size:0.78rem;
           font-weight:600; white-space:nowrap;}}
.qm-badge {{display:inline-block; padding:3px 12px; border-radius:14px; color:white; font-weight:700;}}
.qm-banner {{border-left:6px solid {BLUE}; background:#eef4ff; padding:10px 14px; border-radius:6px; margin:0.4rem 0 0.8rem 0;}}
.qm-banner b.up {{color:{RED};}} .qm-banner b.down {{color:{GREEN};}} .qm-banner b.neutral {{color:{BLUE};}}
.qm-mail {{white-space:pre-wrap; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:0.8rem;
           background:#f8fafc; border:1px solid #e5e7eb; border-radius:6px; padding:10px; max-height:420px; overflow:auto;}}
table.qm-t {{width:100%; border-collapse:collapse; font-size:0.9rem;}}
table.qm-t td, table.qm-t th {{border-bottom:1px solid #eef0f3; padding:6px 8px; text-align:left; vertical-align:top;}}
table.qm-t th {{color:#475467; font-weight:600;}}
table.qm-t tr.rec td {{background:#e7f5ec; font-weight:600;}}
.qm-small {{color:#667085; font-size:0.82rem;}}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- helpers
def chip(level: str, text: str) -> str:
    return f'<span class="qm-chip" style="background:{CHIP.get(level, GREY)}">{html.escape(text)}</span>'


def mailbox(text: str) -> str:
    """Pre-formatted text box that survives Streamlit's markdown (no blank lines inside the HTML block)."""
    return "<div class='qm-mail'>" + html.escape(str(text)).replace("\n", "<br>") + "</div>"


def money(x: float) -> str:
    return f"${x:,.2f}"


def esc(s: str) -> str:
    """Escape $ so Streamlit markdown doesn't treat '$a ... $b' as LaTeX math."""
    return str(s).replace("$", "\\$")


def fmt_value(l: dict, v: float | None = None) -> str:
    v = l["value"] if v is None else v
    u = l["unit"]
    if u == "$/lb":
        return f"${v:,.3f} per lb"
    if u == "$/ea":
        return f"${v:,.2f} each"
    if u == "hr/lot":
        return f"{v:.3g} hours per batch"
    if u == "hr/unit":
        return f"{v:.3g} hours per part"
    if u == "hr/order":
        return f"{v:.3g} hours, once"
    return f"{v:.3g} {u}"


def fmt_range(l: dict) -> str:
    lo, hi, u = l["low"], l["high"], l["unit"]
    if u == "$/lb":
        return f"${lo:,.3f} to ${hi:,.3f} per lb"
    if u == "$/ea":
        return f"${lo:,.2f} to ${hi:,.2f} each"
    suffix = {"hr/lot": " per batch", "hr/unit": " per part", "hr/order": ", once"}.get(u, "")
    return f"{lo:.3g} to {hi:.3g} hours{suffix}"


def pct_text(pct: float) -> str:
    return "about the same" if abs(pct) < 0.05 else f"{pct:+.1f}%"


def field_text(name: str, v) -> str:
    if v is None:
        return "not stated"
    if name == "thickness_in":
        return f'{frac(float(v))}" ({float(v):.3f} in)'
    if name == "cosmetic_weld":
        return "yes, the weld will show (cosmetic)" if v else "no, standard weld"
    if name == "finish":
        return str(v).replace("_", " ")
    if name == "due_date":
        return f"{v:%a %b %d, %Y}"
    if name == "part_family":
        return plain.FAMILY.get(str(v), str(v).replace("_", " "))
    if name == "material":
        return plain.MATERIAL.get(str(v), str(v))
    return str(v)


@st.cache_resource(show_spinner="Loading the shop's history (the first run also sets up a small search index)...")
def boot() -> dict:
    store.vector_store()
    pricing.win_model()
    return intake.load_demo_rfqs()


def K(name: str) -> str:
    """Widget key for the current 'generation'. Reset bumps the generation so the browser drops every old
    widget (and its remembered value) and draws fresh ones with their defaults."""
    gen = st.session_state.get("_gen", 0)
    return name if gen == 0 else f"{name}~{gen}"


def reset_demo() -> None:
    memory.reset_memory()
    pipeline.clear_caches()
    gen = st.session_state.get("_gen", 0) + 1
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.session_state["_gen"] = gen


def S() -> dict:
    if "qm" not in st.session_state:
        st.session_state.qm = {"rfq_states": {}, "last": {}, "banner": {}, "g1_ver": {}, "ledger_sel": {},
                               "paste": None, "quick": None, "quick_n": 0}
    return st.session_state.qm


def mem_signature() -> str:
    m = memory.list_memory()
    return f"{len(m)}:{m.doc_id.iloc[-1] if len(m) else ''}"


def cause_of_change(old: dict, new: dict) -> list[str]:
    """Plain-English reasons the numbers moved."""
    c = []
    ops, nps = old["ps"], new["ps"]
    for gid in set(ops["gap_actions"]) | set(nps["gap_actions"]):
        a, b = ops["gap_actions"].get(gid, "ask"), nps["gap_actions"].get(gid, "ask")
        if a != b:
            c.append(f"you chose to {'assume an answer for' if b == 'assume' else 'ask the customer about'} "
                     f"\"{gid.replace('_', ' ')}\"")
    if ops["gate1_edits"] != nps["gate1_edits"] or ops["gate1_excluded"] != nps["gate1_excluded"] \
            or ops["gate1_approved"] != nps["gate1_approved"]:
        lab = {l["key"]: plain.line_label(l) for l in new["res"]["proposal"]["lines"]}
        eds = [f"{lab.get(k, k)} to {v['value']:.3g}" for k, v in nps["gate1_edits"].items()]
        eds += [f"removed {lab.get(k, k)}" for k in nps["gate1_excluded"]]
        c.append("the estimator changed the plan: " + ", ".join(eds) if eds else "the estimator approved the plan")
    if ops["material_age_days"] != nps["material_age_days"]:
        c.append(f"our newest steel price quote is now {nps['material_age_days']} days older"
                 if nps["material_age_days"] else "the steel price quote is back to its real age")
    if old["mem"] != new["mem"]:
        learned = any(e["source_type"] == "override" and e["ref"] != "This quote (Gate 1)" and e["counted"]
                      for l in new["res"]["ledger"] for e in l["evidence"])
        if learned or not c:
            c.append(f"the shop notebook now holds {new['mem'].split(':')[0]} saved note(s)"
                     + (": this quote learned from one" if learned else ""))
    return c


# ---------------------------------------------------------------- boot + sidebar
RFQS = boot()
st_ = S()

with st.sidebar:
    st.markdown("## Quote Memory")
    st.caption("Helps **Boone Creek Fabrication** (a made-up shop) quote faster and more accurately by "
               "remembering what past jobs really took.")
    pick = st.radio("Which job are we quoting?", list(RFQS) + ["QUICK", "PASTE"],
                    format_func=lambda k: JOB_LABELS.get(k, k), key=K("rfq_pick"))
    rfq = None
    if pick == "QUICK":
        with st.form(K("qd_form")):
            st.caption("Type in any job and we build the customer's email and spec sheet for you.")
            qd_customer = st.selectbox("Customer", list(store.base_tables()["customers"].name), key=K("qd_customer"))
            qd_family = st.selectbox("What are we making?", list(quick.FAMILY_PHRASE), format_func=plain.FAMILY.get,
                                     key=K("qd_family"))
            qd_material = st.selectbox("Material", list(quick.MATERIAL_TEXT), format_func=plain.MATERIAL.get,
                                       key=K("qd_material"))
            a_, b_ = st.columns(2)
            qd_thick = a_.selectbox("Thickness", list(quick.THICKNESS), index=3, format_func=lambda t: f'{t}"',
                                    key=K("qd_thick"))
            qd_qty = b_.number_input("How many?", 1, 5000, 120, step=10, key=K("qd_qty"))
            a_, b_ = st.columns(2)
            qd_batch = a_.number_input("Batch size", 1, 5000, 40, step=10, key=K("qd_batch"),
                                       help="How many we make at once. Setup is spread over a batch.")
            qd_due = b_.date_input("Needed by", quick.default_due(), key=K("qd_due"))
            qd_weld = st.selectbox("Welding", list(quick.WELD), format_func=quick.WELD.get, key=K("qd_weld"))
            a_, b_ = st.columns(2)
            qd_finish = a_.selectbox("Finish", list(quick.FINISH), format_func=quick.FINISH.get, key=K("qd_finish"))
            qd_color = b_.selectbox("Color", quick.COLORS, format_func=str.capitalize, key=K("qd_color"),
                                    help="Only used for powder coat. 'Not stated' makes the system ask.")
            qd_tol = st.selectbox("Tolerance", list(quick.TOLERANCE), format_func=quick.TOLERANCE.get, key=K("qd_tol"))
            qd_pn = st.text_input("Part number (optional)", key=K("qd_pn"),
                                  help="Leave empty for a part we have never built. Try " + quick.EXAMPLE_PARTS + ".")
            qd_conflict = st.checkbox("Make the spec sheet disagree on the quantity", key=K("qd_conflict"),
                                      help="Shows the system catching a conflict.")
            qd_go = st.form_submit_button("Build this request", key=K("qd_go"), type="primary")
        if qd_go:
            st_["quick_n"] += 1
            st_["quick"] = quick.quick_rfq(qd_customer, qd_family, qd_material, qd_thick, qd_qty, qd_batch, qd_weld,
                                           qd_finish, qd_color, qd_tol, qd_due, qd_pn, qd_conflict,
                                           rfq_id=f"{quick.ID_PREFIX}{st_['quick_n']}")
            st.session_state[K("step")] = STEPS[0]          # a new request starts at step 1
        if st_["quick"]:
            rfq = st_["quick"]
            st.caption("Loaded: " + quick.summary(rfq))
    elif pick == "PASTE":
        txt = st.text_area("Paste a customer email", key=K("paste_text"), height=180,
                           placeholder="From: buyer@customer.example\nSubject: RFQ ...\n\nPlease quote 100 pcs ...")
        if st.button("Read this email", key=K("paste_go")):
            st_["paste"] = txt
            for d in (st_["rfq_states"], st_["last"], st_["banner"]):
                d.pop("RFQ-PASTE", None)
        if st_["paste"]:
            rfq = intake.pasted_rfq(st_["paste"])
    else:
        rfq = RFQS[pick]
    st.divider()
    details = st.toggle("Show the details", key=K("details"),
                        help="Off = the simple story. On = evidence scores, charts and raw data.")
    age = st.slider("What if our steel price quote were older? (add days)", 0, 180, 0, 15, key=K("mat_age"),
                    help="Steel prices go stale fast. Older quotes count for less, so confidence drops and the "
                         "quote is only valid for a shorter time.")
    st.divider()
    prov, mode = llm.current_provider(), llm.demo_mode()
    reader = "simple built-in rules (no AI model)" if prov == "mock" else llm.current_model()
    st.markdown(f"**Email reader:** {reader}  \n" + ("**Mode:** saved answers only (works offline)" if mode == "offline"
                                                      else "**Mode:** live"))
    mem = memory.list_memory()
    with st.expander(f"Shop notebook: {len(mem)} saved note(s)"):
        if mem.empty:
            st.caption("Nothing yet. When the estimator or manager changes something and says why, "
                       "the reason is saved here and used on the next similar quote.")
        for r in mem.itertuples(index=False):
            st.markdown(f"<div class='qm-small'><b>{r.doc_id}</b> · {html.escape(str(r.text))}</div>",
                        unsafe_allow_html=True)
    st.button("Start over", key=K("reset"), on_click=reset_demo,
              help="Clears the notebook and every choice so you can run the demo again from the top.")
    st.caption("All data is synthetic. The company and its customers are made up. Rates and prices are illustrative.")

if rfq is None:
    st.info("Fill in the request in the sidebar and click **Build this request**." if pick == "QUICK"
            else "Paste a customer email in the sidebar and click **Read this email**.")
    st.stop()

rid = rfq["rfq_id"]


def pipeline_state(r_id: str) -> dict:
    ps = st_["rfq_states"].setdefault(r_id, pipeline.default_state())
    ps["material_age_days"] = int(age)
    prefix, gen = f"gap_{r_id}_", st.session_state.get("_gen", 0)
    for k in list(st.session_state.keys()):
        if not (isinstance(k, str) and k.startswith(prefix)):
            continue
        name, _, g = k.partition("~")
        if (int(g) if g else 0) == gen:
            ps["gap_actions"][name[len(prefix):]] = "assume" if st.session_state[k] == ASSUME else "ask"
    return ps


# baselines so switching jobs later can show what changed (e.g. Job 2 learning from Job 1's note)
msig = mem_signature()
for other_id, other in RFQS.items():
    if other_id not in st_["last"]:
        ops = pipeline_state(other_id)
        r0 = pipeline.run_pipeline(other, ops)
        st_["last"][other_id] = {"sig": json.dumps([ops, msig], sort_keys=True, default=str), "res": r0,
                                 "ps": json.loads(json.dumps(ops, default=str)), "mem": msig}

ps = pipeline_state(rid)
with st.spinner("Reading the request and weighing the evidence..."):
    res = pipeline.run_pipeline(rfq, ps)
sig = json.dumps([ps, msig], sort_keys=True, default=str)
cur = {"sig": sig, "res": res, "ps": json.loads(json.dumps(ps, default=str)), "mem": msig}
last = st_["last"].get(rid)
if last and last["sig"] != sig:
    d = pipeline.diff(last["res"], res)
    if d:
        d["cause"] = cause_of_change(last, cur)
        st_["banner"][rid] = d
        pct_ = (d["p50"][1] / d["p50"][0] - 1) * 100 if d["p50"][0] else 0
        st.toast(esc(f"Typical cost {money(d['p50'][0])} to {money(d['p50'][1])} ({pct_text(pct_)}) · "
                     f"suggested price {money(d['rec'][0])} to {money(d['rec'][1])}"))
st_["last"][rid] = cur

spec, led, risk, pr = res["spec"], res["ledger"], res["risk"], res["pricing"]
n_asks = sum(1 for g in res["gaps"] if g["action"] == "ask")
tri = res["triage"]

# ---------------------------------------------------------------- header
tri_color = {"S": GREEN, "M": YELLOW, "L": RED}[tri["label"]]
st.markdown(f"<p class='qm-title'>{html.escape(spec.get('customer_name') or 'Unknown customer')} · "
            f"{html.escape(spec.get('part_number') or 'no part number')}</p>", unsafe_allow_html=True)
st.markdown(f"<span class='qm-badge' style='background:{tri_color}'>{plain.TRACK[tri['label']]}</span> "
            f"<span class='qm-small'>&nbsp;Why: {html.escape(tri.get('plain') or tri['reason'])}</span>",
            unsafe_allow_html=True)

solid = sum(1 for l in led if l["chip"] == "green")
shaky = [plain.line_label(l) for l in led if l["chip"] != "green"]
if res["insufficient"]:
    price_box = ("Not priced", "not enough information yet")
else:
    price_box = (money(pr["recommended"]), f"we would win it about {round(pr['rec_p_win'] * 10)} times in 10")
kp = [("Typical cost per part", money(risk["p50"]),
       f"very likely between {money(risk['p10'])} and {money(risk['p90'])}"),
      ("Price we suggest", price_box[0], price_box[1]),
      ("How sure are we?", f"{solid} of {len(led)} lines solid",
       ("needs a look: " + ", ".join(shaky[:2]) + (" and more" if len(shaky) > 2 else "")) if shaky
       else "every cost line is backed by good evidence")]
st.markdown("<div class='qm-kpis'>" + "".join(
    f"<div><span>{html.escape(a)}</span><b>{html.escape(b)}</b><br><i>{html.escape(c)}</i></div>" for a, b, c in kp)
            + "</div>", unsafe_allow_html=True)

ban = st_["banner"].get(rid)
if ban:
    def arrow(a, b, fmt, neutral=False):
        cls = "neutral" if neutral or abs(b - a) < 1e-6 else ("up" if b > a else "down")
        return f"{fmt(a)} to <b class='{cls}'>{fmt(b)}</b>"
    pct = (ban["p50"][1] / ban["p50"][0] - 1) * 100 if ban["p50"][0] else 0
    (lo0, hi0), (lo1, hi1) = ban["range"]
    lines_txt = ", ".join(f"{html.escape(c['label'])}: {plain.CONF_WORD.get(c['chip_from'], 'new')} to "
                          f"{plain.CONF_WORD[c['chip_to']]}" for c in ban["changed_lines"][:4]
                          if c["chip_from"] != c["chip_to"])
    cause = "; ".join(ban.get("cause") or []) or "something you changed"
    st.markdown(
        f"<div class='qm-banner'><b>What just changed</b> <span class='qm-small'>(because {html.escape(cause)})</span><br>"
        f"Typical cost per part: {arrow(ban['p50'][0], ban['p50'][1], money)} ({pct_text(pct)}) &nbsp;·&nbsp; "
        f"Very likely between {money(lo0)}–{money(hi0)} to <b>{money(lo1)}–{money(hi1)}</b> &nbsp;·&nbsp; "
        f"Suggested price: {arrow(ban['rec'][0], ban['rec'][1], money, neutral=True)}"
        + (f" &nbsp;·&nbsp; Quote good for: {ban['validity'][0]} to <b class='up'>{ban['validity'][1]} days</b>"
           if ban.get("validity") and ban["validity"][0] != ban["validity"][1] else "")
        + (f"<br><span class='qm-small'>Confidence changed on: {lines_txt}"
           + (f" · removed: {html.escape(', '.join(ban['removed_lines']))}" if ban.get("removed_lines") else "")
           + "</span>" if lines_txt or ban.get("removed_lines") else "")
        + "</div>", unsafe_allow_html=True)


def step_status(i: int) -> str:
    if i == 0:
        return f"{n_asks} open question{'s' if n_asks != 1 else ''}" if n_asks else "done"
    if i == 1:
        return "approved" if ps["gate1_approved"] else "needs approval"
    if i == 3 and ps["gate1_approved"]:
        return "approved" if ps["gate2_approved"] and not res["gate2_stale"] else "needs approval"
    if i == 4:
        return "ready" if res["quote"]["ready"] else "draft"
    return ""


step = st.radio("Step", STEPS, horizontal=True, key=K("step"), label_visibility="collapsed",
                format_func=lambda s: f"{s} ({step_status(STEPS.index(s))})" if step_status(STEPS.index(s)) else s)
st.divider()


# ---------------------------------------------------------------- 1 read the request
def sec_read():
    x = res["intake"]
    st.markdown("#### What the customer asked for")
    left, right = st.columns([2, 3])
    with left:
        st.markdown("**The customer's email**")
        st.markdown(mailbox(rfq.get("email_text", "")), unsafe_allow_html=True)
        if rfq.get("customer_spec"):
            with st.expander("Attached spec sheet"):
                st.json(rfq["customer_spec"])
    with right:
        meta = x["llm"]
        if meta["provider"] == "mock":
            who = ("a hand-checked copy of what the AI reads (demo without a live model)" if meta["source"] == "fixture"
                   else "simple built-in rules (no AI model)")
        else:
            who = {"cache": f"a saved copy of {meta['model']}'s reading", "live": f"{meta['model']} (live)",
                   "fixture": "a hand-checked fallback", "fallback": "simple built-in rules"}.get(
                meta["source"], f"{meta['model']}")
        st.markdown(f"**What we understood** <span class='qm-small'>· read by {html.escape(who)}. "
                    f"The AI only reads the words. All the math is ordinary arithmetic.</span>",
                    unsafe_allow_html=True)
        rows = []
        for name, f in x["fields"].items():
            if name in ("notes",):
                continue
            where = []
            if f.get("source_quote") and f.get("email_value") is not None:
                q = html.escape(f["source_quote"][:70])
                where.append(("From the email: “" + q + "”") if f.get("verified") else f"WARNING, not found in the email: “{q}”")
            if "CONFLICT" in (f.get("origin") or ""):
                where.append(f"<b style='color:{RED}'>The email says {html.escape(field_text(name, f['email_value']))}"
                             f" but the spec sheet says {html.escape(field_text(name, f['sheet_value']))}</b>")
            elif f.get("sheet_raw") is not None:
                where.append(f"Spec sheet: {html.escape(str(f['sheet_raw'])[:40])}")
            lvl = FIELD_CHIP[f["confidence"]]
            rows.append(f"<tr><td>{html.escape(f['label'])}</td><td><b>{html.escape(field_text(name, f['value']))}</b></td>"
                        f"<td>{chip(lvl, plain.CONF_WORD[lvl])}</td>"
                        f"<td class='qm-small'>{'<br>'.join(where) or '—'}</td></tr>")
        st.markdown("<table class='qm-t'><tr><th>What</th><th>What we read</th><th>How sure</th><th>Where we saw it</th></tr>"
                    + "".join(rows) + "</table>", unsafe_allow_html=True)
        facts = []
        if spec.get("repeat_part"):
            facts.append(f"we have built this part number before ({', '.join(spec['prior_runs'])})")
        if spec.get("revision_change"):
            facts.append(f"**it is a new revision** of a part we built ({', '.join(spec['prior_revs'])})")
        if spec.get("first_run"):
            facts.append("**we have never built this part**")
        if spec.get("is_new_customer"):
            facts.append("this is a new customer")
        if spec.get("assumed_from_analog"):
            facts.append("**guessing from our closest past job:** " + ", ".join(
                f"{f.replace('_in', '').replace('_', ' ')} = {field_text(f, spec[f])}" for f in spec["assumed_from_analog"]))
        if facts:
            st.markdown("From our history: " + "; ".join(facts) + ".")

    st.markdown("#### Things to sort out before we can quote")
    if not res["gaps"]:
        st.success("Nothing missing and nothing that disagrees. The request is complete.")
    conts = {c["source"]: c for c in res["contingencies"]}
    for g in res["gaps"]:
        with st.container(border=True):
            a, b = st.columns([2, 3])
            a.markdown(f"**{html.escape(g['title'])}**")
            a.radio("What do we do?", [ASK, ASSUME], key=K(f"gap_{rid}_{g['id']}"), horizontal=True,
                    index=1 if g["action"] == "assume" else 0)
            if g["action"] == "ask":
                b.markdown(f"**Question for the customer:** {g['question']}")
                b.caption("The quote stays a draft on this point until the customer answers.")
            else:
                c = conts.get(g["id"])
                extra = f", about {money(c['amount'])} per part" if c else ""
                b.markdown(f"**We would print this on the quote:** {g['assumption']}")
                b.caption(esc(f"We add a {g['contingency_pct']:.0%} safety cushion to the affected cost{extra}, "
                               f"in case the guess is wrong."))
    if res["due"].get("slack_days") is not None:
        d = res["due"]
        verdict = ("we cannot make that date" if d["slack_days"] < 0 else "tight but doable" if d["slack_days"] < 7
                   else "comfortable")
        msg = (f"Delivery check: {verdict}. The first batch needs about {d['hours_first_release']:.0f} shop hours, "
               f"so the soonest we could ship is about {d['min_lead_days']} days out. The customer allows "
               f"{d['available_days']} days ({d['slack_days']:+d} days to spare).")
        (st.warning if d["slack_days"] < 5 else st.caption)(msg)
    if res["email"]:
        with st.expander("Draft email to the customer (one email covering every question)", expanded=False):
            st.markdown(mailbox(res["email"]), unsafe_allow_html=True)
            em = res["email_meta"]
            if em.get("source") == "template":
                st.caption("Drafted from a template (instant).")
                if llm.current_provider() != "mock" and st.button("Have the AI draft it", key=K(f"email_llm_{rid}")):
                    ps["email_llm"] = True
                    st.rerun()
            else:
                who = "a template" if em.get("provider") == "mock" else f"{em.get('model')}"
                st.caption(f"Drafted by {who}. A person reviews it before it is sent.")


# ---------------------------------------------------------------- 2 plan the work
def sec_plan():
    an = res["analog"]
    match = "Very close match" if an["sim"] >= 0.85 else "Good match" if an["sim"] >= 0.65 else "Loose match"
    with st.container(border=True):
        st.markdown(f"**Closest past job: {an['job_id']}** · {an['part_number']} · {an['qty']} parts · "
                    f"{'we won it' if an['won'] else 'we lost it'} · "
                    f"{'we have the real hours it took' if an['has_actuals'] else 'we only have the estimate'}")
        st.caption(f"{match}" + (f" (similarity {an['sim']:.2f})" if details else "") + f". Why: {an['why']}")
        st.caption(an["description"])
    if details:
        with st.expander("Other similar past jobs"):
            sj = res["similar"].head(8)
            st.dataframe(pd.DataFrame({"Job": sj.job_id, "Part": sj.part_number, "Qty": sj.qty, "Won": sj.won,
                                       "Real hours": sj.has_actuals, "Similarity": sj.sim.round(2), "Why": sj.why}),
                         hide_index=True)
    diff = [r for r in res["proposal"]["diff"] if not r["effect"].startswith(("Same", "Similar", "No fixture"))]
    st.markdown("**How this order is different from that job**")
    if diff:
        st.table(pd.DataFrame(diff).rename(columns={"field": "What", "rfq": "This order", "analog": f"Job {an['job_id']}",
                                                     "effect": "What it means for cost"}).set_index("What"))
    else:
        st.caption("Nothing. It is the same job again.")
    st.caption("Our plan starts from that job's parts list and shop steps, using the hours it really took, "
               "then applies the differences above. Prices come later.")

    st.markdown("#### Checkpoint 1 · The estimator approves the plan")
    lines = res["proposal"]["lines"]
    labels = {l["key"]: plain.line_label(l) if l["kind"] == "routing" else l["label"] for l in lines}
    if ps["gate1_approved"]:
        n_route = sum(1 for kk in ps["gate1_edits"] if kk in res["overrides"])
        st.success("Checkpoint 1 approved: the estimator signed off on the plan."
                   + (f" {n_route} change(s) saved to the shop notebook, so similar quotes learn from them." if n_route else "")
                   + (" Other changes are logged in the notebook." if len(ps["gate1_edits"]) > n_route
                      or ps["gate1_excluded"] else ""))
        for kk, e in ps["gate1_edits"].items():
            l = next(x for x in lines if x["key"] == kk)
            st.markdown(esc(f"- Changed **{labels[kk]}** from {l['proposed']:.3g} to **{e['value']:.3g}** "
                            f"{plain.unit(l['uom'])}. Reason: _{e['reason']}_"))
        for kk in ps["gate1_excluded"]:
            st.markdown(f"- Removed **{labels.get(kk, kk)}**")
        if st.button("Re-open the plan", key=K(f"g1_reopen_{rid}")):
            ps["gate1_approved"] = False
            ps["gate2_approved"] = False          # a new plan invalidates the approved price
            st_["g1_ver"][rid] = st_["g1_ver"].get(rid, 0) + 1
            st.rerun()
        return
    prev = {kk: e["value"] for kk, e in ps["gate1_edits"].items()}
    prop = {l["key"]: float(l["proposed"]) for l in lines}
    fx = next((l for l in lines if l["key"] == "fixture.setup" and l.get("check")), None)
    fx_no = False
    fx_hours = 0.0
    if fx:
        with st.container(border=True):
            st.markdown("**Does the old fixture still fit the new revision?**")
            st.caption("A fixture is the jig that holds parts in place while we weld. If the hole pattern or shape "
                       "changed, the old one may not fit. Our history says a new one takes about "
                       f"{config.FIXTURE_DEFAULT_HR:.0f} hours to build.")
            choice = st.radio("Fixture", [FIX_YES, FIX_NO], key=K(f"fixture_{rid}"), horizontal=True,
                              index=1 if prev.get("fixture.setup", 0) > 0 else 0, label_visibility="collapsed")
            fx_no = choice == FIX_NO
            if fx_no:
                fx_hours = st.number_input("Hours to build a new fixture", min_value=0.0, step=0.5,
                                           value=float(prev.get("fixture.setup") or config.FIXTURE_DEFAULT_HR),
                                           key=K(f"fixture_hr_{rid}"))
    base = pd.DataFrame([{
        "key": l["key"], "Use it?": l["key"] not in set(ps["gate1_excluded"]), "Step or part": labels[l["key"]],
        "Unit": plain.unit(l["uom"]), "Suggested": round(prop[l["key"]], 3),
        "Your value": round(float(prev.get(l["key"], prop[l["key"]])), 3), "Based on": plain.source_from(l["source"])}
        for l in lines if l is not fx]).set_index("key")
    ver = st_["g1_ver"].get(rid, 0)
    st.markdown("**The plan: parts and shop steps** <span class='qm-small'>· change any number in “Your value”, "
                "or untick a row to drop it</span>", unsafe_allow_html=True)
    ed = st.data_editor(base, key=K(f"plan_{rid}_{ver}"), hide_index=True, height=min(36 * len(base) + 40, 560),
                        disabled=["Step or part", "Unit", "Suggested", "Based on"],
                        column_config={"Your value": st.column_config.NumberColumn(format="%.3f", min_value=0.0),
                                       "Use it?": st.column_config.CheckboxColumn(width="small")})
    pend = {kk: float(v) for kk, v in ed["Your value"].items() if pd.notna(v) and abs(float(v) - prop[kk]) > 1e-9}
    excl = [kk for kk, inc in ed["Use it?"].items() if not inc]
    if fx_no and abs(fx_hours - prop["fixture.setup"]) > 1e-9:
        pend["fixture.setup"] = float(fx_hours)
    changes = [f"**{labels[kk]}**: {prop[kk]:.3g} to {v:.3g}" for kk, v in pend.items()]
    changes += [f"remove **{labels[kk]}**" for kk in excl]
    if changes:
        st.markdown(esc("Your changes: " + "; ".join(changes)))
    for kk, v in pend.items():
        if prop[kk] > 0 and not 0.5 <= v / prop[kk] <= 2.0:
            st.warning(esc(f"{labels[kk]}: {prop[kk]:.3g} to {v:.3g} is more than double (or less than half) of "
                           f"the past job. Please double-check the number."))
    prev_reason = next((e["reason"] for e in ps["gate1_edits"].values() if e.get("reason")), "")
    reason = st.text_input("Why? (needed for any change. The notebook remembers it, so the next similar quote learns.)",
                           value=prev_reason, key=K(f"g1_reason_{rid}"),
                           placeholder="e.g. The Rev C hole pattern moved, so the old fixture will not fit.")
    if st.button("Approve the plan", key=K(f"g1_approve_{rid}"), type="primary"):
        if (pend or excl) and not reason.strip():
            st.error("Add a reason for your change first. The reason is what the next quote learns from.")
        else:
            ps["gate1_edits"] = {kk: {"value": v, "reason": reason.strip()} for kk, v in pend.items()}
            ps["gate1_excluded"] = excl
            ps["gate1_approved"] = True
            memory.remove_for_rfq(rid, kinds=("gate1_line", "gate1_bom", "gate1_exclude"))
            for kk, v in pend.items():
                l = next(x for x in lines if x["key"] == kk)
                if l["kind"] == "routing":
                    memory.record_line_override(rid, spec, kk, labels[kk], l.get("work_center"), prop[kk], v, reason)
                else:
                    memory.record_decision(rid, spec, "gate1_bom", f"Estimator changed {l['label']} from "
                                           f"{prop[kk]:.3g} to {v:.3g} {plain.unit(l['uom'])}. Reason: {reason.strip()}")
            for kk in excl:
                memory.record_decision(rid, spec, "gate1_exclude",
                                       f"Estimator removed {labels.get(kk, kk)} from the plan. Reason: {reason.strip()}")
            st.rerun()


# ---------------------------------------------------------------- 3 cost it
def _based_on(l: dict) -> str:
    c = Counter(e["source_type"] for e in l["evidence"] if e["counted"])
    return " · ".join(f"{n} {SRC_PLURAL[t][0 if n == 1 else 1]}" for t, n in c.most_common(3)) or "nothing usable"


def evidence_sentence(l: dict) -> str:
    n = sum(1 for e in l["evidence"] if e["counted"])
    agree = ("They agree closely" if (l["cv"] or 0) < 0.12 else "They disagree a lot" if (l["cv"] or 0) > 0.3
             else "They mostly agree")
    amount = "plenty of" if l["sum_score"] >= 3 else "some" if l["sum_score"] >= 1.2 else "very little"
    word = plain.CONF_WORD[l["chip"]].lower()
    return (f"We found {n} pieces of evidence ({_based_on(l)}), which is {amount} to go on. {agree}, "
            f"so we are {word} confidence in this number.")


def sec_cost():
    if not ps["gate1_approved"]:
        st.info("These are draft numbers. The estimator has not approved the plan yet (step 2), so they can still change.")
    st.markdown(esc(f"#### About {money(risk['p50'])} per part · very likely between {money(risk['p10'])} and "
                    f"{money(risk['p90'])}"))
    order = sorted(led, key=lambda l: (CAT_ORDER[l["category"]], led.index(l)))
    rows = []
    for l in order:
        learned = any(e["source_type"] == "override" and e["ref"] != "This quote (Gate 1)" and e["counted"]
                      for e in l["evidence"])
        edited = l["overridden"] and l["key"] in res["overrides"] or abs(float(l["approved"]) - float(l["proposed"])) > 1e-9
        flags = [t for t, on in (("Changed by estimator", edited), ("Learned from the notebook", learned),
                                 ("Warning", bool(l["warnings"])), ("Lesson from past jobs", bool(l["patterns"]))) if on]
        rows.append({"How sure": plain.CONF_WORD[l["chip"]], "Item": plain.line_label(l), "Kind": CAT_LABEL[l["category"]],
                     "Our estimate": fmt_value(l), "Cost per part": round(l["cost"], 2), "Based on": _based_on(l),
                     "Notes": ", ".join(flags)})
    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Where the cost comes from** <span class='qm-small'>· click a row to see why we believe "
                    "the number</span>", unsafe_allow_html=True)
        df = pd.DataFrame(rows)
        color = {"High": SOFT["green"], "Medium": SOFT["yellow"], "Low": SOFT["red"]}
        sty = df.style
        sty = (getattr(sty, "map", None) or sty.applymap)(lambda v: f"background-color: {color.get(v, '')}", subset=["How sure"])
        ev = st.dataframe(sty, hide_index=True, on_select="rerun", selection_mode="single-row", key=K(f"ledger_{rid}"),
                          height=min(38 * len(rows) + 40, 640),
                          column_config={"Cost per part": st.column_config.NumberColumn(format="$%.2f"),
                                         "Notes": st.column_config.TextColumn(width="medium")})
        sel = list(getattr(getattr(ev, "selection", None), "rows", []) or [])
        keys = [l["key"] for l in order]
        if sel and st_["ledger_sel"].get(rid) != sel[0]:
            st_["ledger_sel"][rid] = sel[0]
            st.session_state[K(f"drawer_{rid}")] = keys[sel[0]]
        for lab, w in [(plain.line_label(l), w) for l in order for w in l["warnings"]
                       if not w.startswith("Override differs")][:3]:
            st.warning(esc(f"**{lab}**: {w}"))
        st.caption(esc(f"Costs add up to {money(sum(l['cost'] for l in led))} per part before any safety cushion "
                       f"(batch size {spec.get('lot_qty')}). Shop hours are charged at illustrative rates."))
    with right:
        default = next((l["key"] for l in order if l["patterns"]), None) or min(order, key=lambda l: l["confidence"])["key"]
        dkey = K(f"drawer_{rid}")
        if st.session_state.get(dkey) not in keys:
            st.session_state[dkey] = default
        dk = st.selectbox("Why do we believe this number?", keys, key=dkey,
                          format_func=lambda kk: plain.line_label(next(l for l in order if l["key"] == kk)))
        l = next(x for x in order if x["key"] == dk)
        with st.container(border=True):
            st.markdown(f"**{plain.line_label(l)}** · {chip(l['chip'], plain.CONF_WORD[l['chip']] + ' confidence')}",
                        unsafe_allow_html=True)
            st.markdown(f"### {esc(fmt_value(l))}")
            st.caption(esc(f"Could reasonably be {fmt_range(l)} · {money(l['cost'])} per part"))
            st.markdown(f"<div class='qm-small'>{html.escape(evidence_sentence(l))}</div>", unsafe_allow_html=True)
            for w in l["warnings"]:
                st.warning(esc(w))
            for e in l["evidence"]:
                if e["source_type"] == "override" and e["ref"] != "This quote (Gate 1)" and e["counted"]:
                    st.success(esc(f"**Learned from an earlier quote** ({e['ref']}): {e['text']}"))
            ev_df = pd.DataFrame([{
                "Where it came from": f"{plain.SOURCE.get(e['source_type'], e['source'])} · {e['ref']}",
                "What it said": None if e["value"] is None else fmt_value(l, e["value"]),
                "How much it counts": plain.trust(e["score"]) if e["counted"] else "Not used",
                **({"Score = similarity x authority x recency": f"{e['score']:.2f} = {e['similarity']:.2f} x "
                                                                f"{e['authority']:.1f} x {e['decay']:.2f}"}
                   if details else {})} for e in l["evidence"]])
            st.dataframe(ev_df, hide_index=True, height=min(36 * len(ev_df) + 40, 400))
            notes = [e for e in l["evidence"] if e.get("text") and e["counted"]
                     and e["source_type"] in ("pattern", "override", "note", "actual")][:4]
            if notes:
                with st.expander("What the shop wrote down"):
                    for e in notes:
                        st.markdown(f"**{plain.SOURCE.get(e['source_type'], e['source'])} · {e['ref']}**")
                        st.markdown(mailbox(e["text"]), unsafe_allow_html=True)
            if details:
                st.caption("Score = similarity x authority x recency. Authority: real hours 1.0 · note, override or "
                           "lesson 0.8 · past quote 0.6 · shop rule of thumb 0.3. Older evidence counts less (half-life: "
                           "material 30 days, shop time 540 days, notes 365 days).")
    if res["patterns"]:
        st.markdown("#### Lessons from our history")
        for p in res["patterns"]:
            st.info(esc(f"**{p['title']}**  \n{p['narration']}"
                        + (f"  \n_Data: {p['stat']}. Adjustment: {p['adjustment']}._" if details else "")))
    st.markdown("**Steel prices**")
    for mat, info in res["material_meta"].items():
        stale = (info.get("newest_age") or 0) > config.MATERIAL_STALE_DAYS
        name = plain.MATERIAL.get(mat, mat)
        if stale:
            st.warning(esc(f"{name}: our newest supplier quote is {info['newest_age']} days old. We should re-quote it, "
                           f"so this quote is only good for {config.QUOTE_VALIDITY_STALE_DAYS} days and carries a "
                           f"{info['escalation_pct'] * 100:.1f}% cushion for price moves."))
        else:
            st.success(esc(f"{name}: our newest supplier quote is {info['newest_age']} days old. Fresh enough."))
    if res["contingencies"]:
        st.markdown("**Safety cushion for the things we are guessing**")
        st.dataframe(pd.DataFrame([{"Because": x["label"], "Cushion": f"{x['pct'] * 100:.1f}%",
                                    "Adds per part": money(x["amount"])} for x in res["contingencies"]]), hide_index=True)
    if details:
        st.markdown("#### How we get the range")
        a, b = st.columns([3, 2])
        with a:
            s = np.array(risk["samples"])
            fig = go.Figure(go.Histogram(x=s, nbinsx=40, marker_color="#9db8e8", name="simulated cost"))
            for q, name, col in [("p10", "low end", GREY), ("p50", "typical", BLUE), ("p90", "high end", RED)]:
                fig.add_vline(x=risk[q], line_color=col, line_dash="dash",
                              annotation_text=f"{name} {money(risk[q])}", annotation_position="top")
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10), showlegend=False,
                              xaxis_title="Cost per part ($)", yaxis_title="Simulated runs", bargap=0.05)
            st.plotly_chart(fig, key=K(f"hist_{rid}"))
            st.caption(f"We ran the job {risk['n']:,} times in a computer, each time drawing every cost line from its "
                       f"low-to-high range. Steel lines move together; shop-time lines partly move together.")
        with b:
            spread = sorted(led, key=lambda l: -(l["high"] - l["low"]) * l["multiplier"])[:6]
            fig2 = go.Figure(go.Bar(y=[plain.line_label(l) for l in spread][::-1],
                                    x=[(l["high"] - l["low"]) * l["multiplier"] for l in spread][::-1], orientation="h",
                                    marker_color=[CHIP[l["chip"]] for l in spread][::-1]))
            fig2.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10), title="What makes the cost uncertain",
                               xaxis_title="$ per part between low and high")
            st.plotly_chart(fig2, key=K(f"drivers_{rid}"))
        mix = {CAT_LABEL[k_]: v for k_, v in sorted(risk["by_category"].items(), key=lambda kv: CAT_ORDER[kv[0]])}
        st.caption(esc("Cost mix per part: " + " · ".join(f"{k_} {money(v)}" for k_, v in mix.items())))


# ---------------------------------------------------------------- 4 set the price
def sec_price():
    if res["insufficient"]:
        st.error("We do not have enough to price this yet: " + "; ".join(res["insufficient"])
                 + ". Answer the open questions in step 1 or pick a closer past job.")
        return
    cushion = pr["risk_adj_cost"] - risk["p50"]
    st.markdown("#### Three prices to choose from")
    st.markdown(esc(f"Our **planning cost is {money(pr['decision_cost'])} per part**: the typical cost "
                    f"({money(risk['p50'])}) plus a safety cushion ({money(cushion)}) because the real cost could "
                    f"come in higher."))
    opts = pricing.price_options(pr, risk, spec)
    trs = "".join(
        f"<tr class='{'rec' if o['name'].startswith('Rec') else ''}'><td>{o['name']}</td><td>{money(o['price'])}</td>"
        f"<td>{plain.in_ten(o['p_win'])}" + (f" ({o['p_win']:.0%})" if details else "") + f"</td>"
        f"<td>{money(o['profit_if_win'])}</td><td><b>{money(o['average_profit'])}</b></td></tr>" for o in opts)
    st.markdown("<table class='qm-t'><tr><th>Choice</th><th>Price per part</th><th>Chance we win it</th>"
                "<th>Profit per part if we win</th><th>Average profit per part quoted</th></tr>" + trs + "</table>",
                unsafe_allow_html=True)
    st.caption("Average profit = chance of winning x profit if we win. A lower price wins more often but earns less each "
               "time; a higher price earns more but loses more often. The recommended price is where the average is highest. "
               "The chance of winning comes from how customers reacted to our past quotes.")
    for p in res["patterns"]:
        if p["id"] == "P4":
            st.warning(esc(f"**{p['title']}**: {p['narration']}"))
    mem_ = memory.list_memory()
    if not mem_.empty and "kind" in mem_.columns:
        past = mem_[(mem_.kind == "gate2_price") & (mem_.part_family == spec.get("part_family")) & (mem_.rfq_id != rid)]
        for r in past.itertuples(index=False):
            st.info(esc(f"**A manager priced a similar quote differently before** ({r.rfq_id}): {r.text}"))

    st.markdown("#### Checkpoint 2 · The manager approves the price")
    if ps["gate2_approved"] and res["gate2_stale"]:
        st.warning(esc(f"The approved price ({money(res['chosen_price'])}) is out of date: {res['gate2_stale']}. "
                       "Please approve it again."))
        ps["gate2_approved"] = False
    if ps["gate2_approved"]:
        st.success(esc(f"Checkpoint 2 approved at {money(res['chosen_price'])} per part"
                       + (f" · reason: {ps['gate2_reason']}" if ps["gate2_reason"] else "")))
        if st.button("Re-open the price", key=K(f"g2_reopen_{rid}")):
            ps["gate2_approved"] = False
            st.rerun()
    else:
        if not ps["gate1_approved"]:
            st.info("The estimator needs to approve the plan first (step 2), because the price depends on it.")
        names = [o["name"] for o in opts]
        pick_ = st.radio("Which price?", names + ["Another amount"], index=1, horizontal=True, key=K(f"price_choice_{rid}"))
        if pick_ == "Another amount":
            price = st.number_input("Price per part ($)", min_value=0.0, step=1.0, value=round(pr["recommended"], 2),
                                    key=K(f"price_custom_{rid}"))
        else:
            price = round(next(o["price"] for o in opts if o["name"] == pick_), 2)
        inside = pr["range"][0] - 0.005 <= price <= pr["range"][1] + 0.005
        pw = pricing.pwin_at(price, risk["p50"], spec)
        st.caption(esc(f"At {money(price)}: we would win about {round(pw * 10)} in 10, and earn about "
                       f"{money(pw * (price - pr['decision_cost']))} per part on average."))
        reason = ""
        if not inside:
            st.warning("This price is outside our recommended range. Add a reason. It goes in the shop notebook.")
            reason = st.text_input("Reason for a price outside the range", key=K(f"g2_reason_{rid}"))
        if st.button("Approve the price", key=K(f"g2_approve_{rid}"), type="primary", disabled=not ps["gate1_approved"]):
            if price < 0.5 * risk["p50"]:
                st.error(esc(f"{money(price)} is less than half of the typical cost ({money(risk['p50'])}). "
                             "Please check the amount."))
            elif not inside and not reason.strip():
                st.error("Add a reason before approving a price outside the recommended range.")
            else:
                ps["gate2_price"] = float(price)
                ps["expedite"] = False
                ps["gate2_reason"] = reason.strip()
                ps["gate2_approved"] = True
                ps["gate2_p50"] = float(risk["p50"])
                if not inside:
                    memory.record_decision(rid, spec, "gate2_price",
                                           f"Manager priced {money(price)} instead of the recommended range "
                                           f"{money(pr['range'][0])}–{money(pr['range'][1])}. Reason: {reason.strip()}")
                st.rerun()
    if details:
        st.markdown("#### Price, win chance and profit")
        x = np.array(pr["prices"])
        fig = go.Figure()
        fig.add_vrect(x0=pr["range"][0], x1=pr["range"][1], fillcolor="#1e8e3e", opacity=0.12, line_width=0,
                      annotation_text="recommended range", annotation_position="bottom left")
        fig.add_trace(go.Scatter(x=x, y=pr["exp_margin"], name="Average profit ($ per part)", line=dict(color=BLUE, width=3)))
        fig.add_trace(go.Scatter(x=x, y=np.array(pr["p_win"]) * 100, name="Chance we win (%)", yaxis="y2",
                                 line=dict(color=GREY, dash="dot")))
        fig.add_vline(x=pr["recommended"], line_color=GREEN, annotation_text=f"suggested {money(pr['recommended'])}")
        fig.add_vline(x=pr["floor_price"], line_color=RED, line_dash="dash", annotation_text="minimum margin",
                      annotation_position="bottom right")
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="Price per part ($)",
                          yaxis=dict(title="Average profit ($ per part)"),
                          yaxis2=dict(title="Chance we win (%)", overlaying="y", side="right", range=[0, 100],
                                      tickvals=[0, 25, 50, 75, 100], showgrid=False),
                          legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig, key=K(f"curve_{rid}"))
        st.caption(esc(f"Minimum margin {pr['floor_pct']:.0%} gives a floor of {money(pr['floor_price'])}. The win-chance "
                       f"model uses price vs. cost, customer type, new customer and order size. No AI is involved in the price."))


# ---------------------------------------------------------------- 5 send the quote
def sec_quote():
    q = res["quote"]
    checks = [("Plan approved (checkpoint 1)", bool(ps["gate1_approved"])),
              ("Price approved (checkpoint 2)", bool(ps["gate2_approved"]) and not res["gate2_stale"]),
              (f"Customer questions answered ({len(q['pending'])} open)", not q["pending"])]
    st.markdown("**Ready to send?**")
    for text, ok in checks:
        st.markdown(("- Done: " if ok else "- Still to do: ") + text)
    if q["ready"]:
        st.success("Ready to send: the plan and the price are both approved and nothing is waiting on the customer.")
    elif res["insufficient"]:
        st.warning("Not priced yet: we do not have enough information.")
    else:
        st.warning("This is a draft until everything above is done.")
    md = pipeline.quote_markdown(res)
    with st.container(border=True):
        st.markdown(esc(md.replace("# Quotation", "### Quotation", 1)))
    c1, c2 = st.columns(2)
    c1.download_button("Download quote (Markdown)", md, file_name=f"{rid}_quote.md", mime="text/markdown",
                       key=K(f"dl_md_{rid}"))
    c2.download_button("Download quote (HTML)", quote_html.render(res), file_name=f"{rid}_quote.html", mime="text/html",
                       key=K(f"dl_html_{rid}"))


{STEPS[0]: sec_read, STEPS[1]: sec_plan, STEPS[2]: sec_cost, STEPS[3]: sec_price, STEPS[4]: sec_quote}[step]()

if details:
    with st.expander("Raw data (for debugging)"):
        st.caption(f"Pipeline {res['elapsed_s']}s · provider {llm.current_provider()} · mode {llm.demo_mode()}")
        st.json({"spec": {k: str(v) for k, v in spec.items()}, "llm": res["llm_meta"], "state": ps}, expanded=False)
