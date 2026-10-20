# API

Start: `uvicorn smartcity.api.app:app --port 8000` and the worker `python -m smartcity.api.worker`.
Mutating endpoints require `Authorization: Bearer $API_AUTH_TOKEN` (disabled if the variable is unset).
Every response carries `run_id, mode, data_as_of, generated_at, source_status, model_version, artifact_status, warnings`.

| Method | Path | Notes |
|---|---|---|
| GET | /health/live | process alive |
| GET | /health/ready | 503 unless DB, model, knowledge index, SUMO and LLM are available |
| GET | /sources/status | source inventory with freshness |
| GET | /road-links, /road-links/{id}, /road-links/{id}/observations | graph nodes; PostGIS observations |
| POST | /forecasts | REPLAY forecast with conformal intervals for a link/origin |
| GET | /forecasts/{id} | persisted forecast |
| POST | /explanations | queued job (grouped KernelSHAP) |
| GET | /explanations/{id} | stored explanation |
| POST | /retrieval/search | FAISS evidence + INSUFFICIENT_EVIDENCE status |
| POST | /advisories | queued LangGraph run |
| GET | /advisories/{id} | full decision trace |
| POST | /simulations | queued SUMO runs |
| GET | /jobs/{id} | job status, stdout/stderr, exit code, runtime |
| POST | /advisories/{id}/review | HUMAN_APPROVED_FOR_SIMULATION / HUMAN_REJECTED / REQUEST_REVISION |
| GET | /experiments, /evidence/status | result CSVs and evidence registry |
