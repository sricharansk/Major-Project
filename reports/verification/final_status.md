# Final status

Last updated: 2026-10-21 08:25 IST / 02:55 UTC (after the real-data run on the workstation, the SUMO testbed
audits in the development container, `progress.md` Milestones 4-6, and the final-review deck in `presentation/`). Statuses follow `progress.md`; evidence paths are in
this repository unless marked "workstation".

| Component | Status | Evidence | Notes |
|---|---|---|---|
| Data audit and provenance | VERIFIED | `reports/data_audit/source_inventory.csv`, `data/manifests/` (workstation fetch logs) | server-side identity and date-range audit before every download |
| Raw downloads | VERIFIED (workstation) | fetch logs (workstation), `progress.md` Milestone 2 | speeds 2026-01-01..10-20, links, weather, collisions, events, volume, 311, OSM, embedding model, 14 knowledge documents |
| Preprocessing, splits, leakage tests | VERIFIED | `reports/data_audit/speeds_preprocessing.json`, `artifacts/models/*/split_manifest.json`, `tests/leakage` | 990,226 valid rows, 19 gridded links, observed fraction 0.611; 16 links modelled (train coverage >= 0.5) |
| Graph + PyG Temporal signal | PARTIAL | `reports/data_audit/graph_validation.json`, `graph_edges.csv`, `artifacts/models/proposed-*/feature_schema.json` | real graph is sparse by nature of the DOT link set: 26 nodes, 16 edges, 6 isolated; three rules documented |
| Baselines and proposed model | VERIFIED | `reports/experiments/forecast_metrics.csv`, `artifacts/models/*/run_info.json` | operational test MAE proposed 4.773/5.331/6.155 mph (GRU 4.715/5.373/6.174); trained under the recorded 4,096-windows-per-epoch budget, seed 42 |
| Multi-seed study (deep forecasters) | VERIFIED (workstation, 2026-10-21) | `reports/experiments/multi_seed_summary.csv`, `multi_seed_metrics.csv`, `artifacts/models/multi_seed_runs.json`, paper Table `tab:multiseed` | 9 runs (proposed / GRU / temporal Transformer x seeds 42, 1, 2) on the RTX 4050; seed-mean MAE proposed 4.69/5.34/6.15, GRU 4.67/5.37/6.18, Transformer 4.72/5.38/6.23; proposed lower than the Transformer at every horizon and the GRU at 30/60 min (bootstrap intervals exclude zero), GRU lower at 15 min; 3 seeds only. The proposed model is not bit-reproducible on GPU at a fixed seed (GATv2 scatter); GRU and Transformer are |
| Ablations | VERIFIED | `reports/experiments/ablation_metrics.csv` | gate +0.067 [0.048, 0.086]; weather -0.046 [-0.069, -0.021] (negative result); 311 +0.014; events/incidents NOT_APPLICABLE on the operational track |
| Conformal calibration | VERIFIED | `reports/experiments/uncertainty_metrics.csv`, `artifacts/calibration/` | coverage 0.909/0.907/0.903; congested 0.798/0.794/0.757 (limitation 10); gate defers ~26 % |
| Explanations of the trained model | VERIFIED | `artifacts/explanations/explanations_summary.json`, `neighbour_removal.csv`, `temporal_window_sensitivity.csv` | exact grouped KernelSHAP on proposed-20261020T201110-0e333f; eligibility rule after the first pass hit a dark feed |
| Knowledge corpus + FAISS retrieval | VERIFIED | `artifacts/retrieval/retrieval_eval.json`, `knowledge/indexes/index_manifest.json` | 15 documents, 1,633 chunks; Recall@8 0.818, MRR 0.702, status accuracy 0.964 on project-drafted labels |
| LLM (Ollama qwen2.5:7b) | VERIFIED | `reports/experiments/llm_calls.csv`, `artifacts/agent_traces/` | two passes (2026-10-20; 2026-10-21 after the simulation-gate correction): 24/24 schema-valid structured responses, all monitor_only; 15.3-125.5 s per call (17.6-51.8 s in the second pass) on the workstation |
| LangGraph workflow + safety constraints | VERIFIED | `reports/experiments/advisory_metrics.csv`, `tests/safety` | 19 runs per pass, identical decisions in both passes: DEFER_DATA / DEFER_UNCERTAINTY / DEFER_EVIDENCE / REJECT_CONSTRAINT / PENDING_HUMAN_REVIEW reached; SIMULATION_PASSED path not reached by a real advisory (LLM chose monitor_only); on a testbed without admissible demand a signal-change candidate now ends in ERROR_TOOL (NOT_EVALUATED) |
| SUMO/TraCI runs and protected controller | VERIFIED (runs) | `reports/experiments/simulation_metrics.csv` (45 runs), `simulation_demand_selection_*.csv` (30 runs), `simulation_testbed_audit.json` | corridor 82 edges, 22 signals; rebuilt in the container and reproduced exactly; TraCI wrapper now uses the active (re-timed) program |
| Paired controller comparison | PARTIAL: first comparison SUPERSEDED, corrected comparison NOT RUN | `simulation/scenarios/demand_selection_*.json` (3 corrected protocols), `simulation_testbed_audit_v4_*.json`, `simulation_turnlane_check.json`, paper Tables VII-VIII | every corrected protocol fails the preregistered baseline test; with 2025 two-direction counts the mapped link runs at 5.8 mph simulated vs 10.95 mph observed; protocol v5 split calibration (workstation, 2026-10-23) reaches at most 8.10 mph at the largest preregistered green factor (2.5), 2.85 mph short of the 1.5 mph tolerance, so no factor is selected and the comparison stays NOT RUN (`split_calibration_v5_*.json`, Milestone 11); rule not relaxed |
| API + Postgres job queue + worker | VERIFIED (software) | `tests/integration/test_api.py`, `test_db.py`, `reports/verification/api_smoke.json`, `db_smoke.json` | |
| Dashboard | VERIFIED (software) | `reports/verification/dashboard_smoke.json` | |
| MLflow tracking + export | VERIFIED | `reports/verification/mlflow_runs.json` (workstation export) | |
| Docker packaging | VERIFIED (workstation) | `reports/verification/docker_smoke.json` | compose build OK, 3 images 4.67 GB; the development container cannot build images |
| Paper | VERIFIED (draft complete) | `paper/main.pdf` (10 pages, rebuilt 2026-10-21), `paper/tables/*.tex`, `reports/verification/paper_claims.csv` (C01-C28) | every results/discussion/limitations/conclusion statement written from artifacts; 26/26 references CHECKED; author block has the student; co-authors and order still to confirm |
| Final review presentation | VERIFIED | `presentation/Final_Review_S_K_Sricharan_25MML1010.pptx` (25 slides, VIT template) and PDF | built from committed result files by `presentation/build_final_review.py`; section 9 is results and outcomes with the three-seed table (no Gantt chart); slides 17-21 are dashboard screenshots (REPLAY/SIMULATION; forecast and traffic map captured on the workstation 2026-10-23) plus the v5 split-calibration chart (NOT RUN outcome) |

Open items (need the authors or the workstation):
1. Paper: author block confirmed by the student on 2026-10-21 (S K Sricharan; Dr. R. Srinivasa Perumal, guide). The
   IEEE Word version is `paper/ieee_conference_paper.docx` (built by `make paper-docx`); `paper/main.tex` carries the
   same author block.
2. Simulation: recent two-direction counts are now in use (2025). An admissible testbed needs signal timing that
   matches reality: either calibrate splits and 25 mph progression to the observed 10.95 mph PM-peak speed (a
   calibration decision for the authors) or obtain NYC DOT timing plans; only then can `simulation evaluate` and an
   advisory reaching the simulation gate be run.
   Protocol v5 (`split_calibration`, 2026-10-21) is prepared for the workstation: the corridor green share of the Webster
   plan is scaled by one factor chosen so that the fixed-time baseline reproduces the observed 10.95 mph on link 4456494,
   subject to the unchanged admissibility rule (`docs/laptop_run.md` section 6). NOT RUN until the workstation runs it;
   if it runs, the comparison is reported as a calibrated scenario testbed, not a digital twin.
   **Run on the workstation 2026-10-23 (Milestone 11): NOT RUN.** No factor in the preregistered grid 1.0-2.5 reaches the
   target: speed rises monotonically from 5.82 to 8.10 mph, factors 2.0 and 2.5 are admissible, the closest (2.5) is
   2.85 mph short of 10.95 mph against a 1.5 mph tolerance, so no program was selected and `select-demand`,
   `simulation evaluate`, the agent re-run, `report export` and `paper sync` did not run. The rule was not relaxed. The
   next step is a decision for the authors: a new preregistered protocol (v6) with a wider factor grid and/or offset
   (progression) calibration, NYC DOT timing plans, or closing the comparison as NOT RUN. Network provenance deviation
   of that run: limitation 26.

3. DONE 2026-10-21: `agents evaluate` re-run on the workstation against the corrected simulation gate (same 19 decisions;
   the LLM again chose monitor_only, so the gate was not reached).
5. DONE 2026-10-21: multi-seed study (seeds 42, 1, 2 for proposed, GRU and temporal Transformer; nine GPU runs on the
   workstation). Seed-mean test MAE proposed 4.69/5.34/6.15 mph, GRU 4.67/5.37/6.18, temporal Transformer 4.72/5.38/6.23;
   the proposed model is 0.03-0.08 mph below the Transformer at every horizon and below the GRU at 30/60 min (day-block
   bootstrap intervals exclude zero), the GRU is better at 15 min. Three seeds only; reported as small, not decisive.
4. Superseded runs (ablation bootstrap unit error, first agents pass) stay on the workstation (`progress.md` Milestone 3).

Software tests: 82 collected (unit, leakage, safety, PostGIS and SUMO integration, e2e). GitHub Actions run 65 on main
354106e (PR #21 merged, 2026-10-21 10:09 UTC, PostGIS service container, SUMO 1.28, CPU torch) passed; re-verified in the
development container on 2026-10-23: 80 passed, the two PostGIS tests need the Postgres service and ran only in CI;
lint clean after removing two unused variables (no behaviour change).
