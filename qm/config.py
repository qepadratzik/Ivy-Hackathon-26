"""Env loading and every tunable constant in one place.

All dollar figures are ILLUSTRATIVE (synthetic data for a fictional shop).
Final values are mirrored in docs/assumptions.md.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except Exception:  # dotenv is optional at runtime
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MEMORY_DIR = Path(os.getenv("QM_MEMORY_DIR") or DATA_DIR / "memory")   # demo-session overrides (gitignored)
CHROMA_DIR = Path(os.getenv("QM_CHROMA_DIR") or DATA_DIR / "chroma")    # vector store (gitignored, rebuilt)
SQLITE_PATH = Path(os.getenv("QM_SQLITE_PATH") or DATA_DIR / "quote_memory.sqlite")
CACHE_DIR = ROOT / "cache" / "llm"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "llm"
DEMO_RFQ_DIR = ROOT / "demo" / "rfqs"


def env(name: str, default: str = "") -> str:
    val = os.getenv(name, "")
    return val.strip() if val and val.strip() else default


MODEL_PROVIDER = env("MODEL_PROVIDER", "mock").lower()
OLLAMA_HOST = env("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = env("OLLAMA_MODEL", "qwen3:8b")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", "claude-haiku-4-5")
DEMO_MODE = env("DEMO_MODE", "live").lower()
RANDOM_SEED = int(env("RANDOM_SEED", "42"))
LLM_TIMEOUT_S = 60
LLM_TEMPERATURE = 0.1

# "Today" for the demo. Fixed so recency weights and tests are reproducible.
AS_OF = date(2026, 9, 30)

# ---------------------------------------------------------------- shop model
# Burdened work-center rates, $/hr (ILLUSTRATIVE). Defaults are shop rules of thumb.
WORK_CENTERS = {
    #  name          rate   default_setup_hr  default_run_hr_per_unit
    "cut":          (120.0, 0.50, 0.08),    # laser (plate) or saw (tube)
    "press_brake":  (95.0,  0.75, 0.06),    # bending
    "weld":         (85.0,  2.00, 0.50),    # fit-up, tack, weld and clean-up
    "machining":    (110.0, 1.00, 0.12),    # drill and tap
    "inspect_pack": (75.0,  0.25, 0.05),
}
WC_ORDER = list(WORK_CENTERS)
WC_LABELS = {
    "cut": "Cut", "press_brake": "Bend", "weld": "Fit & weld", "machining": "Drill & tap",
    "inspect_pack": "Inspect & pack", "fixture": "Fixture build (one-time)",
}
# One-time fixture line (added by the first-run / new-revision rule). Charged at the weld rate.
FIXTURE_DEFAULT_HR = 6.0
FIXTURE_RATE = WORK_CENTERS["weld"][0]

# Powder coat vendor price per part by size class (ILLUSTRATIVE).
POWDER_COAT_PRICE = {"small": 4.50, "medium": 8.75, "large": 26.00}
POWDER_COAT_DAYS = 8          # vendor turnaround, calendar days
ZINC_PRICE = {"small": 2.10, "medium": 4.25, "large": 12.00}

# ---------------------------------------------------------------- evidence (Section 7.4)
AUTHORITY = {
    "actual": 1.0,
    "supplier_quote": 1.0,     # a real supplier price quote is hard data
    "note": 0.8,
    "override": 0.8,
    "pattern": 0.8,
    "past_quote": 0.6,
    "shop_default": 0.3,
}
HALF_LIFE_DAYS = {
    "material": 30,
    "labor": 540,
    "note": 365,
    "purchased": 365,
    "outside": 365,
}
SIM_THRESHOLD = 0.35
TOP_K_JOBS = 6
CONF_SCORE_SATURATION = 3.0     # confidence = min(1, sum(score)/3) * (1 - min(1, CV))
SPREAD_BASE = 0.10
SPREAD_SLOPE = 0.40
SPREAD_MAX = 0.60
CHIP_GREEN = 0.70
CHIP_YELLOW = 0.40
MATERIAL_STALE_DAYS = 30

# ---------------------------------------------------------------- uncertainty / pricing
MC_SAMPLES = 2000
LABOR_CORRELATION = 0.5       # labor lines share a common factor (a bad week hits cutting, bending and welding together)
RISK_SHARE = 0.5              # risk-adjusted cost = P50 + RISK_SHARE * (P90 - P50)
PRICE_GRID = (1.0, 1.8, 161)  # candidate price multipliers on P50
REC_BAND = 0.90               # recommended range = exp margin >= 90% of peak
# Capacity: minimum acceptable margin over risk-adjusted cost rises with shop load (the floor) ...
MIN_MARGIN_AT_LOAD = [(0.0, 0.04), (0.5, 0.10), (0.8, 0.22), (1.0, 0.35)]
# ... and shop time has an opportunity cost: busy shop -> each labor hour displaces other work;
# slow shop -> burdened overhead is already sunk, so thinner margins still pay. Share of labor cost.
CAPACITY_PREMIUM_AT_LOAD = [(0.0, -0.10), (0.5, 0.0), (1.0, 0.30)]
EXPEDITE_PRICE_PCT = 0.12     # +12% price ...
EXPEDITE_DAYS_SAVED = 7       # ... for one week faster (ILLUSTRATIVE)
QUOTE_VALIDITY_DAYS = 30
QUOTE_VALIDITY_STALE_DAYS = 15

# Gap contingency defaults (share of the affected lines' cost)
GAP_CONTINGENCY = {"finish_color": 0.03, "qty_conflict": 0.05, "material": 0.08, "default": 0.05}


def provider_label() -> str:
    if MODEL_PROVIDER == "ollama":
        return f"ollama:{OLLAMA_MODEL}"
    if MODEL_PROVIDER == "anthropic":
        return f"anthropic:{ANTHROPIC_MODEL}"
    return "mock"


def anthropic_key_present() -> bool:
    """Presence check only. Never print or log the value."""
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
