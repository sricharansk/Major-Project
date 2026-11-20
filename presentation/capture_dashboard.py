"""Capture the Streamlit dashboard pages used in the final-review deck and the paper (presentation/assets/dashboard_2026-11-20/*.png).

Start the dashboard first (PYTHONPATH=src streamlit run src/smartcity/dashboard/app.py --server.headless true), then:
    python presentation/capture_dashboard.py [http://localhost:8501] [chromium executable | msedge]
Requires playwright and Pillow. The sidebar is cropped away; page title and mode label stay in the picture.
Pages that need the local data and weights (Traffic map, Multi-horizon forecast) render only on the workstation.
"""
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"
EXE = sys.argv[2] if len(sys.argv) > 2 else None
OUT = Path(__file__).resolve().parent / "assets" / "dashboard_2026-11-20"  # fresh 2x captures; the original set in assets/dashboard is cropped by the deck and paper builders
SCALE = 2  # device scale factor; crop boxes below are in CSS pixels
SIDEBAR, RIGHT, TOP = 360, 40, 70
# sidebar label, output name, text to scroll to (None = top of page), action before the capture
JOBS = [("Overview & status", "overview", None, None), ("Data audit & provenance", "data_audit", None, None),
        ("Traffic map", "traffic_map_laptop", None, None), ("Multi-horizon forecast", "forecast_laptop", None, None),
        ("Experiment results", "experiments", None, None),
        ("Uncertainty & reliability", "uncertainty", "coverage_by_horizon.csv", None),
        ("Explainability", "explainability", None, None), ("Evidence retrieval", "retrieval", None, "search"),
        ("Agent trace & advisory", "agent", None, None), ("SUMO comparisons", "sumo", None, None),
        ("Live monitoring", "live", None, None), ("Live monitoring", "live_table", "Scored so far", None)]

OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
    if EXE in ("msedge", "chrome"):
        browser = p.chromium.launch(channel=EXE)
    else:
        browser = p.chromium.launch(executable_path=EXE) if EXE else p.chromium.launch()
    page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=SCALE, color_scheme="light")
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("text=Overview & status", timeout=60000)
    for label, name, target, action in JOBS:
        page.locator('[data-testid="stSidebar"] label').filter(has_text=label).first.click()
        time.sleep(7)
        page.wait_for_load_state("networkidle")
        page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=180000)
        if action == "search":
            page.get_by_role("button", name="Search", exact=True).and_(page.get_by_test_id("stBaseButton-secondary")).click()
            page.wait_for_selector("text=Status:", timeout=180000)
            page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=180000)
            time.sleep(2)
        page.add_style_tag(content='[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important}')
        page.evaluate("() => document.querySelectorAll('*').forEach(e => { if (e.scrollTop > 0) e.scrollTop = 0; })")
        time.sleep(1)
        if target:
            page.get_by_text(target, exact=True).first.evaluate("e => e.scrollIntoView({block: 'start'})")
            time.sleep(1.5)
        raw = Path(tmp) / f"{name}.png"
        page.screenshot(path=str(raw))
        im = Image.open(raw)
        w, h = im.size
        top = 0 if target else TOP * SCALE
        im.crop((SIDEBAR * SCALE, top, w - RIGHT * SCALE, h)).save(OUT / f"{name}.png", optimize=True)
        print(name, "saved", im.size)
    # the pooled LIVE metrics table is wider than a 1600 px page; a wider viewport shows the MAE and persistence columns
    page.set_viewport_size({"width": 3000, "height": 1000})
    time.sleep(3)
    page.get_by_text("Scored so far", exact=True).first.evaluate("e => e.scrollIntoView({block: 'start'})")
    time.sleep(2)
    raw = Path(tmp) / "live_table_wide.png"
    page.screenshot(path=str(raw))
    im = Image.open(raw)
    w, h = im.size
    im.crop((SIDEBAR * SCALE, 0, w - RIGHT * SCALE, h // 2)).save(OUT / "live_table_wide.png", optimize=True)
    print("live_table_wide saved", im.size)
    browser.close()
