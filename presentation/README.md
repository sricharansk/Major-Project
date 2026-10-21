# Final review presentation

`Final_Review_S_K_Sricharan_25MML1010.pptx` is the M.Tech project work final-review deck, built on the VIT Chennai
final-review template (`assets/final_review_template.pptx`) with its slide order, headings and font rules. A PDF copy
is alongside it. Section 9 of the template ("Timeline / Gantt chart") is replaced by "Results & outcomes", as asked by
the student on 21 Oct 2026.

Every number in the deck was copied from a committed result file (`reports/experiments/*.csv`,
`reports/experiments/simulation_testbed_audit*.json`, `reports/verification/final_status.md`,
`reports/verification/paper_claims.csv`) and checked against it; the builder holds them as literals, so after any
artifact change the literals must be re-checked and the deck rebuilt. Section 9 shows the three-seed results
(`reports/experiments/multi_seed_summary.csv`) next to the seed-42 run used everywhere else. Simulation figures are SUMO outputs, not real-street measurements, and no simulated
controller gain is shown (the first comparison is SUPERSEDED, the corrected one NOT RUN).

## Dashboard screenshots (slides 17-20)

`assets/dashboard/*.png` are screenshots of the project's Streamlit dashboard reading the committed artifacts, taken
with `capture_dashboard.py`. Each slide names the mode label the page itself shows (REPLAY or SIMULATION; the overview
page has none). No LIVE view is shown: the capture machine could not reach the NYC Open Data or Open-Meteo feeds. The
Multi-horizon forecast and Traffic map pages need the trained model file and processed data, which live on the
training laptop, so they are not in this version.

```bash
PYTHONPATH=src streamlit run src/smartcity/dashboard/app.py --server.headless true &
python presentation/capture_dashboard.py http://localhost:8501   # optional 2nd arg: chromium executable
```

## Rebuild

`assets/final_review_template_24_slides.pptx` is the template with slides duplicated (a second literature-survey
slide, five more outcome slides of which four hold the dashboard screenshots, a second results-and-outcomes slide and
a references slide). The builder fills it:

```bash
python presentation/build_final_review.py presentation/assets/final_review_template_24_slides.pptx \
    presentation/Final_Review_S_K_Sricharan_25MML1010.pptx presentation/assets/vit_chennai_15_logo.png
```

Requires `python-pptx` and `Pillow`. The combined VIT Chennai / 15-years logo is cropped from the Review-II deck.
