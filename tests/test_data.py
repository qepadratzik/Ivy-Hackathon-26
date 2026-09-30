"""Phase 1 gate: seeded patterns P1-P5 are discoverable, noise exists, hero jobs are present."""
from datetime import date, timedelta

import pandas as pd
import pytest

from qm import data_gen


@pytest.fixture(scope="module")
def t():
    return data_gen.generate(seed=42)


def _completed(t):
    ops = t["routing_ops"]
    return set(ops[ops.run_hr_act.notna()].job_id)


def test_scale_and_shape(t):
    j = t["jobs"]
    assert 140 <= len(j) <= 175
    assert set(j.part_family) == {"hitch_bracket", "guard", "frame", "mounting_plate", "tube_assembly"}
    assert j.customer_id.nunique() == 7
    assert 0.50 <= j.won.mean() <= 0.68
    assert j.quote_date.min() >= date(2024, 10, 1) and j.quote_date.max() <= date(2026, 9, 30)
    assert (j.est_cost > 0).all() and (j.quoted_price > j.est_cost).all()


def test_p1_cosmetic_weld_overrun(t):
    j, o = t["jobs"], t["routing_ops"]
    w = o[(o.work_center == "weld") & o.run_hr_act.notna()].merge(j[["job_id", "cosmetic_weld"]], on="job_id")
    cos = w[w.cosmetic_weld]
    ratio = (cos.run_hr_act / cos.run_hr_est).mean()
    assert len(cos) >= 8 and 1.25 <= ratio <= 1.45
    non = w[~w.cosmetic_weld]
    assert (non.run_hr_act / non.run_hr_est).mean() < 1.10


def test_p2_first_run_no_fixture_setup_overrun(t):
    j, o, d = t["jobs"], t["routing_ops"], t["docs"]
    p2 = j[j.first_run & ~j.has_fixture_line]
    ft = o[(o.work_center == "weld") & o.setup_hr_act.notna() & o.job_id.isin(p2.job_id)]
    assert len(ft) >= 5
    assert (ft.setup_hr_act / ft.setup_hr_est).mean() >= 1.5
    notes = d[d.job_id.isin(ft.job_id) & (d.doc_type == "debrief") & d.text.str.contains("fixture|jig", case=False)]
    assert len(notes) >= 3


def test_p3_press_brake_thick_plate_ncr(t):
    j, o, d = t["jobs"], t["routing_ops"], t["docs"]
    pb = o[(o.work_center == "press_brake") & o.run_hr_act.notna()].merge(j[["job_id", "thickness_in"]], on="job_id")
    thick = pb[pb.thickness_in >= 0.5]
    ncr_jobs = set(d[(d.doc_type == "ncr") & (d.work_center == "press_brake")].job_id)
    rate = thick.job_id.isin(ncr_jobs).mean()
    assert len(thick) >= 8 and 0.20 <= rate <= 0.45


def test_p4_prairie_price_sensitive(t):
    j = t["jobs"]
    pic = j[j.customer_id == "C01"].assign(r=lambda x: x.quoted_price / x.est_cost)
    low, high = pic[pic.r < 1.25], pic[pic.r >= 1.30]
    assert len(low) >= 5 and len(high) >= 5
    assert low.won.mean() >= 0.70
    assert high.won.mean() <= 0.25


def test_p5_steel_rising(t):
    p = t["material_prices"]
    a = p[p.material == "A36"]
    first = a[a.quote_date < date(2025, 4, 1)].price_per_lb.mean()
    last = a[a.quote_date >= date(2026, 4, 1)].price_per_lb.mean()
    assert 1.12 <= last / first <= 1.18
    assert a.quote_date.max() >= date(2026, 9, 18)  # fresh quote for the demo


def test_noise(t):
    j, o = t["jobs"], t["routing_ops"]
    won_done = j[j.won & (pd.to_datetime(j.quote_date) + pd.to_timedelta(j.lead_time_days + 7, "D")
                          < pd.Timestamp(2026, 9, 30))]
    missing = ~won_done.job_id.isin(_completed(t))
    assert 0.04 <= missing.mean() <= 0.20
    assert j[j.material == "A36"].material_raw_name.nunique() >= 3
    norm = j.assign(n=j.part_number.map(data_gen.normalize_pn))
    dup_variants = norm.groupby("n").part_number.nunique()
    assert (dup_variants > 1).sum() >= 3
    assert (j.finish.fillna("") == "").sum() >= 2
    emails = t["docs"][t["docs"].doc_type == "rfq_email"]
    assert len(emails) == len(j)


def test_hero_jobs(t):
    j, o = t["jobs"].set_index("job_id"), t["routing_ops"]
    for jid in data_gen.HERO_IDS:
        assert jid in j.index
    for jid in ["J-1042", "J-0987"]:
        r = j.loc[jid]
        assert r.part_family == "hitch_bracket" and r.cosmetic_weld and r.won and r.thickness_in == 0.375
        assert 100 <= r.qty <= 300
        assert o[o.job_id == jid].run_hr_act.notna().all()
    assert not j.loc["J-1077"].won
    assert o[o.job_id == "J-1077"].run_hr_act.isna().all()
    r = j.loc["J-1103"]
    assert r.first_run and not r.has_fixture_line
    ft = o[(o.job_id == "J-1103") & (o.work_center == "weld")].iloc[0]
    assert ft.setup_hr_act / ft.setup_hr_est >= 1.6
    d = t["docs"]
    assert d[(d.job_id == "J-1103") & (d.doc_type == "debrief")].text.str.contains("fixture").any()
    mp = j[j.part_number == "LHM-MP-0620"]
    assert len(mp) >= 3 and mp.won.all()
    assert "HLWHB3300" not in set(j.part_number.map(data_gen.normalize_pn))


def test_deterministic():
    a, b = data_gen.generate(seed=42), data_gen.generate(seed=42)
    for k in a:
        pd.testing.assert_frame_equal(a[k], b[k])


def test_normalize_pn():
    assert data_gen.normalize_pn("CVE-HB-4410 Rev C") == "CVEHB4410"
    assert data_gen.normalize_pn("cve hb 4410") == "CVEHB4410"
    assert data_gen.normalize_pn("CVE-HB-4410 REV. B") == "CVEHB4410"
