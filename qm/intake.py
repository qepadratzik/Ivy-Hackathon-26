"""S1 Intake: RFQ email -> structured spec.

The LLM only COPIES text: every field value is a string as written in the email plus a verbatim
source quote and a confidence. Python then normalizes (materials, fractions, dates, families) and
verifies that each source quote really appears in the email; if not, the field is downgraded.
The customer's attached spec sheet (structured JSON) is parsed deterministically and merged;
disagreements become conflicts in gaps.py.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from qm import config, llm, store
from qm.data_gen import normalize_pn

Conf = Literal["high", "medium", "low"]


class Field(BaseModel):
    value: str | None = None
    confidence: Conf = "low"
    source_quote: str | None = None


class RFQSpec(BaseModel):
    customer_name: Field = Field()
    part_number: Field = Field()
    part_description: Field = Field()
    part_family: Field = Field()
    material: Field = Field()
    thickness_in: Field = Field()
    qty: Field = Field()
    release_qty: Field = Field()
    tolerance_class: Field = Field()
    cosmetic_weld: Field = Field()
    finish: Field = Field()
    finish_color: Field = Field()
    due_date: Field = Field()
    notes: Field = Field()


FIELD_LABELS = {
    "customer_name": "Customer", "part_number": "Part number", "part_description": "Description",
    "part_family": "Part family", "material": "Material", "thickness_in": "Thickness",
    "qty": "Total quantity", "release_qty": "Release (lot) size", "tolerance_class": "Tolerance",
    "cosmetic_weld": "Cosmetic weld", "finish": "Finish", "finish_color": "Finish color",
    "due_date": "Due date (first release)", "notes": "Notes",
}
FAMILIES = ["hitch_bracket", "guard", "frame", "mounting_plate", "tube_assembly"]

INTAKE_PROMPT = """Extract the RFQ fields from the customer's EMAIL below.
Rules:
- Copy values as written in the email. Do NOT invent, guess, convert or calculate anything.
- If a field is not stated in the email: value null, confidence "low", source_quote null.
- source_quote = the shortest exact phrase copied from the email that supports the value.
- confidence: "high" = stated explicitly, "medium" = stated but informal or ambiguous.
- Field meanings:
  customer_name: the buyer's company. part_number: as written. part_description: one line.
  part_family: one of hitch_bracket, guard, frame, mounting_plate, tube_assembly (or null).
  material: material/grade as written (e.g. 3/8" A36 plate). thickness_in: thickness as written (e.g. 3/8").
  qty: TOTAL quantity as written. release_qty: quantity per release/lot, only if stated.
  tolerance_class: "standard" or "tight" as stated. cosmetic_weld: "yes" if cosmetic/visible/appearance
  welds are required, "no" if standard/structural or no cosmetic requirement, else null.
  finish: finish process as written (e.g. powder coat). finish_color: the color only if stated.
  due_date: the first required delivery date as written. notes: anything else the estimator must know.

EMAIL (received {received}):
<<<
{email}
>>>"""


# ---------------------------------------------------------------- normalization helpers
_MATERIAL_PATTERNS = [
    ("5052AL", r"5052|alum"),
    ("A500", r"a[\s-]?500|\bhss\b|\btube\b(?!.*plate)"),
    ("A36", r"a[\s-]?36|hr\s*plate|hot[\s-]?rolled|\bhrs\b"),
]
GAUGE = {"16": 0.0598, "14": 0.075, "12": 0.105, "11": 0.1196, "10": 0.135, "7": 0.1793}


def normalize_material(text: str | None) -> str | None:
    if not text:
        return None
    t = str(text).lower()
    # plate/sheet/bar callouts beat the tube mention when both appear
    for code, pat in _MATERIAL_PATTERNS:
        if code == "A500" and re.search(r"a[\s-]?36", t):
            continue
        if re.search(pat, t):
            return code
    return None


def parse_thickness(text) -> float | None:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text) if text > 0 else None
    t = str(text).lower().replace("”", '"').replace("''", '"')
    m = re.search(r"(\d+)\s*(?:ga|gauge|gage)\b", t)
    if m and m.group(1) in GAUGE:
        return GAUGE[m.group(1)]
    m = re.search(r"(\d+)\s*/\s*(\d+)", t)
    if m and int(m.group(2)) in (2, 4, 8, 16, 32):
        return round(int(m.group(1)) / int(m.group(2)), 4)
    m = re.search(r"(?<![\d/])(\d*\.\d+)", t)
    if m:
        v = float(m.group(1))
        return v if 0 < v < 3 else None
    return None


def parse_int(text) -> int | None:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    m = re.search(r"(\d[\d,]*)", str(text))
    return int(m.group(1).replace(",", "")) if m else None


def normalize_family(*texts) -> str | None:
    t = " ".join(str(x) for x in texts if x).lower()
    if not t:
        return None
    for fam in FAMILIES:
        if fam in t or fam.replace("_", " ") in t:
            return fam
    if "hitch" in t:
        return "hitch_bracket"
    if "guard" in t or "shield" in t:
        return "guard"
    if "tube assembly" in t or "tube assy" in t:
        return "tube_assembly"
    if "mounting plate" in t or "adapter plate" in t:
        return "mounting_plate"
    if "frame" in t:
        return "frame"
    return None


def normalize_finish(text) -> str | None:
    if not text:
        return None
    t = str(text).lower()
    if "powder" in t:
        return "powder_coat"
    if "zinc" in t:
        return None   # not offered in this shop model: becomes a question for the customer
    if any(w in t for w in ("paint", "primer", "e-coat", "ecoat")):
        return "powder_coat"  # closest priced finish in this shop's history
    if any(w in t for w in ("none", "bare", "oiled", "raw", "no finish", "mill")):
        return "none"
    return None


def normalize_bool(text) -> bool | None:
    if text is None:
        return None
    if isinstance(text, bool):
        return text
    t = str(text).strip().lower()
    if t in ("", "null", "none", "n/a", "unknown"):
        return None
    if re.search(r"\bno\b|not cosmetic|no cosmetic|standard|structural|false", t):
        return False
    if re.search(r"\byes\b|cosmetic|visible|appearance|show[\s-]?side|true", t):
        return True
    return None


def normalize_tolerance(text) -> str | None:
    if not text:
        return None
    t = str(text).lower()
    if "tight" in t:
        return "tight"
    m = re.findall(r"0?\.(\d+)", t)
    if m:
        vals = [float("0." + x) for x in m]
        return "tight" if min(vals) < 0.010 else "standard"
    if "standard" in t or "std" in t:
        return "standard"
    return None


_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                       "nov", "dec"], 1)}


def parse_date(text, received: date) -> date | None:
    if text is None:
        return None
    if isinstance(text, date):
        return text
    t = str(text).strip().lower()
    m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", t)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", t)
    if m:
        y = int(m.group(3)) if m.group(3) else received.year
        y = y + 2000 if y < 100 else y
        try:
            d = date(y, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
        return d if m.group(3) or d >= received else date(y + 1, d.month, d.day)
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:,?\s*(20\d\d))?", t)
    if m:
        y = int(m.group(3)) if m.group(3) else received.year
        try:
            d = date(y, _MONTHS[m.group(1)], int(m.group(2)))
        except ValueError:
            return None
        return d if m.group(3) or d >= received else date(y + 1, d.month, d.day)
    m = re.search(r"(\d+)\s*weeks?", t)
    if m:
        return received + timedelta(weeks=int(m.group(1)))
    return None


def normalize_field(name: str, raw, received: date):
    if name == "material":
        return normalize_material(raw)
    if name == "thickness_in":
        return parse_thickness(raw)
    if name in ("qty", "release_qty"):
        return parse_int(raw)
    if name == "part_family":
        return normalize_family(raw)
    if name == "finish":
        return normalize_finish(raw)
    if name == "cosmetic_weld":
        return normalize_bool(raw)
    if name == "tolerance_class":
        return normalize_tolerance(raw)
    if name == "due_date":
        return parse_date(raw, received)
    if name == "finish_color":
        v = str(raw).strip().lower() if raw else None
        return None if v in (None, "", "null", "none", "n/a", "tbd", "not specified") else v
    return str(raw).strip() if raw not in (None, "") else None


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("”", '"').replace("’", "'")).strip().lower()


_WORD_RE = re.compile(r"[a-z0-9]+(?:[/.\-][a-z0-9]+)*")


def verify_quotes(extracted: dict, email: str) -> dict:
    """Anti-hallucination guard. Each value must cite the email:
    exact (whitespace/quote-normalized) quote -> verified;
    every word of the quote appears in the email (small models paraphrase punctuation) -> verified,
      confidence capped at medium;
    otherwise -> unverified, confidence low (becomes a gap if the field is required).
    Quantities must also appear as a number inside their quote."""
    body = _norm_ws(email)
    body_tokens = set(_WORD_RE.findall(body))
    for name, f in extracted.items():
        if f.get("value") in (None, ""):
            f.update(confidence="low", source_quote=None, verified=None)
            continue
        q = _norm_ws(f.get("source_quote") or "").strip(" .,;:\"'")
        exact = bool(q) and q in body
        toks = _WORD_RE.findall(q)
        approx = (not exact) and bool(toks) and all(t in body_tokens for t in toks)
        ok = exact or approx
        if ok and name in ("qty", "release_qty"):
            n = parse_int(f["value"])
            ok = n is not None and str(n) in q.replace(",", "")
        f["verified"] = ok
        if not ok:
            f["confidence"] = "low"
        elif approx and f.get("confidence") == "high":
            f["confidence"] = "medium"
    return extracted


# ---------------------------------------------------------------- rule-based fallback extractor
def rule_extract(email: str) -> dict:
    """Deterministic regex extraction: used when no model output is available (mock paste box,
    offline cache miss, or two invalid model replies). Confidence is at most 'medium'."""
    out = {k: {"value": None, "confidence": "low", "source_quote": None} for k in RFQSpec.model_fields}
    body = email.split("\n\n", 1)[1] if "\nSubject:" in email and "\n\n" in email else email

    def put(name, value, quote, conf="medium"):
        if value and quote and out[name]["value"] is None:
            out[name] = {"value": str(value), "confidence": conf, "source_quote": quote.strip()}

    for name in store.customers_by_name():
        m = re.search(re.escape(name.split()[0]) + r"[^\n]*", email, re.I)
        if m and name.split()[0].lower() in m.group(0).lower():
            put("customer_name", m.group(0).strip(), m.group(0))
            break
    m = re.search(r"\b([A-Z]{2,4}-[A-Z]{2}-\d{2,5}(?:\s+Rev\s+[A-Z0-9])?)", email)
    if m:
        put("part_number", m.group(1), m.group(1))
    m = re.search(r"(\d[\d,]*)\s*(?:pcs|pieces|pc|ea|units)\b(?!\s*per)", body, re.I) or \
        re.search(r"(?:qty|quantity)\s*(?:is|of|:)?\s*(\d[\d,]*)", body, re.I)
    if m:
        put("qty", m.group(1), m.group(0))
    m = re.search(r"(?:releases?|lots?)\s+of\s+(\d+)", body, re.I)
    if m:
        put("release_qty", m.group(1), m.group(0))
    m = re.search(r"(\d+/\d+\"?|\d*\.\d+\"?|\d+\s*ga)\s*(?:\"|in\.?)?\s*([^\n,.;]*?(?:a-?36|a-?500|5052|plate|sheet|steel)[^\n,.;]*)",
                  body, re.I)
    if m:
        put("material", m.group(0), m.group(0))
        put("thickness_in", m.group(1), m.group(1))
    else:
        m = re.search(r"\b(a-?36|a-?500|5052|alumin(?:um|ium))\b[^\n,.;]*",
                      body, re.I)
        if m:
            put("material", m.group(0), m.group(0))
    m = re.search(r"[^\n.]*(no cosmetic|not cosmetic|structural weld|standard weld|no welding)[^\n.]*", body, re.I)
    if m:
        put("cosmetic_weld", "no", m.group(0))
    else:
        m = re.search(r"[^\n.]*(cosmetic|visible side|appearance)[^\n.]*", body, re.I)
        if m:
            put("cosmetic_weld", "yes", m.group(0))
    m0 = re.search(r"finish[^\n.]*?\b(none|bare|no finish|raw|mill finish|as[- ]welded)\b[^\n.,]*", body, re.I)
    if m0:
        put("finish", "none", m0.group(0))
    m = re.search(r"(powder[\s-]?coat[^\n.,]*|paint[^\n.,]*)", body, re.I)
    if m:
        put("finish", m.group(1), m.group(1))
        line = re.search(r"[^\n]*" + re.escape(m.group(1)) + r"[^\n]*", body).group(0)
        c = re.search(r"\b(gloss black|black|red|yellow|orange|gray|grey|white|green|blue)\b", line, re.I)
        if c:
            put("finish_color", c.group(1), c.group(1))
    m = re.search(r"(?:by|due|need(?:ed)?\s+(?:them\s+)?by|delivery)\s*:?\s*((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?|20\d\d-\d\d-\d\d)",
                  body, re.I)
    if m:
        put("due_date", m.group(1), m.group(0))
    m = re.search(r"[^\n.]*(standard tolerance|\+/-\s*0?\.\d+)[^\n.]*", body, re.I)
    if m:
        put("tolerance_class", m.group(0), m.group(0))
    fam = normalize_family(body[:600])
    if fam:
        m = re.search(r"(hitch bracket|guard|shield|frame|mounting plate|tube assembly)(?:[^\n.]|\.(?=\d))*", body, re.I)
        put("part_family", fam, m.group(0) if m else fam)
        put("part_description", m.group(0) if m else fam, m.group(0) if m else fam)
    return out


# ---------------------------------------------------------------- spec sheet (structured) parse
SHEET_MAP = {"customer": "customer_name", "part_number": "part_number", "description": "part_description",
             "material": "material", "thickness_in": "thickness_in", "qty": "qty", "release_qty": "release_qty",
             "tolerance": "tolerance_class", "weld": "cosmetic_weld", "finish": "finish",
             "finish_color": "finish_color", "due_date": "due_date", "notes": "notes"}


def parse_sheet(sheet: dict | None, received: date) -> dict:
    out = {}
    if not sheet:
        return out
    for k, name in SHEET_MAP.items():
        raw = sheet.get(k)
        if raw in (None, ""):
            continue
        if name == "cosmetic_weld" and str(raw).strip().lower() in ("none", "no welding", "n/a"):
            val = None
        else:
            val = normalize_field(name, raw, received)
        out[name] = {"raw": raw, "value": val}
    if "thickness_in" not in out and "material" in sheet:
        t = parse_thickness(sheet["material"])
        if t:
            out["thickness_in"] = {"raw": sheet["material"], "value": t}
    if "part_family" not in out:
        fam = normalize_family(sheet.get("description"), sheet.get("part_number"))
        if fam:
            out["part_family"] = {"raw": sheet.get("description"), "value": fam}
    return out


# ---------------------------------------------------------------- main entry
def extract(rfq: dict) -> dict:
    """Returns {'fields': {name: {...}}, 'spec': flat normalized dict, 'conflicts': [...], 'llm': meta}."""
    received = rfq.get("received_date") or config.AS_OF
    if isinstance(received, str):
        received = date.fromisoformat(received)
    email = rfq.get("email_text", "")
    prompt = INTAKE_PROMPT.format(received=received.isoformat(), email=email.strip())
    raw, meta = llm.call_model_meta("intake_extract", prompt, RFQSpec, fallback=lambda: rule_extract(email))
    try:
        extracted = RFQSpec.model_validate(raw).model_dump()
    except Exception:
        extracted = RFQSpec.model_validate(rule_extract(email)).model_dump()
        meta = dict(meta, source="fallback", error="unparseable model output")
    extracted = verify_quotes(extracted, email)
    sheet = parse_sheet(rfq.get("customer_spec"), received)

    fields, conflicts = {}, []
    for name in RFQSpec.model_fields:
        e = extracted[name]
        ev = normalize_field(name, e["value"], received) if e["value"] is not None else None
        s = sheet.get(name)
        sv = s["value"] if s else None
        f = {"label": FIELD_LABELS[name], "email_raw": e["value"], "email_value": ev,
             "sheet_raw": s["raw"] if s else None, "sheet_value": sv,
             "source_quote": e.get("source_quote"), "verified": e.get("verified")}
        if ev is not None and sv is not None:
            same = (ev == sv) if name not in ("part_description", "notes", "customer_name", "part_number") else True
            if name == "part_number":
                same = normalize_pn(ev) == normalize_pn(sv)
            if same:
                val = sv if name in ("part_description",) else ev
                f.update(value=val, confidence="high", origin="email + spec sheet")
            else:
                f.update(value=ev, confidence="medium", origin="CONFLICT: email vs spec sheet")
                conflicts.append({"field": name, "email": ev, "sheet": sv, "email_raw": e["value"],
                                  "sheet_raw": s["raw"]})
        elif sv is not None:
            f.update(value=sv, confidence="high", origin="spec sheet")
        elif ev is not None:
            f.update(value=ev, confidence=e["confidence"], origin="email")
        else:
            f.update(value=None, confidence="low", origin="not stated")
        if name == "notes" and sv and ev and sv != ev:
            f["value"] = f"{ev} | {sv}"
        fields[name] = f

    spec = {k: v["value"] for k, v in fields.items()}
    if spec.get("part_family") is None:
        spec["part_family"] = normalize_family(spec.get("part_description"), spec.get("part_number"))
        if spec["part_family"]:
            fields["part_family"].update(value=spec["part_family"], confidence="medium",
                                         origin="inferred from description")
    if spec.get("part_family") == "tube_assembly" and spec.get("material") == "A36" \
            and re.search(r"a-?500|\bhss\b|\btube\b", f"{fields['material'].get('email_raw')} {email}", re.I):
        spec["material"] = "A500"   # a tube assembly is priced on its tube; end plates ride along in the BOM
        fields["material"].update(value="A500", origin=fields["material"]["origin"] + " (tube assembly: A500 tube)")
    spec.update(enrich(spec, email, received))
    return {"fields": fields, "spec": spec, "conflicts": conflicts, "llm": meta, "received": received,
            "prompt": prompt}


def enrich(spec: dict, email: str, received: date) -> dict:
    """Deterministic facts derived from history: customer record, repeat part, first run, lot size."""
    extra = {"received_date": received}
    cust = None
    name = (spec.get("customer_name") or "").lower()
    for cname, rec in store.customers_by_name().items():
        if name and (cname in name or name in cname or cname.split()[0] in name):
            cust = rec
            break
    extra["customer_id"] = cust["customer_id"] if cust else None
    extra["segment"] = cust["segment"] if cust else "OEM"
    extra["is_new_customer"] = bool(cust["is_new"]) if cust else True
    if cust:
        extra["customer_name"] = cust["name"]
    jobs = store.base_tables()["jobs"]
    pn = spec.get("part_number")
    prior = jobs[jobs.part_number.map(normalize_pn) == normalize_pn(pn)] if pn else jobs.iloc[0:0]
    extra["repeat_part"] = len(prior) > 0
    extra["prior_runs"] = sorted(prior.job_id.tolist())
    extra["prior_revs"] = sorted(set(prior.part_number))
    says_new = bool(re.search(r"new design|first (production )?run|new part|first article", email, re.I))
    extra["first_run"] = (not extra["repeat_part"]) or (says_new and not extra["repeat_part"])
    extra["revision_change"] = bool(extra["repeat_part"] and pn and pn not in set(prior.part_number))
    extra["lot_qty"] = spec.get("release_qty") or spec.get("qty")
    extra["rfq_text"] = email
    extra["no_welding"] = bool(re.search(r"\bno weld(?:ing|s)?\b|\bnot welded\b|\bweld-?free\b", email, re.I))
    extra["weldment"] = spec.get("part_family") in ("hitch_bracket", "frame", "tube_assembly", "guard") \
        and not extra["no_welding"]
    return extra


# ---------------------------------------------------------------- demo RFQ loading
def load_rfq(path_json) -> dict:
    from pathlib import Path
    p = Path(path_json)
    meta = json.loads(p.read_text(encoding="utf-8"))
    email = (p.parent / meta["email_file"]).read_text(encoding="utf-8")
    return {"rfq_id": meta["rfq_id"], "label": meta.get("label", meta["rfq_id"]),
            "received_date": date.fromisoformat(meta["received_date"]), "email_text": email,
            "customer_spec": meta.get("customer_spec"), "expected": meta.get("expected", {})}


def load_demo_rfqs(folder=None) -> dict[str, dict]:
    from pathlib import Path
    folder = Path(folder or config.DEMO_RFQ_DIR)
    out = {}
    for f in sorted(folder.glob("*.json")):
        r = load_rfq(f)
        out[r["rfq_id"]] = r
    return out


def pasted_rfq(text: str) -> dict:
    return {"rfq_id": "RFQ-PASTE", "label": "Pasted RFQ", "received_date": config.AS_OF,
            "email_text": text, "customer_spec": None, "expected": {}}
