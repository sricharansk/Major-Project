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
Verification state: [reports/verification/final_status.md](reports/verification/final_status.md).

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

### Services

```bash
docker compose up --build            # postgres+postgis, api, worker, dashboard
# or locally
make api        # http://localhost:8000/docs
make worker
make dashboard  # http://localhost:8501
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

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
