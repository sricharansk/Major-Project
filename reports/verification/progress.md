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
- Speeds Manhattan 2026-07-01..2026-10-20: re-run OK, 793,971 rows in 27 page files (~52.4k rows per full week).
- Events: current 9,137 rows, historical 116,480 rows (since 2025-06-01). Volume Manhattan: 2024 21,772; 2025 18,048;
  2026 672. 311 Manhattan 2026 (filtered complaint types): ~7k-12.5k per month, Oct 1-20 4,204. OSM: manhattan_major
  22.1 MB, west_st_corridor 2.1 MB (overpass-api.de). all-MiniLM-L6-v2: 11 files, model.safetensors 90.9 MB.
- Knowledge documents (5 FHWA/MUTCD): FAILED with HTTP 406 because the downloader sent `Accept: application/json`;
  fixed (`cmd_url` now sends a browser-style Accept header) and queued for re-download.
- Jan-Jul 2026 speeds backfill: running.
- Workstation runtime: Python 3.12.10, torch 2.11.0+cu128 (CUDA on RTX 4050), torch_geometric 2.8.1,
  torch-geometric-temporal 0.56.2, eclipse-sumo 1.28.0 installed outside the repo path (Windows 260-char path limit),
  Ollama + qwen2.5:7b. No PostgreSQL/PostGIS or Docker on the workstation: DB-backed stages stay in the container.
- Pipeline stages on real data: NOT_STARTED (guide: `docs/laptop_run.md`, runner: `scripts/run_real_pipeline.py`).

### Milestone 2b: first real-data pipeline passes (workstation)
- `data preprocess` (14.6 s): 1,968,303 raw rows; 978,018 with `speed <= 0` treated as missing; 59 above the speed
  cap; 990,226 valid rows over 26 links, 2026-01-01T05:03Z to 2026-10-20T03:58Z; 5-minute grid 84,084 steps x 19
  links (train-coverage eligibility), observed fraction 0.611.
- `graph build`, endpoint rule only (PR #3 code): 26 nodes, 4 edges, 20 isolated. With the corridor rule (PR #4):
  26 nodes, 5 edges (4 endpoint, 1 corridor), 18 isolated, 88 candidate pairs audited. Cause found from the
  audit: DOT `link_points` polylines stop short of the named link ends (e.g. "FDR S 63rd - 25th St" is 1.5 km of
  geometry for a 3 km segment and ends 1,509 m before "FDR S 25th St - Catherine Slip" starts), and one chain
  link ("12th ave @ 45th - 11 ave ganservoort st") carries no direction token. A third, named-endpoint rule was
  added (this PR); the workstation reruns from `graph build`.
- First training attempt ran on the CPU (`configs/training.yaml` had `device: cpu` and the runner never moved
  tensors): ~9 min per GRU epoch. FIXED: `device: auto` resolves to CUDA when available, tensors and model move to
  the resolved device, the resolved device and cuDNN state are recorded in each run config and `run_info.json`.
  A reproducible process crash at exit (0xC0000409, GRU + cuDNN on Windows/CUDA 12.8/torch 2.11) is avoided by
  disabling cuDNN for GRU runs on CUDA only. Unit/leakage/safety/e2e: 41 passed on the workstation with the e2e
  test training on the RTX 4050; 43 passed in the container after the graph change.
- Docker: Dockerfiles fixed (torch-geometric-temporal installed `--no-deps`; `xgboost-cpu` instead of the CUDA
  wheel). `docker compose build` succeeded on the workstation (3 images, 4.67 GB) and `verify smoke` there
  reported api/db/dashboard/docker OK. The workstation's smoke JSON files are not yet in the repository: its `git
  push` fails for lack of a GitHub sign-in on that machine (owner asked to sign in once), so the container-side
  `docker_smoke.json` (BLOCKED) remains the committed evidence until then.

### Milestone 1b: service smoke checks (cloud container)
- `verify smoke`: API endpoints (live, sources, road-links, experiments, evidence; auth 401; deployment approval
  422) OK; Postgres/PostGIS upsert, spatial query and job-queue round trip OK; Streamlit headless start OK
  (health + index 200). Docker: compose config OK; `docker compose build` BLOCKED (see below). Evidence files:
  `reports/verification/{api,db,dashboard,docker}_smoke.json`.
- Paper skeleton compiles to a 5-page PDF with generated NOT RUN tables (`paper/main.pdf`).

### Open blockers
- Docker Compose build: BLOCKED. Docker Hub returned HTTP 429 for `python:3.12-slim` (mirror.gcr.io works and the
  base image is now a build arg), but the build container cannot reach deb.debian.org or download.pytorch.org
  under the environment's network policy, and ghcr.io/mlflow is denied (403). To be built on the workstation.
- Bibliography: 23 entries checked against publisher records (`paper/REFERENCES_STATUS.md`); johnson2019faiss DOI string still to confirm on IEEE Xplore (search result did not display it).
