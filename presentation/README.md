# Final review presentation

`Final_Review_S_K_Sricharan_25MML1010.pptx` is the M.Tech project work final-review deck, built on the VIT Chennai
final-review template (`assets/final_review_template.pptx`) with its slide order, headings and font rules. A PDF copy
is alongside it. Section 9 of the template ("Timeline / Gantt chart") is replaced by "Results & outcomes", as asked by
the student on 21 Oct 2026.

Every number in the deck was copied from a committed result file (`reports/experiments/*.csv`,
`reports/experiments/simulation_testbed_audit*.json`, `reports/verification/final_status.md`,
`reports/verification/paper_claims.csv`) and checked against it; the builder holds them as literals, so after any
artifact change the literals must be re-checked and the deck rebuilt. Section 9 shows the three-seed results
(`reports/experiments/multi_seed_summary.csv`) next to the seed-42 run used everywhere else. Simulation figures are
SUMO outputs on a calibrated scenario testbed, not real-street measurements or NYC DOT timing, and are labelled
SIMULATION. Slide 16 lists the calibration protocols (the first 20 Oct comparison is SUPERSEDED; v6 selects a 90 s
common cycle, green factor 1.5 and 25 mph offsets, 10.08 vs 10.95 mph observed,
`simulation/scenarios/split_calibration_v6_counts2025_cycle_splits_offsets.json`). Slide 21 charts the corrected
45-run comparison from `reports/experiments/simulation_metrics.csv` (claims C44-C46): a simulated result only.

## Dashboard screenshots (slides 17-21)

`assets/dashboard/*.png` are screenshots of the project's Streamlit dashboard reading the committed artifacts, taken
with `capture_dashboard.py`. Each slide names the mode label the page itself shows (REPLAY or SIMULATION; the overview
page has none). No LIVE view is shown: LIVE observational mode (the Live monitoring page) is implemented but has not been run, so
that page only says NOT_RUN. The
Multi-horizon forecast and Traffic map pages need the trained model file and processed data, which live on the
training laptop: `forecast_laptop.png` and `traffic_map_laptop.png` were captured there on 23 Oct 2026 (REPLAY,
1600x1000) and the builder crops off their sidebar and toolbar.

```bash
PYTHONPATH=src streamlit run src/smartcity/dashboard/app.py --server.headless true &
python presentation/capture_dashboard.py http://localhost:8501   # optional 2nd arg: chromium executable
```

## Rebuild

`assets/final_review_template_25_slides.pptx` is the template with slides duplicated (a second literature-survey
slide, six more outcome slides of which five hold the dashboard screenshots, a second results-and-outcomes slide and
a references slide). The builder fills it:

```bash
python presentation/build_final_review.py presentation/assets/final_review_template_25_slides.pptx \
    presentation/Final_Review_S_K_Sricharan_25MML1010.pptx presentation/assets/vit_chennai_15_logo.png
```

Requires `python-pptx` and `Pillow`. The combined VIT Chennai / 15-years logo is cropped from the Review-II deck.
