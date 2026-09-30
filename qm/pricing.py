"""S8 Pricing: win-probability model + expected-margin curve + recommendation.

Win model: LogisticRegression on the shop's past quotes (won/lost), features:
  price_to_cost_ratio, segment one-hot, is_new_customer, qty_bucket one-hot, customer one-hot
  (customer one-hot added because price sensitivity is customer-specific in this history, see P4).
Candidate prices: [1.0, 1.8] x P50 cost.
  exp_margin(price) = P(win | price/P50) x (price - decision_cost)
  risk_adjusted_cost = P50 + RISK_SHARE x (P90 - P50)       <- wider uncertainty => more cushion
  decision_cost = risk_adjusted_cost + labor_cost x capacity_premium(load)   <- busy shop => opportunity cost
Recommended price = peak of exp_margin above the capacity floor; range = exp_margin >= 90% of that.
Capacity slider (shop load) also raises the floor: minimum margin over risk-adjusted cost.
The LLM is never involved here.
"""
from __future__ import annotations

import threading

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from qm import config, store
from qm.data_gen import qty_bucket

SEGMENTS = ["OEM", "tier1", "aftermarket"]
_MODEL: dict | None = None
_LOCK = threading.Lock()


RATIO_CENTER, RATIO_SCALE = 1.30, 0.10   # standardize so L2 regularization doesn't flatten the price effect


def _features(ratio, segment: str, is_new: bool, qty: float, customer_id: str | None, customers: list[str]):
    ratio = np.atleast_1d(np.asarray(ratio, dtype=float))
    n = len(ratio)
    cols = [(ratio - RATIO_CENTER) / RATIO_SCALE]
    cols += [np.full(n, 1.0 if segment == s else 0.0) for s in SEGMENTS]
    cols.append(np.full(n, 1.0 if is_new else 0.0))
    b = qty_bucket(qty or 1)
    cols += [np.full(n, 1.0 if b == k else 0.0) for k in (1, 2, 3, 4)]
    cols += [np.full(n, 1.0 if customer_id == c else 0.0) for c in customers]
    return np.column_stack(cols)


def win_model() -> dict:
    global _MODEL
    with _LOCK:
        if _MODEL is None:
            t = store.base_tables()
            j = t["jobs"].merge(t["customers"], on="customer_id")
            customers = sorted(t["customers"].customer_id)
            X = np.vstack([_features(r.quoted_price / r.est_cost, r.segment, bool(r.is_new), r.qty, r.customer_id,
                                     customers) for r in j.itertuples(index=False)])
            y = j.won.astype(int).to_numpy()
            m = LogisticRegression(C=1.0, max_iter=2000).fit(X, y)
            _MODEL = {"model": m, "customers": customers, "n": len(y), "win_rate": float(y.mean()),
                      "ratio_coef_per_0.1x": float(m.coef_[0][0])}
        return _MODEL


def win_prob(ratios, spec: dict) -> np.ndarray:
    wm = win_model()
    X = _features(ratios, spec.get("segment") or "OEM", bool(spec.get("is_new_customer")), spec.get("qty") or 1,
                  spec.get("customer_id"), wm["customers"])
    return wm["model"].predict_proba(X)[:, 1]


def min_margin(load: float) -> float:
    xs, ys = zip(*config.MIN_MARGIN_AT_LOAD)
    return float(np.interp(load, xs, ys))


def capacity_premium(load: float) -> float:
    xs, ys = zip(*config.CAPACITY_PREMIUM_AT_LOAD)
    return float(np.interp(load, xs, ys))


def price_curve(spec: dict, risk: dict, load: float = 0.5) -> dict:
    p50, p90 = risk["p50"], risk["p90"]
    rac = p50 + config.RISK_SHARE * (p90 - p50)
    labor = float(risk.get("by_category", {}).get("labor", 0.0))
    cap_cost = labor * capacity_premium(load)
    decision_cost = rac + cap_cost
    lo, hi, n = config.PRICE_GRID
    mult = np.linspace(lo, hi, int(n))
    prices = p50 * mult
    pw = win_prob(mult, spec)
    em = pw * (prices - decision_cost)
    floor_pct = min_margin(load)
    floor_price = rac * (1 + floor_pct)
    ok = prices >= floor_price
    if ok.any() and em[ok].max() > 0:
        i = int(np.argmax(np.where(ok, em, -np.inf)))
        floor_binding = False
    else:
        i = int(np.argmax(ok)) if ok.any() else len(prices) - 1
        floor_binding = True
    peak = em[i]
    if not floor_binding and np.argmax(em) != i:
        floor_binding = True
    in_range = ok & (em >= config.REC_BAND * peak) if peak > 0 else (np.arange(len(prices)) == i)
    idx = np.where(in_range)[0]
    rng_lo, rng_hi = float(prices[idx.min()]), float(prices[idx.max()])
    rec = float(prices[i])
    return {
        "prices": prices.round(2).tolist(), "mult": mult.round(4).tolist(), "p_win": pw.round(4).tolist(),
        "exp_margin": em.round(3).tolist(), "risk_adj_cost": rac, "capacity_cost": cap_cost,
        "decision_cost": decision_cost, "floor_pct": floor_pct, "floor_price": floor_price,
        "floor_binding": floor_binding, "recommended": rec, "rec_markup": rec / p50, "rec_p_win": float(pw[i]),
        "rec_exp_margin": float(peak), "range": (rng_lo, rng_hi), "load": load,
    }


def price_at_lot(ledger: list[dict], cont_total_per_unit: float, lot: int, markup: float, spec: dict) -> float:
    """Unit price if released in lots of `lot` (setup lines re-spread; one-time fixture stays per order)."""
    base_lot = max(1, int(spec.get("lot_qty") or spec.get("qty") or 1))
    cost = cont_total_per_unit
    for l in ledger:
        c = l["cost"]
        if l["kind"] == "routing" and l["hour_type"] == "setup" and l["work_center"] != "fixture":
            c = c * base_lot / max(1, lot)
        cost += c
    return cost * markup


def expedite(rec_price: float, lead_days: int) -> dict:
    return {"price": rec_price * (1 + config.EXPEDITE_PRICE_PCT), "lead_days": max(5, lead_days - config.EXPEDITE_DAYS_SAVED),
            "pct": config.EXPEDITE_PRICE_PCT, "days_saved": config.EXPEDITE_DAYS_SAVED}


def gate2_check(price: float | None, curve: dict) -> dict:
    if price is None:
        return {"status": "pending", "in_range": None}
    lo, hi = curve["range"]
    inside = lo - 0.005 <= price <= hi + 0.005
    return {"status": "ok" if inside else "needs_reason", "in_range": inside}


def pwin_at(price: float, p50: float, spec: dict) -> float:
    return float(win_prob([price / p50], spec)[0])
