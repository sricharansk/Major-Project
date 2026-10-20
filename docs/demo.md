# Demonstration sequence

1. `streamlit run src/smartcity/dashboard/app.py` -> **Data audit**: source inventory and verified ranges.
2. **Multi-horizon forecast** (REPLAY badge): pick a link and test-partition origin; observed history, 15/30/60-min forecasts, conformal intervals, source timestamp and data age.
3. **Explainability**: grouped SHAP of the proposed model for alerts; neighbour and temporal sensitivity.
4. **Evidence retrieval**: query the FAISS index; INSUFFICIENT_EVIDENCE for out-of-scope queries.
5. **Agent trace & advisory**: LLM candidate, constraint table, SUMO comparison, decision; a DEFER and a REJECT case.
6. Record a human review through `POST /advisories/{id}/review` (simulation-only approval).
7. **SUMO comparisons** (SIMULATION badge) and **Experiment results**; MLflow UI: `mlflow ui --backend-store-uri sqlite:///mlflow.db`.
8. Paper tables: `python -m smartcity.cli paper sync` then compile `paper/main.tex`.
9. Finish on **Limitations & model card**.
