"""Plain-language names for everything a non-technical viewer sees (used by the UI and the change banner)."""
from __future__ import annotations

from qm import config

FAMILY = {"hitch_bracket": "Hitch bracket", "guard": "Guard", "frame": "Frame", "mounting_plate": "Mounting plate",
          "tube_assembly": "Tube assembly"}
MATERIAL = {"A36": "A36 steel plate", "A500": "A500 steel tube", "5052AL": "5052 aluminum sheet"}
CONF_WORD = {"green": "High", "yellow": "Medium", "red": "Low"}
SOURCE = {"actual": "Past job (what it really took)", "past_quote": "Past quote", "shop_default": "Shop rule of thumb",
          "note": "Shop note", "override": "Estimator note", "pattern": "Lesson from past jobs",
          "supplier_quote": "Supplier price"}
UNITS = {"lb/unit": "lb per part", "ea/unit": "each per part", "hr/lot": "hours per batch", "hr/unit": "hours per part",
         "hr/order": "hours, once", "$/lb": "$ per lb", "$/ea": "$ each"}
TRACK = {"S": "Fast track", "M": "Standard review", "L": "Full review"}


def unit(u: str) -> str:
    return UNITS.get(u, u)


def line_label(l: dict) -> str:
    """Name of a BOM / routing line, e.g. 'Cut: setup (once per batch)'."""
    if l.get("kind") == "routing":
        wc = l.get("work_center")
        if wc == "fixture":
            return "Fixture build (one-time)"
        name = config.WC_LABELS.get(wc, str(wc))
        return f"{name}: " + ("setup (once per batch)" if l.get("hour_type") == "setup" else "run time (per part)")
    return l.get("label", l.get("key", ""))


def trust(score: float) -> str:
    """How much one piece of evidence counts (its score = similarity x authority x recency)."""
    return "A lot" if score >= 0.6 else "Some" if score >= 0.3 else "A little"


def source_from(text: str) -> str:
    """'J-1042 actual' -> 'Job J-1042 (actual hours)' for the plan table."""
    t = str(text)
    if t.startswith("rule:"):
        return "Rule: " + t[5:].strip()
    for suffix, word in ((" actual", "actual hours"), (" estimate", "last quote"), (" BOM", "parts list"),
                         (" BOM (scaled for thickness)", "parts list, scaled for thickness"),
                         (" BOM (material swapped)", "parts list, material swapped")):
        if t.endswith(suffix):
            return f"Job {t[:-len(suffix)]} ({word})"
    return t


def in_ten(p: float) -> str:
    return f"about {round(p * 10)} in 10"
