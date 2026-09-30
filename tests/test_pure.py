"""Unit tests for the pure functions: evidence math + note gating, Monte Carlo helpers, pricing curve,
gap rules, triage. Emphasis on edge cases (no evidence, one row, conflicts, zeros, clamping).
Complements tests/test_ledger.py and tests/test_intake.py, which cover the same code end-to-end."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from qm import config, evidence, gaps, pricing, triage, uncertainty


def row(value, score, counted=True):
    return dict(value=value, score=score, counted=counted)


# ================================================================ evidence.recency_decay
@pytest.mark.parametrize("key", sorted(config.HALF_LIFE_DAYS))
def test_recency_decay_half_life_math(key):
    hl = config.HALF_LIFE_DAYS[key]
    assert evidence.recency_decay(0, hl) == 1.0
    assert evidence.recency_decay(hl, hl) == pytest.approx(0.5)
    assert evidence.recency_decay(2 * hl, hl) == pytest.approx(0.25)
    assert evidence.recency_decay(hl / 2, hl) == pytest.approx(2 ** -0.5)


@pytest.mark.parametrize("age", [-1, -0.5, -365])
def test_recency_decay_negative_age_treated_as_zero(age):
    assert evidence.recency_decay(age, 30) == 1.0


@pytest.mark.parametrize("hl", [None, 0])
def test_recency_decay_without_half_life_is_one(hl):
    assert evidence.recency_decay(10_000, hl) == 1.0


def test_recency_decay_monotonic_and_bounded():
    d = [evidence.recency_decay(a, 180) for a in np.linspace(0, 3000, 61)]
    assert all(0 < x <= 1 for x in d)
    assert all(b < a for a, b in zip(d, d[1:]))


# ================================================================ evidence.make_row
@pytest.mark.parametrize("src", sorted(config.AUTHORITY))
def test_make_row_authority_per_source_type(src):
    r = evidence.make_row(src, "ref", 2.0, 0.8)
    assert r["authority"] == config.AUTHORITY[src]
    assert r["score"] == pytest.approx(0.8 * config.AUTHORITY[src], abs=1e-4)
    assert r["counted"] is True and r["note"] is None
    assert r["source"] == evidence.SOURCE_LABELS[src]


def test_make_row_score_is_sim_times_authority_times_decay():
    r = evidence.make_row("past_quote", "J-9", 1.5, 0.7, age_days=180, half_life_key="purchased")
    assert r["half_life"] == 180 and r["decay"] == pytest.approx(0.5)
    assert r["score"] == pytest.approx(0.7 * config.AUTHORITY["past_quote"] * 0.5, abs=1e-4)
    assert isinstance(r["value"], float) and r["value"] == 1.5


def test_make_row_similarity_exactly_at_threshold_counts():
    r = evidence.make_row("actual", "J", 1.0, config.SIM_THRESHOLD)
    assert r["counted"] is True and r["score"] == pytest.approx(config.SIM_THRESHOLD, abs=1e-4)


def test_make_row_similarity_below_threshold_scores_zero_with_note():
    r = evidence.make_row("actual", "J", 1.0, config.SIM_THRESHOLD - 0.001)
    assert r["score"] == 0.0 and r["counted"] is False
    assert "below" in r["note"] and str(config.SIM_THRESHOLD) in r["note"]
    assert r["value"] == 1.0   # still shown for context


def test_make_row_below_threshold_keeps_explicit_note():
    r = evidence.make_row("actual", "J", 1.0, 0.1, note="custom")
    assert r["note"] == "custom" and r["counted"] is False


def test_make_row_value_none_not_counted():
    r = evidence.make_row("note", "D-1", None, 0.9, age_days=10, half_life_key="note")
    assert r["value"] is None and r["counted"] is False and r["score"] == 0.0
    assert r["note"] is None          # not a similarity problem, so no "below" note
    assert 0 < r["decay"] < 1         # inputs are still recorded for the UI


def test_make_row_counted_false_is_respected():
    r = evidence.make_row("note", "D-1", 3.0, 0.9, counted=False, note="context only")
    assert r["counted"] is False and r["score"] == 0.0 and r["note"] == "context only"


def test_make_row_zero_value_counts_and_zero_similarity_does_not():
    z = evidence.make_row("actual", "J", 0.0, 0.9)
    assert z["counted"] is True and z["value"] == 0.0 and z["score"] == pytest.approx(0.9)
    s0 = evidence.make_row("actual", "J", 1.0, 0.0)
    assert s0["counted"] is False and s0["score"] == 0.0


def test_make_row_no_half_life_key_means_no_decay():
    r = evidence.make_row("actual", "J", 1.0, 1.0, age_days=5000)
    assert r["decay"] == 1.0 and r["half_life"] is None and r["age_days"] == 5000


def test_make_row_negative_age_gets_no_boost():
    r = evidence.make_row("actual", "J", 1.0, 1.0, age_days=-30, half_life_key="material")
    assert r["decay"] == 1.0 and r["score"] == pytest.approx(1.0)


def test_make_row_unknown_source_type_raises():
    with pytest.raises(KeyError):
        evidence.make_row("rumour", "x", 1.0, 1.0)


# ================================================================ evidence.summarize
def test_summarize_empty_has_no_range_and_max_spread():
    s = evidence.summarize([])
    assert s["value"] is None and s["low"] is None and s["high"] is None
    assert s["confidence"] == 0.0 and s["sum_score"] == 0.0 and s["cv"] is None
    assert s["spread"] == config.SPREAD_MAX


def test_summarize_only_unusable_rows_equals_empty():
    rows = [row(5.0, 1.0, counted=False), row(5.0, 0.0), row(None, 1.0)]
    assert evidence.summarize(rows) == evidence.summarize([])


def test_summarize_forced_value_without_evidence_uses_max_spread():
    s = evidence.summarize([], forced_value=10.0)
    assert s["value"] == 10.0 and s["confidence"] == 0.0
    assert s["low"] == pytest.approx(10 * (1 - config.SPREAD_MAX))
    assert s["high"] == pytest.approx(10 * (1 + config.SPREAD_MAX))


@pytest.mark.parametrize("score", [0.3, 1.0, 2.9, 3.0, 7.5])
def test_summarize_single_row(score):
    s = evidence.summarize([row(4.0, score)])
    conf = min(1.0, score / config.CONF_SCORE_SATURATION)
    assert s["value"] == pytest.approx(4.0) and s["std"] == 0 and s["cv"] == 0
    assert s["confidence"] == pytest.approx(conf)
    assert s["spread"] == pytest.approx(config.SPREAD_BASE + config.SPREAD_SLOPE * (1 - conf))
    assert s["low"] == pytest.approx(4.0 * (1 - s["spread"]))
    assert s["high"] == pytest.approx(4.0 * (1 + s["spread"]))


def test_summarize_saturated_single_row_hits_base_spread():
    s = evidence.summarize([row(4.0, 10.0)])
    assert s["confidence"] == 1.0 and s["spread"] == pytest.approx(config.SPREAD_BASE)


def test_summarize_conflicting_rows_low_confidence_red_chip():
    agree = evidence.summarize([row(5.0, 1.5), row(5.2, 1.5)])
    clash = evidence.summarize([row(1.0, 1.5), row(10.0, 1.5)])
    assert clash["value"] == pytest.approx(5.5) and clash["cv"] == pytest.approx(4.5 / 5.5)
    assert clash["confidence"] < agree["confidence"]
    assert evidence.chip(agree["confidence"]) == "green" and evidence.chip(clash["confidence"]) == "red"
    assert clash["high"] - clash["low"] > agree["high"] - agree["low"]


def test_summarize_cv_above_one_clamps_confidence_to_zero():
    s = evidence.summarize([row(0.0, 0.9), row(100.0, 0.1)])
    assert s["cv"] > 1
    assert s["confidence"] == 0.0
    assert s["spread"] == pytest.approx(config.SPREAD_BASE + config.SPREAD_SLOPE)
    assert s["spread"] <= config.SPREAD_MAX


def test_summarize_spread_always_within_bounds():
    rng = np.random.default_rng(0)
    for _ in range(300):
        n = int(rng.integers(1, 6))
        scale = float(rng.choice([0.0, 0.01, 1.0, 100.0]))
        rows = [row(float(v), float(s)) for v, s in zip(rng.random(n) * scale, rng.random(n) * 3)]
        forced = None if rng.random() < 0.7 else float(rng.random() * 10)
        s = evidence.summarize(rows, forced_value=forced)
        assert config.SPREAD_BASE - 1e-12 <= s["spread"] <= config.SPREAD_MAX + 1e-12
        assert 0.0 <= s["confidence"] <= 1.0
        if s["value"] is not None:
            assert s["low"] <= s["value"] <= s["high"]


def test_summarize_forced_value_overrides_mean_and_measures_disagreement():
    rows = [row(2.0, 1.0), row(2.0, 1.0)]
    base = evidence.summarize(rows)
    same = evidence.summarize(rows, forced_value=2.0)
    far = evidence.summarize(rows, forced_value=4.0)
    assert same["value"] == 2.0 and same["confidence"] == pytest.approx(base["confidence"])
    assert far["value"] == 4.0 and far["sum_score"] == base["sum_score"]
    assert far["std"] == pytest.approx(2.0) and far["cv"] == pytest.approx(0.5)
    assert far["confidence"] < same["confidence"]
    assert far["low"] == pytest.approx(4.0 * (1 - far["spread"]))


def test_summarize_forced_zero_is_not_treated_as_missing():
    s = evidence.summarize([row(2.0, 1.0)], forced_value=0.0)
    assert s["value"] == 0.0 and s["low"] == 0.0 and s["high"] == 0.0
    assert s["cv"] == 1.0 and s["confidence"] == 0.0


def test_summarize_zero_valued_evidence_no_division_by_zero():
    with np.errstate(all="raise"):
        s = evidence.summarize([row(0.0, 1.0), row(0.0, 2.0)])
        mixed = evidence.summarize([row(0.0, 1.0), row(2.0, 1.0)])
    assert s["value"] == 0.0 and s["std"] == 0.0 and s["cv"] == 0.0
    assert s["confidence"] == pytest.approx(1.0)
    assert s["low"] == 0.0 and s["high"] == 0.0
    assert mixed["value"] == pytest.approx(1.0) and np.isfinite(mixed["cv"])


def test_summarize_ignores_uncounted_zero_score_and_none_rows():
    good = [row(3.0, 1.2)]
    noise = [row(100.0, 5.0, counted=False), row(50.0, 0.0), row(None, 2.0)]
    assert evidence.summarize(good + noise) == evidence.summarize(good)


def test_summarize_rows_without_counted_key_are_used():
    s = evidence.summarize([dict(value=2.0, score=1.0)])
    assert s["value"] == 2.0 and s["sum_score"] == 1.0


def test_summarize_weighted_mean_is_order_invariant():
    rows = [row(1.0, 0.5), row(2.0, 1.0), row(4.0, 0.5)]
    s = evidence.summarize(rows)
    assert s["value"] == pytest.approx((0.5 * 1 + 1.0 * 2 + 0.5 * 4) / 2.0)
    r = evidence.summarize(rows[::-1])
    assert r["value"] == pytest.approx(s["value"]) and r["confidence"] == pytest.approx(s["confidence"])


def test_make_row_below_threshold_drops_out_of_summarize():
    rows = [evidence.make_row("actual", "J1", 1.0, 0.9), evidence.make_row("actual", "J2", 50.0, 0.2)]
    s = evidence.summarize(rows)
    assert s["value"] == pytest.approx(1.0) and s["cv"] == 0


# ================================================================ evidence.chip
@pytest.mark.parametrize("conf,color", [
    (1.0, "green"), (config.CHIP_GREEN, "green"), (0.70, "green"), (0.6999, "yellow"),
    (config.CHIP_YELLOW, "yellow"), (0.40, "yellow"), (0.3999, "red"), (0.0, "red"),
])
def test_chip_thresholds(conf, color):
    assert evidence.chip(conf) == color


# ================================================================ evidence.note_applies
def job(**kw):
    base = dict(cosmetic_weld=False, first_run=False, has_fixture_line=False, thickness_in=0.25)
    base.update(kw)
    return pd.Series(base)


@pytest.mark.parametrize("key", ["weld.run", "fit_tack.setup", "press_brake.run", "laser.run"])
def test_note_applies_none_job_always_true(key):
    assert evidence.note_applies(key, None, {"cosmetic_weld": True, "first_run": True, "thickness_in": 0.75})


@pytest.mark.parametrize("key", ["weld.run", "grind.run"])
@pytest.mark.parametrize("job_cos,spec_cos,expected", [
    (True, True, True), (False, False, True), (True, False, False), (False, True, False),
    (True, None, True), (False, None, True),   # unknown on the RFQ: don't gate
])
def test_note_applies_weld_gated_on_cosmetic(key, job_cos, spec_cos, expected):
    assert evidence.note_applies(key, job(cosmetic_weld=job_cos), {"cosmetic_weld": spec_cos}) == expected


def test_note_applies_weld_missing_spec_key_is_ungated():
    assert evidence.note_applies("weld.run", job(cosmetic_weld=True), {})


@pytest.mark.parametrize("key", ["fit_tack.setup", "fixture.setup"])
@pytest.mark.parametrize("job_first,job_fixture,spec_first,expected", [
    (True, False, True, True),     # first-run job built without a fixture: the P2 driver
    (True, True, True, False),     # first run but a fixture was quoted: different situation
    (False, False, True, False),   # repeat job says nothing about a first run
    (False, False, False, True),   # repeat vs repeat
    (False, True, False, True),    # fixture flag only matters on first runs
    (True, False, False, False),   # first-run note on a repeat RFQ
    (True, False, None, False),    # unknown first_run is treated as a repeat
])
def test_note_applies_fit_tack_gated_on_first_run_and_fixture(key, job_first, job_fixture, spec_first, expected):
    nj = job(first_run=job_first, has_fixture_line=job_fixture)
    assert evidence.note_applies(key, nj, {"first_run": spec_first}) == expected


@pytest.mark.parametrize("job_th,spec_th,expected", [
    (0.5, 0.5, True), (0.75, 0.625, True), (0.25, 0.375, True),
    (0.5, 0.375, False), (0.375, 0.5, False), (0.4999, 0.5, False),
    (0.25, None, True), (0.75, None, False),   # missing RFQ thickness is treated as thin
])
def test_note_applies_press_brake_gated_on_half_inch_plate(job_th, spec_th, expected):
    assert evidence.note_applies("press_brake.run", job(thickness_in=job_th), {"thickness_in": spec_th}) == expected


@pytest.mark.parametrize("key", ["laser.run", "press_brake.setup", "weld.setup", "inspect_pack.run", "mat.A36"])
def test_note_applies_other_lines_not_gated(key):
    nj = job(cosmetic_weld=True, first_run=True, has_fixture_line=True, thickness_in=1.0)
    assert evidence.note_applies(key, nj, {"cosmetic_weld": False, "first_run": False, "thickness_in": 0.1})


# ================================================================ uncertainty
def lline(key="weld.run", category="labor", kind="routing", hour_type="run", material=None,
          value=1.0, low=0.8, high=1.3, multiplier=85.0):
    return dict(key=key, category=category, kind=kind, hour_type=hour_type, material=material,
                value=value, low=low, high=high, multiplier=multiplier, cost=value * multiplier)


def toy_ledger():
    """Costs: setup 10, labor 50 (incl. setup), material 35 (A36 30 + A500 5), outside 10, purchased 5 = 100."""
    return [
        lline("laser.setup", hour_type="setup", value=0.5, low=0.4, high=0.7, multiplier=20.0),
        lline("weld.run", value=0.5, low=0.4, high=0.8, multiplier=80.0),
        lline("mat.A36", "material", "bom", None, "A36", 1.0, 0.9, 1.2, 30.0),
        lline("mat.A500", "material", "bom", None, "A500", 1.0, 0.9, 1.2, 5.0),
        lline("out.powder_coat", "outside", "bom", None, None, 10.0, 9.0, 11.0, 1.0),
        lline("buy.bolt", "purchased", "bom", None, None, 2.5, 2.0, 3.0, 2.0),
    ]


@pytest.mark.parametrize("low,high", [(2.0, 2.0), (None, None), (None, 3.0), (3.0, 1.0)])
def test_line_samples_degenerate_is_constant(low, high):
    s = uncertainty.line_samples(lline(value=2.0, low=low, high=high, multiplier=10.0), 50, 1)
    assert s.shape == (50,) and np.all(s == 20.0)


def test_line_samples_within_scaled_bounds():
    s = uncertainty.line_samples(lline(value=1.0, low=0.6, high=1.8, multiplier=50.0), 5000, 7)
    assert s.min() >= 0.6 * 50 and s.max() <= 1.8 * 50
    assert s.mean() == pytest.approx(50 * (0.6 + 1.0 + 1.8) / 3, rel=0.02)   # triangular mean


def test_line_samples_deterministic_per_seed_and_stream():
    ln = lline()
    a = uncertainty.line_samples(ln, 200, 42)
    np.testing.assert_array_equal(a, uncertainty.line_samples(dict(ln), 200, 42))
    assert not np.array_equal(a, uncertainty.line_samples(ln, 200, 43))
    assert not np.array_equal(a, uncertainty.line_samples(dict(ln, key="grind.run"), 200, 42))


def test_stream_key_material_shared_others_per_line():
    assert uncertainty.stream_key({"category": "material", "key": "mat.A36"}) == "material"
    assert uncertainty.stream_key({"category": "material", "key": "mat.A500"}) == "material"
    assert uncertainty.stream_key({"category": "labor", "key": "weld.run"}) == "weld.run"
    assert uncertainty.stream_key({"category": "outside", "key": "out.powder_coat"}) == "out.powder_coat"


def _ranks(x):
    return np.argsort(np.argsort(x))


def test_material_lines_perfectly_rank_correlated_labor_independent():
    a36 = lline("mat.A36", "material", "bom", None, "A36", 0.8, 0.6, 1.1, 120.0)
    a500 = lline("mat.A500", "material", "bom", None, "A500", 1.0, 0.9, 1.6, 15.0)   # different shape
    sa, sb = uncertainty.line_samples(a36, 1000, 3), uncertainty.line_samples(a500, 1000, 3)
    assert np.all(np.diff(sb[np.argsort(sa)]) >= 0)
    assert np.corrcoef(_ranks(sa), _ranks(sb))[0, 1] == pytest.approx(1.0)
    sl = uncertainty.line_samples(lline(), 1000, 3)
    assert abs(np.corrcoef(_ranks(sa), _ranks(sl))[0, 1]) < 0.15


@pytest.mark.parametrize("affects,base", [
    ("setup", 10), ("labor", 50), ("material", 35), ("outside", 10), ("all", 100), ("none", 0),
    (None, 100), ("bogus", 100),   # unknown group falls back to all lines
])
def test_contingency_affects_groups(affects, base):
    g = [dict(id="g1", action="assume", assumption="x", contingency_pct=0.1, affects=affects)]
    (c,) = uncertainty.contingencies(toy_ledger(), g, {})
    assert c["base"] == pytest.approx(base) and c["amount"] == pytest.approx(0.1 * base)
    assert c["source"] == "g1" and c["label"] == "Assumption: x" and c["pct"] == 0.1


def test_contingencies_only_assumed_gaps_with_a_pct_count():
    g = [dict(id="a", action="ask", assumption="x", contingency_pct=0.05, affects="all"),
         dict(id="b", assumption="x", contingency_pct=0.05, affects="all"),          # no action set
         dict(id="c", action="assume", assumption="x", contingency_pct=0.0, affects="all"),
         dict(id="d", action="assume", assumption="x", contingency_pct=None, affects="all"),
         dict(id="e", action="assume", assumption="black", contingency_pct=0.03, affects="outside")]
    out = uncertainty.contingencies(toy_ledger(), g, None)
    assert [c["source"] for c in out] == ["e"] and out[0]["amount"] == pytest.approx(0.3)
    assert uncertainty.contingencies(toy_ledger(), [], {}) == []
    assert uncertainty.contingencies([], g, {})[0]["amount"] == 0


def test_contingencies_material_escalation_rows():
    meta = {"A36": {"escalation_pct": 0.06, "newest_age": 90, "trend_monthly": 0.02},
            "A500": {"escalation_pct": 0.0, "newest_age": 10, "trend_monthly": 0.01},
            "304SS": {"escalation_pct": None, "newest_age": None, "trend_monthly": None},
            "1018": {"escalation_pct": 0.1, "newest_age": 60, "trend_monthly": 0.01}}   # not on this ledger
    gap = [dict(id="finish_color", action="assume", assumption="black", contingency_pct=0.03, affects="outside")]
    out = uncertainty.contingencies(toy_ledger(), gap, meta)
    assert [c["source"] for c in out] == ["finish_color", "escalation_A36", "escalation_1018"]
    a36 = out[1]
    assert a36["base"] == pytest.approx(30.0) and a36["amount"] == pytest.approx(1.8) and a36["pct"] == 0.06
    assert "90 days old" in a36["label"] and "+2.0%/month" in a36["label"]
    assert out[2]["base"] == 0 and out[2]["amount"] == 0


def test_simulate_percentiles_ordered_and_contingency_added_to_p50():
    led = toy_ledger()
    r = uncertainty.simulate(led, [], n=2000, seed=11)
    assert r["p10"] < r["p50"] < r["p90"]
    assert r["band_pct"] >= 0 and r["band_pct"] == pytest.approx((r["p90"] - r["p10"]) / r["p50"])
    assert r["point"] == pytest.approx(100.0) and r["contingency_total"] == 0
    assert r["by_category"] == pytest.approx({"labor": 50, "material": 35, "outside": 10, "purchased": 5})
    r2 = uncertainty.simulate(led, [{"amount": 7.5}, {"amount": 2.5}], n=2000, seed=11)
    assert r2["contingency_total"] == pytest.approx(10.0) and r2["point"] == pytest.approx(110.0)
    assert r2["p50"] == pytest.approx(r["p50"] + 10) and r2["p10"] == pytest.approx(r["p10"] + 10)
    assert r2["p90"] == pytest.approx(r["p90"] + 10)


def test_simulate_wider_lines_widen_band():
    led = toy_ledger()
    wide = [dict(ln, low=ln["value"] * 0.5, high=ln["value"] * 1.5) for ln in led]
    assert uncertainty.simulate(wide, [], n=2000, seed=1)["band_pct"] > \
        uncertainty.simulate(led, [], n=2000, seed=1)["band_pct"]


def test_simulate_deterministic_with_default_sample_count():
    a = uncertainty.simulate(toy_ledger(), [], seed=5)
    assert a == uncertainty.simulate(toy_ledger(), [], seed=5)
    assert a["n"] == config.MC_SAMPLES and len(a["samples"]) <= 1000


def test_simulate_degenerate_and_empty_ledgers():
    led = [lline(value=1.0, low=1.0, high=1.0, multiplier=10.0)]
    r = uncertainty.simulate(led, [{"amount": 1.0}], n=500, seed=1)
    assert r["p10"] == r["p50"] == r["p90"] == pytest.approx(11.0) and r["band_pct"] == 0
    empty = uncertainty.simulate([], [], n=100, seed=1)
    assert empty["p50"] == 0 and empty["band_pct"] == 0.0 and empty["point"] == 0.0


# ================================================================ pricing: load curves
@pytest.mark.parametrize("fn,table", [
    (pricing.min_margin, config.MIN_MARGIN_AT_LOAD),
    (pricing.capacity_premium, config.CAPACITY_PREMIUM_AT_LOAD),
])
def test_load_curves_monotonic_and_match_config(fn, table):
    ys = [fn(float(x)) for x in np.linspace(0, 1, 101)]
    assert all(b >= a for a, b in zip(ys, ys[1:]))
    for x, y in table:
        assert fn(x) == pytest.approx(y)
    assert fn(-0.5) == pytest.approx(table[0][1]) and fn(1.7) == pytest.approx(table[-1][1])   # clamped


def test_load_curves_interpolate_linearly():
    assert pricing.min_margin(0.65) == pytest.approx(0.16)          # halfway between (0.5, .10) and (0.8, .22)
    assert pricing.capacity_premium(0.25) == pytest.approx(-0.05)   # halfway between (0, -.10) and (0.5, 0)


# ================================================================ pricing.price_curve
SPEC = {"customer_id": "C02", "segment": "OEM", "qty": 250, "is_new_customer": False}
RISK = {"p50": 100.0, "p90": 110.0, "by_category": {"labor": 60.0}}
GRID = RISK["p50"] * np.linspace(*config.PRICE_GRID[:2], int(config.PRICE_GRID[2]))


@pytest.fixture(scope="module")
def base_curve():
    return pricing.price_curve(SPEC, RISK, 0.5)


def test_price_curve_costs_and_shape(base_curve):
    c = base_curve
    assert len(c["prices"]) == len(c["p_win"]) == len(c["exp_margin"]) == len(GRID)
    assert c["prices"][0] == pytest.approx(GRID[0]) and c["prices"][-1] == pytest.approx(GRID[-1])
    assert c["risk_adj_cost"] == pytest.approx(100 + config.RISK_SHARE * 10)
    assert c["capacity_cost"] == pytest.approx(0.0)       # capacity premium is 0 at 50% load
    assert c["decision_cost"] == pytest.approx(c["risk_adj_cost"])
    assert c["floor_pct"] == pytest.approx(pricing.min_margin(0.5))
    assert c["floor_price"] == pytest.approx(c["risk_adj_cost"] * (1 + c["floor_pct"]))
    pw = c["p_win"]
    assert all(0 <= p <= 1 for p in pw) and all(b <= a for a, b in zip(pw, pw[1:]))   # dearer never wins more


def test_price_curve_recommended_inside_range_inside_grid(base_curve):
    c = base_curve
    lo, hi = c["range"]
    assert GRID[0] - 1e-9 <= lo <= c["recommended"] <= hi <= GRID[-1] + 1e-9
    assert c["recommended"] >= c["floor_price"] and c["rec_exp_margin"] > 0
    assert c["rec_markup"] == pytest.approx(c["recommended"] / RISK["p50"])


def test_price_curve_higher_load_never_lowers_price_and_raises_floor():
    curves = [pricing.price_curve(SPEC, RISK, float(x)) for x in np.linspace(0, 1, 11)]
    recs = [c["recommended"] for c in curves]
    floors = [c["floor_price"] for c in curves]
    assert all(b >= a - 1e-9 for a, b in zip(recs, recs[1:])) and recs[-1] > recs[0]
    assert all(b > a for a, b in zip(floors, floors[1:]))
    assert all(b >= a for a, b in zip([c["capacity_cost"] for c in curves], [c["capacity_cost"] for c in curves][1:]))
    for c in curves:
        lo, hi = c["range"]
        assert lo <= c["recommended"] <= hi and c["recommended"] >= c["floor_price"]


def test_price_curve_wider_p90_never_lowers_price():
    curves = [pricing.price_curve(SPEC, dict(RISK, p90=p90), 0.5) for p90 in (100, 105, 110, 120, 135, 150, 160)]
    recs = [c["recommended"] for c in curves]
    racs = [c["risk_adj_cost"] for c in curves]
    assert all(b >= a - 1e-9 for a, b in zip(recs, recs[1:])) and recs[-1] > recs[0]
    assert all(b > a for a, b in zip(racs, racs[1:]))


def test_price_curve_binding_floor_recommends_first_grid_price_above_it():
    # no labor, no uncertainty, full shop: floor = 1.35 x P50 sits above the unconstrained optimum
    c = pricing.price_curve(SPEC, {"p50": 100.0, "p90": 100.0, "by_category": {}}, 1.0)
    assert c["floor_binding"] is True and c["capacity_cost"] == 0
    assert c["recommended"] == pytest.approx(GRID[GRID >= c["floor_price"] - 1e-9].min())


@pytest.mark.parametrize("p90,load", [(170.0, 1.0), (250.0, 0.5)])
def test_price_curve_floor_above_grid_does_not_crash(p90, load):
    c = pricing.price_curve(SPEC, dict(RISK, p90=p90), load)
    assert c["floor_price"] > GRID[-1]   # precondition: the floor is off the grid
    lo, hi = c["range"]
    assert lo <= c["recommended"] <= hi and c["floor_binding"]


def test_price_curve_recommendation_not_below_floor_when_floor_off_grid():
    c = pricing.price_curve(SPEC, dict(RISK, p90=400.0), 0.5)
    assert c["floor_price"] > GRID[-1]
    assert c["recommended"] >= c["floor_price"]


# ================================================================ pricing.gate2_check / expedite / price_at_lot
def test_gate2_check():
    curve = {"range": (110.0, 130.0)}
    assert pricing.gate2_check(None, curve) == {"status": "pending", "in_range": None}
    for p in (110.0, 120.0, 130.0, 109.996, 130.004):   # half-cent tolerance at the edges
        assert pricing.gate2_check(p, curve) == {"status": "ok", "in_range": True}, p
    for p in (109.99, 130.01, 0.0, 1e6):
        assert pricing.gate2_check(p, curve) == {"status": "needs_reason", "in_range": False}, p


@pytest.mark.parametrize("lead", [40, 20, 12, 10, 5, 0])
def test_expedite(lead):
    e = pricing.expedite(200.0, lead)
    assert e["price"] == pytest.approx(200.0 * (1 + config.EXPEDITE_PRICE_PCT))
    assert e["lead_days"] == max(5, lead - config.EXPEDITE_DAYS_SAVED) and e["lead_days"] >= 5
    assert e["pct"] == config.EXPEDITE_PRICE_PCT and e["days_saved"] == config.EXPEDITE_DAYS_SAVED


def test_expedite_long_lead_saves_a_full_week():
    assert pricing.expedite(100.0, 30)["lead_days"] == 30 - config.EXPEDITE_DAYS_SAVED


def test_price_at_lot_respreads_setup_but_not_fixture():
    led = [dict(kind="routing", hour_type="setup", work_center="laser", cost=10.0),
           dict(kind="routing", hour_type="setup", work_center="fixture", cost=4.0),
           dict(kind="routing", hour_type="run", work_center="weld", cost=20.0),
           dict(kind="bom", hour_type=None, work_center=None, cost=6.0)]
    spec = {"qty": 250, "lot_qty": 50}
    assert pricing.price_at_lot(led, 1.0, 50, 1.0, spec) == pytest.approx(41.0)
    assert pricing.price_at_lot(led, 1.0, 100, 1.0, spec) == pytest.approx(36.0)     # laser setup halves
    assert pricing.price_at_lot(led, 1.0, 50, 1.3, spec) == pytest.approx(41.0 * 1.3)
    assert pricing.price_at_lot(led, 0.0, 0, 1.0, {"qty": 1}) == pytest.approx(40.0)  # lot clamped to >= 1


# ================================================================ gaps: lead time, actions, email
def test_min_lead_days_zero_hours_is_the_fixed_lead():
    assert gaps.min_lead_days(0, False) == gaps.MATERIAL_LEAD_DAYS + gaps.QUEUE_DAYS


def test_min_lead_days_rounds_up_work_days_and_adds_weekends():
    base = gaps.MATERIAL_LEAD_DAYS + gaps.QUEUE_DAYS
    assert gaps.min_lead_days(0.1, False) == base + 2                        # 1 work day -> ceil(7/5)
    assert gaps.min_lead_days(gaps.HOURS_PER_DAY, False) == base + 2
    assert gaps.min_lead_days(5 * gaps.HOURS_PER_DAY, False) == base + 7     # a work week is a calendar week


def test_min_lead_days_monotonic_and_outside_adds_coat_days():
    d = [gaps.min_lead_days(float(h), False) for h in np.linspace(0, 300, 301)]
    assert all(b >= a for a, b in zip(d, d[1:]))
    for h in (0, 5.9, 6, 6.1, 60, 250):
        assert gaps.min_lead_days(h, True) - gaps.min_lead_days(h, False) == config.POWDER_COAT_DAYS


def test_apply_actions_ignores_invalid_and_does_not_mutate():
    g = [dict(id="a", action="ask"), dict(id="b", action="ask"), dict(id="c", action="assume"), dict(id="d", action="ask")]
    out = gaps.apply_actions(g, {"a": "assume", "b": "ignore", "c": None, "d": "ASSUME", "zzz": "assume"})
    assert [x["action"] for x in out] == ["assume", "ask", "assume", "ask"]
    assert [x["action"] for x in g] == ["ask", "ask", "assume", "ask"]   # input untouched
    assert out[0] is not g[0]
    assert gaps.apply_actions(g, None) == g and gaps.apply_actions(g, {}) == g
    assert gaps.apply_actions(out, {"a": "ask"})[0]["action"] == "ask"   # toggles back


def test_template_email_numbered_questions_and_greeting():
    e = gaps.template_email("Dana", "CVE-HB-4410 Rev C", ["What color?", "Which qty?", "Due date?"])
    lines = e.splitlines()
    assert lines[0] == "Hi Dana,"
    assert "CVE-HB-4410 Rev C" in e
    assert [ln for ln in lines if ln[:1].isdigit()] == ["1. What color?", "2. Which qty?", "3. Due date?"]
    assert lines[-1] == "Estimating, Boone Creek Fabrication"


def test_template_email_without_questions_has_no_numbered_lines():
    e = gaps.template_email("there", "your part", [])
    assert e.startswith("Hi there,") and not any(ln[:1].isdigit() for ln in e.splitlines())


@pytest.mark.parametrize("text,name", [
    ("From: Dana Whitfield <dwhitfield@example.com>\nSubject: RFQ", "Dana"),
    ("Subject: RFQ 4410\nFrom:   Marcus Lee\n\nHi team", "Marcus"),
    ("From:Dana", "Dana"),
    ("", "there"),
    (None, "there"),
    ("Hi team, please quote 250 pcs.", "there"),
    ("Reply-From: Nope\nHi", "there"),            # only a header at line start counts
])
def test_contact_first_name(text, name):
    assert gaps.contact_first_name(text) == name


def test_contact_first_name_empty_from_header():
    assert gaps.contact_first_name("From:\nSubject: RFQ for brackets") == "there"


# ================================================================ gaps.find_gaps
LABELS = {"customer_name": "Customer", "part_family": "Part family", "material": "Material",
          "thickness_in": "Thickness", "qty": "Quantity", "finish": "Finish", "due_date": "Due date"}


def make_intake(values=None, conflicts=(), low=(), drop=(), **spec):
    vals = dict(customer_name="Cedar Valley Equipment", part_family="hitch_bracket", material="A36",
                thickness_in=0.375, qty=250, finish="powder_coat", due_date=date(2026, 11, 6))
    vals.update(values or {})
    fields = {k: {"value": v, "confidence": "low" if k in low else "high", "label": LABELS[k]}
              for k, v in vals.items() if k not in drop}
    s = dict(vals, finish_color="black")
    s.update(spec)
    return {"fields": fields, "spec": s, "conflicts": list(conflicts)}


def by_id(gs):
    return {g["id"]: g for g in gs}


def test_find_gaps_complete_intake_has_none():
    assert gaps.find_gaps(make_intake()) == []


def test_find_gaps_combined_scenario_order_and_defaults():
    x = make_intake({"qty": None, "due_date": None, "material": None},
                    conflicts=[{"field": "material", "email": "A36", "sheet": "A500"}], finish_color=None)
    g = gaps.find_gaps(x)
    assert [i["id"] for i in g] == ["material_conflict", "missing_qty", "missing_due_date", "finish_color"]
    assert all(i["action"] == "ask" for i in g)


def test_find_gaps_material_conflict():
    x = make_intake(conflicts=[{"field": "material", "email": "A36", "sheet": "A500"}])
    (c,) = gaps.find_gaps(x)
    assert c["id"] == "material_conflict" and c["kind"] == "conflict" and c["field"] == "material"
    assert "email says A36, spec sheet says A500" in c["title"]
    assert c["affects"] == "material" and c["contingency_pct"] == config.GAP_CONTINGENCY["material"]
    assert "A36" in c["assumption"]


def test_find_gaps_conflict_suppresses_missing_gap_for_same_field():
    x = make_intake({"material": None}, conflicts=[{"field": "material", "email": "A36", "sheet": "A500"}])
    assert list(by_id(gaps.find_gaps(x))) == ["material_conflict"]


def test_find_gaps_thickness_and_qty_conflicts():
    x = make_intake(conflicts=[{"field": "thickness_in", "email": 0.375, "sheet": 0.5},
                               {"field": "qty", "email": 250, "sheet": 200}])
    g = by_id(gaps.find_gaps(x))
    th, q = g["thickness_in_conflict"], g["qty_conflict"]
    assert '3/8"' in th["title"] and '1/2"' in th["title"] and th["affects"] == "material"
    assert q["affects"] == "setup" and q["contingency_pct"] == config.GAP_CONTINGENCY["qty_conflict"]
    assert "250" in q["question"] and "200" in q["question"]


def test_find_gaps_ignores_conflicts_on_non_conflict_fields():
    x = make_intake(conflicts=[{"field": "due_date", "email": date(2026, 11, 6), "sheet": date(2026, 11, 20)},
                               {"field": "part_number", "email": "A", "sheet": "B"}])
    assert gaps.find_gaps(x) == []


@pytest.mark.parametrize("field,affects,pct", [
    ("part_family", "all", config.GAP_CONTINGENCY["default"]),
    ("qty", "all", config.GAP_CONTINGENCY["default"]),
    ("material", "material", config.GAP_CONTINGENCY["material"]),
    ("thickness_in", "material", config.GAP_CONTINGENCY["material"]),
    ("finish", "outside", config.GAP_CONTINGENCY["default"]),
    ("due_date", "none", 0.0),
    ("customer_name", "none", 0.0),
])
def test_find_gaps_missing_required_field(field, affects, pct):
    (m,) = gaps.find_gaps(make_intake({field: None}, finish_color="black"))
    assert m["id"] == f"missing_{field}" and m["kind"] == "missing" and m["field"] == field
    assert m["affects"] == affects and m["contingency_pct"] == pct
    assert m["title"] == f"{LABELS[field]} not stated" and m["action"] == "ask"


def test_find_gaps_low_confidence_and_absent_fields():
    g = by_id(gaps.find_gaps(make_intake(low=("qty",), drop=("part_family",))))
    assert set(g) == {"missing_qty", "missing_part_family"}
    assert "low confidence" in g["missing_qty"]["title"]
    assert g["missing_part_family"]["title"] == "part_family not stated"   # no label: falls back to the key


@pytest.mark.parametrize("finish,color,expected", [
    ("powder_coat", None, True), ("powder_coat", "", True), ("powder_coat", "black", False),
    ("zinc", None, False), ("none", None, False),
])
def test_find_gaps_powder_coat_color(finish, color, expected):
    g = by_id(gaps.find_gaps(make_intake({"finish": finish}, finish_color=color)))
    assert ("finish_color" in g) == expected
    if expected:
        fc = g["finish_color"]
        assert fc["affects"] == "outside" and fc["contingency_pct"] == config.GAP_CONTINGENCY["finish_color"]
        assert gaps.STOCK_COLORS in fc["question"]


# ================================================================ triage
BASE = dict(part_family="hitch_bracket", part_number="CVE-HB-4410", qty=40, tolerance_class="standard",
            weldment=True, repeat_part=True, prior_runs=["J-1", "J-2"])


def test_triage_L_beats_S_for_cosmetic_repeat():
    s = triage.triage(BASE)
    assert s["label"] == "S" and s["reason"].startswith("repeat of CVE-HB-4410 (2 prior runs)")
    t = triage.triage(dict(BASE, cosmetic_weld=True), analog_sim=0.99)
    assert t["label"] == "L" and t["track"] == "Full review" and "cosmetic weld" in t["reason"]


def test_triage_L_reasons_accumulate():
    t = triage.triage(dict(BASE, first_run=True, cosmetic_weld=True, revision_change=True))
    assert t["label"] == "L" and len(t["reason"].split("; ")) == 3
    assert "new weldment (hitch bracket, first run)" in t["reason"]
    assert triage.triage(dict(BASE, first_run=True, weldment=False))["reason"] == "first run of this part number"


@pytest.mark.parametrize("qty,label", [(None, "S"), (0, "S"), (50, "S"), (51, "M"), (500, "M")])
def test_triage_qty_boundary(qty, label):
    t = triage.triage(dict(BASE, qty=qty))
    assert t["label"] == label
    if label == "M":
        assert t["reason"] == f"qty {qty} > {triage.FAST_TRACK_MAX_QTY}"


@pytest.mark.parametrize("sim,label", [(None, "M"), (0.5, "M"), (0.8999, "M"), (0.90, "S"), (1.0, "S")])
def test_triage_close_analog_threshold(sim, label):
    t = triage.triage(dict(BASE, repeat_part=False), analog_sim=sim)
    assert t["label"] == label
    if label == "S":
        assert f"similarity {sim:.2f}" in t["reason"]
    else:
        assert "no repeat or very close past job" in t["reason"]


def test_triage_M_lists_every_reason():
    t = triage.triage(dict(BASE, repeat_part=False, tolerance_class="tight", qty=120))
    assert t == {"label": "M", "track": "Standard review",
                 "reason": "no repeat or very close past job; tight tolerance; qty 120 > 50"}


def test_triage_missing_tolerance_is_standard():
    assert triage.triage(dict(BASE, tolerance_class=None))["label"] == "S"
