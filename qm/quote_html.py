"""Customer-facing HTML quote (the "Download quote (HTML)" button).

One self-contained page: inline CSS, no scripts, no external fonts or images, so it opens anywhere, prints cleanly
(Ctrl+P / Save as PDF) and can be attached to an email. The Markdown download stays the plain-text version.
Every value comes from the pipeline's quote dict; nothing is computed here.
"""
from __future__ import annotations

import html

ACCENT = "#1a5fb4"

CSS = f"""
@page {{ margin: 16mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #eef1f5; color: #1f2933; font: 15px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.sheet {{ max-width: 780px; margin: 28px auto; background: #fff; border-radius: 10px; overflow: hidden;
          box-shadow: 0 2px 14px rgba(16, 24, 40, .12); }}
.head {{ background: {ACCENT}; color: #fff; padding: 24px 32px; display: flex; justify-content: space-between; gap: 24px; flex-wrap: wrap; }}
.head h1 {{ margin: 0; font-size: 22px; letter-spacing: .2px; }}
.head .sub {{ opacity: .85; font-size: 13px; margin-top: 2px; }}
.head .meta {{ text-align: right; font-size: 13px; line-height: 1.7; }}
.head .meta b {{ font-weight: 600; }}
.body {{ padding: 26px 32px 30px; }}
.banner {{ border-radius: 8px; padding: 10px 14px; margin-bottom: 20px; font-size: 14px; border: 1px solid; }}
.banner.draft {{ background: #fff6e0; border-color: #e5b94a; color: #6b4e00; }}
.banner.stop {{ background: #fdeceb; border-color: #e08b86; color: #8a1c14; }}
.parties {{ display: flex; gap: 28px; flex-wrap: wrap; margin-bottom: 22px; }}
.parties > div {{ flex: 1; min-width: 220px; }}
.label {{ text-transform: uppercase; font-size: 11px; letter-spacing: .08em; color: #667085; margin-bottom: 3px; }}
.val {{ font-size: 15px; }}
.hero {{ border: 1px solid #d0d5dd; border-left: 6px solid {ACCENT}; border-radius: 8px; padding: 16px 20px; margin-bottom: 24px;
         display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; background: #f8fafc; }}
.hero .price {{ font-size: 34px; font-weight: 700; color: #101828; line-height: 1.1; }}
.hero .per {{ font-size: 13px; color: #667085; }}
.hero .qty {{ text-align: right; font-size: 14px; color: #344054; }}
h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: .08em; color: {ACCENT}; margin: 26px 0 8px;
      padding-bottom: 5px; border-bottom: 2px solid #e4e7ec; }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th {{ text-align: left; color: #667085; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .05em;
      padding: 8px 10px; border-bottom: 1px solid #d0d5dd; }}
td {{ padding: 9px 10px; border-bottom: 1px solid #eef0f3; }}
td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
tr.asked td {{ background: #eef4ff; font-weight: 600; }}
.tag {{ display: inline-block; font-size: 11px; font-weight: 600; color: {ACCENT}; background: #dce9fb; border-radius: 9px;
        padding: 1px 8px; margin-left: 6px; }}
.note {{ color: #667085; font-size: 13px; margin-top: 6px; }}
.grid {{ display: flex; gap: 14px; flex-wrap: wrap; }}
.card {{ flex: 1; min-width: 200px; border: 1px solid #e4e7ec; border-radius: 8px; padding: 10px 14px; }}
.card .big {{ font-size: 18px; font-weight: 600; color: #101828; }}
ul {{ margin: 4px 0 0; padding-left: 20px; }}
li {{ margin: 3px 0; }}
.foot {{ background: #f8fafc; border-top: 1px solid #e4e7ec; padding: 14px 32px; font-size: 12px; color: #667085; }}
@media print {{ body {{ background: #fff; }} .sheet {{ box-shadow: none; margin: 0; max-width: none; border-radius: 0; }} }}
"""


def _e(x) -> str:
    return html.escape(str(x))


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>"


def render(res: dict) -> str:
    """Full HTML document for one pipeline result."""
    q, s = res["quote"], res["spec"]
    title = f"Quotation {q['part']}"
    banner = ""
    if res.get("insufficient"):
        banner = (f"<div class='banner stop'><b>Not priced.</b> We do not have enough information yet "
                  f"({_e('; '.join(res['insufficient']))}).</div>")
    elif not q["ready"]:
        banner = ("<div class='banner draft'><b>Draft, not released.</b> An approval is pending or a question to the "
                  "customer is still open.</div>")

    rows = "".join(
        f"<tr class='{'asked' if b['lot'] == q['lot'] else ''}'><td>{b['lot']} pcs per release"
        + ("<span class='tag'>as requested</span>" if b["lot"] == q["lot"] else "")
        + f"</td><td class='num'>{_money(b['unit_price'])}</td></tr>" for b in q["breaks"])
    alt = "".join(f"<p class='note'>If the total order is {a['total']} pcs (releases of {a['lot']}): "
                  f"<b>{_money(a['unit_price'])}</b> per part.</p>" for a in q.get("alt_totals", []))
    tooling = (f"One-time fixture / tooling: <b>{_money(q['tooling'])}</b>, spread over the {q['qty']} pcs"
               if q["tooling"] > 0 else "No tooling charge")
    sections = [
        "<h2>Price by release size</h2>"
        "<table><tr><th>Release size</th><th class='num'>Price per part</th></tr>" + rows + "</table>" + alt,
        "<h2>Setup, tooling and lead time</h2><div class='grid'>"
        f"<div class='card'><div class='label'>Setup</div><div class='big'>{_money(q['setup_per_release'])}</div>"
        "<div class='note'>per release, already included in the prices above</div></div>"
        f"<div class='card'><div class='label'>Tooling</div><div class='val'>{tooling}</div>"
        "<div class='note'>included in the prices above</div></div>"
        f"<div class='card'><div class='label'>Lead time</div><div class='big'>{q['lead_days']} days</div>"
        "<div class='note'>after receipt of order, first release</div></div></div>",
    ]
    if q["assumptions"]:
        sections.append("<h2>Assumptions</h2>" + _list(q["assumptions"]))
    sections.append("<h2>Exclusions</h2>" + _list(q["exclusions"]))
    if q["pending"]:
        sections.append("<h2>Waiting on the customer</h2>" + _list(q["pending"]))
    sections.append(f"<h2>Terms</h2><p>{_e(q['terms'])}</p>")

    desc = s.get("part_description") or "(description not stated)"
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{_e(title)}</title><style>{CSS}</style></head><body><div class='sheet'>"
        "<div class='head'><div><h1>Boone Creek Fabrication</h1>"
        "<div class='sub'>Quotation &middot; fictional shop, synthetic demo data</div></div>"
        f"<div class='meta'><div><b>Reference</b> {_e(res.get('rfq_id') or '')}</div>"
        f"<div><b>Date</b> {q['date']:%B %d, %Y}</div><div><b>Valid for</b> {q['validity_days']} days</div></div></div>"
        "<div class='body'>" + banner +
        "<div class='parties'>"
        f"<div><div class='label'>Prepared for</div><div class='val'><b>{_e(q['customer'])}</b></div></div>"
        f"<div><div class='label'>Part</div><div class='val'><b>{_e(q['part'])}</b><br>{_e(desc)}</div></div></div>"
        "<div class='hero'><div><div class='label'>Price per part</div>"
        f"<div class='price'>{_money(q['unit_price'])}</div>"
        f"<div class='per'>for releases of {q['lot']} pcs</div></div>"
        f"<div class='qty'><div class='label'>Quantity</div><b>{q['qty']} pcs</b> total<br>releases of {q['lot']}</div></div>"
        + "".join(sections) +
        "</div><div class='foot'>Synthetic demo data for a fictional shop. Prices are illustrative.</div>"
        "</div></body></html>")
