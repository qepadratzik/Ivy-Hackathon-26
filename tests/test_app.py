"""Phase 7 gate: headless Streamlit AppTest runs the full demo path Job 1 -> (estimator note) -> Job 2 -> Job 3
through the real widgets, with no exceptions."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from qm import config, memory, store

APP = str(Path(__file__).resolve().parent.parent / "app.py")
S = ["1 · Read the request", "2 · Plan the work", "3 · Cost it", "4 · Set the price", "5 · Send the quote"]
ASSUME = "Assume and quote"
FIX_NO = "No, we need to build a new one"


@pytest.fixture(autouse=True)
def isolated_memory(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    monkeypatch.setenv("DEMO_MODE", "live")
    monkeypatch.setattr(config, "MEMORY_DIR", tmp_path / "memory")
    monkeypatch.setattr(config, "SQLITE_PATH", tmp_path / "qm.sqlite")
    store.vector_store().sync_memory()
    yield
    store.vector_store().sync_memory()


def ok(at):
    assert not at.exception, [e.value for e in at.exception]
    return at


def text_of(at) -> str:
    return "\n".join(str(m.value) for m in at.markdown) + "\n".join(str(c.value) for c in at.caption)


def go(at, step):
    at.radio(key="step").set_value(step)
    return ok(at.run())


def approve_plan(at):
    go(at, S[1])
    at.button(key="g1_approve_RFQ-A").click()
    ok(at.run())
    assert any("Checkpoint 1 approved" in str(s.value) for s in at.success)


def test_full_demo_path():
    at = ok(AppTest.from_file(APP, default_timeout=180).run())
    assert "Cedar Valley" in text_of(at) and "Full review" in text_of(at)

    # Beat 1: a missing detail -> assume black, the banner says what changed
    at.radio(key="gap_RFQ-A_finish_color").set_value(ASSUME)
    ok(at.run())
    assert "What just changed" in text_of(at)

    # Beat 2: Checkpoint 1: the old fixture will not fit -> 6 hours, a reason is required
    go(at, S[1])
    assert at.radio(key="fixture_RFQ-A").value == "Yes, the old fixture still fits"
    at.radio(key="fixture_RFQ-A").set_value(FIX_NO)
    ok(at.run())
    assert at.number_input(key="fixture_hr_RFQ-A").value == config.FIXTURE_DEFAULT_HR
    at.button(key="g1_approve_RFQ-A").click()          # no reason yet -> blocked
    ok(at.run())
    assert any("reason" in str(e.value).lower() for e in at.error)
    at.text_input(key="g1_reason_RFQ-A").set_value("new fixture needed")
    at.button(key="g1_approve_RFQ-A").click()
    ok(at.run())
    mem = memory.list_memory()
    assert len(mem) == 1 and mem.iloc[0].line_key == "fixture.setup" and mem.iloc[0].new_value == 6.0
    assert "Checkpoint 1 approved" in "\n".join(str(s.value) for s in at.success)

    # Re-opening keeps the estimator's answer
    at.button(key="g1_reopen_RFQ-A").click()
    ok(at.run())
    assert at.radio(key="fixture_RFQ-A").value == FIX_NO
    at.button(key="g1_approve_RFQ-A").click()
    ok(at.run())
    assert len(memory.list_memory()) == 1 and "Checkpoint 1 approved" in "\n".join(str(s.value) for s in at.success)

    # Beat 3: cost table + "why we believe it" on the weld line, with the lesson from past jobs
    go(at, S[2])
    at.selectbox(key="drawer_RFQ-A").set_value("weld.run")
    ok(at.run())
    assert any("longer than quoted" in str(i.value) for i in at.info)

    # Beat 4: steel quote gets old -> banner with a shorter validity
    at.slider(key="mat_age").set_value(90)
    ok(at.run())
    assert "days older" in text_of(at) and "Quote good for" in text_of(at)

    # Beat 5: resolve the quantity question, approve the price, quote is ready
    go(at, S[0])
    at.radio(key="gap_RFQ-A_qty_conflict").set_value(ASSUME)
    ok(at.run())
    go(at, S[3])
    at.button(key="g2_approve_RFQ-A").click()
    ok(at.run())
    assert any("Checkpoint 2 approved" in str(s.value) for s in at.success)
    go(at, S[4])
    assert any("Ready to send" in str(s.value) for s in at.success)

    # Beat 6: Job 2 sees Job 1's note as evidence on the fixture line
    at.radio(key="rfq_pick").set_value("RFQ-B")
    go(at, S[2])
    at.selectbox(key="drawer_RFQ-B").set_value("fixture.setup")
    ok(at.run())
    frames = [d.value for d in at.dataframe]
    assert any("Estimator note" in f.to_string() and "M-0001" in f.to_string() for f in frames)
    assert "shop notebook now holds" in text_of(at)

    # Beat 7: Job 3 is a fast-track repeat
    at.radio(key="rfq_pick").set_value("RFQ-C")
    go(at, S[0])
    assert "Fast track" in text_of(at)
    for sec in S:
        go(at, sec)

    # Start over clears the notebook AND regenerates every widget (fresh defaults in the browser)
    at.button(key="reset").click()
    ok(at.run())
    assert memory.list_memory().empty
    assert at.radio(key="rfq_pick~1").value == "RFQ-A" and at.slider(key="mat_age~1").value == 0
    assert at.radio(key="gap_RFQ-A_finish_color~1").value == "Ask the customer"
    at.radio(key="gap_RFQ-A_finish_color~1").set_value(ASSUME)
    ok(at.run())
    assert "What just changed" in text_of(at)


def test_paste_box_and_every_step_for_each_job():
    at = ok(AppTest.from_file(APP, default_timeout=180).run())
    for rid in ["RFQ-B", "RFQ-C", "RFQ-A"]:
        at.radio(key="rfq_pick").set_value(rid)
        for sec in S:
            go(at, sec)
    at.radio(key="rfq_pick").set_value("PASTE")
    ok(at.run())
    at.text_area(key="paste_text").set_value(
        "From: Pat Doe <pat@acme.example>\nSubject: RFQ\n\nPlease quote 60 pcs of a guard, 12 ga A36 sheet, "
        "powder coat orange, standard tolerance. Need by Nov 20.\nThanks, Pat\nBig Sioux Trailer")
    at.button(key="paste_go").click()
    ok(at.run())
    for sec in S:
        go(at, sec)


def test_details_switch_shows_the_technical_views():
    at = ok(AppTest.from_file(APP, default_timeout=180).run())
    go(at, S[2])
    assert not at.get("plotly_chart")
    at.toggle(key="details").set_value(True)
    ok(at.run())
    assert len(at.get("plotly_chart")) == 2
    for rid in ["RFQ-A", "RFQ-B", "RFQ-C"]:
        at.radio(key="rfq_pick").set_value(rid)
        for sec in S:
            go(at, sec)


@pytest.mark.parametrize("mode", ["offline", "live"])
def test_demo_runs_with_ollama_configured_but_unreachable(monkeypatch, mode):
    """Quentin's PC with Ollama stopped: offline mode never touches the network; live mode degrades to
    fixtures/templates. Either way the demo path renders with no exceptions."""
    import requests

    from qm import llm, pipeline

    calls = []

    def down(*a, **k):
        calls.append(1)
        raise requests.ConnectionError("ollama not running")

    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("DEMO_MODE", mode)
    monkeypatch.setattr(llm.requests, "post", down)
    monkeypatch.setattr(llm.requests, "get", down)
    pipeline.clear_caches()
    at = ok(AppTest.from_file(APP, default_timeout=180).run())
    assert "saved answers only" in text_of(at) if mode == "offline" else True
    at.radio(key="gap_RFQ-A_finish_color").set_value(ASSUME)
    ok(at.run())
    for rid in ["RFQ-A", "RFQ-B", "RFQ-C"]:
        at.radio(key="rfq_pick").set_value(rid)
        for sec in S:
            go(at, sec)
    if mode == "offline":
        assert not calls
    pipeline.clear_caches()


def test_price_choices_and_out_of_range_reason():
    at = ok(AppTest.from_file(APP, default_timeout=180).run())
    approve_plan(at)
    go(at, S[3])
    assert at.radio(key="price_choice_RFQ-A").value == "Recommended price"
    rec = None
    for m in at.markdown:
        if "Recommended price" in str(m.value) and "<table" in str(m.value):
            rec = m.value
    assert rec and "Lower price" in rec and "Higher price" in rec
    at.radio(key="price_choice_RFQ-A").set_value("Another amount")
    ok(at.run())
    base = at.number_input(key="price_custom_RFQ-A").value
    at.number_input(key="price_custom_RFQ-A").set_value(round(base * 1.4, 2))
    ok(at.run())
    at.button(key="g2_approve_RFQ-A").click()
    ok(at.run())
    assert any("reason" in str(e.value).lower() for e in at.error)
    at.text_input(key="g2_reason_RFQ-A").set_value("strategic account, backlog is full")
    at.button(key="g2_approve_RFQ-A").click()
    ok(at.run())
    mem = memory.list_memory()
    assert len(mem) == 1 and mem.iloc[0].kind == "gate2_price" and "strategic account" in mem.iloc[0].text
    go(at, S[2])                                  # the drawer picks a default line after a selection exists
    at.selectbox(key="drawer_RFQ-A").set_value("mat.A36")
    ok(at.run())
    assert not at.warning or all("created with a default value" not in str(w.value) for w in at.warning)


def test_price_needs_the_plan_first_and_recommended_needs_no_reason():
    at = ok(AppTest.from_file(APP, default_timeout=180).run())
    go(at, S[3])
    assert at.button(key="g2_approve_RFQ-A").disabled
    assert any("approve the plan first" in str(i.value) for i in at.info)
    approve_plan(at)
    go(at, S[3])
    assert not at.button(key="g2_approve_RFQ-A").disabled
    at.button(key="g2_approve_RFQ-A").click()
    ok(at.run())
    assert any("Checkpoint 2 approved" in str(s.value) for s in at.success)
    assert memory.list_memory().empty


def build_quick(at, **kw):
    at.radio(key="rfq_pick").set_value("QUICK")
    ok(at.run())
    for key, val in kw.items():
        widget = {"qd_customer": at.selectbox, "qd_family": at.selectbox, "qd_material": at.selectbox,
                  "qd_thick": at.selectbox, "qd_weld": at.selectbox, "qd_finish": at.selectbox, "qd_color": at.selectbox,
                  "qd_tol": at.selectbox, "qd_qty": at.number_input, "qd_batch": at.number_input,
                  "qd_pn": at.text_input, "qd_conflict": at.checkbox}[key]
        widget(key=key).set_value(val)
    at.button(key="qd_go").click()
    return ok(at.run())


def test_quick_demo_request_end_to_end_and_learning_between_builds():
    at = ok(AppTest.from_file(APP, default_timeout=180).run())
    ok(at.radio(key="rfq_pick").set_value("QUICK").run())
    assert any("Build this request" in str(i.value) for i in at.info)          # nothing built yet

    build_quick(at, qd_customer="Cedar Valley Equipment", qd_family="hitch_bracket", qd_qty=150, qd_batch=50,
                qd_weld="cosmetic", qd_color="not stated", qd_conflict=True)
    t = text_of(at)
    assert "Cedar Valley Equipment" in t and any("Loaded:" in str(c.value) for c in at.sidebar.caption)
    assert at.radio(key="step").value == S[0]
    assert "Quantity conflict" in t and "Powder coat color not specified" in t
    for g in ("qty_conflict", "finish_color"):
        at.radio(key=f"gap_RFQ-Q1_{g}").set_value(ASSUME)
        ok(at.run())
    go(at, S[1])
    # a brand new part (no part number) already carries a one-time fixture line, so the estimator can just approve
    at.button(key="g1_approve_RFQ-Q1").click()
    ok(at.run())
    assert any("Checkpoint 1 approved" in str(s.value) for s in at.success)
    go(at, S[3])
    at.button(key="g2_approve_RFQ-Q1").click()
    ok(at.run())
    go(at, S[4])
    assert any("Ready to send" in str(s.value) for s in at.success)

    # a second build gets its own id and a clean slate
    build_quick(at, qd_customer="Hawkeye Loader Works", qd_family="guard", qd_material="5052AL", qd_thick="1/8",
                qd_weld="standard", qd_qty=40, qd_batch=40)
    assert at.radio(key="step").value == S[0] and "Hawkeye Loader Works" in text_of(at)
    for sec in S:
        go(at, sec)
    assert not any("Checkpoint 1 approved" in str(s.value) for s in at.success)

    # Start over forgets the quick request
    at.button(key="reset").click()
    ok(at.run())
    at.radio(key="rfq_pick~1").set_value("QUICK")
    ok(at.run())
    assert any("Build this request" in str(i.value) for i in at.info)


def test_quick_demo_every_step_with_details_on_and_odd_choices():
    at = ok(AppTest.from_file(APP, default_timeout=180).run())
    build_quick(at, qd_customer="Loess Hills Machinery", qd_family="mounting_plate", qd_weld="none", qd_qty=40,
                qd_batch=40, qd_pn="LHM-MP-0620")
    assert "Fast track" in text_of(at)
    at.toggle(key="details").set_value(True)
    ok(at.run())
    for sec in S:
        go(at, sec)
    build_quick(at, qd_customer="Big Sioux Trailer", qd_family="frame", qd_material="A500", qd_thick="3/16",
                qd_finish="none", qd_tol="tight", qd_qty=5, qd_batch=500)
    for sec in S:
        go(at, sec)
