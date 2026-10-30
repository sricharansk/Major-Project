"""Capture the Streamlit dashboard pages used in the final-review deck (presentation/assets/dashboard/*.png).

Start the dashboard first (PYTHONPATH=src streamlit run src/smartcity/dashboard/app.py --server.headless true), then:
    python presentation/capture_dashboard.py [http://localhost:8501] [chromium executable]
Requires playwright and Pillow. The sidebar is cropped away; page title and mode label stay in the picture.
"""
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"
EXE = sys.argv[2] if len(sys.argv) > 2 else None
OUT = Path(__file__).resolve().parent / "assets" / "dashboard"
# sidebar label, output name, heading to scroll to (None = top of page)
JOBS = [("Overview & status", "overview", None), ("Data audit & provenance", "data_audit", None),
        ("Experiment results", "experiments", None), ("Uncertainty & reliability", "uncertainty", "coverage_by_horizon.csv"),
        ("Explainability", "explainability", None), ("Agent trace & advisory", "agent", None),
        ("SUMO comparisons", "sumo", None), ("Live monitoring", "live", None),
        ("Live monitoring", "live_scored", "Scored so far")]

OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
    browser = p.chromium.launch(executable_path=EXE) if EXE else p.chromium.launch()
    page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1.5)
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("text=Overview & status", timeout=60000)
    for label, name, target in JOBS:
        page.locator('[data-testid="stSidebar"] label').filter(has_text=label).first.click()
        time.sleep(7)
        page.wait_for_load_state("networkidle")
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
        box = (540, 0, w - 80, h - 140) if target else (540, 140, w - 80, h)
        im.crop(box).save(OUT / f"{name}.png", optimize=True)
        print(name, "saved")
    browser.close()
