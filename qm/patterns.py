"""S6 Patterns: four hardcoded pandas queries over the shop's history, triggered only when the RFQ
matches the condition, shown only if n >= 3. Each returns a stat dict; the numeric adjustment is the
data-derived ratio (never an LLM number). The LLM only turns the dict into one plain sentence.
"""
from __future__ import annotations

import json

import pandas as pd

from qm import llm

MIN_N = 3
PRICE_SENSITIVE_CUTOFF = 1.25

NARRATION_PROMPT = """Pattern data (from this shop's past jobs):
{data}
Write ONE plain-English sentence a shop owner would understand. Use only these numbers."""


def _ops_with_jobs(t: dict) -> pd.DataFrame:
    return t["routing_ops"].merge(t["jobs"], on="job_id")


def p1_cosmetic_weld(spec: dict, t: dict) -> dict | None:
    if not spec.get("cosmetic_weld"):
        return None
    o = _ops_with_jobs(t)
    w = o[(o.work_center == "weld") & o.run_hr_act.notna()]
    cos, std = w[w.cosmetic_weld], w[~w.cosmetic_weld]
    if len(cos) < MIN_N:
        return None
    r = float((cos.run_hr_act / cos.run_hr_est).mean())
    r_std = float((std.run_hr_act / std.run_hr_est).mean()) if len(std) else None
    return dict(id="P1", line_key="weld.run", title="Visible (cosmetic) welds take longer than quoted",
                ratio=round(r, 3), n=len(cos),
                stat=f"cosmetic-weld jobs ran {r:.2f}x their quoted weld run hours (n={len(cos)})"
                     + (f" vs {r_std:.2f}x for standard welds" if r_std else ""),
                adjustment=f"weld run hours x{r:.2f} on the estimate",
                plain=f"On {len(cos)} past jobs with visible welds, welding took {r:.2f}x the quoted hours"
                      + (f" (ordinary welds: {r_std:.2f}x)" if r_std else "") + ", so this quote plans for the extra time.")


def p2_first_run_fixture(spec: dict, t: dict) -> dict | None:
    if not (spec.get("first_run") and spec.get("weldment")):
        return None
    o = _ops_with_jobs(t)
    ft = o[(o.work_center == "weld") & o.setup_hr_act.notna() & o.first_run & ~o.has_fixture_line]
    if len(ft) < MIN_N:
        return None
    r = float((ft.setup_hr_act / ft.setup_hr_est).mean())
    d = t["docs"]
    notes = d[d.job_id.isin(ft.job_id) & d.text.str.contains("fixture|jig", case=False)]
    return dict(id="P2", line_key="weld.setup", title="New welded parts without a fixture run long on setup",
                ratio=round(r, 3), n=len(ft), notes=len(notes),
                stat=f"first-run weldments quoted without a fixture ran {r:.2f}x their fit & weld setup "
                     f"(n={len(ft)}; {len(notes)} debriefs mention building a fixture)",
                adjustment=f"weld setup x{r:.2f}, or quote a one-time fixture line",
                plain=f"New welded parts quoted without a fixture took {r:.2f}x the planned fit & weld setup "
                      f"({len(ft)} jobs; {len(notes)} shop notes mention building one), so plan the fixture time.")


def p3_press_brake_thick(spec: dict, t: dict) -> dict | None:
    th = spec.get("thickness_in")
    if not th or float(th) < 0.5:
        return None
    o = _ops_with_jobs(t)
    pb = o[(o.work_center == "press_brake") & o.run_hr_act.notna() & (o.thickness_in >= 0.5)]
    if len(pb) < MIN_N:
        return None
    d = t["docs"]
    ncr_jobs = set(d[(d.doc_type == "ncr") & (d.work_center == "press_brake")].job_id)
    hit = pb.job_id.isin(ncr_jobs)
    rate = float(hit.mean())
    r_ncr = float((pb[hit].run_hr_act / pb[hit].run_hr_est).mean()) if hit.any() else 1.0
    r_ok = float((pb[~hit].run_hr_act / pb[~hit].run_hr_est).mean()) if (~hit).any() else 1.0
    expected = rate * r_ncr + (1 - rate) * r_ok
    return dict(id="P3", line_key="press_brake.run", title="Bending thick plate (1/2\" and up) often needs rework",
                ratio=round(expected, 3), n=len(pb), ncr_rate=round(rate, 2),
                stat=f"{rate:.0%} of press-brake jobs on 1/2\"+ plate had an NCR (n={len(pb)}); those ran "
                     f"{r_ncr:.2f}x quoted brake hours",
                adjustment=f"press brake run hours x{expected:.2f} (expected rework)",
                plain=f"{rate:.0%} of bending jobs on 1/2-inch-plus plate needed rework ({len(pb)} jobs), "
                      f"so the bending hours include the expected rework.")


def p4_price_sensitive(spec: dict, t: dict) -> dict | None:
    cid = spec.get("customer_id")
    if not cid:
        return None
    j = t["jobs"]
    c = j[j.customer_id == cid].assign(r=lambda x: x.quoted_price / x.est_cost)
    low, high = c[c.r < PRICE_SENSITIVE_CUTOFF], c[c.r >= PRICE_SENSITIVE_CUTOFF + 0.05]
    if len(low) < MIN_N or len(high) < MIN_N:
        return None
    wl, wh = float(low.won.mean()), float(high.won.mean())
    if not (wl >= 0.70 and wh <= 0.25):
        return None  # only a pattern if this customer is sharply price-sensitive (most customers are not)
    return dict(id="P4", line_key="price", title=f"{spec.get('customer_name')} shops on price",
                ratio=None, n=len(c),
                stat=f"won {wl:.0%} of quotes under {PRICE_SENSITIVE_CUTOFF:.2f}x cost (n={len(low)}) but "
                     f"{wh:.0%} at {PRICE_SENSITIVE_CUTOFF + 0.05:.2f}x or more (n={len(high)})",
                adjustment=f"keep the markup under {PRICE_SENSITIVE_CUTOFF:.2f}x; the win model already reflects this",
                plain=f"We won {wl:.0%} of {spec.get('customer_name')}'s quotes priced under {PRICE_SENSITIVE_CUTOFF:.2f}x cost "
                      f"but only {wh:.0%} above that, so keep the markup tight.")


QUERIES = [p1_cosmetic_weld, p2_first_run_fixture, p3_press_brake_thick, p4_price_sensitive]


def find_patterns(spec: dict, t: dict, line_keys: set[str] | None = None, narrate: bool = True) -> list[dict]:
    out = []
    for q in QUERIES:
        p = q(spec, t)
        if not p or p["n"] < MIN_N:
            continue
        if p["id"] == "P2" and line_keys is not None and "fixture.setup" in line_keys:
            # the proposal already carries a one-time fixture line: P2 explains it instead of inflating setup
            p.update(line_key="fixture.setup", ratio=None,
                     adjustment="a one-time fixture line is in this quote, so setup is not inflated",
                     plain=p["plain"].replace("so plan the fixture time.", "so this quote carries a one-time "
                                                                             "fixture line instead."))
        if line_keys is not None and p["line_key"] != "price" and p["line_key"] not in line_keys:
            continue
        if narrate:
            p["narration"], p["narration_source"] = narrate_pattern(p)
        out.append(p)
    return out


def narrate_pattern(p: dict) -> tuple[str, str]:
    data = {k: p[k] for k in ("title", "stat", "adjustment")}
    fallback = p.get("plain") or f"{p['title']}: {p['stat']}, so we apply {p['adjustment']}."
    out, meta = llm.call_model_meta("pattern_narration", NARRATION_PROMPT.format(data=json.dumps(data)),
                                    None, fallback=fallback)
    text = out.strip() if isinstance(out, str) and out.strip() else fallback
    return text, meta.get("source") or "fallback"
