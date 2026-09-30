"""S4 Proposal: closest past job (analog) -> proposed BOM + routing for this RFQ, plus the
difference table (field | new RFQ | analog | expected cost effect).

Proposal values are what Gate 1 shows and the estimator can edit:
  routing lines -> hours (setup = hr per lot, run = hr per unit; the analog's ACTUALS when present)
  BOM lines     -> quantity per unit (lb of material, ea of purchased parts, 1 outside-process pass)
Prices/rates come later from the evidence ledger, never from the proposal.
"""
from __future__ import annotations

import pandas as pd

from qm import config
from qm.data_gen import MATERIAL_ITEM, SIZE_CLASS, frac, normalize_pn

ITEM_TO_MATERIAL = {v: k for k, v in MATERIAL_ITEM.items()}


def line_key_for_bom(item_type: str, item: str) -> str:
    if item_type == "raw":
        return f"mat.{ITEM_TO_MATERIAL.get(item, item)}"
    if item_type == "outside":
        return f"out.{item}"
    return f"pur.{item}"


def _label_bom(item_type: str, item: str) -> str:
    if item_type == "outside":
        return {"powder_coat": "Powder coat (outside)", "zinc_plate": "Zinc plate (outside)"}.get(item, item)
    return item


def build_proposal(spec: dict, analog: pd.Series, tables: dict) -> dict:
    bom = tables["bom_lines"][tables["bom_lines"].job_id == analog.job_id].sort_values("line_no")
    ops = tables["routing_ops"][tables["routing_ops"].job_id == analog.job_id].sort_values("seq")
    rules, lines = [], []

    # --- BOM
    t_new, t_old = spec.get("thickness_in"), analog.thickness_in
    for _, b in bom.iterrows():
        item, typ, q = b["item"], b["item_type"], float(b["qty_per"])
        src = f"{analog.job_id} BOM"
        if typ == "raw":
            mat = ITEM_TO_MATERIAL.get(item)
            if mat == analog.material and spec.get("material") and spec["material"] != mat:
                item = MATERIAL_ITEM.get(spec["material"], item)
                rules.append(f"Material {mat} -> {spec['material']}: swapped the plate line")
                src += " (material swapped)"
            if mat == analog.material and t_new and t_old and abs(float(t_new) - float(t_old)) > 1e-6:
                q = q * float(t_new) / float(t_old)
                rules.append(f'Thickness {frac(t_old)}" -> {frac(t_new)}": plate weight scaled x{float(t_new) / float(t_old):.2f}')
                src += " (scaled for thickness)"
        if typ == "outside" and item in ("powder_coat", "zinc_plate"):
            want = {"powder_coat": "powder_coat", "zinc": "zinc_plate"}.get(spec.get("finish") or "", None)
            if spec.get("finish") in ("none",):
                rules.append(f"Finish none: removed the {item.replace('_', ' ')} line")
                continue
            if want and want != item:
                rules.append(f"Finish change: {item.replace('_', ' ')} -> {want.replace('_', ' ')}")
                item = want
        key = line_key_for_bom(typ, item)
        lines.append(dict(key=key, kind="bom", category={"raw": "material", "purchased": "purchased",
                                                          "outside": "outside"}[typ],
                          item_type=typ, item=item, material=ITEM_TO_MATERIAL.get(item),
                          label=_label_bom(typ, item), uom=b["uom"] + "/unit", proposed=round(q, 3),
                          source=src))
    if spec.get("finish") in ("powder_coat", "zinc") and not any(l["category"] == "outside" for l in lines):
        item = "powder_coat" if spec["finish"] == "powder_coat" else "zinc_plate"
        lines.append(dict(key=f"out.{item}", kind="bom", category="outside", item_type="outside", item=item,
                          material=None, label=_label_bom("outside", item), uom="ea/unit", proposed=1.0,
                          source="rule: finish added"))
        rules.append(f"Finish {spec['finish'].replace('_', ' ')} requested, analog had none: added the outside line")

    # --- routing
    have_fixture = False
    for _, o in ops.iterrows():
        wc = o.work_center
        if wc == "fixture":
            have_fixture = True
        for hour_type in ("setup", "run"):
            if wc == "fixture" and hour_type == "run":
                continue
            act, est = o[f"{hour_type}_hr_act"], o[f"{hour_type}_hr_est"]
            use_act = pd.notna(act)
            val = float(act) if use_act else float(est)
            lines.append(_routing_line(wc, hour_type, val,
                                       f"{analog.job_id} {'actual' if use_act else 'estimate'}"))
    wcs = set(ops.work_center)
    if spec.get("cosmetic_weld") and "weld" in wcs and "grind" not in wcs:
        d = config.WORK_CENTERS["grind"]
        lines.append(_routing_line("grind", "setup", d[1], "rule: cosmetic weld needs grind"))
        lines.append(_routing_line("grind", "run", d[2] * 1.6, "rule: cosmetic weld needs grind"))
        rules.append("Cosmetic weld: added a grind / clean-up op")
    elif spec.get("cosmetic_weld") and "grind" in wcs:
        rules.append("Cosmetic weld: kept the grind / clean-up op")
    if spec.get("first_run") and spec.get("weldment") and not have_fixture and "fit_tack" in wcs:
        lines.insert(_first_routing_index(lines), _routing_line("fixture", "setup", config.FIXTURE_DEFAULT_HR,
                                                                "rule: first run, no fixture on file"))
        rules.append(f"First run and no fixture line on the analog: added a one-time fixture build "
                     f"({config.FIXTURE_DEFAULT_HR:.0f} hr shop default)")
    for l in lines:
        l["include"] = True
    return {"analog_id": analog.job_id, "lines": lines, "rules": rules,
            "diff": diff_table(spec, analog, tables, lines)}


def _first_routing_index(lines: list[dict]) -> int:
    for i, l in enumerate(lines):
        if l["kind"] == "routing":
            return i
    return len(lines)


def _routing_line(wc: str, hour_type: str, val: float, source: str) -> dict:
    lab = config.WC_LABELS.get(wc, wc)
    if wc == "fixture":
        return dict(key="fixture.setup", kind="routing", category="labor", work_center="fixture",
                    hour_type="setup", label=lab, uom="hr/order", proposed=round(val, 3), source=source)
    return dict(key=f"{wc}.{hour_type}", kind="routing", category="labor", work_center=wc, hour_type=hour_type,
                label=f"{lab}: {hour_type}", uom="hr/lot" if hour_type == "setup" else "hr/unit",
                proposed=round(val, 3), source=source)


def _rate(wc: str) -> float:
    return config.FIXTURE_RATE if wc == "fixture" else config.WORK_CENTERS[wc][0]


def diff_table(spec: dict, analog: pd.Series, tables: dict, lines: list[dict]) -> list[dict]:
    rows = []
    cust = tables["customers"].set_index("customer_id")
    a_cust = cust.loc[analog.customer_id]
    # part number / revision
    same_pn = spec.get("part_number") and normalize_pn(spec["part_number"]) == normalize_pn(analog.part_number)
    if same_pn and spec.get("part_number") != analog.part_number:
        eff = "New revision of a part we built: check that the fixture and programs still fit"
    elif same_pn:
        eff = "Same part: programs and fixture on file"
    else:
        eff = "Different part number: closest match by description + specs"
    rows.append(dict(field="Part number", rfq=spec.get("part_number") or "?", analog=analog.part_number, effect=eff))
    rows.append(dict(field="Customer", rfq=f"{spec.get('customer_name')} ({spec.get('segment')})",
                     analog=f"{a_cust['name']} ({a_cust['segment']})",
                     effect="Same customer" if spec.get("customer_id") == analog.customer_id
                     else "Different customer: price uses this customer's win history"))
    # quantity / lot size effect on setup
    lot, a_lot = spec.get("lot_qty") or spec.get("qty"), int(analog.qty)
    setup_cost = sum(l["proposed"] * _rate(l["work_center"]) for l in lines
                     if l["kind"] == "routing" and l["hour_type"] == "setup" and l["work_center"] != "fixture")
    eff = "Similar lot size"
    if lot and a_lot and lot != a_lot:
        delta = setup_cost / lot - setup_cost / a_lot
        eff = f"Setup spread over {lot} pcs instead of {a_lot}: {'+' if delta >= 0 else '-'}${abs(delta):.2f}/unit"
    q_txt = f"{spec.get('qty')} total" + (f", lots of {spec.get('release_qty')}" if spec.get("release_qty") else "")
    rows.append(dict(field="Quantity / lot", rfq=q_txt, analog=f"{a_lot} (one lot)", effect=eff))
    # material + thickness
    t = spec.get("thickness_in")
    rfq_m = f"{spec.get('material') or '?'} {frac(float(t)) + chr(34) if t else ''}".strip()
    an_m = f'{analog.material} {frac(float(analog.thickness_in))}"'
    eff = "Same material and thickness"
    if spec.get("material") != analog.material:
        eff = "Different material: plate line swapped, check the price evidence"
    elif t and abs(float(t) - float(analog.thickness_in)) > 1e-6:
        eff = f"Plate weight scaled x{float(t) / float(analog.thickness_in):.2f}"
    rows.append(dict(field="Material", rfq=rfq_m, analog=an_m, effect=eff))
    # weld
    cw, aw = spec.get("cosmetic_weld"), bool(analog.cosmetic_weld)
    wtxt = lambda c: "cosmetic" if c else ("standard" if c is False else "not stated")
    if cw is None:
        eff = "Weld class unknown"
    elif bool(cw) == aw:
        eff = "Same weld class" + (" (grind op kept)" if cw else "")
    elif cw:
        eff = "Cosmetic vs standard: expect more weld + grind hours (pattern P1)"
    else:
        eff = "Standard vs cosmetic analog: weld/grind hours may come in lower"
    rows.append(dict(field="Weld", rfq=wtxt(cw), analog=wtxt(aw), effect=eff))
    # finish
    fin = (spec.get("finish") or "not stated").replace("_", " ")
    col = spec.get("finish_color") or ("color TBD" if spec.get("finish") == "powder_coat" else "")
    af = (analog.finish or "").lower()
    same_fin = {"powder_coat": "powder" in af, "zinc": "zinc" in af,
                "none": af in ("", "none")}.get(spec.get("finish") or "", False)
    rows.append(dict(field="Finish", rfq=f"{fin} {('(' + col + ')') if col else ''}".strip(),
                     analog=analog.finish or "not recorded",
                     effect="Same process" + (": color to confirm" if col == "color TBD" else "") if same_fin
                     else "Finish line added/removed"))
    # first run / fixture
    fx = any(l["key"] == "fixture.setup" and l["source"].startswith("rule") for l in lines)
    rows.append(dict(field="First run", rfq="yes" if spec.get("first_run") else "no",
                     analog="yes" if analog.first_run else "no",
                     effect=f"One-time fixture line added ({config.FIXTURE_DEFAULT_HR:.0f} hr)" if fx
                     else ("Fixture line carried from analog" if any(l["key"] == "fixture.setup" for l in lines)
                           else "No fixture line")))
    # material price drift since the analog was quoted
    mp = tables["material_prices"]
    m = spec.get("material") or analog.material
    now = mp[(mp.material == m)].sort_values("quote_date").tail(3).price_per_lb.mean()
    then = mp[(mp.material == m) & (mp.quote_date <= analog.quote_date)].sort_values("quote_date").tail(3).price_per_lb.mean()
    if pd.notna(now) and pd.notna(then) and then > 0:
        rows.append(dict(field=f"{m} price", rfq=f"${now:.3f}/lb (latest quotes)",
                         analog=f"${then:.3f}/lb ({analog.quote_date:%b %Y})",
                         effect=f"{(now / then - 1) * 100:+.0f}% since the analog was quoted"))
    rows.append(dict(field="Tolerance", rfq=spec.get("tolerance_class") or "not stated", analog=analog.tolerance_class,
                     effect="Same" if spec.get("tolerance_class") == analog.tolerance_class else "Check inspection time"))
    return rows
