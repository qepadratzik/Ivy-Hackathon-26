"""Seeded synthetic history for the FICTIONAL Boone Creek Fabrication.

    python -m qm.data_gen            # writes data/*.csv (+ data/quote_memory.sqlite)

~150 random jobs over Oct 2024 - Sep 2026 plus handcrafted hero jobs, with seeded patterns:
  P1 cosmetic-weld jobs overrun weld run hours      (act/est ~ N(1.35, 0.08))
  P2 first-run weldments w/o fixture overrun fit/tack setup (x1.6-2.2)
  P3 press brake on plate >= 0.5" gets NCRs / rework (~30%)
  P4 Prairie Implement only wins below ~1.25x cost
  P5 steel price per lb rises (~+15% last 6 months vs first 6)
All numbers are ILLUSTRATIVE. All names are fictional.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, timedelta

import numpy as np
import pandas as pd

from qm import config
from qm import data_text as T

START = date(2024, 10, 1)
END = date(2026, 9, 25)
N_RANDOM = 150
LB_PER_CUIN = 0.2836

CUSTOMERS = [
    # id, name, segment, is_new, notes, prefix, weight
    ("C01", "Prairie Implement Co.", "OEM", False, "Price-driven buyer; awards almost purely on price.", "PIC", 0.22),
    ("C02", "Cedar Valley Equipment", "OEM", False, "Cares about appearance on visible parts.", "CVE", 0.16),
    ("C03", "Hawkeye Loader Works", "OEM", False, "Steady OEM account, mid-volume releases.", "HLW", 0.15),
    ("C04", "North Star Ag Systems", "tier1", False, "Tier-1 to ag OEMs; frequent new part numbers.", "NSA", 0.14),
    ("C05", "Raccoon River Attachments", "aftermarket", False, "Aftermarket attachments, small lots.", "RRA", 0.10),
    ("C06", "Big Sioux Trailer", "tier1", True, "New account in 2026.", "BST", 0.08),
    ("C07", "Loess Hills Machinery", "aftermarket", False, "Repeat orders, small lots, pays on time.", "LHM", 0.15),
]
CUST_BY_ID = {c[0]: c for c in CUSTOMERS}
CUST_BY_NAME = {c[1]: c for c in CUSTOMERS}

FAMILY_CODE = {"hitch_bracket": "HB", "guard": "GD", "frame": "FR", "mounting_plate": "MP", "tube_assembly": "TA"}
FAMILY_WEIGHTS = {"hitch_bracket": 0.28, "guard": 0.18, "frame": 0.16, "mounting_plate": 0.20, "tube_assembly": 0.18}
WELDMENTS = {"hitch_bracket", "frame", "tube_assembly", "guard"}
SIZE_CLASS = {"hitch_bracket": "medium", "guard": "medium", "frame": "large", "mounting_plate": "small",
              "tube_assembly": "medium"}

MATERIALS = {
    # normalized: base $/lb at START, quote interval (days), follows the steel index?
    "A36": (0.74, 7, True),
    "A500": (0.98, 7, True),
    "1018": (1.05, 14, True),
    "304SS": (3.10, 30, False),
    "5052AL": (3.45, 30, False),
}
MATERIAL_ALIASES = {
    "A36": ["A36", "A-36 HR", "HR A36", "ASTM A36 plate", "A36 HR plate"],
    "A500": ["A500 tube", "A500 Gr B", "ASTM A500", "HSS A500"],
    "1018": ["1018", "C1018 CF bar", "1018 CRS"],
    "304SS": ["304 SS", "304 stainless", "SS304"],
    "5052AL": ["5052-H32", "5052 alum", "AL 5052"],
}
MATERIAL_ITEM = {"A36": "A36 plate", "A500": "A500 tube", "1018": "1018 bar", "304SS": "304 SS tube",
                 "5052AL": "5052 aluminum sheet"}
STEEL_SUPPLIERS = ["Skunk River Steel Supply", "Central Iowa Metals", "Heartland Plate & Tube"]
SPECIALTY_SUPPLIERS = ["Prairie Specialty Metals", "Heartland Plate & Tube"]
SUPPLIER_FACTOR = {"Skunk River Steel Supply": 0.98, "Central Iowa Metals": 1.00, "Heartland Plate & Tube": 1.03,
                   "Prairie Specialty Metals": 1.00}

PURCHASED = {
    "Bushing 1.25 OD x 1.00 ID x 1.50 L": 3.05,
    "Bolt kit 4x 1/2-13 Gr8": 2.35,
    "Hardware kit, guard": 1.60,
    "Pivot pin 1.00 dia": 4.80,
    "Grease zerk 1/4-28": 0.45,
}
POWDER_COLORS = ["black", "black", "black", "gloss black", "implement yellow", "orange", "gray", "red"]

# (setup_hr, run_hr_per_unit, probability) base estimates per family and work center
ROUTING = {
    "hitch_bracket": [("laser", 0.50, 0.075, 1), ("press_brake", 0.70, 0.050, 1), ("saw", 0.25, 0.030, 1),
                      ("fit_tack", 2.00, 0.200, 1), ("weld", 0.50, 0.440, 1), ("grind", 0.25, 0.110, 0.5),
                      ("inspect_pack", 0.25, 0.050, 1)],
    "guard": [("laser", 0.50, 0.060, 1), ("press_brake", 0.80, 0.100, 1), ("fit_tack", 1.00, 0.080, 0.6),
              ("weld", 0.40, 0.150, 0.6), ("grind", 0.25, 0.060, 0.3), ("inspect_pack", 0.25, 0.060, 1)],
    "frame": [("saw", 0.40, 0.150, 1), ("laser", 0.50, 0.100, 1), ("press_brake", 0.70, 0.080, 0.6),
              ("fit_tack", 3.00, 0.900, 1), ("weld", 0.60, 2.000, 1), ("grind", 0.30, 0.400, 0.8),
              ("machining", 1.20, 0.300, 0.3), ("inspect_pack", 0.40, 0.200, 1)],
    "mounting_plate": [("laser", 0.40, 0.050, 1), ("press_brake", 0.60, 0.050, 0.4), ("machining", 1.00, 0.100, 1),
                       ("inspect_pack", 0.20, 0.030, 1)],
    "tube_assembly": [("saw", 0.30, 0.060, 1), ("machining", 1.00, 0.120, 1), ("fit_tack", 1.50, 0.150, 1),
                      ("weld", 0.50, 0.300, 1), ("grind", 0.25, 0.080, 0.4), ("inspect_pack", 0.25, 0.050, 1)],
}
LEAD_DAYS = {"hitch_bracket": (25, 35), "guard": (20, 30), "frame": (30, 45), "mounting_plate": (12, 20),
             "tube_assembly": (20, 30)}
QTY_CHOICES = {
    "hitch_bracket": [25, 50, 100, 150, 200, 250, 300, 500],
    "guard": [20, 40, 60, 100, 150, 250],
    "frame": [5, 10, 15, 20, 30, 40, 60],
    "mounting_plate": [20, 25, 40, 50, 100, 200, 300, 500],
    "tube_assembly": [25, 50, 75, 100, 150, 200],
}

HERO_IDS = ["J-0842", "J-0918", "J-0955", "J-0987", "J-1042", "J-1077", "J-1103", "J-1118"]


# ---------------------------------------------------------------- helpers
def steel_index(d: date) -> float:
    """Illustrative steel index: slow drift, then a tariff-driven jump in the last ~6 months."""
    m = (d - START).days / 30.44
    if m < 18:
        return 1.0 + 0.05 * m / 18
    return 1.12 + 0.07 * min(1.0, (m - 18) / 6)


def frac(t: float) -> str:
    table = {0.075: "14 ga", 0.105: "12 ga", 0.135: "10 ga", 0.1875: "3/16", 0.25: "1/4", 0.375: "3/8",
             0.5: "1/2", 0.625: "5/8", 0.75: "3/4"}
    return table.get(round(t, 4), f"{t:.3f}")


def normalize_pn(pn: str) -> str:
    """'CVE-HB-4410 Rev C' -> 'CVEHB4410' (drops revision + punctuation) for repeat detection."""
    s = re.sub(r"\bREV\.?\s*[A-Z0-9]+\b", "", str(pn).upper())
    return re.sub(r"[^A-Z0-9]", "", s)


def qty_bucket(q: float) -> int:
    return 1 if q <= 25 else 2 if q <= 100 else 3 if q <= 300 else 4


def unit_cost_from_lines(bom: list[dict], ops: list[dict], lot: int, use_actual: bool = False) -> float:
    mat = sum(b["qty_per"] * b["unit_cost"] for b in bom)
    lab = 0.0
    for o in ops:
        rate = config.FIXTURE_RATE if o["work_center"] == "fixture" else config.WORK_CENTERS[o["work_center"]][0]
        s = o["setup_hr_act"] if use_actual else o["setup_hr_est"]
        r = o["run_hr_act"] if use_actual else o["run_hr_est"]
        lab += (s / lot + r) * rate
    return mat + lab


# ---------------------------------------------------------------- material prices
def gen_material_prices(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for mat, (base, every, steel) in MATERIALS.items():
        sups = STEEL_SUPPLIERS if steel else SPECIALTY_SUPPLIERS
        d, i = START, 0
        while d <= END:
            sup = sups[i % len(sups)]
            idx = steel_index(d) if steel else 1.0 + 0.02 * np.sin((d - START).days / 120)
            price = base * idx * SUPPLIER_FACTOR[sup] * rng.normal(1.0, 0.012)
            rows.append({"material": mat, "price_per_lb": round(float(price), 3), "quote_date": d, "supplier": sup})
            d += timedelta(days=int(every + rng.integers(-1, 2)))
            i += 1
    # make sure the most recent steel quotes are fresh (within a week of END)
    return pd.DataFrame(rows).sort_values(["material", "quote_date"]).reset_index(drop=True)


def price_at(prices: pd.DataFrame, mat: str, d: date) -> float:
    p = prices[(prices.material == mat) & (prices.quote_date <= d)].tail(3)
    if p.empty:
        p = prices[prices.material == mat].head(1)
    return round(float(p.price_per_lb.mean()), 3)


def purchased_price(item: str, d: date) -> float:
    yrs = (d - START).days / 365
    return round(PURCHASED[item] * (1 + 0.03 * yrs), 2)


# ---------------------------------------------------------------- one job's BOM + routing (estimates)
def build_lines(rng, fam: str, mat: str, t: float, qty: int, cosmetic: bool, finish: str, d: date,
                prices: pd.DataFrame, s: float, fixture: bool, forced_ops: list[str] | None = None):
    bom = []

    def raw(m, lb):
        bom.append({"item_type": "raw", "item": MATERIAL_ITEM[m], "qty_per": round(lb, 2), "uom": "lb",
                    "unit_cost": price_at(prices, m, d), "cost_date": d, "_mat": m})

    def pur(item, n):
        bom.append({"item_type": "purchased", "item": item, "qty_per": n, "uom": "ea",
                    "unit_cost": purchased_price(item, d), "cost_date": d, "_mat": None})

    if fam == "hitch_bracket":
        raw(mat, rng.uniform(150, 210) * s * t * LB_PER_CUIN * 1.15)
        raw("A500", rng.uniform(3.6, 4.8) * s)
        pur("Bushing 1.25 OD x 1.00 ID x 1.50 L", 2)
        pur("Bolt kit 4x 1/2-13 Gr8", 1)
    elif fam == "guard":
        raw(mat, rng.uniform(700, 1100) * s * t * (LB_PER_CUIN if mat != "5052AL" else 0.098) * 1.2)
        pur("Hardware kit, guard", 1)
    elif fam == "frame":
        raw("A500", rng.uniform(90, 180) * s)
        raw(mat, rng.uniform(150, 300) * s * t * LB_PER_CUIN * 1.15)
        pur("Pivot pin 1.00 dia", 2)
        pur("Grease zerk 1/4-28", 2)
    elif fam == "mounting_plate":
        raw(mat, rng.uniform(70, 150) * s * t * LB_PER_CUIN * 1.15)
    elif fam == "tube_assembly":
        raw(mat, rng.uniform(12, 26) * s)
        raw("1018", rng.uniform(1.5, 4.0) * s)
        pur("Grease zerk 1/4-28", 1)
    size = SIZE_CLASS[fam]
    if finish.startswith("powder"):
        bom.append({"item_type": "outside", "item": "powder_coat", "qty_per": 1, "uom": "ea",
                    "unit_cost": round(config.POWDER_COAT_PRICE[size] * rng.uniform(0.95, 1.08), 2),
                    "cost_date": d, "_mat": None})
    elif finish.startswith("zinc"):
        bom.append({"item_type": "outside", "item": "zinc_plate", "qty_per": 1, "uom": "ea",
                    "unit_cost": round(config.ZINC_PRICE[size] * rng.uniform(0.95, 1.08), 2),
                    "cost_date": d, "_mat": None})
    ops = []
    for wc, setup, run, p in ROUTING[fam]:
        include = rng.random() < p
        if wc == "grind" and cosmetic and fam != "mounting_plate":
            include = True
        if wc == "press_brake" and fam in ("frame", "mounting_plate") and t >= 0.5:
            include = include or rng.random() < 0.6
        if forced_ops is not None:
            include = wc in forced_ops
        if not include:
            continue
        run_b = run * (1.6 if (wc == "grind" and cosmetic) else 1.0)
        ops.append({"work_center": wc,
                    "setup_hr_est": round(setup * rng.normal(1.0, 0.08), 2),
                    "run_hr_est": round(run_b * s * rng.normal(1.0, 0.06), 3)})
    if fixture:
        ops.insert(0, {"work_center": "fixture", "setup_hr_est": round(rng.uniform(5.0, 7.0), 1), "run_hr_est": 0.0})
    return bom, ops


def apply_actuals(rng, ops: list[dict], cosmetic: bool, first_run: bool, fixture: bool, ncr_pb: bool) -> None:
    for o in ops:
        wc = o["work_center"]
        s_ratio = rng.normal(1.05, 0.10)
        r_ratio = rng.normal(1.03, 0.07)
        if wc == "weld":
            r_ratio = rng.normal(1.35, 0.08) if cosmetic else rng.normal(1.02, 0.07)
        if wc == "fit_tack" and first_run and not fixture:
            s_ratio = rng.uniform(1.6, 2.2)
        if wc == "press_brake" and ncr_pb:
            r_ratio = rng.uniform(1.25, 1.45)
        if wc == "fixture":
            s_ratio = rng.normal(1.05, 0.12)
        o["setup_hr_act"] = round(o["setup_hr_est"] * max(0.6, s_ratio), 2)
        o["run_hr_act"] = round(o["run_hr_est"] * max(0.6, r_ratio), 3)


def describe(fam: str, mat: str, t: float, cosmetic: bool, finish: str, rng, first_run: bool) -> str:
    weld = rng.choice(["cosmetic welds on visible side", "cosmetic weld, visible side smooth, no spatter",
                       "show-side welds cosmetic"]) if cosmetic else rng.choice(
        ["standard structural welds", "structural welds per print", "standard welds"])
    fin = finish if finish else "finish TBD"
    th = frac(t)
    if fam == "hitch_bracket":
        body = f"Hitch bracket weldment, {th} A36 plate, laser + formed parts, 2x2x3/16 A500 tube, bushings & bolt kit"
    elif fam == "guard":
        m = "5052 aluminum" if mat == "5052AL" else "A36 sheet"
        body = rng.choice([f"Belt guard, {th} {m}, laser cut and formed, tack-welded tabs",
                           f"Shield / guard panel, {th} {m}, formed flanges, welded brackets"])
        if rng.random() < 0.4:
            weld = "light tack welds" if not cosmetic else weld
    elif fam == "frame":
        body = rng.choice([f"Main frame weldment, 3x3x1/4 A500 tube with {th} A36 plates, pivot pins",
                           f"Sub-frame weldment, A500 tube rails, {th} A36 gussets and mounts"])
    elif fam == "mounting_plate":
        body = rng.choice([f"Mounting plate, {th} A36, laser cut, drilled & tapped",
                           f"Adapter / mounting plate, {th} A36 plate, machined holes"])
        weld = "no welding"
    else:
        m = "304 SS tube" if mat == "304SS" else "2x2x3/16 A500 tube"
        body = f"Tube assembly, {m} with 1018 bar end fittings, welded"
    txt = f"{body}; {weld}; {fin}"
    if first_run:
        txt += "; new part, first run"
    return txt


def pick_finish(rng, fam: str, mat: str) -> str:
    if mat in ("304SS", "5052AL"):
        return "none"
    r = rng.random()
    if fam == "mounting_plate" and r < 0.25:
        return "zinc plate"
    if r < 0.08:
        return "none"
    return f"powder coat {rng.choice(POWDER_COLORS)}"


# ---------------------------------------------------------------- hero jobs (deterministic)
def hero_specs() -> list[dict]:
    """Handcrafted jobs so demo RFQs retrieve the intended analogs. Values are per unit / per lot."""
    hb_bom = [("raw", "A36", 19.8), ("raw", "A500", 4.3), ("purchased", "Bushing 1.25 OD x 1.00 ID x 1.50 L", 2),
              ("purchased", "Bolt kit 4x 1/2-13 Gr8", 1), ("outside", "powder_coat", 1)]
    return [
        dict(job_id="J-0918", cust="C02", fam="hitch_bracket", pn="CVE-HB-4410 Rev A", mat="A36", t=0.375, qty=100,
             cosmetic=True, finish="powder coat black", first_run=True, fixture=True, d=date(2025, 5, 14),
             won=True, ratio=1.34, lead=32, bom=hb_bom,
             ops=[("fixture", 6.0, 0, 6.4, 0), ("laser", 0.5, 0.075, 0.55, 0.078), ("press_brake", 0.7, 0.05, 0.75, 0.052),
                  ("saw", 0.25, 0.03, 0.25, 0.031), ("fit_tack", 2.0, 0.20, 2.2, 0.21), ("weld", 0.5, 0.45, 0.55, 0.60),
                  ("grind", 0.25, 0.18, 0.3, 0.2), ("inspect_pack", 0.25, 0.05, 0.25, 0.05)],
             desc="Hitch bracket weldment Rev A, 3/8 A36 plate, laser + formed parts, 2x2x3/16 A500 tube, "
                  "bushings & bolt kit; cosmetic welds on visible side, no spatter; powder coat black; new part, first run",
             debrief="Rev A first run. Fixture we quoted paid for itself, fit-up went fast after that. "
                     "Cosmetic side needed extra blending."),
        dict(job_id="J-0987", cust="C03", fam="hitch_bracket", pn="HLW-HB-2207", mat="A36", t=0.375, qty=150,
             cosmetic=True, finish="powder coat implement yellow", first_run=False, fixture=False, d=date(2025, 12, 2),
             won=True, ratio=1.31, lead=30, bom=hb_bom,
             ops=[("laser", 0.5, 0.075, 0.5, 0.077), ("press_brake", 0.7, 0.05, 0.7, 0.051), ("saw", 0.25, 0.03, 0.25, 0.03),
                  ("fit_tack", 2.0, 0.20, 2.1, 0.2), ("weld", 0.5, 0.44, 0.5, 0.58), ("grind", 0.25, 0.18, 0.25, 0.21),
                  ("inspect_pack", 0.25, 0.05, 0.25, 0.05)],
             desc="Hitch bracket weldment, 3/8 A36 plate, laser cut + formed ears, 2x2x3/16 A500 tube, bushings; "
                  "cosmetic weld, visible side smooth, no spatter; powder coat yellow",
             debrief="Weld ran over on the show side again, about a third over quote. Grind kept up."),
        dict(job_id="J-1042", cust="C02", fam="hitch_bracket", pn="CVE-HB-4410 Rev B", mat="A36", t=0.375, qty=200,
             cosmetic=True, finish="powder coat black", first_run=False, fixture=False, d=date(2026, 3, 10),
             won=True, ratio=1.32, lead=31, bom=hb_bom,
             ops=[("laser", 0.5, 0.075, 0.55, 0.078), ("press_brake", 0.7, 0.05, 0.72, 0.052), ("saw", 0.25, 0.03, 0.25, 0.031),
                  ("fit_tack", 2.0, 0.20, 2.1, 0.21), ("weld", 0.5, 0.46, 0.55, 0.62), ("grind", 0.25, 0.18, 0.3, 0.21),
                  ("inspect_pack", 0.25, 0.05, 0.25, 0.05)],
             desc="Hitch bracket weldment Rev B, 3/8 A36 plate, laser + formed parts, 2x2x3/16 A500 tube, "
                  "bushings & bolt kit; cosmetic welds on visible side, no spatter, smooth; powder coat black",
             debrief="Rev B ran fine on the Rev A fixture. Weld on the visible side still runs long, "
                     "cosmetic spec eats time."),
        dict(job_id="J-1077", cust="C01", fam="hitch_bracket", pn="PIC-HB-5120", mat="A36", t=0.375, qty=300,
             cosmetic=True, finish="powder coat red", first_run=True, fixture=False, d=date(2026, 6, 18),
             won=False, ratio=1.38, lead=33, bom=hb_bom,
             ops=[("laser", 0.5, 0.075, None, None), ("press_brake", 0.7, 0.05, None, None), ("saw", 0.25, 0.03, None, None),
                  ("fit_tack", 2.0, 0.20, None, None), ("weld", 0.5, 0.45, None, None), ("grind", 0.25, 0.16, None, None),
                  ("inspect_pack", 0.25, 0.05, None, None)],
             desc="Hitch bracket weldment, 3/8 A36 plate, laser + formed parts, tube, bushings; cosmetic welds visible "
                  "side; powder coat red",
             debrief=None),
        dict(job_id="J-1103", cust="C04", fam="hitch_bracket", pn="NSA-HB-118", mat="A36", t=0.375, qty=150,
             cosmetic=False, finish="powder coat black", first_run=True, fixture=False, d=date(2026, 7, 8),
             won=True, ratio=1.29, lead=30, bom=hb_bom,
             ops=[("laser", 0.5, 0.075, 0.5, 0.077), ("press_brake", 0.7, 0.05, 0.75, 0.051), ("saw", 0.25, 0.03, 0.25, 0.03),
                  ("fit_tack", 2.0, 0.20, 4.4, 0.21), ("weld", 0.5, 0.42, 0.5, 0.43), ("grind", 0.25, 0.10, 0.25, 0.1),
                  ("inspect_pack", 0.25, 0.05, 0.3, 0.05)],
             desc="Hitch bracket weldment, 3/8 A36 plate, laser + formed parts, 2x2x3/16 A500 tube, bushings & "
                  "bolt kit; standard structural welds; powder coat black; new part, first run",
             debrief="First run on this bracket and nobody quoted a fixture. Spent most of the morning building one "
                     "out of drop, fit/tack setup ran more than double. Quote a new fixture on first-run weldments."),
        dict(job_id="J-0842", cust="C07", fam="mounting_plate", pn="LHM-MP-0620", mat="A36", t=0.5, qty=50,
             cosmetic=False, finish="powder coat black", first_run=True, fixture=False, d=date(2025, 3, 12),
             won=True, ratio=1.33, lead=16,
             bom=[("raw", "A36", 14.6), ("outside", "powder_coat", 1)],
             ops=[("laser", 0.4, 0.05, 0.45, 0.052), ("machining", 1.0, 0.10, 1.1, 0.104), ("inspect_pack", 0.2, 0.03, 0.2, 0.03)],
             desc="Mounting plate, 1/2 A36 plate, laser cut, drilled & tapped 4x 1/2-13; no welding; powder coat black",
             debrief="Ran clean. Tap drill program saved for next time."),
        dict(job_id="J-0955", cust="C07", fam="mounting_plate", pn="LHM-MP-0620", mat="A36", t=0.5, qty=40,
             cosmetic=False, finish="powder coat black", first_run=False, fixture=False, d=date(2025, 10, 1),
             won=True, ratio=1.34, lead=15,
             bom=[("raw", "A36", 14.6), ("outside", "powder_coat", 1)],
             ops=[("laser", 0.4, 0.05, 0.4, 0.051), ("machining", 1.0, 0.10, 1.0, 0.101), ("inspect_pack", 0.2, 0.03, 0.2, 0.03)],
             desc="Mounting plate, 1/2 A36 plate, laser cut, drilled & tapped 4x 1/2-13; no welding; powder coat black",
             debrief=None),
        dict(job_id="J-1118", cust="C07", fam="mounting_plate", pn="LHM-MP-0620", mat="A36", t=0.5, qty=40,
             cosmetic=False, finish="powder coat black", first_run=False, fixture=False, d=date(2026, 8, 5),
             won=True, ratio=1.35, lead=15,
             bom=[("raw", "A36", 14.6), ("outside", "powder_coat", 1)],
             ops=[("laser", 0.4, 0.05, 0.42, 0.05), ("machining", 1.0, 0.10, 1.05, 0.102), ("inspect_pack", 0.2, 0.03, 0.2, 0.03)],
             desc="Mounting plate, 1/2 A36 plate, laser cut, drilled & tapped 4x 1/2-13; no welding; powder coat black",
             debrief="Repeat, programs on file. No issues."),
    ]


# ---------------------------------------------------------------- main generator
def generate(seed: int | None = None) -> dict[str, pd.DataFrame]:
    seed = config.RANDOM_SEED if seed is None else seed
    rng = np.random.default_rng(seed)
    prices = gen_material_prices(rng)
    notes = json.loads((config.DATA_DIR / "seed_notes.json").read_text(encoding="utf-8"))

    # --- random job skeletons, sorted by date
    days = (END - START).days
    dates = sorted(START + timedelta(days=int(x)) for x in rng.integers(0, days - 3, N_RANDOM))
    cust_ids = [c[0] for c in CUSTOMERS]
    cust_w = np.array([c[6] for c in CUSTOMERS])
    fams = list(FAMILY_WEIGHTS)
    fam_w = np.array(list(FAMILY_WEIGHTS.values()))

    pn_pool: dict[tuple, list[str]] = {}
    pn_seen: set[str] = set()
    reserved = {normalize_pn(h["pn"]) for h in hero_specs()} | {"HLWHB3300"}
    jobs, bom_rows, op_rows = [], [], []
    ids = iter(f"J-{n:04d}" for n in range(850, 1400) if f"J-{n:04d}" not in HERO_IDS)

    for d in dates:
        cid = str(rng.choice(cust_ids, p=cust_w / cust_w.sum()))
        if cid == "C06" and d < date(2026, 1, 15):   # Big Sioux is a new 2026 account
            cid = "C04"
        fam = str(rng.choice(fams, p=fam_w / fam_w.sum()))
        key = (cid, fam)
        pool = pn_pool.setdefault(key, [])
        if pool and rng.random() < 0.45:
            pn = str(rng.choice(pool))
        else:
            while True:
                pn = f"{CUST_BY_ID[cid][5]}-{FAMILY_CODE[fam]}-{int(rng.integers(100, 9999))}"
                if normalize_pn(pn) not in reserved and pn not in pool:
                    break
            pool.append(pn)
        first_run = normalize_pn(pn) not in pn_seen
        pn_seen.add(normalize_pn(pn))

        if fam == "hitch_bracket":
            mat, t = "A36", float(rng.choice([0.25, 0.375, 0.5], p=[0.3, 0.45, 0.25]))
        elif fam == "guard":
            mat = "5052AL" if rng.random() < 0.12 else "A36"
            t = float(rng.choice([0.075, 0.105, 0.135]))
        elif fam == "frame":
            mat, t = "A36", float(rng.choice([0.375, 0.5, 0.625], p=[0.4, 0.4, 0.2]))
        elif fam == "mounting_plate":
            mat, t = "A36", float(rng.choice([0.375, 0.5, 0.625, 0.75], p=[0.3, 0.35, 0.2, 0.15]))
        else:
            mat, t = ("304SS" if rng.random() < 0.12 else "A500"), 0.1875
        cosmetic = bool(fam in ("hitch_bracket", "frame", "guard") and rng.random() < {"hitch_bracket": 0.4,
                                                                                         "frame": 0.35,
                                                                                         "guard": 0.3}[fam])
        fixture = bool(first_run and fam in WELDMENTS and fam != "guard" and rng.random() < 0.5)
        finish = pick_finish(rng, fam, mat)
        qty = int(rng.choice(QTY_CHOICES[fam]))
        s = float(rng.uniform(0.8, 1.25))
        bom, ops = build_lines(rng, fam, mat, t, qty, cosmetic, finish, d, prices, s, fixture)

        seg = CUST_BY_ID[cid][2]
        if cid == "C01":
            ratio = float(rng.uniform(1.10, 1.45))
            p_win = 1 / (1 + np.exp(-40 * (1.265 - ratio)))
        else:
            ratio = float(rng.uniform(1.12, 1.55))
            mid = 1.42 if seg == "aftermarket" else 1.38
            p_win = 1 / (1 + np.exp(-12 * (mid - ratio)))
            if CUST_BY_ID[cid][3]:
                p_win *= 0.8
        won = bool(rng.random() < p_win)
        lead = int(rng.integers(*LEAD_DAYS[fam]))
        jid = next(ids)
        jobs.append(dict(job_id=jid, customer_id=cid, part_family=fam, part_number=pn, description="",
                         material=mat, material_raw_name=str(rng.choice(MATERIAL_ALIASES[mat])), thickness_in=t,
                         qty=qty, tolerance_class="tight" if rng.random() < 0.15 else "standard",
                         cosmetic_weld=cosmetic, finish=finish, first_run=first_run, has_fixture_line=fixture,
                         quote_date=d, est_cost=0.0, quoted_price=0.0, won=won, lead_time_days=lead,
                         _ratio=ratio, _bom=bom, _ops=ops, _s=s))

    # --- hero jobs
    for h in hero_specs():
        bom = []
        for typ, item, q in h["bom"]:
            if typ == "raw":
                bom.append({"item_type": "raw", "item": MATERIAL_ITEM[item], "qty_per": q, "uom": "lb",
                            "unit_cost": price_at(prices, item, h["d"]), "cost_date": h["d"], "_mat": item})
            elif typ == "purchased":
                bom.append({"item_type": "purchased", "item": item, "qty_per": q, "uom": "ea",
                            "unit_cost": purchased_price(item, h["d"]), "cost_date": h["d"], "_mat": None})
            else:
                bom.append({"item_type": "outside", "item": "powder_coat", "qty_per": q, "uom": "ea",
                            "unit_cost": config.POWDER_COAT_PRICE[SIZE_CLASS[h["fam"]]], "cost_date": h["d"],
                            "_mat": None})
        ops = [{"work_center": wc, "setup_hr_est": se, "run_hr_est": re_, "setup_hr_act": sa, "run_hr_act": ra}
               for wc, se, re_, sa, ra in h["ops"]]
        jobs.append(dict(job_id=h["job_id"], customer_id=h["cust"], part_family=h["fam"], part_number=h["pn"],
                         description=h["desc"], material=h["mat"], material_raw_name="A36", thickness_in=h["t"],
                         qty=h["qty"], tolerance_class="standard", cosmetic_weld=h["cosmetic"], finish=h["finish"],
                         first_run=h["first_run"], has_fixture_line=h["fixture"], quote_date=h["d"], est_cost=0.0,
                         quoted_price=0.0, won=h["won"], lead_time_days=h["lead"], _ratio=h["ratio"], _bom=bom,
                         _ops=ops, _s=1.0, _hero=True, _debrief=h["debrief"]))

    # --- actuals, NCR flags, costs
    as_of = config.AS_OF
    for j in jobs:
        j["_completed"] = bool(j["won"] and j["quote_date"] + timedelta(days=j["lead_time_days"] + 7) < as_of)
    # ~10% of won + completed jobs never got their actuals keyed in (real-world messiness)
    done_random = [j["job_id"] for j in jobs if j["_completed"] and not j.get("_hero")]
    missing = set(rng.permutation(np.array(done_random))[: int(round(0.10 * len(done_random)))])
    # P3: press brake on >= 0.5" plate, ~30% of completed jobs get an NCR (+ rework hours)
    elig = [j for j in jobs if not j.get("_hero") and j["_completed"] and j["job_id"] not in missing
            and j["thickness_in"] >= 0.5 and any(o["work_center"] == "press_brake" for o in j["_ops"])]
    n_ncr = int(round(0.30 * len(elig)))
    ncr_ids = set(j["job_id"] for j in (list(rng.permutation(np.array(elig, dtype=object)))[:n_ncr] if elig else []))
    for j in jobs:
        if j.get("_hero"):
            continue
        if j["_completed"] and j["job_id"] not in missing:
            apply_actuals(rng, j["_ops"], j["cosmetic_weld"], j["first_run"], j["has_fixture_line"],
                          j["job_id"] in ncr_ids)
        else:
            for o in j["_ops"]:
                o["setup_hr_act"], o["run_hr_act"] = None, None
        j["description"] = describe(j["part_family"], j["material"], j["thickness_in"], j["cosmetic_weld"],
                                    j["finish"], rng, j["first_run"])
    for j in jobs:
        est = unit_cost_from_lines(j["_bom"], j["_ops"], j["qty"])
        j["est_cost"] = round(est, 2)
        j["quoted_price"] = round(est * j["_ratio"], 2)

    # --- noise: missing finish on a few, near-duplicate part numbers
    rand_jobs = [j for j in jobs if not j.get("_hero")]
    for j in list(rng.permutation(np.array(rand_jobs, dtype=object)))[:3]:
        j["finish"] = ""
    repeats = [j for j in rand_jobs if not j["first_run"]]
    for j, fmt in zip(list(rng.permutation(np.array(repeats, dtype=object)))[:4],
                      ["nospace", "space", "suffix", "lower"]):
        pn = j["part_number"]
        j["part_number"] = {"nospace": pn.replace("-", ""), "space": pn.replace("-", " "),
                            "suffix": pn + "-A", "lower": pn.lower()}[fmt]

    jobs.sort(key=lambda j: (j["quote_date"], j["job_id"]))
    for j in jobs:
        for i, b in enumerate(j["_bom"], 1):
            bom_rows.append({"job_id": j["job_id"], "line_no": i, "item_type": b["item_type"], "item": b["item"],
                             "qty_per": b["qty_per"], "uom": b["uom"], "unit_cost": b["unit_cost"],
                             "cost_date": b["cost_date"]})
        for i, o in enumerate(j["_ops"], 1):
            op_rows.append({"job_id": j["job_id"], "seq": i * 10, "work_center": o["work_center"],
                            "setup_hr_est": o["setup_hr_est"], "run_hr_est": o["run_hr_est"],
                            "setup_hr_act": o.get("setup_hr_act"), "run_hr_act": o.get("run_hr_act")})

    docs = gen_docs(rng, jobs, notes, ncr_ids)
    job_cols = ["job_id", "customer_id", "part_family", "part_number", "description", "material",
                "material_raw_name", "thickness_in", "qty", "tolerance_class", "cosmetic_weld", "finish",
                "first_run", "has_fixture_line", "quote_date", "est_cost", "quoted_price", "won", "lead_time_days"]
    customers = pd.DataFrame([{"customer_id": c[0], "name": c[1], "segment": c[2], "is_new": c[3], "notes": c[4]}
                              for c in CUSTOMERS])
    wcs = pd.DataFrame([{"work_center": k, "rate_per_hr": v[0], "default_setup_hr": v[1],
                         "default_run_hr_per_unit": v[2]} for k, v in config.WORK_CENTERS.items()]
                       + [{"work_center": "fixture", "rate_per_hr": config.FIXTURE_RATE,
                           "default_setup_hr": config.FIXTURE_DEFAULT_HR, "default_run_hr_per_unit": 0.0}])
    return {
        "customers": customers,
        "jobs": pd.DataFrame([{k: j[k] for k in job_cols} for j in jobs]),
        "bom_lines": pd.DataFrame(bom_rows),
        "routing_ops": pd.DataFrame(op_rows),
        "docs": docs,
        "material_prices": prices,
        "work_centers": wcs,
    }


def _typos(rng, text: str) -> str:
    if rng.random() < 0.15:
        for good, bad in T.TYPO_SWAPS:
            if good in text:
                return text.replace(good, bad, 1)
    return text


def gen_docs(rng, jobs: list[dict], notes: list[dict], ncr_ids: set[str]) -> pd.DataFrame:
    rows = []
    by_pat = {p: [n for n in notes if n["pattern"] == p] for p in ("P1", "P2", "P3", "none")}
    used: dict[str, int] = {}

    def take(pat: str, fam: str | None = None) -> dict:
        pool = by_pat[pat]
        pref = [n for n in pool if fam and n["part_family"] == fam] or pool
        pref = sorted(pref, key=lambda n: used.get(n["note_id"], 0))
        n = pref[0]
        used[n["note_id"]] = used.get(n["note_id"], 0) + 1
        return n

    def add(job, doc_type, d, text, wc=None, line_key=None):
        rows.append({"doc_id": "", "job_id": job["job_id"], "doc_type": doc_type, "date": d,
                     "part_family": job["part_family"], "work_center": wc, "line_key": line_key,
                     "old_value": None, "new_value": None, "text": text})

    for j in jobs:
        cust = CUST_BY_ID[j["customer_id"]][1]
        weld_key = "cosmetic" if j["cosmetic_weld"] else "standard"
        fin = j["finish"] or "per print"
        email = str(rng.choice(T.RFQ_EMAIL_TEMPLATES)).format(
            contact=str(rng.choice(T.CONTACT_NAMES)), customer=cust, part_number=j["part_number"],
            part_desc=j["description"].split(";")[0], material_text=f"{frac(j['thickness_in'])} {j['material_raw_name']}",
            qty=j["qty"], finish_text=fin, due_text=f"{j['lead_time_days'] // 7 + 1} weeks ARO",
            weld_text=str(rng.choice(T.WELD_TEXT[weld_key])))
        add(j, "rfq_email", j["quote_date"], _typos(rng, email))

        has_act = any(o.get("run_hr_act") is not None for o in j["_ops"])
        if not has_act:
            continue
        done = j["quote_date"] + timedelta(days=j["lead_time_days"])
        wcs = {o["work_center"] for o in j["_ops"]}
        if j.get("_hero"):
            if j.get("_debrief"):
                wc, lk = ("fit_tack", "fit_tack.setup") if "fixture" in j["_debrief"].lower() and j["first_run"] \
                    and not j["has_fixture_line"] else ("weld", "weld.run") if j["cosmetic_weld"] else (None, None)
                add(j, "debrief", done, j["_debrief"], wc, lk)
            continue
        # P2: first-run weldment without fixture line -> ~50% get a fixture debrief
        if j["first_run"] and not j["has_fixture_line"] and "fit_tack" in wcs and rng.random() < 0.55:
            n = take("P2", j["part_family"])
            add(j, "debrief", done, n["text"], "fit_tack", "fit_tack.setup")
        # P1: cosmetic weld overrun notes
        if j["cosmetic_weld"] and "weld" in wcs and rng.random() < 0.45:
            n = take("P1", j["part_family"])
            add(j, "debrief", done, n["text"], "weld", "weld.run")
        # P3: NCR on thick-plate press brake jobs
        if j["job_id"] in ncr_ids:
            n = take("P3", j["part_family"])
            add(j, "ncr", done - timedelta(days=5), n["text"], "press_brake", "press_brake.run")
        # generic debriefs / other notes on ~25% of completed jobs
        if rng.random() < 0.25:
            cand = [n for n in by_pat["none"] if n["work_center"] in wcs or n["work_center"] == "powder_coat"]
            if cand and rng.random() < 0.6:
                n = cand[int(rng.integers(0, len(cand)))]
                if n["mentions_fixture"] and j["first_run"] and not j["has_fixture_line"]:
                    continue  # "used the fixture from last run" makes no sense on a fixture-less first run
                wc = n["work_center"]
                lk = f"{wc}.{n['line']}" if wc in config.WORK_CENTERS else "out.powder_coat"
                add(j, n["doc_type"], done, n["text"], wc, lk)
            else:
                add(j, "debrief", done, str(rng.choice(T.GENERIC_DEBRIEFS)))

    df = pd.DataFrame(rows).sort_values(["date", "job_id", "doc_type"]).reset_index(drop=True)
    df["doc_id"] = [f"D-{i:04d}" for i in range(1, len(df) + 1)]
    return df[["doc_id", "job_id", "doc_type", "date", "part_family", "work_center", "line_key", "old_value",
               "new_value", "text"]]


def save(tables: dict[str, pd.DataFrame], data_dir=None) -> None:
    data_dir = data_dir or config.DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(data_dir / f"{name}.csv", index=False)
    build_sqlite(tables)


def build_sqlite(tables: dict[str, pd.DataFrame], path=None) -> None:
    path = path or config.SQLITE_PATH
    with sqlite3.connect(path) as con:
        for name, df in tables.items():
            df.to_sql(name, con, if_exists="replace", index=False)


if __name__ == "__main__":
    t = generate()
    save(t)
    j = t["jobs"]
    print(f"jobs={len(j)} won={j.won.mean():.0%} bom={len(t['bom_lines'])} ops={len(t['routing_ops'])} "
          f"docs={len(t['docs'])} prices={len(t['material_prices'])}")
