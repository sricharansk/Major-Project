# Model card: context-gated GATv2-Transformer for multi-horizon link-speed forecasting

Fields marked *(from artifacts)* are filled by the real-data run; until `reports/experiments/forecast_metrics.csv`
exists they read NOT_RUN. Nothing here is an estimate.

## Model details

* **Architecture**: `smartcity.models.deep.ContextGatedGraphTransformer` — GATv2 spatial layer over the directed
  link graph, availability-aware gate over context feature groups, Transformer encoder over the lag window,
  linear heads for 15/30/60-minute horizons.
* **Inputs**: per-link standardised speed lags, missing indicators, calendar features, historical weather forecast, 311
  (24 h lag), link attributes (operational track). Feature list: `artifacts/models/<run>/feature_schema.json`.
* **Output**: speed in mph per link per horizon, with split-conformal intervals from
  `artifacts/calibration/calibrator.json`.
* **Training data**: NYC DOT real-time speed links, Manhattan, 2026-01-01 to 2026-10-20 (train partition only);
  exact bounds in `artifacts/models/<run>/split_manifest.json`.
* **Selected run** *(from artifacts)*: `artifacts/models/selected.json`.

## Intended use

Research prototype for retrospective (REPLAY) evaluation and for feeding a simulation-only signal advisory
workflow. Not for operational traffic management; no output of this system controls real infrastructure.

## Out-of-scope uses

Any live control, safety-critical use, or use outside the trained link set and period. Boroughs other than
Manhattan were not trained on. Forecasts for links whose data are stale or mostly missing are gated to DEFER by the
workflow and should be treated the same way by any other consumer.

## Metrics *(from artifacts)*

Test-partition MAE/RMSE by horizon, paired against persistence, historical average, XGBoost, LightGBM, GRU and a
temporal Transformer on the identical valid-target mask: `reports/experiments/forecast_metrics.csv`.
Ablations with bootstrap CIs: `reports/experiments/ablation_metrics.csv`. Conformal coverage and width:
`reports/experiments/uncertainty_metrics.csv`.

## Evaluation protocol

Chronological splits with purge gaps; scalers fitted on train; seed 42 for the main run and seeds 42, 1, 2 for the
three-seed comparison of the deep models (`reports/experiments/multi_seed_summary.csv`); early stopping on validation
MAE; test touched once per model. Identical origins and target mask for all models.

## Explainability

Grouped exact KernelSHAP on this model (not a surrogate) for alert cases, plus neighbour and temporal sensitivity:
`artifacts/explanations/`. Explanations are of the model's behaviour, not causal claims about traffic.

## Known limitations

* Operational weather is Open-Meteo's historical-forecast product, a re-forecast proxy for what was knowable at
  the time, not an archived agency forecast.
* DOT links are a sparse, highway-heavy selection, not a full street network; neighbours are often distant.
* Three seeds for the deep models only (seed-mean MAE 4.69/5.34/6.15 mph; GRU 4.67/5.37/6.18; temporal Transformer
  4.72/5.38/6.23); baselines and ablations are single-seed. On the GPU the model is not bit-reproducible at a fixed
  seed (GATv2 scatter).
* Context sources are sparse in time; the gate was designed for that but the ablation table is the evidence, not
  the design intent.
* See `reports/limitations.md` for the full list, including anything BLOCKED in this run.

## Ethical and legal

Public open data under NYC Open Data terms, Open-Meteo (CC BY 4.0) and OpenStreetMap (ODbL). No personal data is
used; collision records are aggregated to link-time counts.
