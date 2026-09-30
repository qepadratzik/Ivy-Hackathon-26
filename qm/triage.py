"""S3 Triage: S/M/L is an OUTPUT (Locked Decision 4), never an input.

L / full review : new weldment, first run, or cosmetic weld (history says these overrun)
S / fast-track  : repeat part number or very close analog + standard tolerance + qty <= 50
M / standard    : everything else
"""
from __future__ import annotations

FAST_TRACK_MAX_QTY = 50
CLOSE_ANALOG_SIM = 0.90


def triage(spec: dict, analog_sim: float | None = None) -> dict:
    fam = (spec.get("part_family") or "part").replace("_", " ")
    reasons_l = []
    if spec.get("first_run") and spec.get("weldment"):
        reasons_l.append(f"new weldment ({fam}, first run)")
    elif spec.get("first_run"):
        reasons_l.append("first run of this part number")
    if spec.get("cosmetic_weld"):
        reasons_l.append("cosmetic weld (past cosmetic jobs overran weld hours)")
    if spec.get("revision_change"):
        reasons_l.append("revision change vs. the last build")
    if reasons_l:
        return {"label": "L", "track": "Full review", "reason": "; ".join(reasons_l)}

    qty = spec.get("qty") or 0
    repeat = bool(spec.get("repeat_part"))
    close = analog_sim is not None and analog_sim >= CLOSE_ANALOG_SIM
    std = spec.get("tolerance_class") in (None, "standard")
    if (repeat or close) and std and qty <= FAST_TRACK_MAX_QTY:
        why = (f"repeat of {spec.get('part_number')} ({len(spec.get('prior_runs', []))} prior runs)" if repeat
               else f"very close past job (similarity {analog_sim:.2f})")
        return {"label": "S", "track": "Fast-track",
                "reason": f"{why}; standard tolerance; qty {qty} <= {FAST_TRACK_MAX_QTY}"}
    bits = []
    if not (repeat or close):
        bits.append("no repeat or very close past job")
    if not std:
        bits.append("tight tolerance")
    if qty > FAST_TRACK_MAX_QTY:
        bits.append(f"qty {qty} > {FAST_TRACK_MAX_QTY}")
    return {"label": "M", "track": "Standard review", "reason": "; ".join(bits) or "default"}
