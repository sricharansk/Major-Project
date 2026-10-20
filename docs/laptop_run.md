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
