# Paper figures

All charts are drawn by `paper/figures/make_figures.py` from the committed result files; nothing is typed in by hand
except the two diagrams, which describe the code in `src/smartcity`. Each figure exists as `<name>.pdf` (vector, for
LaTeX) and `<name>.png` (300 dpi, for Word). Widths: single column 3.45 in, double column 7.16 in.

| File | Width | Draft caption | Source | Mode |
|---|---|---|---|---|
| fig_system_architecture | double | System overview: public data sources, preprocessing and graph construction, the forecaster with conformal calibration and SHAP explanations, the retrieval-augmented advisory workflow with deterministic safety checks, and the SUMO testbed, human review queue and delivery layer. No command is ever sent to a real signal. | src/smartcity | diagram |
| fig_model_architecture | single | The proposed forecaster: six feature groups are projected and fused by an availability-aware gate, passed through two GATv2 layers over the directed link graph and two Transformer encoder layers over the 24-step window, and read out at the last step for the 15, 30 and 60 min horizons; split conformal prediction adds a 90 % band. 158 k parameters. | src/smartcity/models/deep.py, configs/model.yaml, artifacts/models/proposed-20261020T201110-0e333f/run_info.json | diagram |
| fig_code_structure | single | Package layout of the implementation. | src/smartcity, tests | diagram |
| fig_forecast_mae | single | Test MAE by model and horizon on the operational track (chronological test period 6 Sep to 20 Oct 2026, 16 links). | reports/experiments/forecast_metrics.csv | REPLAY |
| fig_multi_seed | single | Seed mean and standard deviation of test MAE over seeds 1, 2 and 42 for the proposed model, the GRU and the temporal-only Transformer. | reports/experiments/multi_seed_summary.csv | REPLAY |
| fig_conformal_coverage | single | Empirical coverage of the 90 % split-conformal intervals by horizon, overall and by congestion level of the target link; coverage falls to 0.76 to 0.80 under congestion. | reports/experiments/uncertainty_metrics.csv | REPLAY |
| fig_ablation | single | Change in test MAE when one input group is removed, with 95 % bootstrap intervals over test days. Removing the gate hurts; removing the weather features helps (a negative result for those features). | reports/experiments/ablation_metrics.csv | REPLAY |
| fig_shap_groups | single | Mean absolute grouped KernelSHAP attribution per input group over the 12 explained test points of the trained proposed model. | artifacts/explanations/explanations_summary.json | REPLAY |
| fig_temporal_window | single | Test MAE of the proposed model when only the most recent minutes of input history are kept. | artifacts/explanations/explanations_summary.json (temporal_window) | REPLAY |
| fig_deferral | single | Deferral-gate trade-off: MAE on retained origins against the share of origins deferred, per horizon; the square marks the chosen missing-data threshold (0.34). | artifacts/calibration/deferral_tradeoff.csv | REPLAY |
| fig_live_by_day | double | The three live afternoons (latest-available origin, forecasts issued at the feed's own latency): model versus persistence MAE per horizon on each afternoon and pooled. Persistence is ahead at 15 and 30 min in the pooled result. | reports/experiments/live_metrics_by_day.csv, reports/experiments/live_metrics.csv | LIVE |
| fig_sumo_calibration | single | Protocol v6 signal-timing calibration on the SUMO corridor: seed-mean simulated speed on the reference link for each cycle, offset and green-factor cell against the observed 10.95 mph target (band: tolerance 1.5 mph). The star marks the selected cell (90 s cycle, factor 1.5, 25 mph offsets). | simulation/scenarios/split_calibration_v6_counts2025_cycle_splits_offsets.json | SIMULATION |
| fig_sumo_comparison | double | Controller comparison on the calibrated testbed, seed means over five matched seeds: mean time loss per vehicle and completed trips for fixed time, the forecast-triggered rule and the uncalibrated actuated reference. A simulation finding on a calibrated scenario testbed, not a real-world gain. | reports/experiments/simulation_metrics.csv (networks 36fb9c1fb895b7e7, 98e143b6f4e1296a) | SIMULATION |
| fig_advisory_decisions | single | Decisions of the 19 replayed advisory cases by policy: the constrained policies route every case to human review or a deferral; the unconstrained LLM is rejected by the safety constraints in three of four cases. | reports/experiments/advisory_metrics.csv | REPLAY |
| fig_retrieval_queries | single | Recall@8 and reciprocal rank of the 22 scored retrieval queries (six status-only queries carry no relevant document); labels reviewed by the first author on 19 Nov 2026. | reports/experiments/retrieval_metrics.csv | REPLAY |

Dashboard screenshots for the paper live in `presentation/assets/dashboard/` (REPLAY/SIMULATION views; a fresh
capture of every page, including the live page with the three afternoons, is being taken on the workstation).
