# Final status

Last updated: 2026-10-21 07:35 IST / 02:05 UTC (after the real-data run on the workstation, the SUMO testbed
audit in the development container, `progress.md` Milestone 4, and the final-review deck in `presentation/`). Statuses follow `progress.md`; evidence paths are in
this repository unless marked "workstation".

| Component | Status | Evidence | Notes |
|---|---|---|---|
| Data audit and provenance | VERIFIED | `reports/data_audit/source_inventory.csv`, `data/manifests/` (workstation fetch logs) | server-side identity and date-range audit before every download |
| Raw downloads | VERIFIED (workstation) | fetch logs (workstation), `progress.md` Milestone 2 | speeds 2026-01-01..10-20, links, weather, collisions, events, volume, 311, OSM, embedding model, 14 knowledge documents |
| Preprocessing, splits, leakage tests | VERIFIED | `reports/data_audit/speeds_preprocessing.json`, `artifacts/models/*/split_manifest.json`, `tests/leakage` | 990,226 valid rows, 19 gridded links, observed fraction 0.611; 16 links modelled (train coverage >= 0.5) |
| Graph + PyG Temporal signal | PARTIAL | `reports/data_audit/graph_validation.json`, `graph_edges.csv`, `artifacts/models/proposed-*/feature_schema.json` | real graph is sparse by nature of the DOT link set: 26 nodes, 16 edges, 6 isolated; three rules documented |
| Baselines and proposed model | VERIFIED | `reports/experiments/forecast_metrics.csv`, `artifacts/models/*/run_info.json` | operational test MAE proposed 4.773/5.331/6.155 mph (GRU 4.715/5.373/6.174); trained under the recorded 4,096-windows-per-epoch budget, one seed |
| Ablations | VERIFIED | `reports/experiments/ablation_metrics.csv` | gate +0.067 [0.048, 0.086]; weather -0.046 [-0.069, -0.021] (negative result); 311 +0.014; events/incidents NOT_APPLICABLE on the operational track |
| Conformal calibration | VERIFIED | `reports/experiments/uncertainty_metrics.csv`, `artifacts/calibration/` | coverage 0.909/0.907/0.903; congested 0.798/0.794/0.757 (limitation 10); gate defers ~26 % |
| Explanations of the trained model | VERIFIED | `artifacts/explanations/explanations_summary.json`, `neighbour_removal.csv`, `temporal_window_sensitivity.csv` | exact grouped KernelSHAP on proposed-20261020T201110-0e333f; eligibility rule after the first pass hit a dark feed |
| Knowledge corpus + FAISS retrieval | VERIFIED | `artifacts/retrieval/retrieval_eval.json`, `knowledge/indexes/index_manifest.json` | 15 documents, 1,633 chunks; Recall@8 0.818, MRR 0.702, status accuracy 0.964 on project-drafted labels |
| LLM (Ollama qwen2.5:7b) | VERIFIED | `reports/experiments/llm_calls.csv`, `artifacts/agent_traces/` | 12/12 schema-valid structured responses; 15.9-125.5 s per call on the workstation |
| LangGraph workflow + safety constraints | VERIFIED | `reports/experiments/advisory_metrics.csv`, `tests/safety` | 19 runs: DEFER_DATA / DEFER_UNCERTAINTY / DEFER_EVIDENCE / REJECT_CONSTRAINT / PENDING_HUMAN_REVIEW reached; SIMULATION_PASSED path not reached by a real advisory (LLM chose monitor_only); on a testbed without admissible demand a signal-change candidate now ends in ERROR_TOOL (NOT_EVALUATED) |
| SUMO/TraCI runs and protected controller | VERIFIED (runs) | `reports/experiments/simulation_metrics.csv` (45 runs), `simulation_demand_selection_*.csv` (30 runs), `simulation_testbed_audit.json` | corridor 82 edges, 22 signals; rebuilt in the container and reproduced exactly; TraCI wrapper now uses the active (re-timed) program |
| Paired controller comparison | PARTIAL: first comparison SUPERSEDED, corrected comparison NOT RUN | `simulation/scenarios/demand_selection_netconvert_guess.json`, `demand_selection_webster_retimed.json`, paper Tables VII-VIII | 2026-10-20 runs let SUMO re-route half the mainline off West St and used a 0.2 m entry stub; corrected testbed (fixed routes, ATR 1,389 veh/h) fails its preregistered baseline test with netconvert programs (17.7 % unfinished) and Webster re-timed programs (4.3 %; rule 1 %); rule not relaxed |
| API + Postgres job queue + worker | VERIFIED (software) | `tests/integration/test_api.py`, `test_db.py`, `reports/verification/api_smoke.json`, `db_smoke.json` | |
| Dashboard | VERIFIED (software) | `reports/verification/dashboard_smoke.json` | |
| MLflow tracking + export | VERIFIED | `reports/verification/mlflow_runs.json` (workstation export) | |
| Docker packaging | VERIFIED (workstation) | `reports/verification/docker_smoke.json` | compose build OK, 3 images 4.67 GB; the development container cannot build images |
| Paper | VERIFIED (draft complete) | `paper/main.pdf` (10 pages, rebuilt 2026-10-21), `paper/tables/*.tex`, `reports/verification/paper_claims.csv` (C01-C28) | every results/discussion/limitations/conclusion statement written from artifacts; 24/24 references CHECKED; author block has the student; co-authors and order still to confirm |
| Final review presentation | VERIFIED | `presentation/Final_Review_S_K_Sricharan_25MML1010.pptx` (19 slides, VIT template) and PDF | built from committed result files by `presentation/build_final_review.py`; rebuild reproduces it |

Open items (need the authors or the workstation):
1. Paper: confirm co-authors and author order (the student is filled in).
2. Simulation: an admissible testbed needs reviewed NYC DOT signal timing plans for West St and recent two-direction
   counts (or an explicit, documented decision by the authors to change the preregistered rule); only then can
   `simulation evaluate` and an advisory reaching the simulation gate be run.
3. Re-run `agents evaluate` on the workstation so the agent traces reflect the corrected simulation gate.
4. Superseded runs (ablation bootstrap unit error, first agents pass) stay on the workstation (`progress.md` Milestone 3).

Software tests: 66 passed in the development container on 2026-10-21 (unit, leakage, safety, PostGIS and SUMO
integration, e2e).
