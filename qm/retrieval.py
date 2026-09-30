"""Similar past jobs and related notes.

sim = 0.5 * embed_cos(description) + 0.5 * structured_sim
structured_sim = 0.32*same_family + 0.16*same_material + 0.16*thickness_closeness + 0.16*qty_bucket_match
                 + 0.20*same_weld_class
(HANDOFF weights 0.4/0.2/0.2/0.2 scaled by 0.8 to make room for weld class: cosmetic vs standard weld is
the single biggest labor driver in this shop's history, see pattern P1.)
Vector similarity is only ever used on text; all values come from the structured tables.
"""
from __future__ import annotations

import pandas as pd

from qm import config, store
from qm.data_gen import frac, normalize_pn, qty_bucket

MATERIAL_FAMILY = {"A36": "carbon", "A500": "carbon", "1018": "carbon", "304SS": "stainless", "5052AL": "aluminum"}
MIN_CANDIDATES_FOR_MATERIAL_FILTER = 5


def query_text(spec: dict) -> str:
    """The RFQ as one line of text, phrased like the job descriptions in history."""
    parts = []
    if spec.get("part_number"):
        parts.append(f"{spec['part_number']}:")
    parts.append(spec.get("part_description") or (spec.get("part_family") or "part").replace("_", " "))
    if spec.get("cosmetic_weld") is True:
        parts.append("; cosmetic welds on visible side, no spatter, smooth")
    elif spec.get("cosmetic_weld") is False and spec.get("part_family") != "mounting_plate":
        parts.append("; standard structural welds")
    if spec.get("thickness_in") and spec.get("material"):
        parts.append(f"; {frac(float(spec['thickness_in']))} {spec['material']} plate")
    if spec.get("finish"):
        parts.append(f"; {spec['finish'].replace('_', ' ')} {spec.get('finish_color') or ''}".rstrip())
    if spec.get("first_run"):
        parts.append("; new part, first run")
    return " ".join(parts).replace(" ;", ";")


def thickness_closeness(a, b) -> float:
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return 0.5
    if a <= 0 or b <= 0:
        return 0.5
    return max(0.0, 1 - abs(a - b) / max(a, b))


def qty_match(a, b) -> float:
    try:
        ba, bb = qty_bucket(float(a)), qty_bucket(float(b))
    except (TypeError, ValueError):
        return 0.5
    return 1.0 if ba == bb else 0.5 if abs(ba - bb) == 1 else 0.0


W_FAMILY, W_MATERIAL, W_THICK, W_QTY, W_WELD = 0.32, 0.16, 0.16, 0.16, 0.20


def weld_match(spec: dict, job: pd.Series) -> float:
    if spec.get("cosmetic_weld") is None:
        return 0.5
    return 1.0 if bool(spec["cosmetic_weld"]) == bool(job.cosmetic_weld) else 0.0


def structured_sim(spec: dict, job: pd.Series) -> float:
    return (W_FAMILY * (spec.get("part_family") == job.part_family)
            + W_MATERIAL * (spec.get("material") == job.material)
            + W_THICK * thickness_closeness(spec.get("thickness_in"), job.thickness_in)
            + W_QTY * qty_match(spec.get("qty"), job.qty)
            + W_WELD * weld_match(spec, job))


def why_matched(spec: dict, job: pd.Series, ecos: float) -> str:
    bits = []
    if spec.get("part_family") == job.part_family:
        bits.append("same family")
    if spec.get("part_number") and normalize_pn(spec["part_number"]) == normalize_pn(job.part_number):
        bits.append("same part number (earlier rev/run)")
    if spec.get("material") == job.material:
        bits.append(f"same material {job.material}")
    if spec.get("thickness_in"):
        bits.append(f"{frac(float(job.thickness_in))} vs {frac(float(spec['thickness_in']))} thick")
    bits.append(f"qty {job.qty} vs {spec.get('qty')}")
    if spec.get("cosmetic_weld") is not None and bool(job.cosmetic_weld) == bool(spec.get("cosmetic_weld")):
        bits.append("cosmetic weld too" if job.cosmetic_weld else "standard weld too")
    bits.append(f"text match {ecos:.2f}")
    return "; ".join(bits)


def similar_jobs(spec: dict, tables: dict | None = None) -> pd.DataFrame:
    """All candidate jobs scored and sorted by similarity (desc)."""
    t = tables or store.tables()
    jobs = t["jobs"]
    cand = jobs
    if spec.get("part_family") in set(jobs.part_family):
        cand = jobs[jobs.part_family == spec["part_family"]]
        mf = MATERIAL_FAMILY.get(spec.get("material") or "")
        if mf:
            same = cand[cand.material.map(MATERIAL_FAMILY) == mf]
            if len(same) >= MIN_CANDIDATES_FOR_MATERIAL_FILTER:
                cand = same
    if cand.empty:
        return cand.assign(sim=[], embed_cos=[], structured_sim=[], why=[], has_actuals=[])
    vs = store.vector_store()
    ecos = vs.cos(query_text(spec), cand.job_id.tolist())
    ops = t["routing_ops"]
    with_act = set(ops[ops.run_hr_act.notna()].job_id)
    rows = []
    for _, j in cand.iterrows():
        ss = structured_sim(spec, j)
        ec = ecos[j.job_id]
        rows.append({"job_id": j.job_id, "sim": round(0.5 * ec + 0.5 * ss, 4), "embed_cos": round(ec, 4),
                     "structured_sim": round(ss, 4), "why": why_matched(spec, j, ec),
                     "has_actuals": j.job_id in with_act})
    scored = pd.DataFrame(rows).merge(cand, on="job_id")
    return scored.sort_values(["sim", "quote_date"], ascending=[False, False]).reset_index(drop=True)


def pick_analog(sims: pd.DataFrame) -> pd.Series | None:
    """Most similar WON job with actuals, with recency as a soft tiebreaker (weight 15%, labor
    half-life): a 2-year-old job is a weaker template than last quarter's, but similarity dominates.
    Falls back to the top job overall."""
    if sims.empty:
        return None
    good = sims[sims.won & sims.has_actuals]
    pool = good if not good.empty else sims
    age = pool.quote_date.map(lambda d: (config.AS_OF - d).days)
    score = pool.sim * (0.85 + 0.15 * 0.5 ** (age / config.HALF_LIFE_DAYS["labor"]))
    return pool.loc[score.idxmax()]


def related_notes(spec: dict, work_center: str | None = None, line_key: str | None = None,
                  doc_types=("debrief", "ncr", "override"), tables: dict | None = None) -> pd.DataFrame:
    """Debriefs/NCRs/override notes relevant to this RFQ (and optionally one cost line)."""
    t = tables or store.tables()
    d = t["docs"]
    d = d[d.doc_type.isin(doc_types)]
    if line_key:
        d = d[(d.line_key == line_key) | (d.line_key.isna() & (d.work_center == work_center))]
    elif work_center:
        d = d[d.work_center == work_center]
    if d.empty:
        return d.assign(sim=[], embed_cos=[])
    vs = store.vector_store()
    vs.sync_memory()
    ecos = vs.cos(query_text(spec), d.doc_id.tolist())
    fam = spec.get("part_family")
    out = d.assign(
        embed_cos=[round(ecos[i], 4) for i in d.doc_id],
        same_family=[f == fam for f in d.part_family],
    )
    wc_match = [1.0 if (work_center is None or w == work_center) else 0.0 for w in out.work_center]
    out = out.assign(sim=[round(0.5 * e + 0.5 * (0.6 * sf + 0.4 * wm), 4)
                          for e, sf, wm in zip(out.embed_cos, out.same_family, wc_match)])
    return out.sort_values(["sim", "date"], ascending=[False, False]).reset_index(drop=True)
