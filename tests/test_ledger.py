"""Phases 4-6 acceptance: evidence engine (incl. the HANDOFF 7.4 worked example), ledger, patterns,
uncertainty, pricing, and the override -> memory -> next-RFQ loop."""
import pytest

from qm import config, evidence, intake, memory, pipeline, pricing, store

R = intake.load_demo_rfqs()


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    monkeypatch.setenv("DEMO_MODE", "live")
    monkeypatch.setattr(config, "MEMORY_DIR", tmp_path / "memory")
    monkeypatch.setattr(config, "SQLITE_PATH", tmp_path / "qm.sqlite")
    store.vector_store().sync_memory()
    yield
    store.vector_store().sync_memory()


def line(res, key):
    return next(l for l in res["ledger"] if l["key"] == key)


# ---------------------------------------------------------------- 7.4 worked example
def test_worked_example_matches_handoff():
    rows = [dict(value=v, score=s, counted=True) for v, s in
            [(0.62, 0.71), (0.58, 0.54), (0.45, 0.47), (0.40, 0.30)]]
    s = evidence.summarize(rows)
    assert s["value"] == pytest.approx(0.537, abs=0.001)
    assert s["cv"] == pytest.approx(0.16, abs=0.005)
    assert s["confidence"] == pytest.approx(0.56, abs=0.01)
    assert s["low"] == pytest.approx(0.39, abs=0.005) and s["high"] == pytest.approx(0.69, abs=0.01)
    assert evidence.chip(s["confidence"]) == "yellow"


def test_make_row_score_and_threshold():
    r = evidence.make_row("actual", "J-1", 1.0, 0.9, age_days=540, half_life_key="labor")
    assert r["decay"] == pytest.approx(0.5) and r["score"] == pytest.approx(0.45)
    low = evidence.make_row("actual", "J-2", 1.0, 0.30)
    assert low["score"] == 0 and not low["counted"] and "below" in low["note"]
    d = evidence.make_row("shop_default", "Shop", 2.0, 1.0)
    assert d["score"] == pytest.approx(0.3) and d["decay"] == 1.0


def test_summarize_edge_cases():
    none = evidence.summarize([])
    assert none["value"] is None and none["confidence"] == 0 and none["spread"] == config.SPREAD_MAX
    one = evidence.summarize([dict(value=5.0, score=0.3, counted=True)])
    assert one["value"] == 5.0 and one["cv"] == 0 and one["confidence"] == pytest.approx(0.1)
    conflict = evidence.summarize([dict(value=1.0, score=1.5, counted=True), dict(value=10.0, score=1.5, counted=True)])
    assert conflict["confidence"] < 0.4 and conflict["spread"] <= config.SPREAD_MAX
    forced = evidence.summarize([dict(value=2.0, score=3.0, counted=True)], forced_value=8.0)
    assert forced["value"] == 8.0 and forced["confidence"] < 0.4   # override far from all evidence


# ---------------------------------------------------------------- Phase 4
def test_rfq_a_ledger_complete_and_p1_on_weld():
    res = pipeline.run_pipeline(R["RFQ-A"], {})
    assert res["analog"]["job_id"] == "J-1042"
    assert len(res["ledger"]) >= 15
    for l in res["ledger"]:
        assert l["value"] is not None and l["low"] <= l["value"] <= l["high"]
        assert 0 <= l["confidence"] <= 1 and l["chip"] in ("green", "yellow", "red")
        assert l["evidence"] and all("why" in e and "score" in e for e in l["evidence"])
    weld = line(res, "weld.run")
    assert "P1" in weld["patterns"]
    assert any(e["source_type"] == "pattern" and e["ref"] == "P1" for e in weld["evidence"])
    assert [p["id"] for p in res["patterns"]] == ["P1"]
    assert line(res, "mat.A36")["chip"] == "green" and not line(res, "mat.A36")["warnings"]


def test_aging_material_drops_confidence_and_flags():
    fresh = pipeline.run_pipeline(R["RFQ-A"], {})
    old = pipeline.run_pipeline(R["RFQ-A"], {"material_age_days": 90})
    a, b = line(fresh, "mat.A36"), line(old, "mat.A36")
    assert b["chip"] in ("red", "yellow") and b["confidence"] < a["confidence"] - 0.3
    assert b["high"] - b["low"] > a["high"] - a["low"]
    assert any("re-quote material or shorten quote validity to 15 days" in w for w in b["warnings"])
    assert old["validity_days"] == 15 and fresh["validity_days"] == 30
    assert old["risk"]["band_pct"] > fresh["risk"]["band_pct"]
    assert old["pricing"]["recommended"] > fresh["pricing"]["recommended"]
    d = pipeline.diff(fresh, old)
    assert d and any(c["key"] == "mat.A36" for c in d["changed_lines"]) and "validity" in d["text"]


def test_rfq_b_first_run_fixture_and_p2():
    res = pipeline.run_pipeline(R["RFQ-B"], {})
    assert res["analog"]["job_id"] == "J-1103"
    assert any(l["key"] == "fixture.setup" for l in res["ledger"])
    assert "P2" in line(res, "fit_tack.setup")["patterns"]


def test_rfq_c_fast_track_high_confidence():
    res = pipeline.run_pipeline(R["RFQ-C"], {})
    assert res["triage"]["label"] == "S" and res["analog"]["job_id"] == "J-1118"
    assert all(l["chip"] == "green" for l in res["ledger"])
    assert not res["gaps"] and res["email"] is None


def test_notes_gated_by_driver():
    res = pipeline.run_pipeline(R["RFQ-B"], {})   # standard weld: cosmetic overrun notes must not count
    weld = line(res, "weld.run")
    assert not any(e["source_type"] == "note" and e["counted"] and "cosmetic" in (e["text"] or "").lower()
                   for e in weld["evidence"])


# ---------------------------------------------------------------- Phase 5
def test_uncertainty_ordering_and_contingency():
    res = pipeline.run_pipeline(R["RFQ-A"], {})
    r = res["risk"]
    assert r["p10"] < r["p50"] < r["p90"] and 0.02 < r["band_pct"] < 0.5
    res2 = pipeline.run_pipeline(R["RFQ-A"], {"gap_actions": {"finish_color": "assume"}})
    assert res2["risk"]["contingency_total"] > 0 and res2["risk"]["p50"] > r["p50"]
    assert res2["email"] and "color" not in res2["email"].lower()


def test_prairie_gets_lower_markup_than_others():
    res = pipeline.run_pipeline(R["RFQ-A"], {})
    risk = res["risk"]
    marks = {}
    for cid, seg in [("C01", "OEM"), ("C02", "OEM"), ("C03", "OEM"), ("C04", "tier1"), ("C07", "aftermarket")]:
        spec = dict(res["spec"], customer_id=cid, segment=seg)
        marks[cid] = pricing.price_curve(spec, risk, 0.5)["rec_markup"]
    assert marks["C01"] == min(marks.values()) and marks["C01"] < marks["C02"] - 0.05


def test_capacity_slider_moves_recommendation():
    lo = pipeline.run_pipeline(R["RFQ-A"], {"capacity": 0.2})["pricing"]
    hi = pipeline.run_pipeline(R["RFQ-A"], {"capacity": 0.95})["pricing"]
    assert hi["recommended"] > lo["recommended"] and hi["floor_price"] > lo["floor_price"]
    lo_r, hi_r = lo["range"], hi["range"]
    assert lo_r[0] <= lo["recommended"] <= lo_r[1]


def test_gate2_out_of_range_needs_reason_and_expedite():
    res = pipeline.run_pipeline(R["RFQ-A"], {})
    lo, hi = res["pricing"]["range"]
    assert pipeline.run_pipeline(R["RFQ-A"], {"gate2_price": (lo + hi) / 2})["gate2"]["status"] == "ok"
    assert pipeline.run_pipeline(R["RFQ-A"], {"gate2_price": hi * 1.2})["gate2"]["status"] == "needs_reason"
    ex = pipeline.run_pipeline(R["RFQ-A"], {"expedite": True})
    assert ex["chosen_price"] > res["pricing"]["recommended"] and ex["quote"]["lead_days"] < res["lead_days"]


def test_gate1_override_is_locked_and_flows_to_price():
    base = pipeline.run_pipeline(R["RFQ-A"], {})
    old = line(base, "fit_tack.setup")["proposed"]
    res = pipeline.run_pipeline(R["RFQ-A"], {"gate1_edits": {"fit_tack.setup": {"value": old + 6, "reason": "new fixture needed"}}})
    ft = line(res, "fit_tack.setup")
    assert ft["overridden"] and ft["value"] == pytest.approx(old + 6)
    assert ft["evidence"][0]["ref"] == "This quote (Gate 1)"
    assert res["risk"]["p50"] > base["risk"]["p50"] and res["pricing"]["recommended"] > base["pricing"]["recommended"]


def test_quote_breaks_and_draft_state():
    res = pipeline.run_pipeline(R["RFQ-A"], {})
    q = res["quote"]
    lots = [b["lot"] for b in q["breaks"]]
    assert 50 in lots and 250 in lots and 200 in lots
    prices = {b["lot"]: b["unit_price"] for b in q["breaks"]}
    assert prices[50] > prices[250]
    assert not q["ready"] and q["pending"]
    md = pipeline.quote_markdown(res)
    assert "DRAFT" in md and "CVE-HB-4410 Rev C" in md


# ---------------------------------------------------------------- Phase 6
def test_override_on_a_surfaces_on_b_and_reset_removes_it():
    before = line(pipeline.run_pipeline(R["RFQ-B"], {}), "fit_tack.setup")
    assert not any(e["source_type"] == "override" for e in before["evidence"])
    a = pipeline.run_pipeline(R["RFQ-A"], {})
    old = line(a, "fit_tack.setup")["proposed"]
    memory.record_line_override("RFQ-A", a["spec"], "fit_tack.setup", "Fit & tack: setup (hr/lot)", "fit_tack",
                                old, old + 6, "new fixture needed")
    after = line(pipeline.run_pipeline(R["RFQ-B"], {}), "fit_tack.setup")
    ov = [e for e in after["evidence"] if e["source_type"] == "override"]
    assert ov and ov[0]["counted"] and "new fixture needed" in ov[0]["text"] and ov[0]["authority"] == 0.8
    assert after["value"] > before["value"]
    c = line(pipeline.run_pipeline(R["RFQ-C"], {}), "inspect_pack.setup")   # unrelated line/RFQ unaffected
    assert not any(e["source_type"] == "override" for e in c["evidence"])
    assert memory.reset_memory() == 1
    again = line(pipeline.run_pipeline(R["RFQ-B"], {}), "fit_tack.setup")
    assert not any(e["source_type"] == "override" for e in again["evidence"])
    assert again["value"] == pytest.approx(before["value"])


def test_remove_for_rfq_replaces_previous_gate1_rows():
    a = pipeline.run_pipeline(R["RFQ-A"], {})
    memory.record_line_override("RFQ-A", a["spec"], "weld.run", "Weld: run", "weld", 0.6, 0.7, "x")
    memory.record_decision("RFQ-A", a["spec"], "gate2_price", "Manager priced above range: strategic account")
    assert memory.remove_for_rfq("RFQ-A") == 1
    assert len(memory.list_memory()) == 1


@pytest.mark.parametrize("text", ["", "asdf qwerty", "Please quote a guard in aluminum, 60 pcs, powder coat red. "
                                                   "Need by Nov 20.\nThanks, Pat\nBig Sioux Trailer"])
def test_thin_or_nonsense_pastes_still_give_sane_numbers(text):
    res = pipeline.run_pipeline(intake.pasted_rfq(text), {})
    s = res["spec"]
    assert s["qty"] and s["lot_qty"] and s["material"] and s["part_family"]
    assert 5 < res["risk"]["p50"] < 2000 and res["pricing"]["recommended"] > res["risk"]["p50"]
    for f in s["assumed_from_analog"]:
        assert f"missing_{f}" in [g["id"] for g in res["gaps"]]
    if "aluminum" in text:
        assert s["material"] == "5052AL" and s["part_family"] == "guard" and s["qty"] == 60
