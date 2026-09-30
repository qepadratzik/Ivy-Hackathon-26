"""Phase 2 gate: demo RFQs retrieve the intended hero analogs and relevant notes,
with the Chroma/MiniLM backend and with the TF-IDF fallback."""
import pytest

from qm import retrieval, store

DESC = ("Hitch bracket weldment: 4 laser-cut plate parts, 2 formed parts, 1 tube 2x2x3/16 A500; "
        "purchased bushings (2 per assy) and bolt kit")
A = dict(part_number="CVE-HB-4410 Rev C", part_family="hitch_bracket", material="A36", thickness_in=0.375,
         qty=250, cosmetic_weld=True, finish="powder_coat", part_description=DESC)
B = dict(A, part_number="HLW-HB-3300", qty=150, cosmetic_weld=False, finish_color="gloss black", first_run=True)
C = dict(part_number="LHM-MP-0620", part_family="mounting_plate", material="A36", thickness_in=0.5, qty=40,
         finish="powder_coat", finish_color="black",
         part_description="Mounting plate: laser cut 1/2 A36 plate, drilled and tapped 4x 1/2-13, no welding.")


@pytest.fixture(params=["chroma", "tfidf"])
def backend(request, monkeypatch):
    if request.param == "tfidf":
        monkeypatch.setenv("QM_EMBEDDINGS", "tfidf")
    else:
        monkeypatch.delenv("QM_EMBEDDINGS", raising=False)
    store.reset_vector_cache()
    yield request.param
    store.reset_vector_cache()


@pytest.mark.parametrize("spec,analog", [(A, "J-1042"), (B, "J-1103"), (C, "J-1118")])
def test_demo_rfqs_hit_hero_analogs(backend, spec, analog):
    sims = retrieval.similar_jobs(spec)
    assert retrieval.pick_analog(sims).job_id == analog
    assert (sims.part_family == spec["part_family"]).all()
    assert sims.sim.between(0, 1).all()


def test_rfq_a_top_is_hero_and_why_string(backend):
    sims = retrieval.similar_jobs(A)
    assert "J-1042" in list(sims.job_id.head(3))                     # hero is among the closest matches
    top = sims[sims.job_id == "J-1042"].iloc[0]
    assert "same part number" in top.why and "cosmetic weld too" in top.why


def test_notes_for_a_weld_line_are_cosmetic_debriefs(backend):
    notes = retrieval.related_notes(A, "weld", "weld.run")
    top = notes.head(3)
    assert (top.doc_type == "debrief").all()
    assert top.text.str.contains("visible|cosmetic|spatter|show side|faces out", case=False).all()
    assert (top.sim >= 0.35).all()


def test_notes_for_b_setup_include_fixture_debrief(backend):
    notes = retrieval.related_notes(B, "weld", "weld.setup")
    assert notes.iloc[0].job_id == "J-1103"
    assert notes.head(3).text.str.contains("fixture|jig", case=False).any()


def test_structured_sim_pieces():
    assert retrieval.thickness_closeness(0.375, 0.375) == 1
    assert retrieval.thickness_closeness(0.25, 0.5) == 0.5
    assert retrieval.thickness_closeness(None, 0.5) == 0.5
    assert retrieval.qty_match(200, 250) == 1 and retrieval.qty_match(50, 200) == 0.5
    assert retrieval.qty_match(10, 500) == 0
