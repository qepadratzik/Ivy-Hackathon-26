"""Phase 3 gate: intake + gaps + triage on the demo RFQs, normalization, anti-hallucination guard."""
import json
from datetime import date

import pytest

from qm import config, gaps, intake, llm, triage

RFQS = intake.load_demo_rfqs()


@pytest.fixture(autouse=True)
def mock_provider(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    monkeypatch.setenv("DEMO_MODE", "live")


@pytest.mark.parametrize("rid", ["RFQ-A", "RFQ-B", "RFQ-C"])
def test_demo_rfqs_expected_gaps_and_triage(rid):
    r = RFQS[rid]
    x = intake.extract(r)
    g = gaps.find_gaps(x)
    assert sorted(i["id"] for i in g) == sorted(r["expected"]["gaps"])
    assert all(i["action"] == "ask" for i in g)
    assert triage.triage(x["spec"])["label"] == r["expected"]["triage"]


def test_rfq_a_details():
    x = intake.extract(RFQS["RFQ-A"])
    s = x["spec"]
    assert (s["material"], s["thickness_in"]) == ("A36", 0.375)      # "3/8 plate" vs "0.375 A-36 HR": no conflict
    assert s["qty"] == 250 and s["lot_qty"] == 50 and s["cosmetic_weld"] is True
    assert s["finish"] == "powder_coat" and s["finish_color"] is None
    assert s["due_date"] == date(2026, 11, 6) and s["customer_id"] == "C02"
    assert s["repeat_part"] and s["revision_change"] and not s["first_run"]
    assert [c["field"] for c in x["conflicts"]] == ["qty"]
    assert x["fields"]["material"]["origin"] == "email + spec sheet"


def test_rfq_b_is_first_run_and_c_is_repeat():
    b = intake.extract(RFQS["RFQ-B"])["spec"]
    c = intake.extract(RFQS["RFQ-C"])["spec"]
    assert b["first_run"] and not b["repeat_part"] and b["cosmetic_weld"] is False
    assert c["repeat_part"] and c["prior_runs"] == ["J-0842", "J-0955", "J-1118"]


def test_fixture_source_quotes_are_verbatim():
    for rid, r in RFQS.items():
        fx = json.loads((config.FIXTURE_DIR / f"intake_extract__RFQ_{rid[-1]}.json").read_text())
        body = intake._norm_ws(r["email_text"])
        for name, f in fx["output"].items():
            if f["value"] is not None:
                assert intake._norm_ws(f["source_quote"]) in body, (rid, name)


def test_hallucinated_quote_is_downgraded():
    fake = {k: {"value": None, "confidence": "low", "source_quote": None} for k in intake.RFQSpec.model_fields}
    fake["qty"] = {"value": "999", "confidence": "high", "source_quote": "Quantity is 999 pcs"}
    fake["material"] = {"value": "A36", "confidence": "high", "source_quote": "3/8\" A36 plate"}
    out = intake.verify_quotes(fake, RFQS["RFQ-A"]["email_text"])
    assert out["qty"]["confidence"] == "low" and out["qty"]["verified"] is False
    assert out["material"]["verified"] is True and out["material"]["confidence"] == "high"


def test_low_confidence_required_field_becomes_gap(monkeypatch):
    r = dict(RFQS["RFQ-C"], customer_spec=None)
    bad = json.loads((config.FIXTURE_DIR / "intake_extract__RFQ_C.json").read_text())["output"]
    bad["qty"] = {"value": "400", "confidence": "high", "source_quote": "Qty 400."}   # not in the email
    monkeypatch.setattr(llm, "_fixture_for", lambda task, prompt: {"output": bad})
    x = intake.extract(r)
    assert "missing_qty" in [g["id"] for g in gaps.find_gaps(x)]


def test_rule_extract_fallback_reads_rfq_a():
    r = RFQS["RFQ-A"]
    x = intake.extract(dict(r, customer_spec=None, email_text=r["email_text"].replace("CVE-HB-4410", "XYZ-HB-1")))
    s = x["spec"]
    assert x["llm"]["source"] == "fallback"
    assert (s["qty"], s["release_qty"], s["material"], s["thickness_in"]) == (250, 50, "A36", 0.375)
    assert s["cosmetic_weld"] is True and s["finish"] == "powder_coat" and s["due_date"] == date(2026, 11, 6)


@pytest.mark.parametrize("raw,code", [("A36", "A36"), ("A-36 HR", "A36"), ("HR A36", "A36"), ("ASTM A36 plate", "A36"),
                                      ("0.375 A-36 HR", "A36"), ('3/8" A36 plate', "A36"), ("A500 Gr B", "A500"),
                                      ("HSS A500", "A500"), ("5052-H32", "5052AL"),
                                      ("304 stainless", None), ("C1018 CF bar", None), ("unobtainium", None)])
def test_material_aliases(raw, code):
    assert intake.normalize_material(raw) == code


@pytest.mark.parametrize("raw,val", [('3/8"', 0.375), ("0.375", 0.375), ("1/2 A36", 0.5), ("12 ga", 0.105),
                                     (".25", 0.25), (None, None), ("thick", None)])
def test_thickness(raw, val):
    assert intake.parse_thickness(raw) == val


def test_dates():
    rec = date(2026, 9, 29)
    assert intake.parse_date("Nov 6", rec) == date(2026, 11, 6)
    assert intake.parse_date("11/06/2026", rec) == date(2026, 11, 6)
    assert intake.parse_date("2026-11-06", rec) == date(2026, 11, 6)
    assert intake.parse_date("Jan 5", rec) == date(2027, 1, 5)
    assert intake.parse_date("4 weeks ARO", rec) == date(2026, 10, 27)


def test_triage_rules():
    base = dict(part_family="mounting_plate", qty=40, tolerance_class="standard", weldment=False)
    assert triage.triage(dict(base, repeat_part=True))["label"] == "S"
    assert triage.triage(dict(base, repeat_part=True, qty=51))["label"] == "M"
    assert triage.triage(dict(base, repeat_part=False), analog_sim=0.95)["label"] == "S"
    assert triage.triage(dict(base, repeat_part=True, tolerance_class="tight"))["label"] == "M"
    assert triage.triage(dict(base, repeat_part=True, cosmetic_weld=True))["label"] == "L"
    assert triage.triage(dict(base, first_run=True, weldment=True))["label"] == "L"


def test_ask_assume_toggle_and_email():
    x = intake.extract(RFQS["RFQ-A"])
    g = gaps.apply_actions(gaps.find_gaps(x), {"finish_color": "assume"})
    email, _ = gaps.clarification_email(g, x["spec"], RFQS["RFQ-A"]["email_text"])
    assert "color" not in email.lower() and "250" in email and email.startswith("Hi Dana")
    g2 = gaps.apply_actions(g, {"qty_conflict": "assume"})
    assert gaps.clarification_email(g2, x["spec"], "")[0] is None


def test_due_date_check():
    spec = {"due_date": date(2026, 11, 6), "received_date": date(2026, 9, 29)}
    risk, info = gaps.due_date_check(spec, 60, True)
    assert risk is None and info["slack_days"] >= 0
    risk, info = gaps.due_date_check(spec, 200, True)
    assert risk["id"] == "due_date_risk" and info["slack_days"] < 0


def test_intake_live_result_is_cached(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("QM_CACHE_DIR", str(tmp_path))
    fx = json.loads((config.FIXTURE_DIR / "intake_extract__RFQ_C.json").read_text())["output"]

    class R:
        status_code, text = 200, ""
        def json(self): return {"message": {"content": json.dumps(fx)}}
        def raise_for_status(self): pass

    calls = []
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: calls.append(1) or R())
    a = intake.extract(RFQS["RFQ-C"])
    b = intake.extract(RFQS["RFQ-C"])
    assert a["llm"]["source"] == "live" and b["llm"]["source"] == "cache" and len(calls) == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_paraphrased_quote_is_accepted_at_medium():
    fake = {k: {"value": None, "confidence": "low", "source_quote": None} for k in intake.RFQSpec.model_fields}
    fake["finish"] = {"value": "powder coat", "confidence": "high", "source_quote": "finish is powder coat, per our usual"}
    fake["qty"] = {"value": "250", "confidence": "high", "source_quote": "quantity is 250 pcs total."}
    out = intake.verify_quotes(fake, RFQS["RFQ-A"]["email_text"])
    assert out["finish"]["verified"] and out["finish"]["confidence"] == "medium"
    assert out["qty"]["verified"] and out["qty"]["confidence"] == "high"      # exact after trimming the period


def test_rule_extract_finds_thickness_after_the_material_words_but_not_a_tolerance():
    e = ("From: a@b.example\nSubject: RFQ\n\nPlease quote 80 pcs of a guard, 5052 aluminum sheet 0.125 in, "
         "powder coat black, standard tolerance +/-0.030 in.")
    out = intake.rule_extract(e)
    assert intake.parse_thickness(out["thickness_in"]["value"]) == 0.125
    e2 = "From: a@b.example\nSubject: RFQ\n\nPlease quote 10 pcs of a guard. Tolerance +/-0.030 in."
    assert intake.rule_extract(e2)["thickness_in"]["value"] is None


def test_zero_or_negative_quantity_counts_as_not_stated():
    assert intake.normalize_field("qty", "0", None) is None and intake.normalize_field("release_qty", "0 pcs", None) is None
    assert intake.normalize_field("qty", "250 pcs", None) == 250
