# Final status

Last updated: 2026-10-28 19:50 UTC (protocol v6 calibration passed and the corrected controller comparison ran on the workstation; LIVE mode implemented, NOT RUN; see `progress.md` Milestones 13-14). Earlier
baseline: 2026-10-21 02:55 UTC after the real-data run on the workstation, the SUMO testbed audits and the final-review deck. Statuses follow `progress.md`; evidence paths are in
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
| LLM (Ollama qwen2.5:7b) | VERIFIED | `reports/experiments/llm_calls.csv`, `artifacts/agent_traces/` | three passes (2026-10-20; 2026-10-21 after the simulation-gate correction; 2026-10-28 on the calibrated testbed): 36/36 schema-valid structured responses, all monitor_only; 15.3-125.5 s per call (18-54 s in the later passes) on the workstation |
| LangGraph workflow + safety constraints | VERIFIED | `reports/experiments/advisory_metrics.csv`, `tests/safety` | 19 runs per pass, identical decisions in all three passes: DEFER_DATA / DEFER_UNCERTAINTY / DEFER_EVIDENCE / REJECT_CONSTRAINT / PENDING_HUMAN_REVIEW reached; SIMULATION_PASSED path not reached by a real advisory (LLM chose monitor_only); the simulation gate is admissible since 2026-10-28 but no real advisory proposed a signal change to reach it |
| SUMO/TraCI runs and protected controller | VERIFIED (runs) | `reports/experiments/simulation_metrics.csv` (45 runs, 2026-10-28), `simulation_split_calibration_v6_*.csv` (75 runs), `simulation_demand_selection_v6_*.csv` (15 runs), `simulation_testbed_audit.json` | corridor 82 edges, 22 signals; v6 calibration selected 90 s cycle / green factor 1.5 / 25 mph offsets: 10.08 vs 10.95 mph observed, 0 unfinished, 0 teleports; TraCI wrapper uses the active (calibrated) program |
| Paired controller comparison | RUN 2026-10-28 on the calibrated testbed (PARTIAL: actuated uncalibrated, side demand 0) | `reports/experiments/simulation_metrics.csv` (45 runs, seeds 1-5, 0 teleports), `simulation/scenarios/split_calibration_v6_*.json`, `demand_selection.json`, paper Tables `tab:sim`, `tab:splitcal6` | matched pair fixed time vs forecast rule on the v6 plan: routine peak identical (271.6 s, 4,975 trips); event surge 450.2 -> 426.0 s (-5.4 %), completed 5,720 -> 5,910, unfinished 540 -> 350; incident 465.9 -> 443.9 s (-4.7 %), 5,725 -> 5,919, 536 -> 341; same direction in every seed. Actuated runs on netconvert's actuated programs (uncalibrated reference, not ranked). The 2026-10-20 comparison stays SUPERSEDED; v5 reached 8.10 mph and selected nothing. SIMULATED result on a calibrated scenario testbed (not NYC DOT timing), not a real-world gain |
| API + Postgres job queue + worker | VERIFIED (software) | `tests/integration/test_api.py`, `test_db.py`, `reports/verification/api_smoke.json`, `db_smoke.json` | |
| Dashboard | VERIFIED (software) | `reports/verification/dashboard_smoke.json` | |
| Live observational run (LIVE mode) | IMPLEMENTED (PR #28 merged), NOT RUN | `src/smartcity/live/pipeline.py`, `tests/unit/test_live.py` (8 tests incl. an end-to-end batch with a stub model), `docs/laptop_run.md` section 8 | pull -> forecast (saved before the target) -> score later; dashboard page "Live monitoring", `GET /forecasts/live/*`, paper Table `tab:live` (NOT RUN placeholder); needs the public feed, so it runs on the workstation; limitation 27 |
| MLflow tracking + export | VERIFIED | `reports/verification/mlflow_runs.json` (workstation export) | |
| Docker packaging | VERIFIED (workstation) | `reports/verification/docker_smoke.json` | compose build OK, 3 images 4.67 GB; the development container cannot build images |
| Paper | VERIFIED (draft complete) | `paper/main.pdf` (10 pages, rebuilt 2026-10-21), `paper/tables/*.tex`, `reports/verification/paper_claims.csv` (C01-C48) | every results/discussion/limitations/conclusion statement written from artifacts; 26/26 references CHECKED; author block has the student; co-authors and order still to confirm |
| Final review presentation | VERIFIED | `presentation/Final_Review_S_K_Sricharan_25MML1010.pptx` (25 slides, VIT template) and PDF | built from committed result files by `presentation/build_final_review.py`; section 9 is results and outcomes with the three-seed table (no Gantt chart); slides 17-21 are dashboard screenshots (REPLAY/SIMULATION; forecast and traffic map captured on the workstation 2026-10-23, the rest in the development container 2026-10-28) plus the corrected 45-run comparison chart (SIMULATION, calibrated scenario testbed); LIVE mode not shown (NOT RUN) |

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
   **Decision 2026-10-25: protocol v6 preregistered (development container), NOT RUN.** The authors chose a second
   preregistered calibration over closing the comparison or waiting for NYC DOT timing plans. `split_calibration` in
   `configs/simulation.yaml` now fixes a grid of common cycle (Webster per-signal cycles, 90 s, 120 s) x corridor green
   factor (1.0, 1.5, 2.0, 2.5, 3.0) x progression offsets (none, 25 mph along the southbound chain, only with a common
   cycle): 25 cells x 3 development seeds = 75 fixed-time runs; the admissibility rule and the 10.95 +- 1.5 mph target
   are unchanged, ties go to the least intervention (`src/smartcity/simulation/calibrate.py`, `docs/laptop_run.md`
   section 7, 14 unit tests and 2 SUMO tests). Paper Table `tab:splitcal6` is a NOT RUN placeholder until the
   workstation runs it; any selected program is a calibrated scenario testbed, not NYC DOT timing.

3. DONE 2026-10-21: `agents evaluate` re-run on the workstation against the corrected simulation gate (same 19 decisions;
   the LLM again chose monitor_only, so the gate was not reached).
5. DONE 2026-10-21: multi-seed study (seeds 42, 1, 2 for proposed, GRU and temporal Transformer; nine GPU runs on the
   workstation). Seed-mean test MAE proposed 4.69/5.34/6.15 mph, GRU 4.67/5.37/6.18, temporal Transformer 4.72/5.38/6.23;
   the proposed model is 0.03-0.08 mph below the Transformer at every horizon and below the GRU at 30/60 min (day-block
   bootstrap intervals exclude zero), the GRU is better at 15 min. Three seeds only; reported as small, not decisive.
4. Superseded runs (ablation bootstrap unit error, first agents pass) stay on the workstation (`progress.md` Milestone 3).

Software tests: 95 collected on this branch (unit, leakage, safety, PostGIS and SUMO integration, e2e): 82 at main
354106e (GitHub Actions run 65, PR #21, 2026-10-21 10:09 UTC, PostGIS service container, SUMO 1.28, CPU torch, passed),
84 at main ab95bca (PR #22 added two paper-table tests), 95 with the eleven protocol v6 tests (2026-10-25). Re-verified in
the development container on 2026-10-23 (80 passed; the two PostGIS tests need the Postgres service and ran only in CI)
and on 2026-10-25 (lint clean; unit, leakage, safety, e2e and SUMO suites passed before and after the v6 change).
