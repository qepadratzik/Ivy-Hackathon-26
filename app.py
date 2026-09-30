"""Quote Memory: Evidence-Weighted Quoting (Streamlit UI).

    streamlit run app.py

All data is synthetic; Boone Creek Fabrication and every customer are fictional.
One state dict lives in st.session_state["qm"]; the pipeline is a pure function of it.
"""
from __future__ import annotations

import html
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from qm import config, intake, llm, memory, pipeline, pricing, store
from qm.data_gen import frac

st.set_page_config(page_title="Quote Memory", page_icon="📐", layout="wide", initial_sidebar_state="expanded")

GREEN, YELLOW, RED, GREY, BLUE = "#1e8e3e", "#c98a00", "#d93025", "#6b7280", "#1a5fb4"
CHIP = {"green": GREEN, "yellow": YELLOW, "red": RED, "high": GREEN, "medium": YELLOW, "low": RED}
DOT = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
ASK, ASSUME = "Ask the customer", "Assume & quote"
SECTIONS = ["1 · Requirements", "2 · Approach (Gate 1)", "3 · Cost ledger", "4 · Risk", "5 · Price (Gate 2)",
            "6 · Quote"]
RFQ_LABELS = {"RFQ-A": "A · Cedar Valley hitch bracket (main)", "RFQ-B": "B · Hawkeye hitch bracket (first run)",
              "RFQ-C": "C · Loess Hills mounting plate (repeat)", "PASTE": "Paste your own RFQ"}
CAT_ORDER = {"material": 0, "purchased": 1, "outside": 2, "labor": 3}
CAT_LABEL = {"material": "Material", "purchased": "Purchased parts", "outside": "Outside process", "labor": "Labor"}

st.markdown(f"""
<style>
.block-container {{padding-top: 2.6rem; padding-bottom: 3rem;}}
.qm-kpis {{display:flex; gap:10px; flex-wrap:wrap; margin:0.2rem 0 0.4rem 0;}}
.qm-kpis div {{flex:1; min-width:150px; border:1px solid #e4e7ec; border-radius:8px; padding:6px 10px; background:white;}}
.qm-kpis span {{display:block; color:#667085; font-size:0.75rem;}}
.qm-kpis b {{font-size:1.35rem; color:#101828;}}
.qm-kpis i {{font-style:normal; color:#667085; font-size:0.78rem;}}
.qm-title {{font-size:1.35rem; font-weight:700; margin:0; line-height:1.3;}}
.qm-chip {{display:inline-block; padding:1px 9px; border-radius:10px; color:white; font-size:0.78rem;
           font-weight:600; white-space:nowrap;}}
.qm-badge {{display:inline-block; padding:3px 12px; border-radius:14px; color:white; font-weight:700;}}
.qm-step {{display:flex; gap:6px; flex-wrap:wrap; margin:0.3rem 0 0.6rem 0;}}
.qm-step div {{flex:1; min-width:110px; text-align:center; font-size:0.74rem; padding:6px 4px; border-radius:6px;
               border:1px solid #d0d5dd; color:#344054; background:#f9fafb;}}
.qm-step div.done {{background:#e7f5ec; border-color:{GREEN}; color:#14532d;}}
.qm-step div.wait {{background:#fff6e0; border-color:{YELLOW}; color:#6b4e00;}}
.qm-step div.now {{background:#e8f0fe; border-color:{BLUE}; color:#0b3d91; font-weight:700;}}
.qm-banner {{border-left:6px solid {BLUE}; background:#eef4ff; padding:10px 14px; border-radius:6px; margin:0.4rem 0 0.8rem 0;}}
.qm-banner b.up {{color:{RED};}} .qm-banner b.down {{color:{GREEN};}}
.qm-mail {{white-space:pre-wrap; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:0.8rem;
           background:#f8fafc; border:1px solid #e5e7eb; border-radius:6px; padding:10px; max-height:420px; overflow:auto;}}
table.qm-t {{width:100%; border-collapse:collapse; font-size:0.85rem;}}
table.qm-t td, table.qm-t th {{border-bottom:1px solid #eef0f3; padding:5px 6px; text-align:left; vertical-align:top;}}
table.qm-t th {{color:#475467; font-weight:600;}}
.qm-small {{color:#667085; font-size:0.8rem;}}
.qm-quote {{background:white; border:1px solid #d0d5dd; border-radius:8px; padding:18px 22px;}}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- helpers
def chip(level: str, text: str) -> str:
    return f'<span class="qm-chip" style="background:{CHIP.get(level, GREY)}">{html.escape(text)}</span>'


def money(x: float) -> str:
    return f"${x:,.2f}"


def esc(s: str) -> str:
    """Escape $ so Streamlit markdown doesn't treat '$a ... $b' as LaTeX math."""
    return str(s).replace("$", "\\$")


def fmt_value(l: dict, v: float | None = None) -> str:
    v = l["value"] if v is None else v
    if l["unit"] in ("$/lb", "$/ea"):
        return f"${v:,.3f}/{l['unit'][2:]}" if l["unit"] == "$/lb" else f"${v:,.2f}/ea"
    return f"{v:.3g} {l['unit']}"


def field_text(name: str, v) -> str:
    if v is None:
        return "not stated"
    if name == "thickness_in":
        return f'{frac(float(v))}" ({float(v):.3f} in)'
    if name == "cosmetic_weld":
        return "yes (cosmetic)" if v else "no (standard)"
    if name == "finish":
        return str(v).replace("_", " ")
    if name == "due_date":
        return f"{v:%a %b %d, %Y}"
    if name == "part_family":
        return str(v).replace("_", " ")
    return str(v)


@st.cache_resource(show_spinner="Loading the shop's history (first run downloads a small local embedding model)...")
def boot() -> dict:
    store.vector_store()
    pricing.win_model()
    return intake.load_demo_rfqs()


def S() -> dict:
    if "qm" not in st.session_state:
        st.session_state.qm = {"rfq_states": {}, "last": {}, "banner": {}, "g1_pending": {}, "g1_ver": {},
                               "ledger_sel": {}, "paste": None}
    return st.session_state.qm


def mem_signature() -> str:
    m = memory.list_memory()
    return f"{len(m)}:{m.doc_id.iloc[-1] if len(m) else ''}"


def cause_of_change(old: dict, new: dict) -> list[str]:
    c = []
    ops, nps = old["ps"], new["ps"]
    for gid in set(ops["gap_actions"]) | set(nps["gap_actions"]):
        a, b = ops["gap_actions"].get(gid, "ask"), nps["gap_actions"].get(gid, "ask")
        if a != b:
            c.append(f"gap '{gid.replace('_', ' ')}' switched {a} → {b}")
    if ops["gate1_edits"] != nps["gate1_edits"] or ops["gate1_excluded"] != nps["gate1_excluded"]:
        eds = [f"{k} → {v['value']:.2f}" for k, v in nps["gate1_edits"].items()]
        c.append("Gate 1 edits: " + (", ".join(eds) if eds else "cleared"))
    if ops["material_age_days"] != nps["material_age_days"]:
        c.append(f"newest material quote aged {ops['material_age_days']} → {nps['material_age_days']} days")
    if ops["capacity"] != nps["capacity"]:
        c.append(f"shop load {ops['capacity']:.0%} → {nps['capacity']:.0%}")
    if (ops.get("gate2_price"), ops.get("expedite")) != (nps.get("gate2_price"), nps.get("expedite")):
        c.append("price decision changed")
    if old["mem"] != new["mem"]:
        learned = any(e["source_type"] == "override" and e["ref"] != "This quote (Gate 1)" and e["counted"]
                      for l in new["res"]["ledger"] for e in l["evidence"])
        if learned or not c:
            c.append(f"memory now holds {new['mem'].split(':')[0]} saved override(s)"
                     + (": this quote learned from one" if learned else ""))
    return c


# ---------------------------------------------------------------- boot + sidebar
RFQS = boot()
st_ = S()

with st.sidebar:
    st.markdown("## 📐 Quote Memory")
    st.caption("Evidence-weighted quoting for **Boone Creek Fabrication** (fictional). "
               "Every number shows its sources.")
    pick = st.radio("Which RFQ?", list(RFQS) + ["PASTE"], format_func=lambda k: RFQ_LABELS.get(k, k), key="rfq_pick")
    rfq = None
    if pick == "PASTE":
        txt = st.text_area("Paste an RFQ email", key="paste_text", height=180,
                           placeholder="From: buyer@customer.example\nSubject: RFQ ...\n\nPlease quote 100 pcs ...")
        if st.button("Read this RFQ", key="paste_go"):
            st_["paste"] = txt
        if st_["paste"]:
            rfq = intake.pasted_rfq(st_["paste"])
    else:
        rfq = RFQS[pick]
    st.divider()
    st.markdown("**What-if controls**")
    cap = st.slider("Shop load (how busy are we?)", 0, 100, 50, 5, format="%d%%", key="capacity",
                    help="Busy shop: each hour displaces other work, so the price floor and opportunity cost rise.")
    age = st.slider("Age our newest material quote by (days)", 0, 180, 0, 15, key="mat_age",
                    help="Simulates a stale steel quote: material evidence decays fast (30-day half-life).")
    st.divider()
    prov, mode = llm.current_provider(), llm.demo_mode()
    st.markdown(f"**Model:** `{llm.current_model() if prov != 'mock' else 'mock fixtures'}`  \n"
                f"**Mode:** `{mode}`" + ("  (cache only, never calls a model)" if mode == "offline" else ""))
    mem = memory.list_memory()
    with st.expander(f"🧠 Memory: {len(mem)} saved override(s)"):
        if mem.empty:
            st.caption("Nothing yet. Overrides with reasons at Gate 1 / Gate 2 are saved here and reused as evidence.")
        for r in mem.itertuples(index=False):
            st.markdown(f"<div class='qm-small'><b>{r.doc_id}</b> · {html.escape(str(r.text))}</div>",
                        unsafe_allow_html=True)
    if st.button("↺ Reset demo state", key="reset", help="Removes demo-session overrides from memory and clears all choices."):
        memory.reset_memory()
        pipeline.clear_caches()
        st.session_state.clear()
        st.rerun()
    st.caption("All data is synthetic. Company and customer names are fictional. Rates and prices are illustrative.")

if rfq is None:
    st.info("Paste an RFQ email in the sidebar and click **Read this RFQ**.")
    st.stop()

rid = rfq["rfq_id"]


def pipeline_state(r_id: str) -> dict:
    ps = st_["rfq_states"].setdefault(r_id, pipeline.default_state())
    ps["capacity"] = cap / 100
    ps["material_age_days"] = int(age)
    prefix = f"gap_{r_id}_"
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith(prefix):
            ps["gap_actions"][k[len(prefix):]] = "assume" if st.session_state[k] == ASSUME else "ask"
    return ps


# baselines so switching RFQs later can show what changed (e.g. B learning from A's override)
msig = mem_signature()
for other_id, other in RFQS.items():
    if other_id not in st_["last"]:
        ops = pipeline_state(other_id)
        r0 = pipeline.run_pipeline(other, ops)
        st_["last"][other_id] = {"sig": json.dumps([ops, msig], sort_keys=True, default=str), "res": r0,
                                 "ps": json.loads(json.dumps(ops, default=str)), "mem": msig}

ps = pipeline_state(rid)
with st.spinner("Reading the RFQ and weighing the evidence..."):
    res = pipeline.run_pipeline(rfq, ps)
sig = json.dumps([ps, msig], sort_keys=True, default=str)
cur = {"sig": sig, "res": res, "ps": json.loads(json.dumps(ps, default=str)), "mem": msig}
last = st_["last"].get(rid)
if last and last["sig"] != sig:
    d = pipeline.diff(last["res"], res)
    if d:
        d["cause"] = cause_of_change(last, cur)
        st_["banner"][rid] = d
st_["last"][rid] = cur

spec, led, risk, pr = res["spec"], res["ledger"], res["risk"], res["pricing"]

# ---------------------------------------------------------------- header
tri = res["triage"]
tri_color = {"S": GREEN, "M": YELLOW, "L": RED}[tri["label"]]
c1, c2 = st.columns([3, 2])
with c1:
    st.markdown(f"<p class='qm-title'>{rid} · {html.escape(spec.get('customer_name') or 'Unknown customer')} · "
                f"{html.escape(spec.get('part_number') or 'no part number')}</p>", unsafe_allow_html=True)
    st.markdown(f"<span class='qm-badge' style='background:{tri_color}'>{tri['label']} · {tri['track']}</span> "
                f"<span class='qm-small'>&nbsp;Why: {html.escape(tri['reason'])}</span>", unsafe_allow_html=True)
with c2:
    n_asks = sum(1 for g in res["gaps"] if g["action"] == "ask")
    st.markdown(f"<div class='qm-small' style='text-align:right'>Received {spec['received_date']:%b %d, %Y} · "
                f"due {spec['due_date']:%b %d} · {len(led)} cost lines · "
                f"{n_asks} open question(s)</div>" if spec.get("due_date") else "", unsafe_allow_html=True)

steps = []
states = ["done", "wait" if n_asks else "done", "done" if ps["gate1_approved"] else "now",
          "done" if ps["gate1_approved"] else "", "done" if ps["gate1_approved"] else "",
          "done" if ps["gate2_approved"] else ("now" if ps["gate1_approved"] else ""),
          "done" if res["quote"]["ready"] else ("now" if ps["gate2_approved"] else "")]
marks = {"done": "✓ ", "wait": "… ", "now": "▶ ", "": ""}
st.markdown("<div class='qm-step'>" + "".join(
    f"<div class='{s}'>{marks[s]}{html.escape(n)}</div>" for n, s in zip(pipeline.STAGES, states)) + "</div>",
            unsafe_allow_html=True)

mix = {c: sum(1 for l in led if l["chip"] == c) for c in ("green", "yellow", "red")}
kp = [("Cost per unit (P50)", money(risk["p50"]), "median of 2,000 simulations"),
      ("Likely range (P10–P90)", f"{money(risk['p10'])} – {money(risk['p90'])}", f"band {risk['band_pct'] * 100:.1f}% of P50"),
      ("Recommended price / unit", money(pr["recommended"]), f"range {money(pr['range'][0])} – {money(pr['range'][1])}"),
      ("Win chance at that price", f"{pr['rec_p_win']:.0%}", f"markup {pr['rec_markup']:.2f}× P50"),
      ("How sure are we? (cost lines)", f"🟢{mix['green']} 🟡{mix['yellow']} 🔴{mix['red']}", "green ≥0.70 · red <0.40")]
st.markdown("<div class='qm-kpis'>" + "".join(f"<div><span>{a}</span><b>{b}</b><br><i>{c}</i></div>" for a, b, c in kp)
            + "</div>", unsafe_allow_html=True)

ban = st_["banner"].get(rid)
if ban:
    def arrow(a, b, fmt):
        cls = "up" if b > a else "down"
        return f"{fmt(a)} → <b class='{cls}'>{fmt(b)}</b>"
    pct = (ban["p50"][1] / ban["p50"][0] - 1) * 100 if ban["p50"][0] else 0
    lines_txt = ", ".join(
        f"{html.escape(c['label'])} {DOT.get(c['chip_from'], '⚪')}{(c['from'] or 0):.2f}→{DOT[c['chip_to']]}{c['to']:.2f}"
        for c in ban["changed_lines"][:6]) or "none"
    cause = "; ".join(ban.get("cause") or []) or "inputs changed"
    st.markdown(
        f"<div class='qm-banner'><b>What just changed</b> <span class='qm-small'>(because {html.escape(cause)})</span><br>"
        f"P50 cost/unit: {arrow(ban['p50'][0], ban['p50'][1], money)} ({pct:+.1f}%) &nbsp;·&nbsp; "
        f"Band width: {arrow(ban['band'][0] * 100, ban['band'][1] * 100, lambda x: f'{x:.1f}%')} &nbsp;·&nbsp; "
        f"Recommended price: {arrow(ban['rec'][0], ban['rec'][1], money)}<br>"
        f"<span class='qm-small'>Lines that changed confidence: {lines_txt}</span></div>", unsafe_allow_html=True)

section = st.radio("Section", SECTIONS, horizontal=True, key="section", label_visibility="collapsed")
st.divider()


# ---------------------------------------------------------------- 1 requirements
def sec_requirements():
    x = res["intake"]
    st.markdown("#### Gaps & conflicts")
    if not res["gaps"]:
        st.success("Nothing missing or conflicting: the RFQ is complete.")
    icon = {"conflict": "⚔️", "missing": "❓", "risk": "⏱️"}
    conts = {c["source"]: c for c in res["contingencies"]}
    for g in res["gaps"]:
        with st.container(border=True):
            a, b = st.columns([2, 3])
            a.markdown(f"**{icon.get(g['kind'], '•')} {html.escape(g['title'])}**")
            a.radio("What do we do?", [ASK, ASSUME], key=f"gap_{rid}_{g['id']}", horizontal=True,
                    index=1 if g["action"] == "assume" else 0)
            if g["action"] == "ask":
                b.markdown(f"**Question for the customer:** {g['question']}")
                b.caption("The quote stays a draft on this item until the customer answers.")
            else:
                c = conts.get(g["id"])
                extra = f" → +{money(c['amount'])}/unit on {g['affects']} lines" if c else ""
                b.markdown(f"**Assumption printed on the quote:** {g['assumption']}")
                b.caption(esc(f"Contingency {g['contingency_pct']:.0%} of the affected cost{extra}."))
    if res["due"].get("slack_days") is not None:
        d = res["due"]
        msg = (f"Due-date check: first release needs ~{d['hours_first_release']:.0f} shop hours → minimum lead ~"
               f"{d['min_lead_days']} days; customer allows {d['available_days']} days (slack {d['slack_days']:+d}).")
        (st.warning if d["slack_days"] < 5 else st.caption)(msg)
    if res["email"]:
        with st.expander("✉️ Draft clarification email (one email covering every 'ask' item)", expanded=False):
            st.markdown(f"<div class='qm-mail'>{html.escape(res['email'])}</div>", unsafe_allow_html=True)
            em = res["email_meta"]
            st.caption(f"Drafted by {em.get('provider')}:{em.get('model')} ({em.get('source')}). Review before sending.")

    st.markdown("#### What the customer asked for")
    left, right = st.columns([2, 3])
    with left:
        st.markdown("**The customer's request (email)**")
        st.markdown(f"<div class='qm-mail'>{html.escape(rfq.get('email_text', ''))}</div>", unsafe_allow_html=True)
        if rfq.get("customer_spec"):
            with st.expander("📎 Attached spec sheet (structured)"):
                st.json(rfq["customer_spec"])
    with right:
        meta = x["llm"]
        src = {"fixture": "mock fixture", "cache": "cached model output", "live": "model", "fallback": "rule-based fallback"}
        st.markdown(f"**What we understood** <span class='qm-small'>· extracted by "
                    f"`{meta['provider']}:{meta['model']}` ({src.get(meta['source'], meta['source'])}); the model only "
                    f"copies text, Python converts it; every value must quote the email</span>", unsafe_allow_html=True)
        rows = []
        for name, f in x["fields"].items():
            if name in ("notes",):
                continue
            where = []
            if f.get("source_quote") and f.get("email_value") is not None:
                q = html.escape(f["source_quote"][:70])
                where.append(("📧 “" + q + "”") if f.get("verified") else f"⚠ quote not found in email: “{q}”")
            if f.get("sheet_raw") is not None:
                where.append(f"📎 spec sheet: {html.escape(str(f['sheet_raw'])[:40])}")
            if "CONFLICT" in (f.get("origin") or ""):
                where.append(f"<b style='color:{RED}'>conflict: email {html.escape(field_text(name, f['email_value']))}"
                             f" vs sheet {html.escape(field_text(name, f['sheet_value']))}</b>")
            word = {"high": "high", "medium": "medium", "low": "low"}[f["confidence"]]
            rows.append(f"<tr><td>{html.escape(f['label'])}</td><td><b>{html.escape(field_text(name, f['value']))}</b></td>"
                        f"<td>{chip(f['confidence'], word)}</td><td class='qm-small'>{'<br>'.join(where) or '—'}</td></tr>")
        st.markdown("<table class='qm-t'><tr><th>Field</th><th>Value</th><th>How sure?</th><th>Where it came from</th></tr>"
                    + "".join(rows) + "</table>", unsafe_allow_html=True)
        facts = []
        if spec.get("repeat_part"):
            facts.append(f"repeat part number (prior runs: {', '.join(spec['prior_runs'])})")
        if spec.get("revision_change"):
            facts.append(f"**new revision** vs. {', '.join(spec['prior_revs'])}")
        if spec.get("first_run"):
            facts.append("**first run** (part number not in our history)")
        facts.append(f"customer segment: {spec.get('segment')}" + (" (new customer)" if spec.get("is_new_customer") else ""))
        st.markdown("From our history: " + "; ".join(facts))


# ---------------------------------------------------------------- 2 approach / gate 1
def sec_approach():
    an = res["analog"]
    with st.container(border=True):
        st.markdown(f"**Closest past job: {an['job_id']}** · {an['part_number']} · qty {an['qty']} · "
                    f"{'won' if an['won'] else 'lost'} · {'actual hours on file' if an['has_actuals'] else 'estimate only'}"
                    f" · similarity {an['sim']:.2f}")
        st.caption(f"Why it matched: {an['why']}")
        st.caption(an["description"])
    with st.expander("Other similar past jobs (top 8)"):
        sj = res["similar"].head(8)
        st.dataframe(pd.DataFrame({"Job": sj.job_id, "Part": sj.part_number, "Qty": sj.qty, "Won": sj.won,
                                   "Actuals": sj.has_actuals, "Similarity": sj.sim.round(2), "Why": sj.why}),
                     hide_index=True)
    st.markdown("**What's different from the analog**")
    st.dataframe(pd.DataFrame(res["proposal"]["diff"]).rename(
        columns={"field": "Field", "rfq": "This RFQ", "analog": f"Analog {an['job_id']}", "effect": "Expected cost effect"}),
                 hide_index=True)
    if res["proposal"]["rules"]:
        st.markdown("Rules applied: " + " · ".join(f"`{r}`" for r in res["proposal"]["rules"]))
    st.caption("Proposal = the analog's BOM + routing (its ACTUAL hours where recorded), adjusted by the rules above. "
               "Prices and rates come later from the evidence ledger.")

    st.markdown("#### Gate 1 · Estimator approves the BOM + routing")
    lines = res["proposal"]["lines"]
    if ps["gate1_approved"]:
        st.success("✓ Gate 1 approved by the estimator." + (
            f" {len(ps['gate1_edits'])} override(s) saved to memory." if ps["gate1_edits"] else ""))
        for kk, e in ps["gate1_edits"].items():
            l = next(x for x in lines if x["key"] == kk)
            st.markdown(esc(f"- ✎ **{l['label']}**: {l['proposed']:.2f} → **{e['value']:.2f}** {l['uom']} · reason: _{e['reason']}_"))
        if st.button("Re-open Gate 1", key=f"g1_reopen_{rid}"):
            ps["gate1_approved"] = False
            st_["g1_pending"][rid] = {kk: e["value"] for kk, e in ps["gate1_edits"].items()}
            st_["g1_ver"][rid] = st_["g1_ver"].get(rid, 0) + 1
            st.rerun()
        return
    pending = dict(st_["g1_pending"].get(rid, {}))
    base = pd.DataFrame([{
        "key": l["key"], "Include": l["key"] not in ps["gate1_excluded"], "Line": l["label"], "Unit": l["uom"],
        "From analog": round(float(l["proposed"]), 3), "Your value": round(float(pending.get(l["key"], l["proposed"])), 3),
        "Source": l["source"]} for l in lines]).set_index("key")
    ver = st_["g1_ver"].get(rid, 0)
    ed = st.data_editor(base, key=f"g1_{rid}_{ver}", hide_index=True, disabled=["Line", "Unit", "From analog", "Source"],
                        column_config={"Your value": st.column_config.NumberColumn(format="%.3f", min_value=0.0),
                                       "Include": st.column_config.CheckboxColumn(width="small")})
    prop = {l["key"]: float(l["proposed"]) for l in lines}
    pend = {kk: float(v) for kk, v in ed["Your value"].items() if abs(float(v) - prop[kk]) > 1e-9}
    excl = [kk for kk, inc in ed["Include"].items() if not inc]
    qa1, qa2, qa3 = st.columns([3, 2, 1])
    keys = [l["key"] for l in lines]
    labels = {l["key"]: f"{l['label']} ({l['uom']})" for l in lines}
    qk = qa1.selectbox("Quick adjust a line", keys, format_func=lambda kk: labels[kk], key=f"qa_line_{rid}",
                       index=keys.index("fit_tack.setup") if "fit_tack.setup" in keys else 0)
    qd = qa2.number_input("Change by (+/−)", value=6.0 if qk == "fit_tack.setup" else 0.0, step=0.5,
                          key=f"qa_delta_{rid}_{qk}")
    qa3.markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
    if qa3.button("Apply", key=f"qa_apply_{rid}"):
        pend[qk] = round(pend.get(qk, prop[qk]) + float(qd), 4)
        st_["g1_pending"][rid] = pend
        st_["g1_ver"][rid] = ver + 1
        st.rerun()
    if pend:
        st.markdown("Pending changes: " + "; ".join(f"**{labels[kk]}** {prop[kk]:.2f} → {v:.2f}" for kk, v in pend.items()))
    reason = st.text_input("Why? (required for any change; saved to memory so the next similar quote learns)",
                           key=f"g1_reason_{rid}", placeholder="e.g. new fixture needed: Rev C moved the hole pattern")
    if st.button("✓ Approve Gate 1", key=f"g1_approve_{rid}", type="primary"):
        if (pend or excl) and not reason.strip():
            st.error("Add a reason for your change(s) before approving. The reason is what the next quote learns from.")
        else:
            ps["gate1_edits"] = {kk: {"value": v, "reason": reason.strip()} for kk, v in pend.items()}
            ps["gate1_excluded"] = excl
            ps["gate1_approved"] = True
            memory.remove_for_rfq(rid)
            for kk, v in pend.items():
                l = next(x for x in lines if x["key"] == kk)
                memory.record_line_override(rid, spec, kk, f"{l['label']} ({l['uom']})", l.get("work_center"),
                                            prop[kk], v, reason)
            st_["g1_pending"][rid] = {}
            st.rerun()


# ---------------------------------------------------------------- 3 ledger
def _short(e: dict) -> str:
    return {"pattern": f"pattern {e['ref']}", "actual": f"{e['ref']} actuals", "past_quote": f"{e['ref']}'s quote",
            "supplier_quote": "recent supplier quotes", "shop_default": "the shop default",
            "note": f"note {e['ref']}", "override": f"override {e['ref']}"}.get(e["source_type"], e["ref"])


def evidence_sentence(l: dict) -> str:
    ev = [e for e in l["evidence"] if e["counted"]]
    top = " and ".join(dict.fromkeys(_short(e) for e in ev[:2])) or "nothing usable"
    why = ("sources agree closely" if (l["cv"] or 0) < 0.12 else "sources disagree" if (l["cv"] or 0) > 0.3
           else "sources mostly agree")
    weight = "plenty of" if l["sum_score"] >= 3 else "some" if l["sum_score"] >= 1.2 else "thin"
    return (f"Mostly {top}. {weight.capitalize()} evidence (weight {l['sum_score']:.1f} of 3) and {why} "
            f"(CV {l['cv'] or 0:.2f}), so confidence is {l['confidence']:.2f}.")


def sec_ledger():
    if not ps["gate1_approved"]:
        st.info("Draft ledger: the estimator hasn't approved the approach yet (Gate 1). Numbers update live.")
    order = sorted(led, key=lambda l: (CAT_ORDER[l["category"]], led.index(l)))
    rows = []
    for l in order:
        learned = any(e["source_type"] == "override" and e["ref"] != "This quote (Gate 1)" and e["counted"]
                      for e in l["evidence"])
        flags = ("✎" if l["overridden"] else "") + ("🧠" if learned else "") + ("⚠" if l["warnings"] else "") \
            + " ".join(l["patterns"])
        rows.append({"Sure?": f"{DOT[l['chip']]} {l['confidence']:.2f}", "Flags": flags, "Line": l["label"],
                     "Estimate": fmt_value(l), "Range": f"{l['low']:.3g} – {l['high']:.3g}",
                     "$/unit": round(l["cost"], 2), "Sources": l["n_evidence"]})
    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Cost ledger** <span class='qm-small'>· click a row (or pick below) to see where the number "
                    "came from</span>", unsafe_allow_html=True)
        ev = st.dataframe(pd.DataFrame(rows), hide_index=True, on_select="rerun", selection_mode="single-row",
                          key=f"ledger_{rid}", height=min(38 * len(rows) + 40, 760),
                          column_config={"$/unit": st.column_config.NumberColumn(format="$%.2f")})
        sel = list(getattr(getattr(ev, "selection", None), "rows", []) or [])
        keys = [l["key"] for l in order]
        if sel and st_["ledger_sel"].get(rid) != sel[0]:
            st_["ledger_sel"][rid] = sel[0]
            st.session_state[f"drawer_{rid}"] = keys[sel[0]]
        st.caption(esc(f"Total of lines: {money(sum(l['cost'] for l in led))}/unit · lot size {spec.get('lot_qty')} · "
                       f"burdened rates illustrative · ✎ estimator override · 🧠 learned from another quote · "
                       f"⚠ warning · P# pattern"))
    with right:
        default = next((l["key"] for l in order if l["patterns"]), None) or min(order, key=lambda l: l["confidence"])["key"]
        dk = st.selectbox("Where this number came from", keys, key=f"drawer_{rid}",
                          index=keys.index(default), format_func=lambda kk: next(l["label"] for l in order if l["key"] == kk))
        l = next(x for x in order if x["key"] == dk)
        with st.container(border=True):
            sure = f"How sure: {l['confidence']:.2f}"
            st.markdown(f"**{l['label']}** · {chip(l['chip'], sure)}", unsafe_allow_html=True)
            st.markdown(f"### {esc(fmt_value(l))}")
            st.caption(esc(f"Range {fmt_value(l, l['low'])} – {fmt_value(l, l['high'])} (±{l['spread'] * 100:.0f}%) · "
                           f"{money(l['cost'])}/unit"))
            st.markdown(f"<div class='qm-small'>{html.escape(evidence_sentence(l))}</div>", unsafe_allow_html=True)
            for w in l["warnings"]:
                st.warning(w)
            for e in l["evidence"]:
                if e["source_type"] == "override" and e["ref"] != "This quote (Gate 1)" and e["counted"]:
                    st.success(f"🧠 **Learned from an earlier quote** ({e['ref']}): {e['text']}  \n"
                               f"Counted as evidence with score {e['score']:.2f} → value {e['value']:.2f}.")
            ev_df = pd.DataFrame([{
                "Evidence": f"{e['source']} · {e['ref']}", "Value": None if e["value"] is None else round(e["value"], 3),
                "Score": e["score"] if e["counted"] else None,
                "= sim × auth × recency": f"{e['similarity']:.2f} × {e['authority']:.1f} × {e['decay']:.2f}"}
                for e in l["evidence"]])
            st.dataframe(ev_df, hide_index=True, height=min(36 * len(ev_df) + 40, 420))
            st.caption("Score = similarity × authority × recency. Authority: actual 1.0 · note/override/pattern 0.8 · "
                       "past quote 0.6 · shop default 0.3.")
            for e in l["evidence"][:10]:
                with st.expander(f"{e['source']} · {e['ref']} · score {e['score']:.2f}"):
                    st.markdown(f"**Why matched:** {e['why']}")
                    if e.get("text"):
                        st.markdown(f"<div class='qm-mail'>{html.escape(str(e['text']))}</div>", unsafe_allow_html=True)
                    if e.get("date"):
                        st.caption(f"Dated {e['date']} · {e['age_days']} days old · half-life {e['half_life'] or '—'} days")
    if res["patterns"]:
        st.markdown("#### Patterns found in our history")
        for p in res["patterns"]:
            st.info(esc(f"**{p['id']} · {p['title']}**  \n{p['narration']}  \n"
                        f"_Data: {p['stat']}. Adjustment: {p['adjustment']}._"))


# ---------------------------------------------------------------- 4 risk
def sec_risk():
    a, b = st.columns([3, 2])
    with a:
        s = np.array(risk["samples"])
        fig = go.Figure(go.Histogram(x=s, nbinsx=40, marker_color="#9db8e8", name="simulated cost"))
        for q, name, col in [("p10", "P10", GREY), ("p50", "P50", BLUE), ("p90", "P90", RED)]:
            fig.add_vline(x=risk[q], line_color=col, line_dash="dash",
                          annotation_text=f"{name} {money(risk[q])}", annotation_position="top")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), showlegend=False,
                          xaxis_title="Cost per unit ($)", yaxis_title="Simulations", bargap=0.05)
        st.plotly_chart(fig, key=f"hist_{rid}")
        st.caption(f"{risk['n']:,} Monte Carlo draws: each ledger line drawn from its triangular (low, value, high) "
                   f"range; steel lines move together; other lines independent (understates correlated risk).")
    with b:
        spread = sorted(led, key=lambda l: -(l["high"] - l["low"]) * l["multiplier"])[:6]
        fig2 = go.Figure(go.Bar(y=[l["label"] for l in spread][::-1],
                                x=[(l["high"] - l["low"]) * l["multiplier"] for l in spread][::-1], orientation="h",
                                marker_color=[CHIP[l["chip"]] for l in spread][::-1]))
        fig2.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), title="Where the uncertainty comes from",
                           xaxis_title="$/unit between low and high")
        st.plotly_chart(fig2, key=f"drivers_{rid}")
    c = st.columns(4)
    for i, (lab, key_) in enumerate([("P10", "p10"), ("P50", "p50"), ("P90", "p90")]):
        c[i].metric(lab, money(risk[key_]))
    c[3].metric("Contingencies", money(risk["contingency_total"]))
    if res["contingencies"]:
        st.dataframe(pd.DataFrame([{"Contingency": x["label"], "%": f"{x['pct'] * 100:.1f}%",
                                    "On": money(x["base"]), "$/unit": money(x["amount"])} for x in res["contingencies"]]),
                     hide_index=True)
    st.markdown("**Material freshness**")
    for mat, info in res["material_meta"].items():
        stale = (info.get("newest_age") or 0) > config.MATERIAL_STALE_DAYS
        txt = (f"{mat}: newest supplier quote is {info['newest_age']} days old; steel trend "
               f"{(info.get('trend_monthly') or 0) * 100:+.1f}%/month")
        if stale:
            st.warning(txt + f" → re-quote material or shorten quote validity to {config.QUOTE_VALIDITY_STALE_DAYS} days "
                             f"(escalation contingency {info['escalation_pct'] * 100:.1f}%).")
        else:
            st.success(txt + " → fresh.")
    mixc = {CAT_LABEL[k_]: v for k_, v in sorted(risk["by_category"].items(), key=lambda kv: CAT_ORDER[kv[0]])}
    st.caption("Cost mix per unit: " + " · ".join(f"{k_} {money(v)}" for k_, v in mixc.items()))


# ---------------------------------------------------------------- 5 price / gate 2
def sec_price():
    a, b = st.columns([3, 2])
    with a:
        x = np.array(pr["prices"])
        fig = go.Figure()
        fig.add_vrect(x0=pr["range"][0], x1=pr["range"][1], fillcolor="#1e8e3e", opacity=0.12, line_width=0,
                      annotation_text="recommended range", annotation_position="bottom left")
        fig.add_trace(go.Scatter(x=x, y=pr["exp_margin"], name="Expected margin $/unit", line=dict(color=BLUE, width=3)))
        fig.add_trace(go.Scatter(x=x, y=np.array(pr["p_win"]) * 100, name="Win chance %", yaxis="y2",
                                 line=dict(color=GREY, dash="dot")))
        fig.add_vline(x=pr["recommended"], line_color=GREEN, annotation_text=f"rec {money(pr['recommended'])}")
        fig.add_vline(x=pr["floor_price"], line_color=RED, line_dash="dash", annotation_text="floor",
                      annotation_position="bottom right")
        if abs(res["chosen_price"] - pr["recommended"]) > 0.01:
            fig.add_vline(x=res["chosen_price"], line_color="black", line_dash="dot", annotation_text="picked")
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="Unit price ($)",
                          yaxis=dict(title="Expected margin ($/unit)"),
                          yaxis2=dict(title="Win chance (%)", overlaying="y", side="right", range=[0, 100],
                                      tickvals=[0, 25, 50, 75, 100], showgrid=False),
                          legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig, key=f"curve_{rid}")
    with b:
        st.markdown(esc(f"**Recommended: {money(pr['recommended'])}/unit** ({pr['rec_markup']:.2f}× P50 cost, "
                        f"win chance {pr['rec_p_win']:.0%})"))
        st.caption(esc(f"Range {money(pr['range'][0])} – {money(pr['range'][1])} keeps ≥90% of the best expected margin."))
        st.markdown(
            f"<table class='qm-t'><tr><td>P50 cost</td><td>{money(risk['p50'])}</td></tr>"
            f"<tr><td>+ risk cushion (50% of P90−P50)</td><td>{money(pr['risk_adj_cost'] - risk['p50'])}</td></tr>"
            f"<tr><td>+ capacity cost (shop load {pr['load']:.0%})</td><td>{money(pr['capacity_cost'])}</td></tr>"
            f"<tr><th>= decision cost</th><th>{money(pr['decision_cost'])}</th></tr>"
            f"<tr><td>Minimum margin at this load</td><td>{pr['floor_pct']:.0%} → floor {money(pr['floor_price'])}</td></tr>"
            f"</table>", unsafe_allow_html=True)
        st.caption("Expected margin = win chance × (price − decision cost). Win chance comes from a logistic model "
                   "on our past quotes (price/cost ratio, customer, segment, new customer, quantity). No LLM involved.")
        e1, e2 = st.columns(2)
        e1.metric("Standard", money(pr["recommended"]), f"{res['lead_days']} days lead", delta_color="off")
        ex = res["expedite"]
        e2.metric("Expedite (illustrative)", money(ex["price"]), f"{ex['lead_days']} days (−{ex['days_saved']})",
                  delta_color="off")
    for p in res["patterns"]:
        if p["id"] == "P4":
            st.warning(esc(f"**{p['title']}**: {p['narration']}"))
    st.markdown("#### Gate 2 · Manager picks the price")
    if ps["gate2_approved"]:
        st.success(esc(f"✓ Gate 2 approved at {money(res['chosen_price'])}/unit"
                       + (" (expedite)" if ps["expedite"] else "") + (f" · reason: {ps['gate2_reason']}" if ps["gate2_reason"] else "")))
        if st.button("Re-open Gate 2", key=f"g2_reopen_{rid}"):
            ps["gate2_approved"] = False
            st.rerun()
        return
    kp = f"g2_price_{rid}"
    if kp not in st.session_state:
        st.session_state[kp] = round(pr["recommended"], 2)
    c1, c2, c3 = st.columns([2, 2, 2])
    price = c1.number_input("Unit price ($)", min_value=0.0, step=1.0, key=kp)
    if c2.button(esc(f"Use recommended ({money(pr['recommended'])})"), key=f"g2_userec_{rid}"):
        st.session_state[kp] = round(pr["recommended"], 2)
        st.rerun()
    exp_on = c3.toggle("Expedite (+12%, −7 days)", key=f"g2_exp_{rid}")
    final = price * (1 + config.EXPEDITE_PRICE_PCT) if exp_on else price
    inside = pr["range"][0] - 0.005 <= price <= pr["range"][1] + 0.005
    pw = pricing.pwin_at(price, risk["p50"], spec)
    st.caption(esc(f"At {money(price)}: markup {price / risk['p50']:.2f}×, win chance {pw:.0%}, expected margin "
                   f"{money(pw * (price - pr['decision_cost']))}/unit" + (f" · with expedite the customer pays {money(final)}" if exp_on else "")))
    reason = ""
    if not inside:
        st.warning("This price is outside the recommended range: a reason is required and will be saved to memory.")
        reason = st.text_input("Reason for pricing outside the range", key=f"g2_reason_{rid}")
    if st.button("✓ Approve Gate 2", key=f"g2_approve_{rid}", type="primary"):
        if not inside and not reason.strip():
            st.error("Add a reason before approving a price outside the recommended range.")
        else:
            ps["gate2_price"] = float(final)
            ps["expedite"] = bool(exp_on)
            ps["gate2_reason"] = reason.strip()
            ps["gate2_approved"] = True
            if not inside:
                memory.record_decision(rid, spec, "gate2_price",
                                       f"Manager priced {money(price)} vs recommended {money(pr['range'][0])}–"
                                       f"{money(pr['range'][1])}. Reason: {reason.strip()}")
            st.rerun()


# ---------------------------------------------------------------- 6 quote
def sec_quote():
    q = res["quote"]
    if q["ready"]:
        st.success("✓ Ready to send: both gates approved and no open questions.")
    else:
        why = []
        if not ps["gate1_approved"]:
            why.append("Gate 1 (approach) not approved")
        if not ps["gate2_approved"]:
            why.append("Gate 2 (price) not approved")
        if q["pending"]:
            why.append(f"{len(q['pending'])} question(s) waiting on the customer")
        st.warning("Draft: " + "; ".join(why) + ".")
    md = pipeline.quote_markdown(res)
    with st.container(border=True):
        st.markdown(esc(md.replace("# Quotation", "### Quotation", 1)))
    c1, c2 = st.columns(2)
    c1.download_button("⬇ Download quote (Markdown)", md, file_name=f"{rid}_quote.md", mime="text/markdown",
                       key=f"dl_md_{rid}")
    page = (f"<!doctype html><html><head><meta charset='utf-8'><title>{rid} quote</title>"
            f"<style>body{{font-family:Arial,sans-serif;max-width:760px;margin:40px auto;color:#111}}</style></head>"
            f"<body><pre style='white-space:pre-wrap;font-family:inherit'>{html.escape(md)}</pre></body></html>")
    c2.download_button("⬇ Download quote (HTML)", page, file_name=f"{rid}_quote.html", mime="text/html",
                       key=f"dl_html_{rid}")


{SECTIONS[0]: sec_requirements, SECTIONS[1]: sec_approach, SECTIONS[2]: sec_ledger, SECTIONS[3]: sec_risk,
 SECTIONS[4]: sec_price, SECTIONS[5]: sec_quote}[section]()

with st.expander("🔧 Debug (raw data)"):
    st.caption(f"Pipeline {res['elapsed_s']}s · provider {llm.current_provider()} · mode {llm.demo_mode()}")
    st.json({"spec": {k: str(v) for k, v in spec.items()}, "llm": res["llm_meta"], "state": ps}, expanded=False)
