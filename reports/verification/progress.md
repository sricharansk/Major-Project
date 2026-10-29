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

### Milestone 2c: coverage audit and eligibility decision (workstation table, 2026-10-20 19:27 UTC)
- Per-link observed fraction of the 5-minute grid by split (train 2026-01-01..06-25, val ..08-08, calib ..09-06,
  test ..10-20): 10 links pass the 0.6 train-coverage rule; 6 links sit at 0.52-0.59 train coverage with 0.65-0.95
  later (West St S to BBT 0.52/0.66/0.57/0.77; BBT W 0.52; BBT E 0.54; QMT E 0.59; FDR S Catherine Slip-BKN Bridge
  0.57; FDR N-TBB E 0.55 then dead); 7 West Side links have no valid observation all year (dead feeds, 549k zero
  rows); Lincoln Tunnel E tubes and W centre tube < 3%. TBB W-FDR S has no data after 2026-05-29 and BQE N-MAN
  Bridge none after 2026-09-02.
- DECISION: `min_link_coverage` 0.6 -> 0.5 (train period only; recorded in `configs/data.yaml` and limitations 7c);
  per-link test support written by `evaluate forecasts` (`link_test_support_<track>.csv`, NOT_EVALUATED where a
  link has no test targets). Graph rule 3 reworked to use the names' entry/exit directions and a start-to-start
  distance cap because the polylines' end bearings are untrustworthy (FDR N Catherine Slip-25th -> 25th-63rd was
  still missed). The workstation reruns from `graph build`; the deep runs on the 10-link set are superseded.
- RAG on the real corpus (workstation, artifact pending push): index 82 s; 28 queries, 22 scored, recall@8 0.8125,
  MRR 0.684, SUPPORTED/INSUFFICIENT_EVIDENCE status accuracy 0.955; 6 queries skipped because the SUMO
  documentation pages were not downloaded on the workstation. `rag fetch-docs` (new) downloads the missing approved
  documents from the pinned v1_28_0 tag before `rag build`.
- SUMO (workstation): the West St corridor extracted from OSM was empty because netconvert drops street names by
  default; fixed on the workstation (`--output.street-names`, hard failure on an empty corridor): 82 edges, 22
  signals, 2 DOT links mapped. Those two links are a dead West Side feed (4616325) and the modelled West St S-BBT
  portal link (4456494), whose observations do not drive the declared scenarios, so the controller comparison is
  a transfer demonstration (limitations 7d).
- Two crash fixes (results folder created before the first RAG/SUMO write).

### Milestone 3: complete real-data run (workstation, 2026-10-20 19:38 UTC to 2026-10-20 21:28 UTC; SUMO still running)
Stage log: `reports/verification/stage_log.jsonl` (every stage rc=0 after the fixes below). Run on Windows 11, RTX 4050
(CUDA, torch 2.11.0+cu128), SUMO 1.28.0, Ollama qwen2.5:7b; `reports/verification/environment.json`.
- Data: 1,968,303 raw rows, 978,018 zero-speed, 59 above the plausibility bound, 990,226 valid; 84,084 grid steps,
  19 gridded links, observed fraction 0.611 (`reports/data_audit/speeds_preprocessing.json`). Eligibility (train
  coverage >= 0.5): 16 links (`link_coverage_operational.csv`); 4456450, 4456452 and 4616340 have no test targets
  (`link_test_support_operational.csv`: NOT_EVALUATED). `link_split_coverage.csv` is regenerated by
  `scripts/link_split_coverage.py` from those files (the first copy was written ad hoc under the 0.6 rule).
- Graph d8c69a468b82cbda: 26 nodes, 16 edges, 6 isolated (`graph_validation.json`, `graph_edges.csv`).
- DECISION (compute budget): `max_train_windows_per_epoch: 4096` for every deep model (fresh sample each epoch,
  early stopping patience 5, max 30 epochs, seed 42); recorded in each run's config.yaml and stated in the paper.
- Forecasts (operational test, 2026-09-06 09:00Z..10-20 04:00Z, n=144,217/144,213/144,205): MAE 15/30/60 min
  persistence 5.139/6.056/7.288; historical average 7.632/7.633/7.637; XGBoost 4.823/5.579/6.308; LightGBM
  4.873/5.599/6.315; GRU 4.715/5.373/6.174; temporal Transformer 4.733/5.338/6.184; proposed 4.773/5.331/6.155
  (`forecast_metrics.csv`). Retrospective proposed 4.666/5.355/6.126. Runs: proposed-20261020T201110-0e333f
  (14 epochs, best 8, val 5.388), gru-20261020T200131-e3eef3, temporal_transformer-20261020T200802-d8bdfb,
  proposed-20261020T210211-4a0685 (retrospective).
- Ablations (`ablation_metrics.csv`, 44 test days with a valid paired target, 1000 bootstrap resamples (code default)): no gate +0.067 [0.048, 0.086];
  no weather -0.046 [-0.069, -0.021] (NEGATIVE RESULT: weather features hurt); no infrastructure +0.014 [0.002,
  0.026]; no events / no incidents NOT_APPLICABLE on the operational track.
- DEFECT FOUND AND FIXED during the run: `evaluate ablations` cast epoch seconds straight to datetime64[D], so the
  "day-block" bootstrap resampled 12,601 five-minute origins as if they were days and its intervals were far too
  narrow. Fixed (`datetime64[s]` first), re-run; the superseded CSV is kept on the workstation as evidence.
- Calibration (`uncertainty_metrics.csv`, `artifacts/calibration/`): q = 12.13/13.47/14.77 mph on 102,301/102,299/102,302
  calibration residuals (15/30/60 min); test coverage 0.909/0.907/0.903; congested (<0.5 ratio) 0.798/0.794/0.757; rush hour
  0.938/0.934/0.926; wet 0.926/0.927/0.917. Gate at its configured operating point (width <= 38.10 mph, missing
  <= 0.34, age <= 20 min): deferral 25.5/25.7/26.1 %, retained MAE 3.717/4.381/5.250 (all: 4.773/5.331/6.155),
  retained coverage 0.948/0.939/0.930 (`deferral_tradeoff.csv`).
- Explanations (`artifacts/explanations/explanations_summary.json`, re-run after PR #8): 12 points (6 top drops, 6
  random) from 132,355 eligible of 201,616 test pairs; mean |SHAP| mph: own last 30 min 8.216, own 30-120 min 2.037,
  calendar 1.088, graph neighbours 0.518, weather 0.195, infrastructure 0.089; temporal window 120/60/30/15/5 min ->
  MAE 5.427/5.997/6.293/6.540/7.113; neighbour removal: 4616342 1.337 mph change, 4616333 0.905, 4616328 0.871,
  4456502 0.673, 4456494 0.0.
- DEFECTS FOUND: (a) the first explanation pass explained link 4616340 at an origin four weeks after its feed went
  dark (prediction -1.0 mph, no observed target); alert eligibility now requires raw observations at all 6 recent
  steps and an observed target (PR #8). (b) The batched edge-index cache was keyed on a data pointer; fixed to
  validate content (PR #8). The re-run neighbour-removal values are identical to the first pass, so the cache had not
  corrupted that run; the exact 0.0 for 4456494 is correct behaviour: its only in-edge comes from the dead feed
  4616325 (excluded from the features), so it has out-edges only and messages never reach it. `n_in_edges` /
  `n_out_edges` are now recorded per row.
- Retrieval (`artifacts/retrieval/retrieval_eval.json`, corpus 50ff3107ae21057d: 15 documents, 1,633 chunks, 171 over
  the encoder's 256-token window): 28/28 queries scored, Recall@8 0.818, MRR 0.702, status accuracy 0.964
  (labels drafted_by_project_unreviewed).
- Agents (`advisory_metrics.csv`, `artifacts/agent_traces/`, `llm_calls.csv`): 7 cases x policies = 19 runs; 12 LLM
  calls, 12/12 schema-valid, 1 attempt each, 15.9-125.5 s per call (first call cold). Stale data -> DEFER_DATA;
  wide interval and the rain period (44-46 mph > 38.1) -> DEFER_UNCERTAINTY; out-of-scope query -> DEFER_EVIDENCE.
  Without retrieval: 3/3 fabricated evidence ids, all rejected by the citation check; with retrieval 0/9. Routine
  rush hour (4616341, no reviewed mapping): REJECT_CONSTRAINT under every policy with constraints,
  PENDING_HUMAN_REVIEW without them. Mapped West St link (4456494): monitor_only under every policy ->
  PENDING_HUMAN_REVIEW; no signal change was proposed, so the simulation gate was never reached by a real advisory
  (SIMULATION_PASSED path exercised by tests only).
- DEFECT FOUND AND FIXED: the first `agents evaluate` pass reported rc=0 while every LLM case had ended in
  ERROR_TOOL (`KeyError: model_run_id`, a field the evaluation cases never set), so the LLM was never called; the
  forecast node now falls back to the calibrator's frozen model run id. The failed pass is kept on the workstation.
- SUMO (`simulation_metrics.csv`, 45 runs OK, 9,645 s wall time, pushed as 77175ff): corridor 82 edges, 22 signals, 25 side
  entries, 2 high-confidence DOT mappings, demand 1,200/150 vph declared (no ATR count matched). RESULT
  INCONCLUSIVE: oversaturated under every controller (per run: completed 1,003-3,441 vs unfinished 3,257-6,979,
  teleports 1,091-2,386; five-seed means in `paper/tables/simulation.tex`). Mean time loss per completed trip fixed/actuated/rule: routine 971.6/987.5/971.6 (rule
  inactive = fixed), surge 780.5/1118.4/739.0, incident 898.4/1070.1/806.0; the rule completes fewer trips (surge
  2,014 vs 2,087; incident 1,236 vs 1,384), so its lower time loss is survivorship. No controller ranking claimed;
  acceptance check extended to completed trips and teleports; demand calibration is future work.
- Export: `report export` regenerates the evidence registry (LLM-01 now backed by `llm_calls.csv` derived from the
  traces; GRAPH-02 by the newest run's `feature_schema.json`; hardware labels from `environment.json`), runtime
  metrics and keeps the workstation's MLflow export. Paper tables regenerated by `paper sync`.
- Not in git on purpose: model weights, prediction arrays, raw data, the FAISS index, document copies and the two
  superseded runs (kept on the workstation; their hashes and run ids are in the registry files).

## 2026-10-21

### Milestone 4: SUMO testbed audit and corrected protocol (development container, 2026-10-21 00:40-01:30 UTC)
Network access had changed: NYC Open Data, Crossref and the OSM editing API were reachable from the container
(Overpass still blocked). SUMO 1.28.0 (same as the workstation) installed with pip; all project dependencies installed
on CPU torch 2.14.1 (torch-geometric-temporal `--no-deps`, as in the Dockerfiles).
- Bibliography: johnson2019faiss DOI confirmed on Crossref (10.1109/TBDATA.2019.2921572, IEEE TBD 7(3) 535-547);
  SUMO's Automatic Routing documentation (v1_28_0) added; 24/24 entries CHECKED.
- Reproduction: `fetch.py speed-links --since 2026-09-20` returned the same 125 links and `graph build` reproduced
  graph hash d8c69a468b82cbda (26 nodes, 16 edges, 6 isolated) from an independent download. ATR volume 2009-2026
  downloaded (per-year counts equal the server-side counts).
- Corridor: `fetch.py osm` gained an OSM-API fallback with the Overpass-equivalent filter. The bbox
  40.700,-74.020,40.737,-74.000 reproduces the workstation corridor exactly (82 edges, 22 signals, corridor phases,
  entries/exits, both DOT mappings; 24/25 side-entry ids, the 25th is the same FDR Drive approach). The original design
  on it reproduces the oversaturated regime (routine fixed-time seed 1: 2,981 / 3,294 / 928 completed / unfinished /
  teleports vs 2,746 / 3,527 / 1,157; `simulation/outputs/sim-routine_peak-fixed_time-s1-20261021T005621-75863c`).
  netconvert output embeds a timestamp, so `prepared.json` now also records a content hash without that header.
- DEFECTS FOUND in the 2026-10-20 testbed: (a) bare from/to flows are routed by SUMO at insertion on current travel
  times (SUMO docs, "Incomplete trips and flows"): at the declared demand 1,853 route replacements and 1,120 of 2,189
  mainline vehicles off West Street (`scripts/sim_testbed_audit.py` -> `simulation_testbed_audit.json`); (b) the NB
  flow was inserted on a 0.2 m stub edge. FIXED: one fixed free-flow route per flow (`route_choice`), entries skip
  edges < 20 m. The 45 runs are kept and labelled SUPERSEDED (paper Table VII, claims C12/C22, SIM-02 PARTIAL).
- Demand: weekday-only ATR rule; the only weekday corridor count is NB Gansevoort St 2014-10-06..10 (15 complete
  PM-peak hours, median 1,389 veh/h, applied to both directions); the SB count (Bloomfield St 2015-03-07..08, median
  2,074) is a weekend and excluded.
- DECISION (preregistered before any run): side-street demand level chosen by `simulation select-demand` on routine
  peak, fixed-time only, seeds 101-103, grid 1.0/0.75/0.5/0.25/0 of 150 veh/h, admissible only with 0 teleports and
  <= 1 % unfinished in every seed.
- RESULT, netconvert programs (15 runs): no level admissible; with no side demand 533 of 3,010 unfinished, time loss
  804 s. Route-aware capacity audit: NB mainline gets 25 s of 90 s on 2 lanes at GS_42451370 (~1,000 veh/h < 1,389).
  An earlier reading (520 veh/h at the joined Battery Place signal) counted a movement the corrected NB route no
  longer makes and was withdrawn before publication of this milestone.
- DECISION: re-time the fixed-time programs with Webster's method (SUMO `tlsCycleAdaptation.py`, tool defaults,
  phase states unchanged) for each tested demand level, a declared assumption; same selection rule.
- RESULT, Webster programs (15 runs): no level admissible; with no side demand 129-131 of 3,010 unfinished (4.3 %),
  0 teleports, NB completes 1,389 trips, its hourly flow (195-197 s time loss) but SB loses 1,014-1,038 s per trip (cause not
  identified; every SB signal estimate >= 2,040 veh/h). The rule was not relaxed. Corrected controller comparison:
  NOT_RUN. The advisory simulation gate now raises NOT_EVALUATED (-> ERROR_TOOL with cause) on such a testbed.
- Tests: 66 passed in the container (unit, leakage, safety, integration incl. PostGIS 16 and SUMO, e2e). Paper rebuilt
  (10 pages) with TeX Live; superseded and audit tables generated by `paper sync`.
- Not re-run in the container (no weights, no Ollama): forecasting, calibration, explanations, RAG, agents.

### Milestone 5: final-review presentation and paper author block (2026-10-21 01:40-02:05 UTC)
- `presentation/Final_Review_S_K_Sricharan_25MML1010.pptx`: the VIT Chennai final-review template filled slide by
  slide (its order, headings and font rules kept; one extra literature-survey, outcome and references slide), title
  slide as in the Review-II deck. Numbers taken from `reports/experiments/*` and the testbed audit; literature rows
  and IEEE references from the checked bibliography. Validated, rendered and visually checked; the builder in
  `presentation/` reproduces it.
- FIX: the proposed model's 60-min test MAE is 6.1546 mph; the abstract, results and README had rounded it to 6.16
  instead of 6.15.
- Paper author block: S K Sricharan, School of Computer Science and Engineering, VIT Chennai (Reg. No. 25MML1010);
  co-authors and order remain for the authors to confirm.

### Milestone 6: recent counts, turn-lane diagnosis and a speed check for the SUMO testbed (2026-10-21 02:05-02:55 UTC)
- NYC Open Data catalog searched for signal timing and counts. No dataset publishes phase timings; Vision Zero
  `d8dp-wfee` lists West Street (Battery Pl - W 57 St 2014; 57 St - Morris St 2019) as re-timed for 25 mph progression.
- `fetch.py counts` (new): Vehicle Classification Counts `96ay-ea4r` and historical volume counts `btm5-ppia` for West St.
  Weekday two-direction counts exist for 2025 (Spring St - W Houston St, 29-30 Apr: PM-peak medians NB 2,510, SB 2,444
  veh/h), 2019, 2017, 2015 and 2014. DECISION: demand from the most recent year with both directions (config
  `count_sources`); the 2014 ATR figure stays in `prepared.json` as `atr_record`.
- DIAGNOSIS (southbound delay under the Webster programs): edge data show the SB queue ending at the West St / Chambers St
  signal. A first reading blamed corridor lanes with no outgoing connection; checking showed those lanes exist with and
  without `--osm.turn-lanes`, so that reading was dropped. The difference is a right-turn-only lane (from OSM turn:lanes)
  on the 45 m link south of Chambers St that forces through traffic to merge. `scripts/sim_turnlane_check.py`: with the
  2014 count, no side demand and Webster programs, SB time loss 1,014-1,038 s and 129-131 unfinished with the
  restrictions, 346-380 s and 0 unfinished without (`simulation_turnlane_check.json`). DECISION: `osm_turn_lanes: false`,
  declared as a simplification that can overstate capacity.
- RESULT, protocol `v4_counts2025_webster_noturnlanes` (15 runs, same preregistered rule): no level admissible; with no
  side demand 523-568 of 5,368 unfinished, 0 teleports; NB completes 2,520-2,524 trips (247-248 s), SB 1,877-1,922
  (1,199-1,226 s); one SB signal ~2,278 veh/h of estimated capacity for 2,444 demanded. A first v4 pass was repeated after
  the plan files were renamed per protocol; results were identical, the duplicate run folders were removed.
- Speed check (`fetch.py speed-profile`, new): link 4456494 weekday PM peak (16-19 h, Apr-Oct 2026, 3,692 records)
  10.95 mph observed vs 5.79-5.85 mph simulated on its 8 mapped SUMO edges
  (`simulation_testbed_audit_v4_counts2025_webster_noturnlanes.json`). The testbed is too slow; the comparison stays
  NOT_RUN and 10.95 mph is the calibration target. The rule was not relaxed.
- Paper: results, limitations, discussion and conclusion updated; two dataset references added (26/26 CHECKED);
  claims C29-C33. Tests: 2 new unit tests for the count selection.

### Milestone 7: multi-seed study and agent re-run (workstation, 2026-10-21 03:35-04:45 UTC)
- Continued from branch `claude/nifty-dijkstra-u5kjbw` (7738d68). The three CPU seed-42 runs of the development
  container have no stored predictions, so their records moved to
  `artifacts/models/multi_seed_runs_container_cpu_seed42.json` and all nine runs were trained on the workstation
  GPU (RTX 4050, torch 2.11.0+cu128) with `scripts/multi_seed_study.py train`, then `analyze` (exit 0).
- REPRODUCIBILITY CHECK: seed 42 reproduced the main-run GRU (17 epochs, best 11, val MAE 5.4763) and temporal
  Transformer (14, 8, 5.4062) exactly, but not the proposed model (25 epochs, best 19, 5.3584 vs 14, 8, 5.3880). The
  only difference to the temporal Transformer is the GATv2 layer (non-deterministic CUDA scatter); runner and model
  code paths for seeding and sampling are unchanged since the main run. The container CPU run gave 21 epochs, val
  5.3556.
- RESULT (`reports/experiments/multi_seed_summary.csv`, `multi_seed_metrics.csv`; 144,205 shared 60-min targets):
  seed-mean test MAE 15/30/60 min: proposed 4.688/5.339/6.153 (s.d. 0.063/0.032/0.015), GRU 4.666/5.370/6.184,
  temporal Transformer 4.723/5.375/6.233. Paired day-block bootstrap (44 days, 1,000 resamples) of the seed-averaged
  MAE difference: Transformer minus proposed +0.035/+0.037/+0.080 (all intervals above zero); GRU minus proposed
  -0.021 [-0.040, -0.004] / +0.032 [0.010, 0.052] / +0.031 [0.007, 0.056]. Reading: proposed lower than the
  Transformer at every horizon and the GRU at 30/60 min, GRU lower at 15 min; small (0.02-0.08 mph), three seeds,
  per-seed ranges overlap, the bootstrap does not include between-seed variance. One Transformer seed (1) stopped
  at best epoch 2. Paper: new generated Table `tab:multiseed` (`paper sync`), results/discussion/limitations/
  conclusion/abstract updated; claims C34-C37; C05/C16 notes updated; deck rebuilt (conclusions slide adds the
  3-seed row; next-milestones footer) and its PDF re-exported with PowerPoint.
- AGENTS RE-RUN (`agents evaluate`, 411 s, then `report export`): same 19 decisions as on 2026-10-20; 12/12 LLM calls
  schema-valid, all monitor_only, so the corrected simulation gate was again not reached; 3/3 invented evidence ids
  without retrieval (rejected), 0/9 with. `llm_calls.csv` is rebuilt from all traces and now holds both passes (24).
  The paper's token ranges were corrected from the file (892-3,619 prompt, 157-321 completion tokens).
- Counts fetched once for the SUMO work: `fetch.py counts --dataset classification --street-like "WEST ST"` (70
  rows) and `--dataset volume_hist` (144 rows) into `data/raw/{classification,volume_hist}/` with fetch logs.
- Not done here: `paper/main.pdf` rebuild (no LaTeX on the workstation).

### Milestone 11: calibrated testbed run on the workstation (protocol v5, 2026-10-23 20:00-20:20 UTC)
- Branch `claude/laptop-sumo-calibration` from origin/main ceadbd4; `docs/laptop_run.md` section 6, stopped at the
  first NOT_RUN as the section requires.
- `simulation prepare`: exit 0 (28 s). PROVENANCE DEVIATION: the network hashes do not match the committed
  `prepared.json`. The workstation's OSM file was the 2026-10-20 Overpass extract with a different bbox; it was kept
  (renamed `data/raw/osm/west_st_corridor.overpass_2026-10-20_bbox40.703.osm`) and the configured bbox
  40.700,-74.020,40.737,-74.000 was re-fetched from the OSM API (`fetch.py osm --source osmapi`, 2,790,185 bytes,
  sha256 44e0e4fe...). Rebuilt corridor is structurally identical to the committed record (82 edges, identical NB/SB
  edge lists, entries/exits, 22 signals, corridor phases, 25 side entries, 2 high-confidence DOT mappings, demand
  record) but the network content hash differs (static 87174681... vs 52dcd2fc...), most likely OSM edits after
  2026-10-21; the committed network file is not in git, so the difference could not be diffed. All v5 runs use this
  one rebuilt network. The uncalibrated factor 1.0 reproduces protocol v4 on the old network (5.82 mph vs 5.79-5.85;
  523-568 unfinished vs 523-568).
- `simulation calibrate-splits`: exit 1, NOT_RUN (514 s; 21 runs, fixed-time, seeds 101-103, no side demand, 2025
  counts NB 2,510 / SB 2,444 veh/h). Simulated speed on the 8 SUMO edges of link 4456494 by green factor:
  1.0 5.82, 1.2 6.16, 1.4 6.52, 1.6 6.85, 1.8 7.13 (all inadmissible: 98-568 unfinished), 2.0 7.49 (admissible:
  1/0/28 unfinished, 0 teleports), 2.5 8.10 (admissible: 0 unfinished, 0 teleports). Target 10.95 mph, tolerance
  1.5 mph: closest admissible 8.10 mph is 2.85 mph short, so `selected_green_factor` is null
  (`simulation/scenarios/split_calibration_v5_counts2025_calibrated_splits.json`,
  `reports/experiments/simulation_split_calibration_v5_counts2025_calibrated_splits.csv`). The rule was not relaxed.
- NOT RUN as a consequence: `select-demand`, `simulation evaluate` (controller comparison), the agent re-run on a
  calibrated testbed, `report export` and `paper sync`. The largest preregistered factor (2.5) is the most admissible
  and the speed was still rising, so the tested range ends below the target; widening it would be a new protocol.
- Dashboard screenshots (REPLAY, 1600x1000, Streamlit on the workstation, captured with Edge via Playwright):
  `presentation/assets/dashboard/forecast_laptop.png`, `traffic_map_laptop.png`.

### Workstation run of protocol v6 (2026-10-25/26): BLOCKED by two code errors before any cell ran
- Branch `claude/laptop-sumo-v6` from origin/main 39e44a5; `docs/laptop_run.md` section 7.
- `simulation prepare`: exit 0 (31 s). Network content hashes MATCH `prepared.json` (static 87174681..., actuated
  ace93240..., OSM 44e0e4fe...); only the whole-file sha256 of the two `.net.xml` changed (netconvert timestamp).
- `simulation calibrate-splits`, attempt 1: exit 1 after 4 s, `KeyError: 'so_chain_starts'`
  (`simulation/calibrate.py`: `c[f"{direction[:2]}_chain_starts"]` gives so/no; `prepared.json` uses sb/nb). Fixed in
  this branch (one line, prefix sb/nb); `configs/simulation.yaml` untouched; unit/leakage/safety tests 84 passed.
- Attempt 2: exit 1 after 5 s, `KeyError` in `progression_offsets` for corridor signal
  `joinedS_246858654_42451375_cluster_1772136801_246923513_4145439094_4207802391`: SUMO `tlsCycleAdaptation.py`
  writes re-timed programs for 21 of the 22 corridor signals (this joined signal keeps its netconvert program), and
  the 25 mph progression step looks up every corridor signal on the southbound chain. Resolving it (offset from the
  network's own program, or no offset for that signal) changes the calibrated programs, so it is a protocol decision
  and was NOT made on the workstation.
- Result: 0 of 75 cells run; no selection; select-demand, evaluate, agents evaluate, report export and paper sync NOT
  RUN. The preregistered rule and the v6 configuration were not changed.

### Workstation run of protocol v6 completed (2026-10-25/26 and 2026-10-28/29)
- Branch `claude/laptop-sumo-v6` on the fixed code (8b90c68, then main 640a0a2 merged; simulation code unchanged).
- `simulation prepare`: exit 0; content hashes match (87174681 / ace93240 / 44e0e4fe).
- `simulation calibrate-splits`: exit 0 (1,730 s, 75 runs). Selected cell: common cycle 90 s, green factor 1.5, 25 mph
  offsets, 10.08 mph simulated on link 4456494 vs 10.95 observed (gap -0.87, tolerance 1.5); 0 unfinished, 0
  teleports. Factors 1.5-3.0 give identical speeds at a common cycle (green bounds bind); least intervention chosen.
- `simulation select-demand`: exit 0 (436 s). Only side-street scale 0.0 is admissible.
- `simulation evaluate`: the first pass was interrupted when the workstation went offline (39/45 runs finished, no
  metrics written); re-run in full on 2026-10-28: exit 0 (1,425 s), 45/45 OK, 0 teleports in every run, seeds 1-5.
  Fixed-time vs forecast rule (same calibrated plan, network and seeds): routine peak identical (rule inactive); event
  surge time loss 450.2 vs 426.0 s, completed 5,720 vs 5,910, unfinished 540 vs 350; incident 465.9 vs 443.9 s,
  5,725 vs 5,919, 536 vs 341. The actuated controller runs on netconvert's actuated programs, not the calibrated plan
  (signal_timing netconvert_guess), so it is an uncalibrated reference, not a matched comparison. Side-street demand
  0; pedestrians NOT_EVALUATED.
- `agents evaluate`: attempt 1 failed (WinError 4551: Windows Application Control blocked the unsigned
  torch_sparse / torch_scatter CUDA extensions). Both were uninstalled from the workstation venv so that PyG-Temporal
  uses the documented direct-module fallback; 87 unit/leakage/safety tests pass. Attempt 2: exit 0 (517 s), same 19
  decisions as before; 12/12 schema-valid; the LLM chose monitor_only on the mapped corridor under every policy, so
  no real advisory reached the (now admissible) simulation gate. `report export` and `paper sync` exit 0.

### Workstation LIVE attempt (2026-10-28 19:49-22:05 UTC, Wednesday 15:49-18:05 New York): NOT_RUN, feed stale
- Branch `claude/laptop-live` from main 257aad9 (then main 6f9c86a); `docs/laptop_run.md` section 8; `tests/unit/test_live.py`
  8 passed.
- First `live pull` (19:49 UTC): exit 0, 0 speed rows: the newest Manhattan record of i4gi-tjb9 was 11:31 New York time
  (about 4 h 20 min old; other boroughs up to 14:12), outside the 4 h pull window. `live forecast`: NOT_RUN, no valid
  live speed records.
- A watcher pulled every ~10 min (12 tries, 19:53-21:51 UTC) and would have started `live run --polls 12 --interval-s
  300` at the first batch with at least one link forecast. Speed rows per pull: 438, 0, 0, 338, 306, 0, 240, 208, 50,
  402, 370, 336; newest record 14:11, then 13:36, then 15:36 New York time. The 14:11 batch was published, withdrawn
  (0 rows at 20:03, 20:14 and 20:46) and republished, and the feed was never less than about 1 h 40 min behind. Every
  `live forecast` batch (9 written, `artifacts/live/forecasts/`) forecast 0 links and withheld all 16
  (INSUFFICIENT_HISTORY: at most 5 of the 24 lookback bins observed, 12 required). The rule was not relaxed.
- Operator note: a first watcher started `live run` after a batch that withheld every link; it was stopped after 16 s
  (no forecasts issued) and the trigger was corrected to "at least one link forecast" before the 12 tries above.
- Result: LIVE observational run NOT_RUN on 2026-10-28 (public feed stale); `live_metrics.csv` not produced; paper
  Table `tab:live` stays NOT RUN. Evidence: `artifacts/live/` (batches, forecast log, last pull) and
  `data/raw/live/*/fetch_log.jsonl` (15 speed, 15 weather, 14 311 pulls with request, status and sha256). To retry on
  another weekday afternoon when the feed is current (about 13:00-16:00 New York).

### Workstation LIVE attempt 2 (2026-10-29 16:29-21:38 UTC, Thursday 12:29-17:38 New York): NOT_RUN, feed stale
- Branch `claude/laptop-live` from main 3e4ea83 (contains attempt 1); `tests/unit/test_live.py` 8 passed.
- At 16:29 UTC the newest i4gi-tjb9 record for the modelled links was 10:11 New York time (about 2 h 18 min old).
- Watcher (trigger: at least one link forecast): 25 pulls, 16:31-21:28 UTC. Newest record per pull moved 10:11 ->
  11:31 -> 12:01 -> 12:31 -> 14:06 -> 13:21 -> 15:36 New York time (it also stepped back, and one pull returned 0
  rows), i.e. 2-2.5 h behind throughout. All 24 `live forecast` batches (`artifacts/live/forecasts/live-20261029T*`)
  forecast 0 links and withheld all 16 (INSUFFICIENT_HISTORY); `live run` was not started; stopped at 21:38 UTC after
  the planned window. The withholding rule was not relaxed.
- Deviation: the workstation dozed between some pulls (the app's keep-awake hold lapsed while the session was idle), so
  three gaps were 20-34 min instead of 10; a 4-min heartbeat kept it awake from 19:47 UTC.
- Across both attempts the public feed ran about 1.7-4.3 h behind real time on weekday afternoons, while the live
  forecaster needs at least 12 of the last 24 five-minute bins (about the last hour). Under the current rule a live
  forecast is therefore not reachable with this feed's present latency; changing that (e.g. a different lookback or
  an origin at the newest available bin with its age shown) would be a new, preregistered decision for the authors.
- Result: LIVE observational run NOT_RUN on 2026-10-29; `live_metrics.csv` not produced; Table `tab:live` stays NOT
  RUN. Evidence: `artifacts/live/` and `data/raw/live/*/fetch_log.jsonl`.

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
- Bibliography: CLEARED 2026-10-21 (24/24 CHECKED, `paper/REFERENCES_STATUS.md`). Paper author block: student filled in; co-authors and order to confirm.
- Simulation: no admissible testbed (Milestones 4 and 6). Recent two-direction counts are now used; what remains is
  signal timing: calibrate splits and 25 mph progression to the observed 10.95 mph PM-peak speed (a calibration choice
  for the authors) or obtain NYC DOT timing plans.
- Agents on the corrected testbed: to re-run on the workstation (`agents evaluate`); with no admissible testbed any
  signal-change candidate now ends in ERROR_TOOL (NOT_EVALUATED) instead of a simulation verdict.

## 2026-10-21 (post-merge verification)

- Independent re-check of the paper and status files against the artifacts (two passes: simulation numbers, then
  every quantitative claim in abstract, results, discussion). Corrections merged in PR #11 (simulation: wall time
  9,645 s, per-run ranges, mapped links 4616325 dead feed + 4456494 modelled) and in the follow-up PR: 60-min proposed
  MAE 6.15 (not 6.16), GRU 15-min 4.71, retrospective 30-min 5.35, deep-model margins 0.01-0.06 mph, 50,415 training
  origins (half-open range), per-horizon calibration counts, LLM token/latency ranges over all 12 calls (892-3,604 /
  157-278 / 15-126 s), gate retained-MAE reduction 15-22 % (not 'a third'), stress cases run under the full system
  only, 'single-day pipeline execution' instead of 'one end-to-end run' (early stages were re-run; the stage log
  shows four baseline passes), 'nearly ten months' of data, test window about 44 days over 45 calendar dates. The
  second pass covered 23 of 64 planned checks before the session limit; limitations, conclusion, method, data,
  experiments, final_status, progress, README and paper_claims were not independently re-checked in that pass.

### Milestone 6b: multi-seed study prepared (development container, 2026-10-21 03:30-03:50 UTC; the runs are Milestone 7)
- The other account's session (branch `claude/nifty-dijkstra-u5kjbw`, 3 unmerged commits) is merged: `scripts/multi_seed_study.py`,
  `runner.train_deep(seed=...)`, `reports/verification/container_reproduction.json` (independent re-download reproduced
  1,968,303 raw rows, graph hash d8c69a468b82cbda, feature schema hash 1d63c3fe45a729be and the same splits).
- Its three CPU seed-42 runs (proposed, gru, temporal_transformer; torch 2.14.1, container) are kept as records in
  `artifacts/models/multi_seed_runs_container_cpu_seed42.json`: their weights and prediction arrays are not
  committed, so they cannot be analysed here and seed 42 was re-run on the workstation GPU (Milestone 7). The CPU proposed run's
  4.689/5.327/6.116 mph reported by that session is not reproducible from the repository and is not used.
- `train-all` (resumable, seed-major) and portable artifact paths added; 3 unit tests. Workstation instructions:
  `docs/laptop_run.md` section 5 (counts fetch, 9 seed runs, `analyze`, `agents evaluate`, export, paper sync).
- Multi-seed results, the agents re-run on the corrected simulation gate and the counts fetch were then run on the workstation (Milestone 7).
- Independent audit of PRs #12-#15 (code, claims C23-C33, deck literals): no fabricated or wrong number; every
  simulation figure recomputes from the committed `result.json` files. Fixed from its findings: a run with missing
  summary metrics could have passed the admissibility test as 0 <= 0 (`run_admissible` now requires complete evidence;
  the gates also refuse to run if the `demand_selection` block is removed; 2 tests); a withdrawn ~520 veh/h figure in a
  `configs/simulation.yaml` comment; "completes all N trips" wording; the deck's test count (66 -> 73 collected,
  deck rebuilt); the deck README now says the builder holds literals checked against the result files; the audit
  script no longer overwrites the cited turn-lane-network audit with an audit of another network; limitation 25
  records which testbed inputs trace to derived files only.

### Milestone 8: IEEE Word paper (development container, 2026-10-21)
- `paper/ieee_conference_paper.docx` built from the conference's A4 Word template (`paper/word/IEEE_conference-template-A4.docx`)
  by `paper/word/build_ieee_docx.py` (`make paper-docx`): text in `paper/word/paper_content.py` follows `paper/main.tex`
  with the PR #16 corrections; tables are read from the generated `paper/tables/*.tex` and
  `reports/data_audit/source_inventory.csv`, so no table number is typed by hand. Formatting follows the guideline the
  student supplied (abstract 247 words without citations, seven alphabetical keywords, Roman section numbers, table
  titles above tables, references numbered by first appearance). Author block: S K Sricharan and Dr. R. Srinivasa
  Perumal (confirmed by the student). The first-page footer keeps the template's copyright placeholder for the conference.
- Check: every number in the Word body text was matched against `paper/sections`, `paper/tables`, `references.bib` and
  `source_inventory.csv` by script (no unmatched figure); LibreOffice renders 9 A4 pages.
- Built before the multi-seed study landed: that build says all forecasting figures are single-seed. The Word paper is
  rebuilt from `paper_content.py` once its text carries the Milestone 7 figures (claims C34-C37).
- Rebuilt on 506de48 with the three-seed results: seed table from `paper/tables/multi_seed.tex`, the seeds paragraph,
  both agent passes (24 LLM calls) and the updated abstract (245 words), discussion, limitations and conclusion, in the
  same wording as the LaTeX sections. Also fixed in LaTeX: `results.tex` input `tables/multi_seed` twice and
  `results_body.tex` still said the study had not been run; `main.pdf` rebuilt (11 pages).
- Rebuilt on 4a49916 (2026-10-23) with the protocol v5 signal-split calibration: the paragraph from
  `results_body.tex` and Table X read from `paper/tables/split_calibration.tex` (SIMULATION; no factor selected,
  controller comparison still NOT RUN). LibreOffice renders 10 A4 pages; no other figure changed.
  Limitations and future work then mirror 8a26e55 (v5 reached 8.1 of 10.95 mph; next step adds progression offsets).
- Rebuilt on 3f2231a (2026-10-25): protocol v6 paragraph (prepared, NOT RUN), its NOT RUN table and the updated
  future-work sentence, mirroring the LaTeX.
- Rebuilt on 43fe4c5 (2026-10-28): "Live observational run" subsection and its NOT RUN table (tab:live). The Word
  builder now renders `split_calibration_v6.tex` and `live.tex` from the generated tables (header, rows, caption
  detail as the note) once they carry results, instead of stopping.
- Rebuilt on 382d9ca (2026-10-28) with the protocol v6 result and the corrected 45-run comparison: v6, comparison
  and third agent-pass paragraphs, Table X (v6 grid, 25 cells) and Table XI (calibrated comparison) from the generated
  tables, and the abstract (248 words), discussion, limitations and conclusion in the LaTeX wording. Also fixed in
  LaTeX: the superseded 2026-10-20 comparison still cited Table~\ref{tab:sim}, which now holds the corrected runs;
  `main.pdf` rebuilt (13 pages). Word paper: 11 A4 pages in LibreOffice.
- Rebuilt on 7052433 (2026-10-28): the live-run paragraph records the stale-feed attempt (NOT RUN), as in LaTeX.
- Rebuilt on aef5f83 (2026-10-29): the live-run paragraph adds the second stale-feed attempt (NOT RUN), as in LaTeX.

### Milestone 9: integration of the multi-seed study, agent re-run and Word paper (development container, 2026-10-21 04:40-05:30 UTC)
- Merged the workstation branch (Milestone 7: nine GPU seed runs, `agents evaluate` re-run, counts) with the Word-paper
  branch (Milestone 8, PR #17) on top of PR #16. Conflicts resolved by keeping the PR #16 wording corrections (nearly ten
  months of data, about 44 test days, 0.01-0.06 mph single-seed margins, retained-coverage sentence) and the
  workstation's multi-seed paragraphs, table (`tab:multiseed`), claims C34-C37 and limitation 8/8b.
- Verified the workstation figures against the committed files before use: `multi_seed_summary.csv` seed means
  4.6878/5.3388/6.1533 (proposed), 4.6664/5.3703/6.1840 (GRU), 4.7233/5.3755/6.2331 (Transformer) equal the means of the
  nine runs in `multi_seed_metrics.csv`; bootstrap intervals as in C35; `multi_seed_runs.json` lists 9 CUDA runs with
  the epochs quoted in C36; `llm_calls.csv` holds 24 calls. `paper sync` regenerated identical tables.
- `paper/main.pdf` rebuilt with TeX Live; the final-review deck rebuilt from the merged builder (three-seed observation,
  0.01-0.06 mph single-seed margin). The multi-seed unit test now checks the table format the workstation's `paper.py` writes.
- Still NOT RUN: the corrected SUMO controller comparison (authors' calibration decision, open item 2).
- Verification pass after the merge: GitHub Actions run 58 on 807f67d ran lint and the full `pytest -q tests` (unit, leakage,
  safety, PostGIS and SUMO integration, e2e) with a PostGIS service container: 75 passed. The deck's test-count literal
  (66, from the workstation build) and the model card's single-seed statements are updated to this state; the evidence
  registry keeps the workstation export of 2026-10-21 04:41 UTC (a container export would overwrite the MLflow run list
  with an empty one, so `report export` is not re-run here).

### Milestone 10: calibrated SUMO testbed protocol prepared (development container, 2026-10-21 06:30-07:00 UTC)
- The container has neither the OSM extract nor the generated network (both ignored in git; NYC Open Data, OSM and
  Open-Meteo are unreachable from it), so SUMO runs stay on the workstation.
- Protocol v5 `split_calibration` (`configs/simulation.yaml`, `src/smartcity/simulation/calibrate.py`,
  `simulation calibrate-splits`): from the Webster plan for the routine peak at zero side demand, the corridor green of
  every corridor signal is scaled by a factor from {1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5} (cycle kept by shortening other
  greens to min_green 7 s, cycle at most 120 s, corridor green at most 90 s, states unchanged); each factor runs under
  the fixed-time baseline on seeds 101-103; admissible factors (unchanged rule: 0 teleports, at most 1 % unfinished)
  are compared by seed-mean space-mean speed on the 8 SUMO edges of link 4456494 (edgeData, 300-3,900 s) and the one
  closest to the observed 10.95 mph is selected if within 1.5 mph. `select-demand` then applies the preregistered
  side-demand rule under that plan (new `calibrated_splits` timing mode), and `evaluate` runs the 45-run comparison.
  7 unit tests on the pure functions (green rescaling, space-mean speed, factor choice).
- Declared and to be stated wherever a result is reported: this is a scenario testbed calibrated to one observed speed,
  not a digital twin and not NYC DOT timing. Comparison: NOT RUN (workstation runbook `docs/laptop_run.md` section 6).

## 2026-10-23 (re-verification after PR #21, development container)

- Repository state: main at 354106e (PR #21 merged 2026-10-21 10:09 UTC). No workstation branch or commit has appeared
  since; the calibrated SUMO protocol (Milestone 10) is still NOT RUN and the controller comparison stays NOT RUN.
- Checks run here: full test suite (80 passed; `tests/integration/test_db.py` needs the PostGIS service and is covered by
  GitHub Actions run 65 on main, which passed), `ruff` lint, byte-compilation of src/scripts/paper/presentation, `doctor`,
  the API smoke (all endpoints answer as expected; readiness 503 because no database is running here) and the Streamlit
  dashboard smoke (health and index 200 within 1 s, headless, reading the committed artifacts in REPLAY mode).
- Fixes: two unused variables removed (`sumo_runner.run_scenario`, `conformal`); the SUMO integration test now writes its
  toy-grid outputs to pytest's temporary directory instead of `simulation/outputs/` (previously left untracked run folders
  behind). No result file changed. `verify all` was not run because its report export would overwrite
  `mlflow_runs.json` with the container's empty MLflow store; `doctor` output for this container was discarded so that
  `environment.json` keeps describing the workstation that produced the results.
- Panel results page: a read-only dashboard built from the committed result files (REPLAY, SUMO NOT RUN) is published as a
  claude.ai Artifact for the review panel; it holds no numbers that are not in `reports/experiments/` or `artifacts/`.
- Still workstation-only: `docs/laptop_run.md` section 6 (calibrate-splits, select-demand, evaluate, agents evaluate,
  report export, paper sync, the two dashboard screenshots).

### Milestone 11b: integration of the v5 run (development container, 2026-10-23 20:30-21:00 UTC)
- Workstation branch `claude/laptop-sumo-calibration` (8ced37a) merged with main (ceadbd4) and the re-verification branch.
- Paper: new generated Table `tab:splitcal` (`paper.split_calibration_table`, part of `paper sync`) and a results paragraph on
  the v5 outcome and the network provenance deviation; claims C38-C40; limitation 24 addendum and new limitation 26;
  final_status open item 2 updated. `paper sync` and the PDF rebuild ran here (the workstation stopped before `paper sync`).
- `prepared.json` paths normalised to POSIX and the writers now emit `as_posix()` paths, so records written on Windows resolve
  on Linux; no figure changed.
- The controller comparison stays NOT RUN; the choice between a wider preregistered grid (v6), offset calibration, NYC DOT
  timing plans or closing the comparison is put to the authors.

### Milestone 12: calibration protocol v6 preregistered (development container, 2026-10-25 21:05-21:40 UTC)
- SK chose "Protocol v6" on the decision card (2026-10-25 21:05 UTC) over closing the comparison or NYC DOT timing plans.
- `configs/simulation.yaml` `split_calibration` rewritten to protocol `v6_counts2025_cycle_splits_offsets` BEFORE any run:
  grid common cycle {Webster per-signal, 90 s, 120 s} x green factor {1.0, 1.5, 2.0, 2.5, 3.0} x offsets {none, 25 mph}
  (offsets only with a common cycle) = 25 cells x seeds 101-103 = 75 fixed-time runs; target, tolerance, side demand
  (0.0), caps (7/90/120 s) and the admissibility rule unchanged; ties to the least intervention. `demand_selection`
  protocol id follows (v5 never reached it). The v5 record and CSV are kept as the v5 result.
- `src/smartcity/simulation/calibrate.py`: `set_common_cycle` (greens scaled together, clearance fixed, floor at
  min green, cycle exact), `order_chain` + `corridor_signal_positions` (travel order and cumulative distance to each
  corridor signal), `progression_offsets` (offset = (distance / speed - corridor green start) mod cycle, positive SUMO
  offset = delay), `apply_offsets`, `grid_cells`, `build_cell_program`; `choose_factor` generalised to cells with the
  preregistered tie-break; record gains `selected_cell`, `progression_direction`, `progression_chain`, per-cell offsets.
- Tests: 7 new unit tests (`tests/unit/test_split_calibration.py`), 2 SUMO tests on the toy grid
  (`tests/integration/test_sumo_runner.py`: offset semantics through TraCI to within one step; chain order and
  positions), 2 paper-table tests. Suite: 95 collected (the two PostGIS tests run only in CI).
- Paper: generated Table `tab:splitcal6` (NOT RUN placeholder, `paper.split_calibration_v6_table`), a results paragraph
  "Protocol v6 (prepared, NOT RUN)", future-work sentence; PDF rebuilt. `docs/laptop_run.md` section 7 is the runbook;
  the laptop line was sent to SK. Nothing has been run; the comparison stays NOT RUN.
- Also this session: main (PR #24, deck 25 slides) merged into the branch; lint clean; 76 unit/leakage/safety/e2e tests
  passed before the v6 change.

### Milestone 12b: the first v6 attempt and its two code errors (development container, 2026-10-25 23:35-23:55 UTC)
- The workstation session did not resume on SK's laptop line (22:35 UTC) and was restarted explicitly at 23:36 UTC. It
  branched `claude/laptop-sumo-v6` from main 39e44a5; `simulation prepare` reproduced the network (content hashes equal to
  `prepared.json`; only the whole-file hashes changed with netconvert's timestamp, as before).
- `calibrate-splits` attempt 1 crashed after 4 s: KeyError `so_chain_starts` (the chain-start key was derived from
  `direction[:2]`). Fixed as `progression_chain()` with explicit `sb_`/`nb_chain_starts` keys and a unit test (cdb951e);
  the workstation had applied the same one-line fix locally (60f7fe2, merged here).
- Attempt 2 crashed after 5 s: KeyError in `progression_offsets` for the joined corridor signal at the southbound exit,
  which `tlsCycleAdaptation.py` leaves out of the Webster plan (it emits programs only for signals the declared demand
  crosses), so the plan had 21 of the 22 corridor signals. Decision, taken before any cell ran and recorded in the config
  comment: such a signal keeps its netconvert program and receives no cycle change, green factor or offset, exactly as in
  v5 (so the Webster-cycle cells still reproduce v5); the plan records it under `signals_not_retimed` and
  `signals_without_offset`. Regression tests: offsets skip signals without a program; `build_cell_program` on the toy grid
  with one corridor signal missing from the plan. The grid, the rule, the target and the seeds are unchanged.
- 0 of 75 cells ran; nothing selected; the comparison stays NOT RUN. The workstation re-runs section 7 from `prepare`.

### Milestone 13: LIVE observational mode implemented (development container, 2026-10-28 18:20-19:40 UTC)
- Gap found against the specification (section 26, live updates): every forecast result so far is REPLAY on the held-out
  partition; `data collect` only stored raw feed pages and no live inference path existed. Built `src/smartcity/live/pipeline.py`:
  `pull` (newest speed rows of the modelled links, current Open-Meteo forecast, 48 h of road-related 311; each response
  stored verbatim with a fetch-log line under `data/raw/live/`), `forecast` (latest complete 5-minute bin; 42-step window
  rebuilt with the TRAIN-fitted scaler through the same block functions the offline build now uses; frozen model run once;
  per-link conformal intervals; links with fewer than 12 observed lookback bins withheld; the reliability gate's data-age
  and missing-input checks recorded per link; written to `artifacts/live/forecasts/` before the first target time, one
  file per origin, never rewritten), `score` (targets matched to observations pulled later; LATE forecasts excluded,
  unobserved targets PENDING; persistence error from the last observed speed; `reports/experiments/live_metrics.csv`,
  `artifacts/live/scored.csv`, `live_summary.json`) and `run` (poll loop plus a settle phase so the last 60-minute
  targets can be scored). Repeated and revised feed records across overlapping pulls are counted; the first occurrence
  is kept, as offline.
- Refactor without numeric change: `features/build.py` traffic, weather, infrastructure and assembly code moved into
  `traffic_block`, `weather_block`, `infrastructure_block`, `assemble` (build() calls them in the same order); meta gains
  `sr311_scale_train` on the next build (older builds: recomputed once from the archived 311 download and cached).
  `context.load_weather/weather_on_grid/sr311_on_grid` accept live frames. 11 feature and leakage tests pass unchanged.
- Surfaces: `GET /forecasts/live/latest` and `/forecasts/live/metrics`; dashboard page "Live monitoring" (LIVE badge,
  source ages, per-link table, scored metrics, per-link chart); `LIVE-01` row in the evidence registry; paper Table
  `tab:live` (NOT RUN placeholder) and a results subsection; limitation 27; `docs/laptop_run.md` section 8 is the runbook.
- Tests: 8 in `tests/unit/test_live.py` (origin rounding, grid placement, repeat/revision counting, feature parity with
  the offline blocks and schema check, scoring statuses incl. LATE, NOT_RUN summary, an end-to-end batch with a stub
  model and a later scoring pass), 2 API tests, 2 paper-table tests. Suite: 111 collected.
- NOT RUN: no network to the feed in the development container. The workstation runs section 8 after the v6 chain.
- Same day, workstation: the v6 calibration record and the demand selection (both finished before the 26 October
  shutdown) were committed and pushed (c86ce5f on `claude/laptop-sumo-v6`); the 45-run controller comparison, interrupted
  at 39/45, is being re-run in full, then agents evaluate, report export and paper sync.

### Milestone 14: integration of the v6 run and the corrected controller comparison (development container, 2026-10-28 19:00-20:00 UTC)
- Merged `claude/laptop-sumo-v6` (c86ce5f, e63a177, 4ebf001) into the build branch after PR #28 (LIVE mode) had merged.
  Records: `split_calibration_v6_counts2025_cycle_splits_offsets.json` (75 runs, selected 90 s / 1.5 / 25 mph, 10.08 mph),
  `demand_selection_v6_*.json` (side scale 0.0), `simulation_metrics.csv` (45 runs, 0 teleports, seeds 1-5),
  `scenarios.json` (calibrated plan `c90.f1.50.p25`), 19 new agent traces, `llm_calls.csv` (+12, 36 total),
  `evidence_registry.csv`, `mlflow_runs.json`, `runtime_metrics.csv` (workstation exports).
- Per-seed check of the matched pair (fixed time vs forecast rule, same plan, network, demand, seeds): time-loss gain
  12.9-29.9 s under the surge and 14.3-33.7 s under the incident, 148-250 more trips completed, in every seed; routine
  peak identical. Actuated rows carry `signal_timing netconvert_guess` and a different network hash (98e143b6f4e1296a vs
  36fb9c1fb895b7e7): an uncalibrated reference, not ranked. Written as such in the paper (results, discussion,
  limitations, conclusion, abstract), README, limitation 24, `overrides.json` (SIM-02 stays PARTIAL with the new reason)
  and claims C41-C48. `paper.simulation_table` now captions a calibrated run and names the uncalibrated controller.
- Paper: Table `tab:splitcal6` carries the 25 cells; Table `tab:sim` the 45 runs; PDF rebuilt. Environment deviation
  (Windows Application Control vs torch_scatter/torch_sparse) recorded as limitation 28 with the OSError fallback fix.
- Still NOT RUN: the LIVE observational window (`docs/laptop_run.md` section 8, workstation). Still open: human review
  of the RAG labels; a testbed with side-street demand, DOT timing plans or pedestrians (future work).

### Milestone 15: live-run attempt recorded (cloud container, 2026-10-28 22:30 UTC)
- Workstation branch `claude/laptop-live` (ad91bf6) merged: nine live batches, forecast log, last pull and 44 pull-log
  entries. `final_status.md` (Live mode: ATTEMPTED, NOT RUN, feed stale), `reports/limitations.md` 27, the paper's
  live subsection (Table `tab:live` stays NOT RUN), README and claim C49 record the attempt and why no forecast was
  issued; `paper/main.pdf` rebuilt (14 pages). Nothing was relaxed; the retry waits for a weekday afternoon with a
  current feed.

### Milestone 16: second live-run attempt recorded (cloud container, 2026-10-29 22:00 UTC)
- Workstation branch `claude/laptop-live` (1bead47) merged: 24 more batches, 25 pulls per source. `final_status.md`,
  `reports/limitations.md` 27, the paper's live subsection, README and claim C50 record that both weekday-afternoon
  attempts found the feed 1.7-4.3 h behind and that under the preregistered rule a live forecast is not reachable at
  this latency; no alternative protocol adopted. `paper/main.pdf` rebuilt.
