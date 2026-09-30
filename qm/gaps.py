"""S2 Gaps & conflicts (deterministic) + the one clarification email (LLM-drafted, template fallback).

Each gap: id, kind (missing|conflict|risk), field, title, question, action (ask|assume), assumption,
contingency_pct, affects (which ledger lines the contingency applies to).
  ask    -> the question goes into the clarification email; the quote stays a draft on that item.
  assume -> the stated assumption goes on the quote and a contingency is added to the affected lines.
"""
from __future__ import annotations

import math
import re
from datetime import date

from qm import config, llm
from qm.data_gen import frac

REQUIRED = ["customer_name", "part_family", "material", "thickness_in", "qty", "finish", "due_date"]
CONFLICT_FIELDS = ["material", "thickness_in", "qty", "finish"]
STOCK_COLORS = "black, gray or implement yellow"


def _fmt(field: str, v) -> str:
    if v is None:
        return "not stated"
    if field == "thickness_in":
        return f'{frac(float(v))}"'
    if field == "finish":
        return str(v).replace("_", " ")
    if isinstance(v, date):
        return v.strftime("%b %d, %Y")
    return str(v)


def find_gaps(intake: dict) -> list[dict]:
    fields, spec = intake["fields"], intake["spec"]
    gaps: list[dict] = []
    covered = set()
    for c in intake["conflicts"]:
        f = c["field"]
        if f not in CONFLICT_FIELDS:
            continue
        covered.add(f)
        e, s = _fmt(f, c["email"]), _fmt(f, c["sheet"])
        label = fields[f]["label"]
        if f == "qty":
            gaps.append(dict(
                id="qty_conflict", kind="conflict", field=f,
                title=f"Quantity conflict: email says {e}, spec sheet says {s}",
                question=f"Your email says {e} pcs total but the spec sheet line says {s} pcs. Which quantity should we quote?",
                assumption=f"Quoted at {e} pcs per your email; {s}-pc pricing shown as a separate break.",
                contingency_pct=config.GAP_CONTINGENCY["qty_conflict"], affects="setup"))
        else:
            gaps.append(dict(
                id=f"{f}_conflict", kind="conflict", field=f,
                title=f"{label} conflict: email says {e}, spec sheet says {s}",
                question=f"Your email says {label.lower()} {e} but the spec sheet says {s}. Which is correct?",
                assumption=f"Quoted per your email ({e}).",
                contingency_pct=config.GAP_CONTINGENCY.get("material" if f in ("material", "thickness_in") else "default"),
                affects="material" if f in ("material", "thickness_in") else "outside"))
    for f in REQUIRED:
        if f in covered:
            continue
        fld = fields.get(f, {})
        if fld.get("value") is None or fld.get("confidence") == "low":
            label = fld.get("label", f)
            affects, pct, assume = "all", config.GAP_CONTINGENCY["default"], f"Assumed {label.lower()} from the closest past job."
            if f in ("material", "thickness_in"):
                affects, pct = "material", config.GAP_CONTINGENCY["material"]
            elif f == "finish":
                affects, assume = "outside", "Assumed powder coat, black (our most common finish)."
            elif f == "due_date":
                affects, pct, assume = "none", 0.0, "Quoted at our standard lead time."
            elif f == "customer_name":
                affects, pct, assume = "none", 0.0, "Treated as a new customer."
            why = "not stated" if fld.get("value") is None else "could not be confirmed in the email"
            gaps.append(dict(id=f"missing_{f}", kind="missing", field=f, title=f"{label} {why}",
                             question=f"Can you confirm the {label.lower()}?", assumption=assume,
                             contingency_pct=pct, affects=affects))
    if spec.get("finish") in ("powder_coat", "zinc") and not spec.get("finish_color") and spec.get("finish") == "powder_coat":
        gaps.append(dict(
            id="finish_color", kind="missing", field="finish_color",
            title="Powder coat color not specified",
            question=f"What powder coat color do you need? Stock colors are {STOCK_COLORS}.",
            assumption="Assumed black (stock color). A non-stock color may add a batch charge.",
            contingency_pct=config.GAP_CONTINGENCY["finish_color"], affects="outside"))
    for g in gaps:
        g.setdefault("action", "ask")
    return gaps


def apply_actions(gaps: list[dict], actions: dict[str, str] | None) -> list[dict]:
    actions = actions or {}
    out = []
    for g in gaps:
        g = dict(g)
        if actions.get(g["id"]) in ("ask", "assume"):
            g["action"] = actions[g["id"]]
        out.append(g)
    return out


# ---------------------------------------------------------------- due-date feasibility (needs the ledger)
HOURS_PER_DAY = 6.0          # shop hours realistically available to one job per working day
MATERIAL_LEAD_DAYS = 5       # calendar days to get plate/tube in
QUEUE_DAYS = 5               # calendar days of queue before the job starts


def min_lead_days(first_release_hours: float, has_outside: bool) -> int:
    work_days = math.ceil(first_release_hours / HOURS_PER_DAY)
    cal = math.ceil(work_days * 7 / 5)
    return cal + MATERIAL_LEAD_DAYS + QUEUE_DAYS + (config.POWDER_COAT_DAYS if has_outside else 0)


def due_date_check(spec: dict, first_release_hours: float, has_outside: bool) -> tuple[dict | None, dict]:
    """Returns (risk gap or None, info dict)."""
    need = min_lead_days(first_release_hours, has_outside)
    info = {"min_lead_days": need, "hours_first_release": round(first_release_hours, 1)}
    due, received = spec.get("due_date"), spec.get("received_date") or config.AS_OF
    if not due:
        return None, info
    avail = (due - received).days
    info.update(available_days=avail, slack_days=avail - need)
    if avail < need:
        return dict(id="due_date_risk", kind="risk", field="due_date",
                    title=f"Due {due:%b %d} gives {avail} days; our minimum is ~{need} days",
                    question=f"Could the first release move to {date.fromordinal(received.toordinal() + need):%b %d}?",
                    assumption="Accepted the requested date; overtime may be needed to meet it (a safety cushion is added).",
                    contingency_pct=0.06, affects="labor", action="ask"), info
    return None, info


# ---------------------------------------------------------------- clarification email
EMAIL_PROMPT = """Write a short clarification email to the customer's buyer.
Buyer first name: {first}
Customer: {customer}
Part: {part}
Ask ONLY these questions, as a numbered list, in this order:
{questions}
Sign it: Estimating, Boone Creek Fabrication"""


def contact_first_name(email_text: str) -> str:
    m = re.search(r"^From:[ \t]*([A-Za-z]+)", email_text or "", re.M)
    return m.group(1) if m else "there"


def template_email(first: str, part: str, questions: list[str]) -> str:
    lines = [f"Hi {first},", "", f"Thanks for the RFQ on {part}. Before we finalize pricing, can you confirm:", ""]
    lines += [f"{i}. {q}" for i, q in enumerate(questions, 1)]
    lines += ["", "We'll turn the quote around as soon as we hear back.", "", "Thanks,",
              "Estimating, Boone Creek Fabrication"]
    return "\n".join(lines)


def clarification_email(gaps: list[dict], spec: dict, email_text: str,
                        use_llm: bool = True) -> tuple[str | None, dict]:
    asks = [g["question"] for g in gaps if g["action"] == "ask"]
    if not asks:
        return None, {"source": None}
    first = contact_first_name(email_text)
    part = spec.get("part_number") or "your part"
    if not use_llm:   # e.g. pasted RFQs: instant template; the model drafts only when asked
        return template_email(first, part, asks), {"source": "template", "provider": "template", "model": "rules"}
    prompt = EMAIL_PROMPT.format(first=first, customer=spec.get("customer_name") or "", part=part,
                                 questions="\n".join(f"{i}. {q}" for i, q in enumerate(asks, 1)))
    out, meta = llm.call_model_meta("clarification_email", prompt, None,
                                    fallback=lambda: template_email(first, part, asks))
    if not isinstance(out, str) or not out.strip():
        out = template_email(first, part, asks)
    return out.strip(), meta
