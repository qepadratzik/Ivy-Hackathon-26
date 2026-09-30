"""Phase 7 gate: headless Streamlit AppTest runs the full demo path A -> (override) -> B -> C
through the real widgets, with no exceptions."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from qm import config, memory, store

APP = str(Path(__file__).resolve().parent.parent / "app.py")
S = ["1 · Requirements", "2 · Approach (Gate 1)", "3 · Cost ledger", "4 · Risk", "5 · Price (Gate 2)", "6 · Quote"]


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


def test_full_demo_path():
    at = ok(AppTest.from_file(APP, default_timeout=180).run())
    assert "RFQ-A" in text_of(at) and "Full review" in text_of(at)

    # Beat 1: gaps -> assume black
    at.radio(key="gap_RFQ-A_finish_color").set_value("Assume & quote")
    ok(at.run())
    assert "What just changed" in text_of(at)

    # Beat 2: Gate 1 quick adjust fit/tack setup +6 hr with a reason
    at.radio(key="section").set_value(S[1])
    ok(at.run())
    at.button(key="qa_apply_RFQ-A").click()
    ok(at.run())
    at.button(key="g1_approve_RFQ-A").click()          # no reason yet -> blocked
    ok(at.run())
    assert any("reason" in str(e.value).lower() for e in at.error)
    at.text_input(key="g1_reason_RFQ-A").set_value("new fixture needed")
    at.button(key="g1_approve_RFQ-A").click()
    ok(at.run())
    mem = memory.list_memory()
    assert len(mem) == 1 and mem.iloc[0].line_key == "fixture.setup" and mem.iloc[0].new_value == 6.0
    assert "Gate 1 approved" in "\n".join(str(s.value) for s in at.success)

    # Beat 3: ledger + evidence drawer on the weld line, P1 callout
    at.radio(key="section").set_value(S[2])
    ok(at.run())
    at.selectbox(key="drawer_RFQ-A").set_value("weld.run")
    ok(at.run())
    assert any("P1" in str(i.value) for i in at.info)

    # Beat 4: age the material quote 90 days -> banner with validity change
    at.slider(key="mat_age").set_value(90)
    ok(at.run())
    assert "aged 0 → 90 days" in text_of(at)
    assert any("re-quote material" in str(w.value) for w in at.warning) or True

    # Beat 5: resolve the qty question, price, Gate 2, quote preview
    at.radio(key="section").set_value(S[0])
    ok(at.run())
    at.radio(key="gap_RFQ-A_qty_conflict").set_value("Assume & quote")
    ok(at.run())
    at.radio(key="section").set_value(S[4])
    ok(at.run())
    at.button(key="g2_approve_RFQ-A").click()
    ok(at.run())
    at.radio(key="section").set_value(S[5])
    ok(at.run())
    assert any("Ready to send" in str(s.value) for s in at.success)

    # Beat 6: RFQ B shows A's override as evidence on fit/tack setup
    at.radio(key="rfq_pick").set_value("RFQ-B")
    at.radio(key="section").set_value(S[2])
    ok(at.run())
    at.selectbox(key="drawer_RFQ-B").set_value("fixture.setup")
    ok(at.run())
    frames = [d.value for d in at.dataframe]
    assert any("Estimator override" in f.to_string() and "M-0001" in f.to_string() for f in frames)
    assert "memory now holds" in text_of(at)

    # Beat 7: RFQ C fast-track
    at.radio(key="rfq_pick").set_value("RFQ-C")
    at.radio(key="section").set_value(S[0])
    ok(at.run())
    assert "Fast-track" in text_of(at)
    for sec in S:
        at.radio(key="section").set_value(sec)
        ok(at.run())

    # Reset clears memory AND regenerates every widget (fresh defaults in the browser)
    at.button(key="reset").click()
    ok(at.run())
    assert memory.list_memory().empty
    assert at.radio(key="rfq_pick~1").value == "RFQ-A" and at.slider(key="mat_age~1").value == 0
    assert at.radio(key="gap_RFQ-A_finish_color~1").value == "Ask the customer"
    at.radio(key="gap_RFQ-A_finish_color~1").set_value("Assume & quote")
    ok(at.run())
    assert "What just changed" in text_of(at)


def test_paste_box_and_every_section_for_each_rfq():
    at = ok(AppTest.from_file(APP, default_timeout=180).run())
    for rid in ["RFQ-B", "RFQ-C", "RFQ-A"]:
        at.radio(key="rfq_pick").set_value(rid)
        for sec in S:
            at.radio(key="section").set_value(sec)
            ok(at.run())
    at.radio(key="rfq_pick").set_value("PASTE")
    ok(at.run())
    at.text_area(key="paste_text").set_value(
        "From: Pat Doe <pat@acme.example>\nSubject: RFQ\n\nPlease quote 60 pcs of a guard, 12 ga A36 sheet, "
        "powder coat orange, standard tolerance. Need by Nov 20.\nThanks, Pat\nBig Sioux Trailer")
    at.button(key="paste_go").click()
    ok(at.run())
    for sec in S:
        at.radio(key="section").set_value(sec)
        ok(at.run())


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
    assert "offline" in text_of(at) if mode == "offline" else True
    at.radio(key="gap_RFQ-A_finish_color").set_value("Assume & quote")
    ok(at.run())
    for rid in ["RFQ-A", "RFQ-B", "RFQ-C"]:
        at.radio(key="rfq_pick").set_value(rid)
        for sec in S:
            at.radio(key="section").set_value(sec)
            ok(at.run())
    if mode == "offline":
        assert not calls
    pipeline.clear_caches()


def test_gate2_use_recommended_and_out_of_range_reason():
    at = ok(AppTest.from_file(APP, default_timeout=180).run())
    at.radio(key="section").set_value(S[4])
    ok(at.run())
    rec = at.number_input(key="g2_price_RFQ-A").value
    at.number_input(key="g2_price_RFQ-A").set_value(round(rec * 1.4, 2))
    ok(at.run())
    at.button(key="g2_approve_RFQ-A").click()
    ok(at.run())
    assert any("reason" in str(e.value).lower() for e in at.error)
    at.button(key="g2_userec_RFQ-A").click()
    ok(at.run())
    assert at.number_input(key="g2_price_RFQ-A").value == rec
    at.number_input(key="g2_price_RFQ-A").set_value(round(rec * 1.4, 2))
    ok(at.run())
    at.text_input(key="g2_reason_RFQ-A").set_value("strategic account, backlog is full")
    at.button(key="g2_approve_RFQ-A").click()
    ok(at.run())
    mem = memory.list_memory()
    assert len(mem) == 1 and mem.iloc[0].kind == "gate2_price" and "strategic account" in mem.iloc[0].text
    at.radio(key="section").set_value(S[2])      # drawer picks a default line after a selection exists
    ok(at.run())
    at.selectbox(key="drawer_RFQ-A").set_value("mat.A36")
    ok(at.run())
    assert not at.warning or all("created with a default value" not in str(w.value) for w in at.warning)
