# Running the real-data pipeline on the author's workstation

The cloud container cannot reach the data hosts or the GPU, so the real-data run happens on the workstation
(Windows, RTX 4050) and only small result artifacts are committed. Nothing below edits code.

## 1. Sync the branch

```powershell
git fetch origin
git checkout -B claude/implement-traffic-system-5rzj9i origin/claude/implement-traffic-system-5rzj9i
.\.venv\Scripts\Activate.ps1
pip install -e .
python -m pytest -q tests\unit tests\leakage tests\safety     # must pass before using real data
```

## 2. Prerequisites on disk

| Item | Path |
|---|---|
| Speed records | `data/raw/speeds/*.json.gz` |
| Link geometry | `data/raw/speeds_links/links_since_*.json.gz` |
| Weather, collisions, events, volume, 311, OSM | `data/raw/<source>/` |
| Sentence-transformer | `data/models/sentence-transformers__all-MiniLM-L6-v2/` |
| OSM corridor / major network | `data/raw/osm/west_st_corridor.osm`, `data/raw/osm/manhattan_major.osm` |
| Ollama | serving on `http://localhost:11434` with `qwen2.5:7b` (configs/agents.yaml default) |
| SUMO (optional) | `pip install eclipse-sumo`; set `SUMO_HOME` to the package `sumo` directory and `SUMO_BINARY` to `<SUMO_HOME>\bin\sumo.exe`. Without it, skip the simulation stages (`--skip simulation`) and the cloud container runs them. |

## 3. Run

```powershell
python scripts\run_real_pipeline.py            # add --skip simulation if SUMO is not installed
```

Stages run in the fixed order listed in `scripts/run_real_pipeline.py` (doctor, audit, preprocess, graph, features for
both tracks, baselines, proposed model, evaluation, calibration, explanations, retrospective track, RAG, SUMO, agents,
export, paper tables). Do not pass `--max-epochs` or `--windows-per-epoch` to the training stages; those are smoke-test
caps. If a stage fails, stop and send the command plus the printed traceback tail back to the project thread; resume
with `--from "<stage>"` after the fix is pulled.

## 3b. After a graph-rule or eligibility change

When the graph rules or the link-eligibility threshold change (`src/smartcity/graph/build.py`, `configs/graph.yaml`,
`configs/data.yaml`), restart with
`python scripts\run_real_pipeline.py --from "graph build"`: features embed the graph hash and every deep model consumes
the edge index, so earlier training runs on the old graph are superseded (they stay in MLflow with their own hash).

## 3c. Finishing under a wall-clock deadline

Two recorded, fair-across-models budget controls exist; both are written into every run's config and `run_info.json`
and must be stated in the results and limitations:

- `training.max_train_windows_per_epoch` (configs/training.yaml): windows sampled per epoch (fresh sample each epoch,
  seeded) instead of all ~50k; `null` = all.
- `--max-minutes M` on `train proposed` (or `python scripts\run_real_pipeline.py --max-minutes M`): wall-clock cap per
  deep model; the best epoch so far is kept and `stopped_reason` records `time_budget_Mmin`.
- `--parallel N` on `train proposed --variants a,b,c` (runner: `--parallel-ablations N`): trains N variants at once in
  separate processes on the same GPU; the per-track registry is lock-protected.

## 4. Hand the results back

Commit to a new branch cut from the tip of `claude/implement-traffic-system-5rzj9i`:

```powershell
git checkout -b claude/laptop-real-data-run
git add reports artifacts data/manifests simulation/scenarios/prepared.json simulation/mappings knowledge/indexes/*.json paper/tables
git commit -m "Add real-data run artifacts from workstation"
git push -u origin claude/laptop-real-data-run
```

`.gitignore` already drops model weights, prediction arrays, raw/processed data, MLflow files and the FAISS index.
Never commit `data/raw`, `data/interim`, `data/processed`, `data/models`, `mlruns`, `mlflow.db`, `.venv`, or any token.

Separately (outside git) build one bundle for the container to pull over the folder connection:

```powershell
tar -czf transfer\real_run_bundle.tar.gz data\processed data\manifests artifacts knowledge\indexes simulation mlflow.db mlruns
```

Report back: per-stage status and wall time (`reports/verification/stage_log.jsonl`), GPU name, preprocess row/link
counts and date range, graph node/edge counts, test MAE lines, calibration coverage, agent decision lines, and the
Ollama digest/version printed by `doctor`.

## 5. Follow-up 2026-10-21: counts, multi-seed study, agents re-run

Run after PR #16 is merged (it carries `scripts/multi_seed_study.py`). Nothing here retrains the main run; the three
deep models are retrained with seeds 42, 1 and 2 into their own folders so the single-seed 0.01-0.06 mph gaps can be
given a spread.

```powershell
git fetch origin
git checkout main
git pull origin main
.\.venv\Scripts\Activate.ps1
pip install -e .
python src\smartcity\ingestion\fetch.py counts --dataset classification --street-like "WEST ST"
python src\smartcity\ingestion\fetch.py counts --dataset volume_hist --street-like "WEST ST"
python scripts\multi_seed_study.py train-all --seeds 42 1 2        # 9 runs, GPU, same budget as the main run
python scripts\multi_seed_study.py analyze                         # multi_seed_metrics.csv + multi_seed_summary.csv
python -m smartcity.cli agents evaluate                             # needs Ollama qwen2.5:7b running
python -m smartcity.cli report export
python -m smartcity.cli paper sync
python -m pytest -q tests\unit tests\safety
```

`train-all` skips any (seed, model) pair whose predictions already exist, so it can be restarted after an interruption.
Hand back as in section 4 (`git add reports artifacts/models/multi_seed_runs.json artifacts/models/ms-* artifacts/agent_traces paper/tables`;
weights and prediction arrays stay ignored) and post the branch name in the project thread. Report the multi-seed
summary lines verbatim; do not round them into a ranking.

## 6. Follow-up 2026-10-21 (b): calibrated SUMO testbed, controller comparison, dashboard screenshots

The corrected testbed (protocol v4) fails the preregistered rule and runs West Street at 5.8 mph simulated against
10.95 mph observed, so the comparison is NOT RUN. Protocol v5 (`configs/simulation.yaml`, `split_calibration`,
fixed before any run) calibrates the corridor green share so that the fixed-time baseline reproduces the observed
speed; the admissibility rule is unchanged. This is a calibrated scenario testbed, not NYC DOT timing, and the
paper will say so. Everything below is SIMULATION; nothing touches real signals.

```powershell
cd "C:\Users\S.K. Sricharan\Downloads\MAJOR PROJECT - FINAL YEAR\PROJECT\repo"
git fetch origin && git checkout -B claude/laptop-sumo-calibration origin/main
.\.venv\Scripts\Activate.ps1
python -m smartcity.cli simulation prepare            # rebuilds the network from data/raw/osm (hashes must match prepared.json)
python -m smartcity.cli simulation calibrate-splits   # 7 factors x 3 seeds, fixed-time only (~20 runs, about 1 h with 4 workers)
python -m smartcity.cli simulation select-demand      # side-demand rule under the calibrated plan (5 levels x 3 seeds)
python -m smartcity.cli simulation evaluate           # 3 scenarios x 3 controllers x 5 seeds = 45 runs, only if a level was selected
python -m smartcity.cli agents evaluate               # the simulation gate can now be reached (Ollama qwen2.5:7b)
python -m smartcity.cli report export
python -m smartcity.cli paper sync
```

If `calibrate-splits` or `select-demand` exits with NOT_RUN, stop there and commit what was produced: the failure is
a result. Also capture the dashboard pages for the deck (REPLAY mode): `streamlit run src/smartcity/dashboard/app.py`,
save "Multi-horizon forecast" as `presentation/assets/dashboard/forecast_laptop.png` and "Traffic map" as
`presentation/assets/dashboard/traffic_map_laptop.png` (about 1600 px wide).

Hand back: `git add reports simulation/scenarios simulation/mappings artifacts/agent_traces paper/tables presentation/assets/dashboard`
(network and demand files stay ignored; their hashes are in `prepared.json` and the calibration record), commit with
the usual trailers, `git push -u origin claude/laptop-sumo-calibration`, and post the branch name in the thread.

## 7. Follow-up 2026-10-25: calibration protocol v6 (common cycle, wider green grid, 25 mph offsets)

Protocol v5 (section 6, run 2026-10-23) reached 8.10 mph at its largest green factor, 2.85 mph short of the observed
10.95 mph, so nothing was selected and the controller comparison stayed NOT RUN. The authors chose a second
preregistered protocol over closing the comparison or waiting for NYC DOT timing plans. Protocol v6 is fixed in
`configs/simulation.yaml` (`split_calibration`, 2026-10-25, before any run): the same construction as v5 plus a
common cycle at every corridor signal (90 or 120 s, or the per-signal Webster cycles as before), green factors 1.0 to
3.0, and corridor-green offsets for a 25 mph platoon along the southbound chain (the mapped link's direction). The
admissibility rule and the 10.95 +- 1.5 mph target are unchanged; ties go to the least intervention. 25 cells x 3 seeds
= 75 fixed-time runs (about 30 min with 4 workers). Any selected program is a calibrated scenario testbed, not NYC DOT
timing, and the paper says so. Everything below is SIMULATION; nothing touches real signals.

```powershell
cd "C:\Users\S.K. Sricharan\Downloads\MAJOR PROJECT - FINAL YEAR\PROJECT\repo"
git fetch origin && git checkout -B claude/laptop-sumo-v6 origin/main
# if the protocol v6 pull request is not merged yet, branch from the build branch instead:
#   git checkout -B claude/laptop-sumo-v6 origin/claude/implement-traffic-system-5rzj9i
.\.venv\Scripts\Activate.ps1
python -m smartcity.cli simulation prepare            # rebuilds the network from data/raw/osm (hashes must match prepared.json)
python -m smartcity.cli simulation calibrate-splits   # protocol v6: 25 cells x 3 seeds, fixed-time only
python -m smartcity.cli simulation select-demand      # side-demand rule under the calibrated plan (5 levels x 3 seeds)
python -m smartcity.cli simulation evaluate           # 3 scenarios x 3 controllers x 5 seeds = 45 runs, only if a level was selected
python -m smartcity.cli agents evaluate               # the simulation gate can now be reached (Ollama qwen2.5:7b)
python -m smartcity.cli report export
python -m smartcity.cli paper sync
```

Re-run note (2026-10-25 23:50 UTC): the first attempt stopped on two code errors before any cell ran (a chain-start
key typo and the one corridor signal the Webster tool leaves out, which now keeps its netconvert program with no
offset, as in v5); both are fixed and tested, the grid and the rule are unchanged. Run the section again from
`prepare` on a fresh `claude/laptop-sumo-v6` branch.

If `calibrate-splits` or `select-demand` exits with NOT_RUN, stop there and commit what was produced: the failure is
a result. `prepare` must report the same network hashes as `prepared.json` (`static_content_sha256` 87174681...);
if it does not, stop and report instead of running the grid on a different network.

Hand back: `git add reports simulation/scenarios simulation/mappings artifacts/agent_traces paper/tables`
(network and demand files stay ignored; their hashes are in `prepared.json` and the calibration record), commit with
the usual trailers, `git push -u origin claude/laptop-sumo-v6`, and post the branch name in the thread.

## 8. Follow-up 2026-10-28: LIVE observational run (new public records, forecasts saved before their targets)

Everything so far is REPLAY (the held-out partition of Jan-Oct 2026) or SIMULATION. The specification's live mode
(section 26: poll, persist, detect repeats and revisions, trigger inference only with enough history, keep the source
age visible, save each forecast before its target, score it when the target arrives) is implemented in
`src/smartcity/live/pipeline.py` and runs only where the public feed is reachable, i.e. on the workstation. It uses
the frozen proposed model and the TRAIN-fitted transforms (the same block functions as the offline feature build; a
schema mismatch stops the run). Everything is labelled LIVE and kept apart from the REPLAY artifacts; nothing touches a
signal.

```powershell
cd "C:\Users\S.K. Sricharan\Downloads\MAJOR PROJECT - FINAL YEAR\PROJECT\repo"
git fetch origin && git checkout -B claude/laptop-live origin/main
# if the LIVE pull request is not merged yet: git checkout -B claude/laptop-live origin/claude/implement-traffic-system-5rzj9i
.\.venv\Scripts\Activate.ps1
python -m smartcity.cli live pull          # one pull: newest speed rows of the 16 links, Open-Meteo forecast, 311 (48 h)
python -m smartcity.cli live forecast      # one LIVE batch for the latest complete 5-minute bin (should say 16 links or why not)
python -m smartcity.cli live run --polls 12 --interval-s 300   # one hour of 5-minute batches, then ~75 min of settling pulls, then score
python -m smartcity.cli report export
python -m smartcity.cli paper sync
```

Run it on a weekday afternoon (the DOT feed is densest then) and leave the machine awake and online for the whole
2 h 15 min; `live run` prints a line per poll. If `live forecast` reports every link withheld (INSUFFICIENT_HISTORY)
the feed is sparse or lagging: run `live pull` again after ten minutes before starting the hour. The settle phase
exists so the 60-minute targets of the last batch can be observed; stopping early leaves them PENDING, which is a
result, not an error.

Hand back: `git add artifacts/live reports/experiments/live_metrics.csv reports/verification paper/tables data/raw/live/*/fetch_log.jsonl`
(the raw pull bodies stay ignored; their hashes are in the fetch logs), commit with the usual trailers,
`git push -u origin claude/laptop-live`, and post the branch name in the thread.

## 9. Follow-up 2026-10-29: LIVE run with a latest-available origin (preregistered protocol)

Two wall-clock attempts (section 8, 28 and 29 Oct) found the public feed 1.7-4.3 h behind on weekday afternoons, so
every link was withheld. The owner chose the preregistered latest-available protocol
(`docs/live_latest_available_protocol.md`): same model, features, lookback rule and scoring; the origin is the newest
bin the feed has published, its data age is recorded on every forecast, and a target is scored only when its bin was
first retrieved after the forecast was written. The wall-clock attempts stay recorded as NOT RUN.

```powershell
cd "C:\Users\S.K. Sricharan\Downloads\MAJOR PROJECT - FINAL YEAR\PROJECT\repo"
git fetch origin && git checkout -B claude/laptop-live origin/main
.\.venv\Scripts\Activate.ps1
python -m pytest -q tests/unit/test_live.py
python -m smartcity.cli live pull
python -m smartcity.cli live forecast --origin latest-available      # should forecast links with a data age of 1-4 h
python -m smartcity.cli live run --polls 24 --interval-s 300 --origin latest-available --settle-max-hours 4
python -m smartcity.cli report export
python -m smartcity.cli paper sync
```

Any weekday between about 12:00 and 18:00 New York time; keep the machine awake and online (a keep-awake heartbeat,
as on 29 Oct) for the two-hour window plus up to four hours of settling: the settle phase stops early as soon as the
feed publishes the last batch's 60-minute target. A poll that finds no newer published bin writes no new batch; that
is expected. Hand back as in section 8, and report the `live_summary.json` status (OK / PARTIAL / NOT_RUN), the number
of batches, the mean data age at issue and the number of rows excluded as published before issue.

