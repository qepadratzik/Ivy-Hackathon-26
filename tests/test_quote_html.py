"""The HTML quote download: self-contained, escaped, and honest about draft / not-priced state."""
import re

import pytest

from qm import intake, pipeline, quote_html

R = intake.load_demo_rfqs()


def approved(rid="RFQ-A"):
    st = {"gate1_approved": True, "gate2_approved": True,
          "gap_actions": {g: "assume" for g in ("qty_conflict", "finish_color")}}
    res = pipeline.run_pipeline(R[rid], st)
    st["gate2_price"] = res["pricing"]["recommended"]
    st["gate2_p50"] = res["risk"]["p50"]
    return pipeline.run_pipeline(R[rid], st)


@pytest.mark.parametrize("rid", ["RFQ-A", "RFQ-B", "RFQ-C"])
def test_renders_a_complete_page_for_each_demo_job(rid):
    res = pipeline.run_pipeline(R[rid], {})
    page = quote_html.render(res)
    q = res["quote"]
    assert page.startswith("<!doctype html>") and page.rstrip().endswith("</html>")
    assert f"${q['unit_price']:,.2f}" in page and res["spec"]["part_number"] in page
    assert "Boone Creek Fabrication" in page and "Price by release size" in page and "Exclusions" in page
    assert "Draft, not released" in page            # nothing approved yet


def test_approved_quote_has_no_draft_banner_and_lists_assumptions():
    res = approved()
    assert res["quote"]["ready"]
    page = quote_html.render(res)
    assert "Draft, not released" not in page and "Not priced" not in page
    assert "Assumptions" in page and "Assumed black" in page and "Waiting on the customer" not in page
    assert f"{res['quote']['validity_days']} days" in page and "as requested" in page


def test_pending_questions_are_listed():
    page = quote_html.render(pipeline.run_pipeline(R["RFQ-A"], {}))
    assert "Waiting on the customer" in page and "Quantity conflict" in page


def test_not_priced_banner():
    res = pipeline.run_pipeline(R["RFQ-A"], {})
    res["insufficient"] = ["no past job is similar enough"]
    assert "Not priced" in quote_html.render(res)


def test_everything_is_escaped_and_self_contained():
    res = pipeline.run_pipeline(R["RFQ-A"], {})
    res["quote"]["customer"] = "<script>alert(1)</script> & Co"
    res["quote"]["assumptions"] = ["<img src=x onerror=alert(1)>"]
    page = quote_html.render(res)
    assert "<script>" not in page and "<img" not in page and "&lt;script&gt;" in page
    assert not re.search(r"https?://|<link|<script|@import|url\(", page)      # nothing loaded from outside
