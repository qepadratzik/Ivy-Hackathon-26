"""Quick demo request: the form values must come back exactly as entered (email rules alone, and with the sheet),
and every combination must run through the whole pipeline."""
import itertools
from datetime import date

import pytest

from qm import intake, pipeline, quick, store


@pytest.fixture(autouse=True)
def mock_provider(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    monkeypatch.setenv("DEMO_MODE", "live")


CUSTOMERS = list(store.base_tables()["customers"].name)
FAMS = list(quick.FAMILY_PHRASE)


def read(rfq, sheet=True):
    r = dict(rfq, customer_spec=rfq["customer_spec"] if sheet else None)
    return intake.extract(r)["spec"]


@pytest.mark.parametrize("customer", CUSTOMERS)
def test_every_customer_is_recognised(customer):
    rfq = quick.quick_rfq(customer, "guard", "A36", "1/4", 80)
    for sheet in (True, False):
        s = read(rfq, sheet)
        assert s["customer_name"] == customer and s["customer_id"] is not None


@pytest.mark.parametrize("fam,mat,weld", itertools.product(FAMS, ["A36", "A500", "5052AL"], ["standard", "cosmetic", "none"]))
def test_email_alone_reads_back_what_was_typed(fam, mat, weld):
    rfq = quick.quick_rfq("Cedar Valley Equipment", fam, mat, "3/16", 120, batch=40, weld=weld, color="gray",
                          due=date(2026, 11, 20))
    for sheet in (False, True):
        s = read(rfq, sheet)
        assert s["part_family"] == fam and s["qty"] == 120 and s["release_qty"] == 40
        assert s["thickness_in"] == 0.1875 and s["finish"] == "powder_coat" and s["finish_color"] == "gray"
        assert s["tolerance_class"] == "standard" and s["due_date"] == date(2026, 11, 20)
        assert s["cosmetic_weld"] == {"standard": False, "cosmetic": True, "none": False}[weld]
        # a tube assembly is priced on its tube; everything else keeps the chosen material
        assert s["material"] == (mat if not (fam == "tube_assembly" and mat == "A36") else "A500")


def test_finish_color_tolerance_and_part_number_variants():
    base = dict(customer="Hawkeye Loader Works", family="frame", material="A36", thickness="1/2", qty=30)
    s = read(quick.quick_rfq(**base, finish="none", tolerance="tight", part_number="HLW-FR-900"))
    assert s["finish"] == "none" and s["tolerance_class"] == "tight" and s["part_number"] == "HLW-FR-900"
    assert s["first_run"] and not s["repeat_part"]
    s = read(quick.quick_rfq(**base, color="not stated"), sheet=True)
    assert s["finish"] == "powder_coat" and s["finish_color"] is None
    s = read(quick.quick_rfq("Loess Hills Machinery", "mounting_plate", "A36", "1/2", 40, part_number="LHM-MP-0620"))
    assert s["repeat_part"] and not s["first_run"]
    s = read(quick.quick_rfq("Cedar Valley Equipment", "hitch_bracket", "A36", "3/8", 250, part_number="CVE-HB-4410 Rev D"))
    assert s["revision_change"]


def test_optional_quantity_conflict_is_caught():
    rfq = quick.quick_rfq("Cedar Valley Equipment", "hitch_bracket", "A36", "3/8", 250, qty_conflict=True)
    x = intake.extract(rfq)
    assert [c["field"] for c in x["conflicts"]] == ["qty"] and x["conflicts"][0]["sheet"] != 250
    res = pipeline.run_pipeline(rfq, {})
    assert "qty_conflict" in [g["id"] for g in res["gaps"]]
    small = quick.quick_rfq("Cedar Valley Equipment", "guard", "A36", "1/8", 2, qty_conflict=True)
    assert intake.extract(small)["conflicts"][0]["sheet"] != 2


def test_missing_color_becomes_a_question():
    res = pipeline.run_pipeline(quick.quick_rfq("Cedar Valley Equipment", "guard", "A36", "1/8", 50, color="not stated"), {})
    assert "finish_color" in [g["id"] for g in res["gaps"]]


@pytest.mark.parametrize("fam,mat", [("hitch_bracket", "A36"), ("guard", "5052AL"), ("frame", "A500"),
                                     ("mounting_plate", "A36"), ("tube_assembly", "A500"), ("guard", "A500")])
def test_every_job_type_runs_end_to_end(fam, mat):
    rfq = quick.quick_rfq("Raccoon River Attachments", fam, mat, "1/4", 60, batch=20, weld="cosmetic")
    res = pipeline.run_pipeline(rfq, {})
    assert quick.is_quick(res["rfq_id"]) and res["risk"]["p50"] > 0 and res["ledger"]
    assert res["quote"]["unit_price"] > 0 or res["insufficient"]


def test_the_email_is_plain_fictional_text():
    rfq = quick.quick_rfq("Big Sioux Trailer", "guard", "A36", "1/4", 10)
    assert ".example" in rfq["email_text"] and "@" in rfq["email_text"] and quick.is_quick(rfq["rfq_id"]) and rfq["rfq_id"] == "RFQ-Q1"
    assert quick.summary(rfq) == 'Big Sioux Trailer: 10 x guard, 1/4" A36 plate'
    conflict = quick.quick_rfq("Big Sioux Trailer", "guard", "A36", "1/4", 100, qty_conflict=True)
    assert "100 x guard" in quick.summary(conflict)           # what the customer emailed, not the spec sheet's number


def test_batch_is_clamped_and_equal_batch_means_one_release():
    assert quick.quick_rfq("Cedar Valley Equipment", "guard", "A36", "1/4", 50, batch=500)["customer_spec"]["release_qty"] is None
    assert quick.quick_rfq("Cedar Valley Equipment", "guard", "A36", "1/4", 50, batch=10)["customer_spec"]["release_qty"] == 10
    assert "releases of" not in quick.quick_rfq("Cedar Valley Equipment", "guard", "A36", "1/4", 50)["email_text"]


@pytest.mark.parametrize("customer", CUSTOMERS)
def test_customer_row_reads_the_signature_not_the_sender_address(customer):
    f = intake.extract(dict(quick.quick_rfq(customer, "guard", "A36", "1/4", 80), customer_spec=None))["fields"]["customer_name"]
    assert f["email_raw"] == customer and "example" not in f["email_raw"] and f["verified"]


@pytest.mark.parametrize("pn,fam,mat,thick", [("LHM-MP-0620", "mounting_plate", "A36", "1/2"),
                                               ("HLW-HB-3300", "hitch_bracket", "A36", "3/8"),
                                               ("CVE-HB-4410 Rev C", "hitch_bracket", "A36", "3/8")])
def test_typing_a_demo_part_number_does_not_trigger_a_canned_reading(pn, fam, mat, thick):
    """The hand-checked readings belong to the three demo emails only, never to a typed part number."""
    rfq = quick.quick_rfq("Loess Hills Machinery", fam, mat, thick, 120, weld="none", color="gray", part_number=pn)
    for sheet in (False, True):
        x = intake.extract(dict(rfq, customer_spec=rfq["customer_spec"] if sheet else None))
        assert x["llm"]["source"] == "fallback" and x["conflicts"] == []
        assert x["spec"]["qty"] == 120 and x["spec"]["finish_color"] == "gray"
        assert all(f["verified"] is not False for f in x["fields"].values())
