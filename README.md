# Predictive Analytics for Smart City Infrastructure

Multi-horizon traffic congestion forecasting and explainable agentic signal advisory using spatiotemporal
transformers and retrieval-augmented generation. MTech final-year research prototype (Manhattan, NYC DOT
real-time speed links).

Everything in this repository runs on real, legally accessible public data; every reported number is produced by a
command in this README and traces to an artifact on disk (`reports/verification/evidence_registry.csv`). Outputs are
labelled **LIVE**, **REPLAY** or **SIMULATION**. The system never sends commands to real traffic infrastructure; the
advisory workflow ends at a simulation-only recommendation that a human reviews.

## What is in here

| Layer | Code | Output |
|---|---|---|
| Data ingestion with provenance | `src/smartcity/ingestion/` | `data/raw/<source>/*.json.gz`, `data/manifests/` |
| Timestamp-safe preprocessing, purged chronological splits | `src/smartcity/preprocessing/`, `features/` | `data/processed/` |
| Directed road-link graph + PyG Temporal signal | `src/smartcity/graph/` | `data/processed/graph_*.json`, `reports/data_audit/graph_validation.json` |
| Baselines and the context-gated GATv2-Transformer | `src/smartcity/models/`, `training/` | `artifacts/models/`, `reports/experiments/forecast_metrics.csv` |
| Split-conformal intervals with reliability gate | `src/smartcity/uncertainty/` | `artifacts/calibration/` |
| Grouped SHAP on the deployed model | `src/smartcity/explainability/` | `artifacts/explanations/` |
| FAISS + MiniLM retrieval over an allowlisted corpus | `src/smartcity/rag/`, `knowledge/` | `knowledge/indexes/`, `artifacts/retrieval/` |
| Ollama LLM (JSON-schema output) and LangGraph advisory workflow | `src/smartcity/agents/` | `artifacts/llm_requests/`, `reports/experiments/advisory_metrics.csv` |
| Deterministic safety constraints | `src/smartcity/safety/` | `tests/safety/` |
| SUMO/TraCI protected controller, matched-seed comparison | `src/smartcity/simulation/` | `simulation/`, `reports/experiments/simulation_metrics.csv` |
| FastAPI service, Postgres/PostGIS job queue, worker | `src/smartcity/api/`, `db/`, `migrations/` | `reports/verification/api_smoke.json` |
| Streamlit dashboard | `src/smartcity/dashboard/` | |
| MLflow tracking, evidence export, paper tables | `src/smartcity/reporting/`, `training/tracking.py` | `reports/verification/`, `paper/tables/` |

Design and interfaces: [docs/architecture.md](docs/architecture.md), [docs/api.md](docs/api.md),
[docs/data_dictionary.md](docs/data_dictionary.md), [docs/methodology.md](docs/methodology.md),
[docs/model_card.md](docs/model_card.md), [docs/demo.md](docs/demo.md). Known limits: [reports/limitations.md](reports/limitations.md).
Verification state: [reports/verification/final_status.md](reports/verification/final_status.md). Final review deck: [presentation/](presentation/).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m smartcity.cli doctor                         # writes reports/verification/environment.json
pytest -q tests/unit tests/leakage tests/safety        # software tests on synthetic fixtures
```

### Real data

```bash
python src/smartcity/ingestion/fetch.py audit                    # verifies dataset identity and observed date ranges
python src/smartcity/ingestion/fetch.py speed-links --since 2026-09-20
python src/smartcity/ingestion/fetch.py speeds --start 2026-01-01 --end 2026-10-20 --borough Manhattan
python src/smartcity/ingestion/fetch.py weather|collisions|events|volume|sr311|osm|hf-model
python scripts/run_real_pipeline.py                             # all stages, in order, with a stage log
```

Stage order and prerequisites (Ollama, SUMO, sentence-transformer weights) are in [docs/laptop_run.md](docs/laptop_run.md);
`make <target>` wraps each stage.

### Simulation testbed (SUMO 1.28.0; runs without the forecasting data)

```bash
python src/smartcity/ingestion/fetch.py osm --bbox 40.700,-74.020,40.737,-74.000 --name west_st_corridor --kind all
python src/smartcity/ingestion/fetch.py volume --start-year 2009 --boro Manhattan   # ATR counts for corridor demand
python src/smartcity/ingestion/fetch.py speed-links --since 2026-09-20 && python -m smartcity.cli graph build
python -m smartcity.cli simulation prepare        # netconvert, corridor, DOT->SUMO mapping, ATR demand
python -m smartcity.cli simulation select-demand  # preregistered baseline test; exits 1 (NOT_RUN) if no level passes
python -m smartcity.cli simulation evaluate       # controller comparison, only after a level was selected
python scripts/sim_testbed_audit.py               # route-choice and signal-capacity audit (2026-10-21 protocols)
python src/smartcity/ingestion/fetch.py counts --dataset classification --street-like "WEST ST"
python src/smartcity/ingestion/fetch.py speed-profile --link 4456494 --start 2026-04-01 --end 2026-10-20
python scripts/sim_testbed_audit.py --protocol v4_counts2025_webster_noturnlanes   # capacity + observed-speed check
python scripts/sim_turnlane_check.py              # with vs without OSM turn-lane restrictions
```

`fetch.py osm` falls back to the OSM editing API when Overpass is unreachable. Set `scenario.signal_timing` in
`configs/simulation.yaml` to `netconvert_guess` or `webster_retimed` and `route_choice` to `dynamic_insertion` to
reproduce the earlier protocols.

### Services

```bash
docker compose up --build            # postgres+postgis, api, worker, dashboard
# or locally
make api        # http://localhost:8000/docs
make worker
make dashboard  # http://localhost:8501
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

## Results of the real-data run (2026-10-20/21, workstation)

Every number is read from `reports/experiments/` and `artifacts/`; `python scripts/results_summary.py` prints them.
Full narrative: `paper/main.pdf`, `reports/verification/progress.md` (Milestone 3), `reports/limitations.md`.

* 26 Manhattan DOT links, 7 dead feeds, 16 modelled, 3 without test data; test 2026-09-06..10-20 (45 days,
  ~144k targets per horizon); all deep models trained under a recorded 4,096-windows-per-epoch budget; the three deep forecasters also over seeds 42/1/2.
* Test MAE (mph, 15/30/60 min): persistence 5.14/6.06/7.29, XGBoost 4.82/5.58/6.31, GRU 4.72/5.37/6.17,
  temporal Transformer 4.73/5.34/6.18, **proposed 4.77/5.33/6.15** (main run, seed 42).
* Three seeds (seed-mean MAE 15/30/60): proposed 4.69/5.34/6.15, GRU 4.67/5.37/6.18, temporal Transformer
  4.72/5.38/6.23; proposed lower than the Transformer at every horizon and than the GRU at 30/60 min by 0.03-0.08 mph
  (day-block bootstrap intervals exclude zero), GRU lower at 15 min; small and preliminary (3 seeds).
* Ablations (day-block bootstrap): no gate +0.067 [0.048, 0.086]; no 311 +0.014 [0.002, 0.026];
  **no weather -0.046 [-0.069, -0.021] (negative result)**.
* Conformal 90% intervals: coverage 0.91/0.91/0.90 overall, 0.80/0.79/0.76 under congestion; gate defers ~26%,
  retained MAE 3.72/4.38/5.25.
* Retrieval: 28 queries, Recall@8 0.818, MRR 0.702 (project-drafted labels). LLM agents (two passes): 24/24 schema-valid calls;
  per pass 3/3 fabricated citations without retrieval (all rejected), 0/9 with; constraints reject the unmapped link; the
  LLM chose monitor-only on the mapped corridor, so no advisory reached the simulation gate.
* SUMO: the first 45-run controller comparison (2026-10-20) is **superseded**. A testbed audit
  (`scripts/sim_testbed_audit.py`, 2026-10-21) found that its bare from/to flows let SUMO re-route at insertion
  (1,120 of 2,189 mainline vehicles sent off West Street) and that the NB flow was inserted on a 0.2 m stub edge.
  With fixed routes and a preregistered side-demand selection rule, **no demand level passes the testbed's own
  baseline test** under any corrected protocol: 2014 ATR count with netconvert or Webster programs, or 2025
  two-direction counts (2,510 NB / 2,444 SB veh/h) without OSM turn-lane restrictions. With the 2025 counts the
  mapped link runs at **5.8 mph in simulation vs 10.95 mph observed** in the weekday PM peak. The corrected controller
  comparison is **NOT RUN** and the advisory simulation gate returns NOT_EVALUATED
  (`reports/limitations.md` 16, 24; paper Table "SUMO testbed audit").

## Honesty rules this repository follows

* No synthetic or illustrative data is presented as a result; test fixtures are labelled as fixtures.
* Train/validation/calibration/test splits are chronological with purge gaps; scalers fit on train only; operational
  features use only data available at prediction time (311 with its declared 24 h lag, collisions and events only in
  the retrospective track).
* Explanations are computed on the trained proposed model, not a surrogate. Retrieved documents are untrusted text;
  constraints are enforced in code, never by the LLM.
* Simulation gains are reported with matched seeds and the scenario's declared assumptions; the testbed is not a
  calibrated digital twin.
* Anything not achieved is recorded as PARTIAL, BLOCKED or FAILED in `reports/verification/` rather than omitted.

## License

MIT (see `LICENSE`). Data sources carry their own terms (NYC Open Data, Open-Meteo, OpenStreetMap ODbL); see
`reports/data_audit/source_inventory.csv`.
