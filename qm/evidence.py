"""S5 Evidence & weights: the core of Quote Memory (HANDOFF 7.4).

    evidence_score = similarity x source_authority x recency_decay
    recency_decay  = 0.5 ** (age_days / half_life)
    line_value     = sum(score*value) / sum(score)
    weighted_std   = sqrt(sum(score*(value-line_value)^2) / sum(score));  CV = weighted_std / line_value
    confidence     = min(1, sum(score)/3) * (1 - min(1, CV))
    spread         = 0.10 + 0.40*(1 - confidence)   (clamped to <= 0.60);  range = value*(1 -/+ spread)

Every row keeps its inputs (similarity, authority, decay, score, "why matched", original text) so the
UI can show exactly where each number came from. Only rows with similarity >= 0.35 count.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

from qm import config, retrieval
from qm.data_gen import SIZE_CLASS, purchased_price

VENDOR_TABLE_DATE = date(2026, 7, 1)
MAX_NOTES_PER_LINE = 3
MAX_OVERRIDE_NOTES_PER_LINE = 3
SOURCE_LABELS = {"actual": "Past job (actual)", "past_quote": "Past quote (estimate)", "shop_default": "Shop default",
                 "note": "Shop-floor note", "override": "Estimator override", "pattern": "Pattern adjustment",
                 "supplier_quote": "Supplier quote"}


# ---------------------------------------------------------------- math (pure)
def recency_decay(age_days: float, half_life: float | None) -> float:
    if not half_life:
        return 1.0
    return float(0.5 ** (max(0.0, age_days) / half_life))


def make_row(source_type: str, ref: str, value: float | None, similarity: float, age_days: float = 0,
             half_life_key: str | None = None, why: str = "", text: str | None = None, when=None,
             counted: bool = True, note: str | None = None) -> dict:
    authority = config.AUTHORITY[source_type]
    hl = config.HALF_LIFE_DAYS[half_life_key] if half_life_key else None
    decay = recency_decay(age_days, hl)
    ok = counted and value is not None and similarity >= config.SIM_THRESHOLD
    if counted and value is not None and similarity < config.SIM_THRESHOLD:
        note = note or f"not counted: similarity below {config.SIM_THRESHOLD}"
    score = similarity * authority * decay if ok else 0.0
    return dict(source_type=source_type, source=SOURCE_LABELS.get(source_type, source_type), ref=ref,
                value=None if value is None else float(value), similarity=round(float(similarity), 3),
                authority=authority, age_days=int(round(age_days)), half_life=hl, decay=round(decay, 3),
                score=round(score, 4), why=why, text=text, date=when, counted=ok, note=note)


def summarize(rows: list[dict], forced_value: float | None = None) -> dict:
    """Weighted value, spread, confidence from evidence rows (uses row['score'] and row['value'])."""
    use = [(r["value"], r["score"]) for r in rows if r.get("counted", True) and r["score"] > 0
           and r["value"] is not None]
    if not use:
        v = forced_value
        spread = config.SPREAD_MAX
        return dict(value=v, sum_score=0.0, std=0.0, cv=None, confidence=0.0, spread=spread,
                    low=None if v is None else v * (1 - spread), high=None if v is None else v * (1 + spread))
    vals = np.array([u[0] for u in use], dtype=float)
    sc = np.array([u[1] for u in use], dtype=float)
    s = float(sc.sum())
    v = float((sc * vals).sum() / s) if forced_value is None else float(forced_value)
    std = float(math.sqrt((sc * (vals - v) ** 2).sum() / s))
    if v > 0:
        cv = std / v
    else:
        cv = 0.0 if std == 0 else 1.0
    conf = min(1.0, s / config.CONF_SCORE_SATURATION) * (1 - min(1.0, cv))
    spread = min(config.SPREAD_MAX, config.SPREAD_BASE + config.SPREAD_SLOPE * (1 - conf))
    return dict(value=v, sum_score=s, std=std, cv=cv, confidence=conf, spread=spread,
                low=v * (1 - spread), high=v * (1 + spread))


def chip(conf: float) -> str:
    return "green" if conf >= config.CHIP_GREEN else "yellow" if conf >= config.CHIP_YELLOW else "red"


# ---------------------------------------------------------------- note gating
def note_applies(line_key: str, note_job: pd.Series | None, spec: dict) -> bool:
    """A debrief/NCR only moves a number if its job matches the RFQ on the driver of that line."""
    if note_job is None:
        return True
    if line_key in ("weld.run", "grind.run"):
        return spec.get("cosmetic_weld") is None or bool(note_job.cosmetic_weld) == bool(spec.get("cosmetic_weld"))
    if line_key in ("fit_tack.setup", "fixture.setup"):
        first = bool(spec.get("first_run"))
        return bool(note_job.first_run) == first and (not first or not bool(note_job.has_fixture_line))
    if line_key == "press_brake.run":
        th = spec.get("thickness_in") or 0
        return (float(note_job.thickness_in) >= 0.5) == (float(th) >= 0.5)
    return True


# ---------------------------------------------------------------- per-line evidence
class Context:
    """Pre-indexed history for one pipeline run."""

    def __init__(self, spec: dict, sims: pd.DataFrame, tables: dict, patterns: list[dict],
                 material_age_offset: int = 0, as_of: date | None = None):
        self.spec, self.sims, self.t, self.patterns = spec, sims, tables, patterns
        self.age_offset = int(material_age_offset or 0)
        self.as_of = as_of or config.AS_OF
        ops = tables["routing_ops"]
        self.ops = {(r.job_id, r.work_center): r for r in ops.itertuples(index=False)}
        self.with_act = set(ops[ops.run_hr_act.notna()].job_id)
        self.jobs = tables["jobs"].set_index("job_id")
        self.bom = tables["bom_lines"]

    def age(self, d) -> int:
        return (self.as_of - d).days


def _job_rows_routing(ctx: Context, wc: str, ht: str) -> tuple[list[dict], list[tuple[float, float]]]:
    rows, est_pairs = [], []
    n = 0
    for j in ctx.sims.itertuples(index=False):
        op = ctx.ops.get((j.job_id, wc))
        if op is None:
            continue
        act, est = getattr(op, f"{ht}_hr_act"), getattr(op, f"{ht}_hr_est")
        age = ctx.age(j.quote_date)
        has_act = pd.notna(act)
        uom = "hr/unit" if ht == "run" else "hr/lot"
        txt = (f"{j.part_number}: {j.description}\nQuoted {est:.3g} {uom}"
               + (f", actual {act:.3g} {uom}" if has_act else " (no actuals: lost or not run yet)"))
        rows.append(make_row("actual" if has_act else "past_quote", j.job_id, act if has_act else est, j.sim, age,
                             "labor", why=j.why, text=txt, when=j.quote_date))
        est_pairs.append((float(est), j.sim * config.AUTHORITY["past_quote"] * recency_decay(age, config.HALF_LIFE_DAYS["labor"])))
        n += 1
        if n >= config.TOP_K_JOBS:
            break
    return rows, est_pairs


def _default_row(wc: str, ht: str) -> dict:
    if wc == "fixture":
        v, what = config.FIXTURE_DEFAULT_HR, "one-time fixture build"
    else:
        v = config.WORK_CENTERS[wc][1 if ht == "setup" else 2]
        what = f"{config.WC_LABELS.get(wc, wc).lower()} {ht}"
    return make_row("shop_default", "Shop default", v, 1.0, 0, None, why=f"Shop rule of thumb for {what}")


def _weighted(pairs: list[tuple[float, float]]) -> float | None:
    s = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / s if s > 0 else None


def evidence_routing(ctx: Context, line: dict) -> tuple[list[dict], dict]:
    wc, ht, key = line["work_center"], line["hour_type"], line["key"]
    rows, est_pairs = _job_rows_routing(ctx, wc, ht)
    default = _default_row(wc, ht)
    rows.append(default)
    est_base = _weighted(est_pairs + [(default["value"], default["score"])])
    structured_base = summarize(rows)["value"]
    info = {"est_base": est_base, "structured_base": structured_base}
    # pattern adjustment rows (data-derived ratio on the estimate-level value)
    for p in ctx.patterns:
        if p.get("line_key") == key and p.get("ratio"):
            rows.append(make_row("pattern", p["id"], est_base * p["ratio"], 1.0, 0, None,
                                 why=f"{p['title']}: {p['stat']}", text=p.get("narration")))
    # notes: debriefs / NCRs (ratio from the note's own job) and estimator overrides (delta)
    notes = retrieval.related_notes(ctx.spec, wc if wc != "fixture" else "fit_tack", key, tables=ctx.t)
    seen, n_notes, n_over = set(), 0, 0
    for nrow in notes.itertuples(index=False):
        if nrow.sim < config.SIM_THRESHOLD or nrow.text in seen:
            continue
        seen.add(nrow.text)
        age = ctx.age(nrow.date)
        if nrow.doc_type == "override":
            if n_over >= MAX_OVERRIDE_NOTES_PER_LINE or pd.isna(nrow.new_value) or pd.isna(nrow.old_value):
                continue
            if ctx.spec.get("rfq_id") and nrow.job_id == ctx.spec.get("rfq_id"):
                continue  # this quote's own Gate 1 edit is already the locked value; don't count it twice
            delta = float(nrow.new_value) - float(nrow.old_value)
            rows.append(make_row("override", nrow.doc_id, max(0.0, structured_base + delta), nrow.sim, age, "note",
                                 why=f"Estimator override on a similar quote ({nrow.job_id}): {delta:+.2f} "
                                     f"{'hr' if ht else ''} applied to this line's evidence base",
                                 text=nrow.text, when=nrow.date))
            n_over += 1
            continue
        if n_notes >= MAX_NOTES_PER_LINE:
            continue
        nj = ctx.jobs.loc[nrow.job_id] if nrow.job_id in ctx.jobs.index else None
        if not note_applies(key, nj, ctx.spec):
            continue
        op = ctx.ops.get((nrow.job_id, wc))
        ratio = None
        if op is not None:
            act, est = getattr(op, f"{ht}_hr_act"), getattr(op, f"{ht}_hr_est")
            if pd.notna(act) and est:
                ratio = float(act) / float(est)
        doc = "NCR" if nrow.doc_type == "ncr" else "Debrief"
        if ratio is None:
            rows.append(make_row("note", nrow.doc_id, None, nrow.sim, age, "note", counted=False,
                                 why=f"{doc} on {nrow.job_id} (context only: no actuals to size it)",
                                 text=nrow.text, when=nrow.date, note="context only"))
        else:
            rows.append(make_row("note", nrow.doc_id, est_base * ratio, nrow.sim, age, "note",
                                 why=f"{doc} on {nrow.job_id}: that job ran {ratio:.2f}x its quoted {ht} hours",
                                 text=nrow.text, when=nrow.date))
        n_notes += 1
    return rows, info


def evidence_material(ctx: Context, line: dict) -> tuple[list[dict], dict]:
    mat = line.get("material")
    mp = ctx.t["material_prices"]
    m = mp[mp.material == mat].sort_values("quote_date", ascending=False)
    rows = []
    for r in m.head(12).itertuples(index=False):
        age = ctx.age(r.quote_date) + ctx.age_offset
        rows.append(make_row("supplier_quote", f"{r.supplier} {r.quote_date:%Y-%m-%d}", r.price_per_lb, 1.0, age,
                             "material", why=f"Same grade ({mat}); supplier price quote",
                             text=f"{r.supplier} quoted {mat} at ${r.price_per_lb:.3f}/lb on {r.quote_date:%b %d, %Y}",
                             when=r.quote_date))
    info = {"newest_age": None, "escalation_pct": 0.0, "trend_monthly": None}
    if not m.empty:
        newest = int(ctx.age(m.iloc[0].quote_date) + ctx.age_offset)
        recent = m[m.quote_date >= m.iloc[0].quote_date - pd.Timedelta(days=180)].sort_values("quote_date")
        trend = 0.0
        if len(recent) >= 4:
            x = np.array([(d - recent.iloc[0].quote_date).days for d in recent.quote_date], dtype=float)
            y = recent.price_per_lb.to_numpy(dtype=float)
            slope = np.polyfit(x, y, 1)[0]
            trend = float(slope * 30.44 / y.mean())
        info.update(newest_age=newest, trend_monthly=trend)
        if newest > config.MATERIAL_STALE_DAYS:
            info["escalation_pct"] = max(0.0, trend) * newest / 30.44
    return rows, info


def _bom_job_rows(ctx: Context, item: str, item_type: str, half_life_key: str) -> list[dict]:
    rows, n = [], 0
    b = ctx.bom[(ctx.bom.item == item) & (ctx.bom.item_type == item_type)].set_index("job_id")
    for j in ctx.sims.itertuples(index=False):
        if j.job_id not in b.index:
            continue
        r = b.loc[j.job_id]
        r = r.iloc[0] if isinstance(r, pd.DataFrame) else r
        has_act = j.job_id in ctx.with_act
        rows.append(make_row("actual" if has_act else "past_quote", j.job_id, r.unit_cost, j.sim, ctx.age(r.cost_date),
                             half_life_key, why=j.why,
                             text=f"{j.part_number}: {item} at ${r.unit_cost:.2f}/{r.uom} "
                                  f"({'purchased for a completed job' if has_act else 'quoted'})",
                             when=r.cost_date))
        n += 1
        if n >= config.TOP_K_JOBS:
            break
    return rows


def evidence_purchased(ctx: Context, line: dict) -> tuple[list[dict], dict]:
    rows = _bom_job_rows(ctx, line["item"], "purchased", "purchased")
    try:
        p = purchased_price(line["item"], ctx.as_of)
        rows.append(make_row("shop_default", "Shop price list", p, 1.0, 0, None,
                             why="Shop's standing price list for this hardware"))
    except KeyError:
        pass
    return rows, {}


def evidence_outside(ctx: Context, line: dict) -> tuple[list[dict], dict]:
    item = line["item"]
    rows = _bom_job_rows(ctx, item, "outside", "outside")
    size = SIZE_CLASS.get(ctx.spec.get("part_family") or "", "medium")
    table = config.POWDER_COAT_PRICE if item == "powder_coat" else config.ZINC_PRICE
    rows.append(make_row("supplier_quote", f"Vendor price table {VENDOR_TABLE_DATE:%Y-%m-%d}", table[size], 1.0,
                         ctx.age(VENDOR_TABLE_DATE), "outside",
                         why=f"Coater's current price table, {size} parts",
                         text=f"{item.replace('_', ' ')} vendor table: small ${table['small']:.2f}, medium "
                              f"${table['medium']:.2f}, large ${table['large']:.2f} per part",
                         when=VENDOR_TABLE_DATE))
    return rows, {}


# ---------------------------------------------------------------- ledger
def _rate(wc: str) -> float:
    return config.FIXTURE_RATE if wc == "fixture" else config.WORK_CENTERS[wc][0]


def build_ledger(spec: dict, lines: list[dict], sims: pd.DataFrame, tables: dict, patterns: list[dict],
                 overrides: dict | None = None, material_age_offset: int = 0) -> tuple[list[dict], dict]:
    """lines = proposal lines after Gate 1 (with 'value' = the approved quantity/hours).
    overrides = {line_key: {'old':..., 'new':..., 'reason':...}} made at Gate 1 on routing lines."""
    overrides = overrides or {}
    ctx = Context(spec, sims, tables, patterns, material_age_offset)
    lot = max(1, int(spec.get("lot_qty") or spec.get("qty") or 1))
    total_qty = max(1, int(spec.get("qty") or lot))
    ledger, meta = [], {"material": {}}
    for ln in lines:
        if not ln.get("include", True):
            continue
        key = ln["key"]
        approved = float(ln.get("value", ln["proposed"]))
        info: dict = {}
        if ln["kind"] == "routing":
            rows, info = evidence_routing(ctx, ln)
            ov = overrides.get(key)
            forced = None
            if ov is not None:
                forced = float(ov["new"])
                rows.insert(0, make_row("override", "This quote (Gate 1)", forced, 1.0, 0, None,
                                        why=f"Estimator edit {ov['old']:.2f} -> {forced:.2f}: {ov.get('reason', '')}",
                                        text=ov.get("reason")))
                rows[0]["authority"] = 1.0
                rows[0]["score"] = 1.0
            wc = ln["work_center"]
            if wc == "fixture":
                mult, unit = _rate(wc) / total_qty, "hr/order"
            elif ln["hour_type"] == "setup":
                mult, unit = _rate(wc) / lot, "hr/lot"
            else:
                mult, unit = _rate(wc), "hr/unit"
            qty_per = 1.0
        else:
            cat = ln["category"]
            if cat == "material":
                rows, info = evidence_material(ctx, ln)
                meta["material"][ln["material"]] = info
                unit = "$/lb"
            elif cat == "purchased":
                rows, info = evidence_purchased(ctx, ln)
                unit = "$/ea"
            else:
                rows, info = evidence_outside(ctx, ln)
                unit = "$/ea"
            forced, qty_per, mult = None, approved, approved
        s = summarize(rows, forced_value=forced)
        if s["value"] is None:  # no evidence at all: fall back to the approved proposal value
            s = summarize([], forced_value=approved if ln["kind"] == "routing" else 0.0)
        rows.sort(key=lambda r: (not r["counted"], -r["score"]))
        warnings = []
        if ln["kind"] == "bom" and ln["category"] == "material" and info.get("newest_age") is not None \
                and info["newest_age"] > config.MATERIAL_STALE_DAYS:
            warnings.append(f"Newest {ln['material']} quote is {info['newest_age']} days old: re-quote material "
                            f"or shorten quote validity to {config.QUOTE_VALIDITY_STALE_DAYS} days.")
        if s["sum_score"] == 0:
            warnings.append("No usable evidence: shop default only, treat as a guess.")
        if forced is not None and s["cv"] is not None and s["cv"] > 0.3:
            warnings.append("Override differs a lot from history: saved with its reason so the next quote learns.")
        pats = [p["id"] for p in patterns if p.get("line_key") == key]
        ledger.append(dict(
            key=key, label=ln["label"], kind=ln["kind"], category=ln["category"],
            work_center=ln.get("work_center"), hour_type=ln.get("hour_type"), material=ln.get("material"),
            item=ln.get("item"), unit=unit, qty_per=qty_per, multiplier=mult,
            value=s["value"], low=s["low"], high=s["high"], confidence=s["confidence"], chip=chip(s["confidence"]),
            sum_score=s["sum_score"], cv=s["cv"], spread=s["spread"],
            n_evidence=sum(1 for r in rows if r["counted"]), evidence=rows,
            cost=s["value"] * mult, cost_low=s["low"] * mult, cost_high=s["high"] * mult,
            overridden=forced is not None, proposed=ln["proposed"], approved=approved,
            patterns=pats, warnings=warnings, info={k: v for k, v in info.items() if not isinstance(v, (list, dict))},
        ))
    return ledger, meta
