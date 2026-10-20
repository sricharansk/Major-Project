# Progress log

Statuses: NOT_STARTED / IMPLEMENTED_UNTESTED / VERIFIED / PARTIAL / BLOCKED / FAILED / NOT_APPLICABLE.
"VERIFIED" means the command was executed and its artifact exists in this repository or on the workstation run.

## 2026-10-20

### Milestone 0: feasibility and environment
- Data feasibility audit (`fetch.py audit`): VERIFIED on the workstation. Speeds dataset i4gi-tjb9 has continuous
  2024-2026 history (Case A); collisions latest crash_date 2026-06-11 (retrospective only); events current feed +
  historical feed; 311 and volume present. `reports/data_audit/source_inventory.csv` is written by `data audit`.
- Cloud container: cannot reach NYC Open Data, Open-Meteo, Hugging Face or Docker Hub (network policy). All
  downloads and the LLM run on the workstation (Windows 11, RTX 4050, Python 3.12.10, Ollama 0.40.6). BLOCKED
  items are recorded in `overrides.json` with reasons.
- Python 3.12 and Ollama installed on the workstation with the owner's approval; `qwen2.5:7b` pulled (digest
  845dbda0ea48..., 4.68 GB, Q4_K_M); smoke test returned a response in 11.4 s with the model mostly on GPU.

### Milestone 1: software stack (cloud container)
- Configs/contracts, preprocessing, graph, features, models, training, calibration, explainability, knowledge/RAG,
  safety constraints, LLM client + batch executor, LangGraph workflow, SUMO runner, DB layer, API + worker,
  dashboard, CLI, audit, simulation pipeline, agent evaluation, reporting/export, paper tables, Docker files, CI:
  IMPLEMENTED and covered by tests.
- Tests executed in the container: 36 unit/leakage/safety, 7 integration (SUMO toy grid via TraCI, Postgres,
  API), 1 end-to-end software smoke test on a synthetic fixture (preprocess -> graph -> features -> baselines ->
  proposed -> ablation -> evaluate -> calibrate -> export): all pass. These verify software behaviour only; they
  produce no project results.
- Git: PR #1 was merged by the owner after its first commit; the remaining commits were rebased onto `main` and
  opened as PR #2 (draft).

### Milestone 2: real-data run (workstation, in progress)
- Downloaded: speed links (125, since 2026-09-20; full-year group-by timed out 6x), weather archive + historical
  forecast (HTTP 200), collisions Manhattan 2026 (Jan 917, Feb 947, Mar 1,011, Apr 1,059, May 1,155, Jun 210).
- Speeds Jul-Oct: first attempt FAILED with `http.client.IncompleteRead` (dropped connection, not retried by the
  downloader); downloader fixed to retry `HTTPException`/`OSError`; re-run resumes from saved pages.
- Pending: events, volume, 311, OSM (x2), sentence-transformer weights, knowledge documents; Jan-Jul speeds backfill.
- Pipeline stages on real data: NOT_STARTED (guide: `docs/laptop_run.md`, runner: `scripts/run_real_pipeline.py`).

### Open blockers
- Docker Compose build: BLOCKED (Docker Hub rate limit in the container).
- Bibliography DOI checks: NOT_STARTED (`paper/REFERENCES_STATUS.md`).
