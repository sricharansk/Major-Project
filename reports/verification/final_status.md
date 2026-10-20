# Final status

Last updated: 2026-10-21 (after the complete real-data run on the workstation, including the 45-run SUMO
controller comparison). Statuses follow `progress.md`; evidence paths are in this repository unless marked
"workstation".

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
| LangGraph workflow + safety constraints | VERIFIED | `reports/experiments/advisory_metrics.csv`, `tests/safety` | 19 runs: DEFER_DATA / DEFER_UNCERTAINTY / DEFER_EVIDENCE / REJECT_CONSTRAINT / PENDING_HUMAN_REVIEW reached; SIMULATION_PASSED path not reached by a real advisory (LLM chose monitor_only) |
| SUMO/TraCI protected controller | VERIFIED (run); result INCONCLUSIVE | `reports/experiments/simulation_metrics.csv` (45 runs OK), `simulation/scenarios/prepared.json`, `scenarios.json`, `simulation/outputs/*/result.json` | corridor 82 edges, 22 signals, 2 mapped DOT links (dead feeds / BBT approach: transfer demonstration); declared demand gridlocks the corridor under every controller, so no controller ranking is claimed (limitation 24) |
| API + Postgres job queue + worker | VERIFIED (software) | `tests/integration/test_api.py`, `test_db.py`, `reports/verification/api_smoke.json`, `db_smoke.json` | |
| Dashboard | VERIFIED (software) | `reports/verification/dashboard_smoke.json` | |
| MLflow tracking + export | VERIFIED | `reports/verification/mlflow_runs.json` (workstation export) | |
| Docker packaging | VERIFIED (workstation) | `reports/verification/docker_smoke.json` | compose build OK, 3 images 4.67 GB; the development container cannot build images |
| Paper | VERIFIED (draft complete) | `paper/main.pdf`, `paper/tables/*.tex`, `reports/verification/paper_claims.csv` | every results/discussion/limitations/conclusion statement written from artifacts and listed in paper_claims.csv; author names and one DOI string remain for the authors |

Open items: johnson2019faiss DOI string unconfirmed (`paper/REFERENCES_STATUS.md`); author block of the paper. Superseded runs (ablation bootstrap unit error, first agents pass) are kept on the
workstation and described in `progress.md` Milestone 3.
