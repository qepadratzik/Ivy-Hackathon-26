"""Capture the demo beats as PNGs for slides / backup (docs/screens/).

Needs: `pip install playwright` + a Chromium (`playwright install chromium`, or CHROMIUM_PATH=...).
Start the app first on an isolated state, e.g.
  QM_MEMORY_DIR=/tmp/qm_mem streamlit run app.py --server.headless true --server.port 8599
then:  python scripts/screenshots.py http://localhost:8599 docs/screens
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8599"
OUT = sys.argv[2] if len(sys.argv) > 2 else "docs/screens"
os.makedirs(OUT, exist_ok=True)


def idle(page, t=2.0):
    time.sleep(0.6)
    for _ in range(80):
        if page.locator("[data-testid='stStatusWidget']").count() == 0:
            break
        time.sleep(0.5)
    time.sleep(t)


def shot(page, name):
    page.screenshot(path=f"{OUT}/{name}.png")
    print("saved", name)


def top(page):
    page.evaluate("""() => { for (const el of document.querySelectorAll('[data-testid="stMain"], section.main, .main'))
                                 { el.scrollTo(0, 0); } window.scrollTo(0, 0); }""")
    time.sleep(0.5)


def section(page, label):
    page.get_by_text(label, exact=True).click()
    idle(page)


with sync_playwright() as p:
    kw = {"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}
    b = p.chromium.launch(**kw)
    page = b.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=1.5)
    page.goto(URL)
    page.wait_for_selector("text=Quote Memory", timeout=180000)
    idle(page, 4)
    page.get_by_role("button", name="↺ Reset demo state").click()
    idle(page, 4)
    shot(page, "01_rfqA_requirements")
    page.get_by_text("Assume & quote").nth(1).click()
    idle(page)
    shot(page, "02_assume_color_banner")
    section(page, "2 · Approach (Gate 1)")
    shot(page, "03_approach_analog")
    page.get_by_role("button", name="Apply").click()
    idle(page)
    page.get_by_label("Why? (required").fill("new fixture needed: Rev C moved the hole pattern")
    page.keyboard.press("Enter")
    idle(page, 1)
    page.get_by_role("button", name="✓ Approve Gate 1").click()
    idle(page)
    shot(page, "04_gate1_override_banner")
    section(page, "3 · Cost ledger")
    shot(page, "05_ledger")
    page.get_by_text("Patterns found in our history").scroll_into_view_if_needed()
    idle(page, 1)
    shot(page, "05b_weld_evidence_and_P1")
    top(page)
    sl = page.get_by_role("slider").nth(1)
    sl.focus()
    for _ in range(6):
        page.keyboard.press("ArrowRight")
        time.sleep(0.15)
    idle(page, 3)
    shot(page, "06_stale_steel_chain_reaction")
    section(page, "4 · Risk")
    shot(page, "07_risk_band")
    section(page, "5 · Price (Gate 2)")
    shot(page, "08_price_curve")
    page.get_by_role("button", name="✓ Approve Gate 2").click()
    idle(page)
    section(page, "6 · Quote")
    shot(page, "09_quote_preview")
    sl = page.get_by_role("slider").nth(1)
    sl.focus()
    for _ in range(6):
        page.keyboard.press("ArrowLeft")
        time.sleep(0.15)
    idle(page, 2)
    page.get_by_text("B · Hawkeye hitch bracket (first run)").click()
    idle(page, 3)
    section(page, "3 · Cost ledger")
    shot(page, "10_rfqB_banner_learned")
    page.get_by_text("Learned from an earlier quote").scroll_into_view_if_needed()
    idle(page, 1)
    shot(page, "11_rfqB_evidence_from_A")
    top(page)
    page.get_by_text("C · Loess Hills mounting plate (repeat)").click()
    idle(page, 3)
    section(page, "1 · Requirements")
    shot(page, "12_rfqC_fast_track")
    b.close()
