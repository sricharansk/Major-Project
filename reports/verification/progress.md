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
