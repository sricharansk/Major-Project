# Final review presentation

`Final_Review_S_K_Sricharan_25MML1010.pptx` is the M.Tech project work final-review deck, built on the VIT Chennai
final-review template (`assets/final_review_template.pptx`) with its slide order, headings and font rules. A PDF copy
is alongside it.

Every number in the deck was copied from a committed result file (`reports/experiments/*.csv`,
`reports/experiments/simulation_testbed_audit.json`, `reports/verification/final_status.md`) and checked against it;
the builder holds them as literals, so after any artifact change the literals must be re-checked and the deck rebuilt.
Simulation figures are SUMO outputs, not real-street measurements.

## Rebuild

`assets/final_review_template_19_slides.pptx` is the template with three slides duplicated (a second literature-survey
slide, a second outcome slide and a references slide). The builder fills it:

```bash
python presentation/build_final_review.py presentation/assets/final_review_template_19_slides.pptx \
    presentation/Final_Review_S_K_Sricharan_25MML1010.pptx presentation/assets/vit_chennai_15_logo.png
```

Requires `python-pptx` and `Pillow`. The combined VIT Chennai / 15-years logo is cropped from the Review-II deck.
