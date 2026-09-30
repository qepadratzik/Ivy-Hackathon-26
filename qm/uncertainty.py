"""S7 Uncertainty: Monte Carlo over the ledger.

Each line ~ Triangular(low, value, high) in its own unit, times its multiplier to $/unit.
2,000 samples. Material (steel) lines move together (one shared market shock); labor lines are partially
correlated (a shared "bad week on the floor" factor, rho = config.LABOR_CORRELATION); purchased and
outside lines are independent (stated in docs/assumptions.md). Gap/escalation contingencies are added as fixed dollars.
Each line has its own seeded random stream, so unrelated edits don't shuffle other lines' draws.
"""
from __future__ import annotations

import zlib

import numpy as np
from scipy.special import ndtr

from qm import config


def stream_key(line: dict) -> str:
    """Steel lines share one random stream = one common market shock (perfectly correlated);
    every other line is independent."""
    return "material" if line["category"] == "material" else line["key"]


def _normal(seed: int, name: str, n: int) -> np.ndarray:
    return np.random.default_rng([seed, zlib.crc32(name.encode())]).standard_normal(n)


def tri_ppf(u: np.ndarray, lo: float, mode: float, hi: float) -> np.ndarray:
    """Inverse CDF of Triangular(lo, mode, hi)."""
    c = (mode - lo) / (hi - lo)
    return np.where(u < c, lo + np.sqrt(u * (hi - lo) * (mode - lo)),
                    hi - np.sqrt((1 - u) * (hi - lo) * (hi - mode)))


def line_samples(line: dict, n: int, seed: int) -> np.ndarray:
    """Triangular draws via a Gaussian copula: steel lines share one market shock (rho = 1), labor lines share
    a 'bad week on the floor' factor (rho = LABOR_CORRELATION), everything else is independent."""
    lo, mode, hi = line["low"], line["value"], line["high"]
    if lo is None or hi is None or hi <= lo:
        return np.full(n, float(mode) * line["multiplier"])
    mode = min(max(float(mode), float(lo)), float(hi))
    z = _normal(seed, stream_key(line), n)
    if line["category"] == "labor":
        load = np.sqrt(config.LABOR_CORRELATION)     # pairwise correlation between labor lines = LABOR_CORRELATION
        z = load * _normal(seed, "labor-common", n) + np.sqrt(1 - load ** 2) * z
    return tri_ppf(ndtr(z), float(lo), mode, float(hi)) * line["multiplier"]


def contingencies(ledger: list[dict], gaps: list[dict], material_meta: dict) -> list[dict]:
    """Fixed-dollar contingencies per unit: 'assume' gaps + stale-material escalation."""
    def cost(filter_fn):
        return sum(l["cost"] for l in ledger if filter_fn(l))

    groups = {
        "setup": lambda l: l["kind"] == "routing" and l["hour_type"] == "setup",
        "labor": lambda l: l["kind"] == "routing",
        "material": lambda l: l["category"] == "material",
        "outside": lambda l: l["category"] == "outside",
        "all": lambda l: True,
        "none": lambda l: False,
    }
    out = []
    for g in gaps:
        if g.get("action") != "assume" or not g.get("contingency_pct"):
            continue
        base = cost(groups.get(g.get("affects"), groups["all"]))
        out.append({"source": g["id"], "label": f"Assumption: {g['assumption']}",
                    "pct": g["contingency_pct"], "base": base, "amount": base * g["contingency_pct"]})
    for mat, info in (material_meta or {}).items():
        esc = info.get("escalation_pct") or 0
        if esc > 0:
            base = sum(l["cost"] for l in ledger if l["category"] == "material" and l.get("material") == mat)
            out.append({"source": f"escalation_{mat}",
                        "label": f"{mat} price escalation: newest quote {info['newest_age']} days old, steel trending "
                                 f"{info['trend_monthly'] * 100:+.1f}%/month",
                        "pct": esc, "base": base, "amount": base * esc})
    return out


def simulate(ledger: list[dict], cont: list[dict], n: int | None = None, seed: int | None = None) -> dict:
    n = n or config.MC_SAMPLES
    seed = config.RANDOM_SEED if seed is None else seed
    total = np.zeros(n)
    by_cat: dict[str, float] = {}
    for l in ledger:
        s = line_samples(l, n, seed)
        total += s
        by_cat[l["category"]] = by_cat.get(l["category"], 0.0) + float(l["cost"])
    cont_total = float(sum(c["amount"] for c in cont))
    total += cont_total
    p10, p50, p90 = (float(x) for x in np.percentile(total, [10, 50, 90]))
    point = float(sum(l["cost"] for l in ledger)) + cont_total
    return {"p10": p10, "p50": p50, "p90": p90, "mean": float(total.mean()), "point": point,
            "band_pct": (p90 - p10) / p50 if p50 else 0.0, "contingency_total": cont_total,
            "by_category": by_cat, "samples": total[:: max(1, n // 1000)].round(2).tolist(), "n": n}
