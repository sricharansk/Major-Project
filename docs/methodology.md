# Methodology

This document describes what the code does, in the order the pipeline runs. Every design choice that affects a
reported number is tied to a configuration key or a source file so a reader can check it. Numbers themselves live
in `reports/experiments/` and are generated, never typed.

## 1. Data and provenance

* **Speed targets**: NYC DOT Real-Time Traffic Speed Data (Socrata `i4gi-tjb9`), Manhattan links, 2026-01-01 to
  2026-10-20. Each page is stored verbatim as gzip JSON with a `fetch_log.jsonl` line (URL, time, HTTP status,
  SHA-256). `python src/smartcity/ingestion/fetch.py audit` verifies the dataset identity and observed date ranges
  server-side before anything is downloaded; results are in `reports/data_audit/source_inventory.csv`.
* **Context sources**: Open-Meteo historical forecast (operational weather) and archive (retrospective weather), NYC Automated Traffic Volume Counts (`7ym2-wayt`, sampled ATR
  counts used only for SUMO demand), NYC permitted events (`tvpp-9vvx` current, `bkfu-528j` historical), Motor Vehicle
  Collisions (`h9gi-nx95`), 311 service requests (`erm2-nwe9`), OpenStreetMap via Overpass (geometry for SUMO).
* **Observation-time rules** (`configs/data.yaml`): collisions and historical events have no reliable announcement
  time, so they are used only in the *retrospective* feature track; 311 is used operationally with a declared 24 h
  lag; the operational track uses Open-Meteo *historical forecasts* (what a forecast issued at the time would have
  said) while the retrospective track uses the finalised archive; `tests/leakage` asserts the track groups.

## 2. Preprocessing (`smartcity.preprocessing`)

1. Socrata timestamps are floating NYC-local; they are localised with `America/New_York` and converted to UTC.
   The ambiguous DST fall-back hour is set to null rather than guessed.
2. Records are snapped to a right-labelled 5-minute grid per link (`frequency_minutes`). Multiple records in one
   bin are averaged; physically impossible speeds (`speed_min_mph`/`speed_max_mph`) are nulled.
3. Gaps are forward-filled for at most 3 steps (`max_ffill_steps`), causally; longer gaps stay missing and a
   `missing` indicator is kept as a feature.
4. **Splits** are chronological: train / validation / calibration / test by date, with purge gaps of one maximum
   horizon plus the longest lag between consecutive partitions so no target window overlaps a neighbouring split
   (`split_manifest.json` per run; `tests/leakage` asserts it).
5. Scalers (per-link mean/std of speed) are fitted on the train partition only and stored with the run.

## 3. Graph (`smartcity.graph`)

Nodes are DOT links. A directed edge `a -> b` is accepted by one of three rules, each recorded per edge:
(1) endpoint continuity: the end point of `a` is within `endpoint_join_m` of the start point of `b` and the heading
change is below `max_heading_change_deg`; (2) corridor continuity: `b` is the nearest link on the same signed corridor
(same name stem and direction token, e.g. "FDR N") whose start lies downstream of `a`'s end within `corridor_join_m`;
(3) named-endpoint continuity: DOT link names state their endpoints ("FDR S 63rd - 25th St" -> "FDR S 25th St -
Catherine Slip"), and when `a`'s "to" label and `b`'s "from" label share a distinctive token (a street number,
"Catherine Slip", "ganservoort", "GWB"; generic words such as "Toll Plaza" or "Manhattan Side" never count), the links
are not opposite directions, `b` starts ahead of `a` and within `named_join_m` of `a`'s end, and the headings are
compatible, the edge is accepted. Rules 2 and 3 exist because the published `link_points` polylines neither tile the
highways nor reliably reach the named end of a link (in the 2026 Manhattan set "FDR S 63rd - 25th St" carries 1.5 km
of geometry for a 3 km segment and stops 1.5 km short of the next segment's start). Every candidate pair, accepted or
rejected, is written with its rationale to `reports/data_audit/graph_edges.csv`, and `graph validate` reports
component counts and isolated nodes. The graph is exposed as a PyTorch Geometric Temporal
`StaticGraphTemporalSignal` (`smartcity.graph.temporal`), so the model consumes a real temporal graph signal.

## 4. Features (`smartcity.features`)

Two tracks share code paths and differ only in which sources are allowed:

| Track | Sources | Purpose |
|---|---|---|
| operational | speed lags, calendar, historical weather forecast, 311 (24 h lag), link attributes | the deployable model |
| retrospective | operational with archive weather in place of the forecast, + collisions + historical events | analysis of incident/event effects |

Feature groups are recorded in `feature_schema.json` so that gating, ablations and explanations use the same
grouping.

## 5. Models (`smartcity.models`, `smartcity.training`)

* **Baselines**: persistence, historical average by link and time-of-day, XGBoost and LightGBM on lagged tabular
  features (one booster per horizon), a GRU, and a temporal Transformer without the graph.
* **Proposed**: *context-gated GATv2 + Transformer encoder*. Per time step, a GATv2 layer mixes neighbouring links
  along the directed graph; an availability-aware gate weights each context feature group by its presence mask so
  missing context cannot masquerade as zero; a Transformer encoder over the lag window produces multi-horizon outputs
  (15/30/60 min) at once. Loss is masked Huber on standardised speed; targets that are missing contribute nothing.
* **Ablations** (`DEEP_VARIANTS` in `training/runner.py`): no gate, no weather, no infrastructure, no events, no
  incidents; `evaluate ablations` reports mean test MAE with a day-block bootstrap CI on the paired difference.
* Early stopping on validation MAE; one fixed seed (`training.seed`); every run writes config, feature schema, split
  manifest, training history, environment and predictions for val/calib/test, and is logged to MLflow.
* Evaluation uses the **same test origins and the same valid-target mask** for every model
  (`runner.evaluate_and_export`), so comparisons are paired.

## 6. Uncertainty (`smartcity.uncertainty`)

Split conformal prediction on the calibration partition, per horizon (global) and per link where the link has
enough calibration residuals (`min_calibration_samples`), at nominal 90 % coverage. Empirical coverage and mean
width are measured on the test partition only. A reliability gate derived from the calibrated width is used by
the advisory workflow to defer when an interval is too wide.

## 7. Explainability (`smartcity.explainability`)

Explanations are computed on the trained proposed model, not a surrogate: grouped exact KernelSHAP over feature
groups for selected alert cases, plus neighbour sensitivity (perturbing upstream links) and temporal sensitivity
(perturbing lag blocks). Tree baselines use TreeSHAP for comparison. Each explanation records runtime, number of
model calls and the exact run id it explains.

## 8. Knowledge retrieval (`smartcity.knowledge`, `smartcity.rag`)

Only documents listed in `knowledge/source_registry.csv` with `approved=yes` and a matching SHA-256 are chunked
(paragraph-aware, ~200 word-pieces, verified against the MiniLM 256-token limit), embedded with
`all-MiniLM-L6-v2` and indexed in FAISS (inner product on normalised vectors). Every chunk carries an authority
label (official standard, agency guidance, project-defined policy). `rag evaluate` reports recall@k, MRR and
support-status accuracy against `knowledge/retrieval_eval_queries.csv`, whose labels were drafted by the project
and whose review status is recorded in the output. Retrieved text is treated as untrusted data.

## 9. LLM and agentic workflow (`smartcity.agents`)

The LLM (Ollama, `qwen2.5:7b`) receives the forecast, interval, explanation summary and retrieved evidence, and
must answer in a JSON schema (`AdvisoryResponse`), validated with Pydantic; invalid output is a recorded failure
state, not retried into compliance silently. The LangGraph workflow has distinct terminal decisions: defer on data
quality, defer on uncertainty, insufficient evidence, rejected by constraints, rejected by simulation, pending human
review. Deterministic constraints (`smartcity.safety`) run in code before any simulation: allowed action types,
phase existence, min/max green, clearance intervals, mapping review status. The LLM never changes a constraint.

## 10. Simulation (`smartcity.simulation`)

A SUMO network is built from OSM geometry for the study corridor; demand comes from matched ATR counts where they
exist and from declared assumptions otherwise (all written to `simulation/scenarios/prepared.json`). The
`ProtectedController` applies only bounded green extensions or pre-validated programs through TraCI. Baseline and
candidate run with matched seeds; the comparison reports corridor and side-road time loss, arrivals and teleports.
The testbed is a scenario, not a calibrated digital twin, and all its outputs are labelled SIMULATION.

## 11. Service, dashboard, tracking

FastAPI exposes forecasts, explanations, retrieval and advisory jobs; long jobs go through a Postgres-backed queue
and a worker. The Streamlit dashboard reads artifacts only. MLflow (SQLite) records every training run;
`report export` writes the evidence registry, runtime metrics and the MLflow run table.

## 12. Verification discipline

`reports/verification/evidence_registry.csv` maps each requirement to code, a command, an artifact and a status.
Status is VERIFIED only when the artifact exists and its check passed; human notes in `overrides.json` can lower a
status (for example to BLOCKED) with a reason, never raise it.
