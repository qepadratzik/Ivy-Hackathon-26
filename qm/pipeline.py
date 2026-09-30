"""Pipeline wiring + change banner + quote preview + CLI.

    run_pipeline(rfq, state) -> result dict   (pure: reads memory, never writes it)
    diff(prev, new)          -> change banner dict (or None)

    python -m qm.pipeline --check-ollama      # connectivity + JSON smoke test (Quentin's PC)
    python -m qm.pipeline --warm demo/rfqs    # pre-fill cache/llm for every demo RFQ
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import date, timedelta

from qm import (config, evidence, gaps, intake, llm, patterns, plain, pricing, proposal, retrieval, store, triage,
                uncertainty)

STAGES = ["Customer Request", "Understand Requirements", "Determine Manufacturing Approach", "Estimate Cost",
          "Assess Risk & Uncertainty", "Determine Price", "Review & Submit Quote"]


def default_state() -> dict:
    return {
        "gap_actions": {},          # gap_id -> ask|assume
        "gap_reasons": {},          # gap_id -> reason (optional)
        "gate1_edits": {},          # line_key -> {"value": float, "reason": str}
        "gate1_excluded": [],       # line keys removed at Gate 1
        "gate1_approved": False,
        "material_age_days": 0,     # "what if our newest material quote were N days older?"
        "capacity": 0.5,            # shop load 0..1
        "gate2_price": None,
        "gate2_reason": "",
        "gate2_approved": False,
        "gate2_p50": None,          # cost snapshot at Gate 2 approval (to detect stale approvals)
        "expedite": False,
        "email_llm": None,          # None = auto (model for demo RFQs, template for pasted ones until asked)
    }


# ---------------------------------------------------------------- intake cache (per RFQ text + provider)
_INTAKE: dict[str, dict] = {}


def get_intake(rfq: dict) -> dict:
    key = hashlib.sha256(json.dumps([rfq.get("rfq_id"), rfq.get("email_text"), rfq.get("customer_spec"),
                                     str(rfq.get("received_date")), llm.current_provider(), llm.current_model(),
                                     llm.demo_mode()], default=str).encode()).hexdigest()
    if key not in _INTAKE:
        _INTAKE[key] = intake.extract(rfq)
    return _INTAKE[key]


def clear_caches() -> None:
    _INTAKE.clear()


# ---------------------------------------------------------------- Gate 1
def apply_gate1(lines: list[dict], edits: dict, excluded: list[str]) -> tuple[list[dict], dict, list[dict]]:
    out, overrides, bom_edits = [], {}, []
    for l in lines:
        l = dict(l)
        l["include"] = l["key"] not in set(excluded or [])
        e = (edits or {}).get(l["key"])
        l["value"] = float(e["value"]) if e else float(l["proposed"])
        if e and abs(l["value"] - float(l["proposed"])) > 1e-9:
            rec = {"old": float(l["proposed"]), "new": l["value"], "reason": e.get("reason", "")}
            if l["kind"] == "routing":
                overrides[l["key"]] = rec
            else:
                bom_edits.append(dict(rec, key=l["key"], label=l["label"]))
        out.append(l)
    return out, overrides, bom_edits


def fill_from_analog(spec: dict, analog) -> dict:
    """Missing essentials are taken from the closest past job (the 'assume' default of the matching gap),
    so a thin or partial RFQ still produces sane numbers. Listed in spec['assumed_from_analog']."""
    spec = dict(spec)
    filled = []
    for field, val in (("part_family", analog.part_family), ("material", analog.material),
                       ("thickness_in", float(analog.thickness_in)), ("qty", int(analog.qty))):
        if spec.get(field) in (None, ""):
            spec[field] = val
            filled.append(field)
    if spec.get("finish") in (None, ""):
        f = (analog.finish or "").lower()
        spec["finish"] = "powder_coat" if "powder" in f else "zinc" if "zinc" in f else "none"
        filled.append("finish")
    if not spec.get("lot_qty"):
        spec["lot_qty"] = spec.get("release_qty") or spec.get("qty")
    if "part_family" in filled:
        spec["weldment"] = spec["part_family"] in ("hitch_bracket", "frame", "tube_assembly", "guard")
    spec["assumed_from_analog"] = filled
    return spec


def first_release_hours(ledger: list[dict], spec: dict) -> float:
    lot = max(1, int(spec.get("lot_qty") or spec.get("qty") or 1))
    h = 0.0
    for l in ledger:
        if l["kind"] != "routing":
            continue
        h += l["value"] if l["hour_type"] == "setup" else l["value"] * lot
    return h


# ---------------------------------------------------------------- main
def run_pipeline(rfq: dict, state: dict | None = None) -> dict:
    t0 = time.time()
    st = default_state()
    st.update(state or {})
    t = store.tables()
    x = get_intake(rfq)
    spec = dict(x["spec"], rfq_id=rfq.get("rfq_id"))
    gap_list = gaps.apply_actions(gaps.find_gaps(x), st["gap_actions"])

    sims = retrieval.similar_jobs(spec, t)
    analog = retrieval.pick_analog(sims)
    if analog is not None:
        spec = fill_from_analog(spec, analog)
    tri = triage.triage(spec, float(analog.sim) if analog is not None else None)
    prop = proposal.build_proposal(spec, analog, t)
    lines, overrides, bom_edits = apply_gate1(prop["lines"], st["gate1_edits"], st["gate1_excluded"])
    pats = patterns.find_patterns(spec, t, {l["key"] for l in lines if l["include"]})
    ledger, meta = evidence.build_ledger(spec, lines, sims, t, pats, overrides, st["material_age_days"])

    has_outside = any(l["category"] == "outside" for l in ledger)
    if not has_outside and any(k.startswith("out.") for k in st["gate1_excluded"] or []):
        # the estimator removed the coating line at Gate 1: the color / finish questions go away too
        gap_list = [g for g in gap_list if g["id"] not in ("finish_color", "finish_conflict")]
    due_gap, due_info = gaps.due_date_check(spec, first_release_hours(ledger, spec), has_outside)
    if due_gap:
        gap_list += gaps.apply_actions([due_gap], st["gap_actions"])
    rid_ = str(rfq.get("rfq_id"))
    use_llm = st["email_llm"] if st["email_llm"] is not None else not (rid_ == "RFQ-PASTE" or rid_.startswith("RFQ-Q"))
    email, email_meta = gaps.clarification_email(gap_list, spec, rfq.get("email_text", ""), use_llm=use_llm)

    cont = uncertainty.contingencies(ledger, gap_list, meta["material"])
    risk = uncertainty.simulate(ledger, cont)
    curve = pricing.price_curve(spec, risk, float(st["capacity"]))
    stale = any((i.get("newest_age") or 0) > config.MATERIAL_STALE_DAYS for i in meta["material"].values())
    lead_days = int(max(due_info["min_lead_days"], 14))
    exp = pricing.expedite(curve["recommended"], lead_days)

    chosen = st["gate2_price"] if st["gate2_price"] is not None else curve["recommended"]
    if st["expedite"] and st["gate2_price"] is None:
        chosen = exp["price"]
    g2 = pricing.gate2_check(float(chosen), curve)
    if st["expedite"]:
        g2 = {"status": "ok", "in_range": True, "expedite": True}
    insufficient = []
    if analog is None or float(analog.sim) < config.SIM_THRESHOLD:
        insufficient.append("no past job is similar enough (similarity below "
                            f"{config.SIM_THRESHOLD}) to build a routing from")
    if len(spec.get("assumed_from_analog") or []) >= 3:
        insufficient.append(f"{len(spec['assumed_from_analog'])} essentials were missing and had to be assumed "
                            f"({', '.join(f.replace('_in', '').replace('_', ' ') for f in spec['assumed_from_analog'])})")
    g2_stale = None
    if st.get("gate2_approved") and st.get("gate2_p50"):
        drift = risk["p50"] / st["gate2_p50"] - 1
        if abs(drift) > 0.005:
            g2_stale = f"costs moved {drift * 100:+.1f}% since the price was approved"
        elif float(chosen) < curve["floor_price"] - 0.005 and not st["expedite"]:
            g2_stale = "the approved price is now below the minimum-margin floor"
    if not st.get("gate1_approved") and st.get("gate2_approved"):
        g2_stale = "the plan was re-opened after the price was approved"
    chosen_pwin = pricing.pwin_at(float(chosen) / (1 + exp["pct"]) if st["expedite"] else float(chosen),
                                  risk["p50"], spec)

    result = {
        "rfq_id": rfq.get("rfq_id"), "rfq": {k: v for k, v in rfq.items() if k != "expected"},
        "intake": x, "spec": spec, "gaps": gap_list, "email": email, "email_meta": email_meta,
        "triage": tri, "similar": sims.head(10), "analog": analog.to_dict() if analog is not None else None,
        "proposal": dict(prop, lines=lines), "overrides": overrides, "bom_edits": bom_edits,
        "patterns": pats, "ledger": ledger, "material_meta": meta["material"], "material_stale": stale,
        "due": due_info, "contingencies": cont, "risk": risk, "pricing": curve, "expedite": exp,
        "lead_days": lead_days, "chosen_price": float(chosen), "chosen_pwin": chosen_pwin, "gate2": g2,
        "gate2_stale": g2_stale, "insufficient": insufficient,
        "state": st, "validity_days": config.QUOTE_VALIDITY_STALE_DAYS if stale else config.QUOTE_VALIDITY_DAYS,
        "llm_meta": [x["llm"], email_meta] + [{"task": "pattern_narration", "source": p.get("narration_source")}
                                              for p in pats],
        "stage": current_stage(st, gap_list),
    }
    result["quote"] = build_quote(result)
    result["elapsed_s"] = round(time.time() - t0, 2)
    return result


def current_stage(st: dict, gap_list: list[dict]) -> int:
    """Index into STAGES of the furthest stage reached (for the header stepper)."""
    if st.get("gate2_approved"):
        return 6
    if st.get("gate1_approved"):
        return 5
    return 2


# ---------------------------------------------------------------- change banner
def summary(res: dict) -> dict:
    return {"p50": res["risk"]["p50"], "band": res["risk"]["band_pct"], "rec": res["pricing"]["recommended"],
            "p10": res["risk"]["p10"], "p90": res["risk"]["p90"],
            "lines": {l["key"]: (plain.line_label(l), l["confidence"], l["chip"]) for l in res["ledger"]},
            "validity": res["validity_days"]}


def diff(prev: dict | None, new: dict) -> dict | None:
    if not prev or prev.get("rfq_id") != new.get("rfq_id"):
        return None
    a, b = summary(prev), summary(new)
    changed = []
    for k, (lab, conf, chip) in b["lines"].items():
        if k in a["lines"]:
            _, c0, ch0 = a["lines"][k]
            if ch0 != chip or abs(conf - c0) >= 0.05:
                changed.append({"key": k, "label": lab, "from": c0, "to": conf, "chip_from": ch0, "chip_to": chip})
        else:
            changed.append({"key": k, "label": lab, "from": None, "to": conf, "chip_from": None, "chip_to": chip})
    removed = [a["lines"][k][0] for k in a["lines"] if k not in b["lines"]]
    moved = (abs(b["p50"] - a["p50"]) > 0.005 or abs(b["band"] - a["band"]) > 0.0005
             or abs(b["rec"] - a["rec"]) > 0.005 or changed or removed or a["validity"] != b["validity"])
    if not moved:
        return None
    pct = (b["p50"] / a["p50"] - 1) * 100 if a["p50"] else 0.0
    parts = [f"P50 cost/unit: ${a['p50']:,.2f} → ${b['p50']:,.2f} ({pct:+.1f}%)",
             f"Band width: {a['band'] * 100:.1f}% → {b['band'] * 100:.1f}%",
             f"Recommended price: ${a['rec']:,.2f} → ${b['rec']:,.2f}"]
    if a["validity"] != b["validity"]:
        parts.append(f"Quote validity: {a['validity']} → {b['validity']} days")
    return {"p50": (a["p50"], b["p50"]), "band": (a["band"], b["band"]), "rec": (a["rec"], b["rec"]),
            "range": ((a["p10"], a["p90"]), (b["p10"], b["p90"])),
            "validity": (a["validity"], b["validity"]),
            "changed_lines": changed, "removed_lines": removed, "text": ". ".join(parts) + "."}


# ---------------------------------------------------------------- quote preview (S10)
def build_quote(res: dict) -> dict:
    spec, ledger, curve, risk = res["spec"], res["ledger"], res["pricing"], res["risk"]
    price = res["chosen_price"]
    markup = price / risk["p50"] if risk["p50"] else 1.0
    lot = int(spec.get("lot_qty") or spec.get("qty") or 1)
    qty = int(spec.get("qty") or lot)
    per_unit_cont = risk["contingency_total"]
    breaks = sorted({lot, min(qty, lot * 2), qty})
    rows = [{"lot": b, "unit_price": round(price if b == lot else
                                           pricing.price_at_lot(ledger, per_unit_cont, b, markup, spec), 2)}
            for b in breaks]
    alt_totals = []
    for c in res["intake"]["conflicts"]:
        if c["field"] == "qty" and isinstance(c["sheet"], int) and c["sheet"] != qty:
            alt_totals.append({"total": c["sheet"], "lot": lot, "unit_price": round(
                pricing.price_at_lot(ledger, per_unit_cont, lot, markup, spec, total=c["sheet"]), 2)})
    setup_per_release = sum(l["value"] * l["multiplier"] * lot for l in ledger
                            if l["kind"] == "routing" and l["hour_type"] == "setup" and l["work_center"] != "fixture")
    tooling = sum(l["value"] * l["multiplier"] * qty for l in ledger if l["key"] == "fixture.setup")
    assumptions = [g["assumption"] for g in res["gaps"] if g["action"] == "assume"]
    pending = [g["title"] for g in res["gaps"] if g["action"] == "ask"]
    for mat, info in res["material_meta"].items():
        if (info.get("newest_age") or 0) > config.MATERIAL_STALE_DAYS:
            assumptions.append(f"{mat} pricing is based on a supplier quote {info['newest_age']} days old; "
                               f"quote valid {config.QUOTE_VALIDITY_STALE_DAYS} days.")
        else:
            assumptions.append(f"{mat} pricing based on current supplier quotes; subject to mill surcharges "
                               f"after {config.QUOTE_VALIDITY_DAYS} days.")
    for f in spec.get("assumed_from_analog") or []:
        assumptions.append(f"{f.replace('_in', '').replace('_', ' ').capitalize()} not stated; quoted as on our closest past job.")
    exclusions = ["Freight (FOB our dock)", "First article inspection report unless noted",
                  "Engineering or print changes after award"]
    if "first article" in (res["rfq"].get("email_text") or "").lower():
        exclusions[1] = "First article inspection report INCLUDED with the first release"
    cats = {}
    for l in ledger:
        cats[l["category"]] = cats.get(l["category"], 0.0) + l["cost"]
    lead = res["expedite"]["lead_days"] if res["state"].get("expedite") else res["lead_days"]
    st = res["state"]
    ready = (st.get("gate1_approved") and st.get("gate2_approved") and not pending and not res.get("gate2_stale")
             and not res.get("insufficient"))
    return {"part": spec.get("part_number") or "(part number not stated)",
            "customer": spec.get("customer_name") or "(customer not stated)", "qty": qty, "lot": lot,
            "unit_price": round(price, 2), "breaks": rows, "alt_totals": alt_totals, "lead_days": lead,
            "setup_per_release": setup_per_release, "tooling": tooling,
            "validity_days": res["validity_days"], "assumptions": assumptions, "exclusions": exclusions,
            "pending": pending, "cost_mix": cats, "ready": bool(ready),
            "date": max(config.AS_OF, date.today()),
            "terms": "Net 30. FOB Boone Creek Fabrication, Boone County, IA. Pricing per the revision named above; "
                     "print changes may require a re-quote."}


def quote_markdown(res: dict) -> str:
    q = res["quote"]
    s = res["spec"]
    out = [f"# Quotation: {q['part']}", "", "**Boone Creek Fabrication** (fictional)  ",
           f"To: {q['customer']}  ", f"Date: {q['date']:%B %d, %Y}  ", f"Valid: {q['validity_days']} days", ""]
    if res.get("insufficient"):
        out += ["> NOT PRICED: not enough information (" + "; ".join(res["insufficient"]) + ").", ""]
    elif not q["ready"]:
        out += ["> DRAFT: not released (an approval is pending or a question is still open).", ""]
    out += [f"**Part:** {q['part']}: {s.get('part_description') or '(description not stated)'}", "",
            f"**Quantity:** {q['qty']} pcs total, releases of {q['lot']}", "",
            "| Unit price if released in lots of | Unit price |", "|---:|---:|"]
    out += [f"| {r['lot']} pcs{' (as requested)' if r['lot'] == q['lot'] else ''} | ${r['unit_price']:,.2f} |"
            for r in q["breaks"]]
    for a in q.get("alt_totals", []):
        out += ["", f"If the total is {a['total']} pcs (releases of {a['lot']}): ${a['unit_price']:,.2f}/unit."]
    out += ["", f"**Setup & tooling (included in the unit prices above):** setup ${q['setup_per_release']:,.2f} per "
                f"release" + (f"; one-time fixture/tooling ${q['tooling']:,.2f}, spread over the {q['qty']} pcs"
                              if q["tooling"] > 0 else "; no tooling charge") + ".", ""]
    out += [f"**Lead time:** {q['lead_days']} days ARO for the first release", ""]
    if q["assumptions"]:
        out += ["**Assumptions**", ""] + [f"- {a}" for a in q["assumptions"]] + [""]
    out += ["**Exclusions**", ""] + [f"- {e}" for e in q["exclusions"]] + [""]
    if q["pending"]:
        out += ["**Waiting on customer**", ""] + [f"- {p}" for p in q["pending"]] + [""]
    out += [f"**Terms:** {q['terms']}", "", "_Synthetic demo data. Prices illustrative._"]
    return "\n".join(out)


# ---------------------------------------------------------------- CLI
def warm(folder: str) -> int:
    """Run every demo RFQ through the pipeline (intake, clarification emails for each ask/assume
    combination, pattern narrations) so the live demo is instant and offline mode has a cache."""
    rfqs = intake.load_demo_rfqs(folder)
    print(f"Provider: {llm.current_provider()}:{llm.current_model()}  mode: {llm.demo_mode()}")
    store.vector_store()
    for rid, r in rfqs.items():
        t0 = time.time()
        res = run_pipeline(r, {})
        ids = [g["id"] for g in res["gaps"]]
        combos = [{}]
        for gid in ids:
            combos += [dict(c, **{gid: "assume"}) for c in list(combos)]
        for c in combos:
            run_pipeline(r, {"gap_actions": c})
        srcs = sorted({m.get("source") or "-" for m in res["llm_meta"]})
        print(f"  {rid}: gaps={ids} analog={res['analog']['job_id']} P50=${res['risk']['p50']:.2f} "
              f"rec=${res['pricing']['recommended']:.2f} llm={srcs} ({time.time() - t0:.1f}s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m qm.pipeline")
    ap.add_argument("--check-ollama", "--check-model", dest="check_ollama", action="store_true",
                    help="smoke-test the configured model provider (ollama or anthropic)")
    ap.add_argument("--warm", metavar="RFQ_DIR", help="warm the LLM cache for all RFQs in a folder")
    args = ap.parse_args(argv)
    if args.check_ollama:
        rfq = intake.load_demo_rfqs().get("RFQ-A")
        prompt = intake.INTAKE_PROMPT.format(received=rfq["received_date"].isoformat(),
                                             email=rfq["email_text"].strip()) if rfq else None
        if not llm.check_ollama(prompt):
            return 1
        if rfq and llm.current_provider() in ("ollama", "anthropic"):
            x = intake.extract(rfq)
            s = x["spec"]
            found = sorted(g["id"] for g in gaps.find_gaps(x))
            want = sorted(rfq["expected"]["gaps"])
            print(f"RFQ A as read by the model: qty={s['qty']} lot={s['lot_qty']} material={s['material']} "
                  f"thickness={s['thickness_in']} cosmetic={s['cosmetic_weld']} finish={s['finish']} "
                  f"color={s['finish_color']} due={s['due_date']}")
            print(f"{'OK' if found == want else 'CHECK'}: gaps {found} (demo expects {want})")
            if found != want:
                print("      The live model read RFQ A differently. For the presentation use MODEL_PROVIDER=mock "
                      "(hand-checked extractions) or tell Claude what it printed.")
        return 0
    if args.warm:
        return warm(args.warm)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
