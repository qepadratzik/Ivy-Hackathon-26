"""Capture the demo beats as PNGs for slides / backup (docs/screens/).

Needs: `pip install playwright` + a Chromium (`playwright install chromium`, or CHROMIUM_PATH=...).
Start the app first on an isolated state, e.g.
  QM_MEMORY_DIR=/tmp/qm_mem streamlit run app.py --server.headless true --server.port 8599
then:  python scripts/screenshots.py http://localhost:8599 docs/screens
"""
import os
import re
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


def step(page, n):
    """Click step n in the horizontal step picker (its label carries a status suffix)."""
    page.locator("label", has_text=re.compile(rf"^{n} · ")).first.click()
    idle(page)


def job(page, label):
    page.get_by_text(label, exact=True).click()
    idle(page, 3)


def details(page, on):
    sw = page.get_by_text("Show the details", exact=True)
    sw.click()
    idle(page, 2)


with sync_playwright() as p:
    kw = {"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}
    b = p.chromium.launch(**kw)
    page = b.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=1.5)
    page.goto(URL)
    page.wait_for_selector("text=Quote Memory", timeout=180000)
    idle(page, 4)
    page.get_by_role("button", name="Start over").click()
    idle(page, 4)
    shot(page, "01_job1_read_the_request")
    page.get_by_text("Assume and quote").nth(1).click()
    idle(page)
    shot(page, "02_assume_color_banner")
    step(page, 2)
    shot(page, "03_plan_closest_past_job")
    page.get_by_text("No, we need to build a new one").click()
    idle(page, 1)
    page.get_by_label("Why? (needed", exact=False).fill("Rev C moved the hole pattern, so the old fixture will not fit.")
    page.keyboard.press("Enter")
    idle(page, 1)
    page.get_by_text("Does the old fixture still fit").scroll_into_view_if_needed()
    shot(page, "04_fixture_question")
    page.get_by_role("button", name="Approve the plan").click()
    idle(page)
    top(page)
    shot(page, "05_plan_approved_banner")
    step(page, 3)
    shot(page, "06_cost_table")
    page.get_by_text("Lessons from our history").scroll_into_view_if_needed()
    idle(page, 1)
    shot(page, "06b_lesson_from_past_jobs")
    top(page)
    sl = page.get_by_role("slider").first
    sl.focus()
    for _ in range(6):
        page.keyboard.press("ArrowRight")
        time.sleep(0.15)
    idle(page, 3)
    shot(page, "07_stale_steel_quote")
    sl.focus()
    for _ in range(6):
        page.keyboard.press("ArrowLeft")
        time.sleep(0.15)
    idle(page, 3)
    step(page, 4)
    shot(page, "08_three_price_options")
    page.get_by_role("button", name="Approve the price").click()
    idle(page)
    step(page, 1)
    page.get_by_text("Assume and quote").nth(0).click()      # the quantity question
    idle(page)
    step(page, 5)
    shot(page, "09_quote_ready")
    job(page, "Job 2 · Similar bracket, first time built (Hawkeye)")
    step(page, 3)
    shot(page, "10_job2_learned_from_job1")
    page.get_by_text("Learned from an earlier quote").first.scroll_into_view_if_needed()
    idle(page, 1)
    shot(page, "11_job2_evidence_from_job1")
    top(page)
    job(page, "Job 3 · Repeat order (Loess Hills)")
    step(page, 1)
    shot(page, "12_job3_fast_track")
    details(page, True)
    step(page, 3)
    shot(page, "13_details_on_cost")
    b.close()
