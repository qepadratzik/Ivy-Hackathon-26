"""Quick demo request: turn a handful of form fields into a realistic customer email plus a matching spec sheet,
so a presenter can run the whole flow on the spot with "on the spot" data.

Everything is fictional (customers come from the synthetic customer table; the sender is "Purchasing"). The email
and the spec sheet carry the same values, exactly like the three demo jobs, so the request reads the same way with the
hosted model, with the saved answers and with the built-in rules. One optional switch makes the spec sheet disagree
on the quantity so the conflict catch can be shown on demand.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from qm import config, plain

FAMILY_PHRASE = {"hitch_bracket": "hitch bracket weldment", "guard": "machine guard", "frame": "welded frame",
                 "mounting_plate": "mounting plate", "tube_assembly": "tube assembly"}
MATERIAL_TEXT = {"A36": "A36 plate", "A500": "A500 tube", "5052AL": "5052 aluminum sheet"}
THICKNESS = {"1/8": 0.125, "3/16": 0.1875, "1/4": 0.25, "3/8": 0.375, "1/2": 0.5}
WELD = {"standard": "Standard weld", "cosmetic": "Visible (cosmetic) weld", "none": "No welding"}
FINISH = {"powder": "Powder coat", "none": "No finish"}
COLORS = ["black", "gray", "implement yellow", "not stated"]
TOLERANCE = {"standard": "Standard", "tight": "Tight"}
EXAMPLE_PARTS = "LHM-MP-0620 (a part we have built), CVE-HB-4410 Rev D (a new revision)"
ID_PREFIX = "RFQ-Q"      # each build gets its own id (RFQ-Q1, RFQ-Q2, ...) so a later build can learn from an earlier one


def is_quick(rfq_id) -> bool:
    return str(rfq_id).startswith(ID_PREFIX)


def default_due() -> date:
    return config.AS_OF + timedelta(days=45)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _sheet_qty(qty: int) -> int:
    alt = max(1, int(round(qty * 0.8 / 5.0)) * 5)
    return alt if alt != qty else qty + 5


def quick_rfq(customer: str, family: str, material: str, thickness: str, qty: int, batch: int | None = None,
              weld: str = "standard", finish: str = "powder", color: str = "black", tolerance: str = "standard",
              due: date | None = None, part_number: str = "", qty_conflict: bool = False,
              rfq_id: str = ID_PREFIX + "1") -> dict:
    """Build an rfq dict (same shape as the demo RFQs) from form values."""
    qty = max(1, int(qty))
    batch = min(int(batch), qty) if batch else qty
    batch = batch if batch != qty else None
    due = due or default_due()
    pn = (part_number or "").strip()
    phrase = FAMILY_PHRASE[family]
    article = "an" if phrase[0] in "aeiou" else "a"
    mat_line = f'{thickness}" {MATERIAL_TEXT[material]}'
    lines = [f"Please quote {qty} pcs of {article} {phrase}" + (f", part number {pn}." if pn else "."),
             f"Material is {mat_line}."]
    if weld == "cosmetic":
        lines.append("Welds are cosmetic: visible side, smooth, no spatter.")
    elif weld == "none":
        lines.append("No welding on this one.")
    else:
        lines.append("Welds are standard, not cosmetic.")
    lines.append("Standard tolerance, +/-0.030 unless noted." if tolerance == "standard"
                 else "Tight tolerance, +/-0.005 on the critical features.")
    if finish == "none":
        lines.append("Finish: none, bare.")
    elif color and color != "not stated":
        lines.append(f"Powder coat {color}.")
    else:
        lines.append("Finish is powder coat per our usual.")
    if batch:
        lines.append(f"We would like releases of {batch}.")
    lines.append(f"Need them by {due:%b} {due.day}.")
    buyer = "Purchasing"
    email = (f"From: {buyer} <purchasing@{_slug(customer)}.example>\nTo: estimating@boonecreekfab.example\n"
             f"Date: Wed, 30 Sep 2026 09:00:00 -0500\nSubject: RFQ {pn or phrase}\n\nHi Boone Creek team,\n\n"
             + "\n".join(lines) + f"\n\nThanks,\n{buyer}\n{customer}\n")
    sheet = {"customer": customer, "part_number": pn or None,
             "description": f"{phrase.capitalize()}, {mat_line}", "material": f"{thickness} {MATERIAL_TEXT[material]}",
             "thickness_in": THICKNESS[thickness], "qty": _sheet_qty(qty) if qty_conflict else qty,
             "release_qty": batch, "tolerance": "+/-0.030 unless noted" if tolerance == "standard" else "+/-0.005",
             "weld": {"standard": "Standard", "cosmetic": "Cosmetic", "none": "None"}[weld],
             "finish": "Powder coat" if finish == "powder" else "None",
             "finish_color": color.title() if finish == "powder" and color != "not stated" else None,
             "due_date": due.isoformat(), "notes": "Entered on the quick demo form."}
    label = f"{customer}: {qty} x {plain.FAMILY[family].lower()}, {thickness}\" {MATERIAL_TEXT[material]}"
    return {"rfq_id": rfq_id, "label": label, "received_date": config.AS_OF, "email_text": email,
            "customer_spec": sheet, "expected": {}}


def summary(rfq: dict) -> str:
    """One line describing the request that was built (for the sidebar): what the customer asked for."""
    return rfq["label"]
