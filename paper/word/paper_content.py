"""Text of the IEEE conference paper (Word version), kept in step with paper/main.tex.

Inline markup understood by build_ieee_docx.py:
  *x*        italic           **x**      bold          `x`   monospace (file paths, commands)
  _{x}       subscript        ^{x}       superscript   [@k1,k2]  citation, numbered by first appearance
  {T:id}     table number     {S:id}     section number

Every number below is taken from the files listed in reports/verification/paper_claims.csv; the tables are
read from the generated paper/tables/*.tex and reports/data_audit/source_inventory.csv by the builder.
"""

TITLE = (
    "Predictive Analytics for Smart City Infrastructure: Multi-Horizon Traffic Congestion Forecasting and "
    "Explainable Agentic Signal Advisory Using Spatiotemporal Transformers and RAG"
)

# One entry per author column: name, then the affiliation lines in template order
# (designation, dept. name of organization, name of organization, city/country, email).
AUTHORS = [
    {
        "name": "S K Sricharan",
        "lines": [
            ("i", "M.Tech. Artificial Intelligence and Machine Learning,"),
            ("i", "School of Computer Science and Engineering (SCOPE)"),
            ("i", "Vellore Institute of Technology, Chennai"),
            ("", "Chennai, India"),
            ("", "sksricharan2003@gmail.com"),
        ],
    },
    {
        "name": "Dr. R. Srinivasa Perumal",
        "lines": [
            ("", "Associate Professor"),
            ("i", "School of Computer Science and Engineering (SCOPE)"),
            ("i", "Vellore Institute of Technology, Chennai"),
            ("", "Chennai, India"),
            ("", "r.srinivasaperumal@vit.ac.in"),
        ],
    },
]

# 150-250 words, one paragraph, no citations, symbols or equations (IEEE guideline supplied with the template).
ABSTRACT = (
    "Traffic management needs accurate, calibrated and explainable multi-horizon forecasts. We present a Manhattan prototype that couples a context-gated graph attention and Transformer forecaster for 15-, 30- and 60-minute "
    "link-speed prediction with a retrieval-augmented, constraint-checked agentic workflow that drafts "
    "simulation-only signal-timing advisories. It runs on a road-link graph "
    "of New York City real-time speeds, fuses weather, 311 and calendar context through an "
    "availability-aware gate, is calibrated with split conformal prediction and explained with grouped Shapley "
    "values. On nearly ten months of public data (1 January to 20 October 2026, 16 "
    "usable links) and a 44-day chronological test partition, the proposed model reaches a mean absolute error of "
    "4.77, 5.33 and 6.15 mph at the three horizons, 7 to 16 percent below persistence and below both "
    "gradient-boosted baselines; over three seeds it is 0.03 to 0.08 mph below a temporal-only Transformer at every "
    "horizon and below a GRU at 30 and 60 minutes, while the GRU is better at 15 minutes. "
    "The availability gate helps; operational weather features hurt. Conformal intervals reach "
    "0.90 to 0.91 coverage overall but only 0.76 to 0.80 under congestion; a deterministic reliability gate defers "
    "26 percent of forecasts and raises coverage on the rest to 0.93 to 0.95. Retrieval removed fabricated "
    "citations. After a second preregistered calibration brought the SUMO testbed to 10.1 of the observed "
    "10.95 mph, a forecast-informed signal rule lowered simulated time loss by about 5 percent under configured "
    "stress while completing more trips, a simulated result and not a real-world gain."
)

# 5-7 keywords in alphabetical order.
KEYWORDS = [
    "Conformal prediction",
    "explainable artificial intelligence",
    "graph neural networks",
    "retrieval-augmented generation",
    "traffic forecasting",
    "traffic simulation",
    "transformers",
]

BODY = [
    ("h1", "Introduction", "intro"),
    ("p", "Urban traffic-management centres typically observe congestion as it happens. Linking an *advance* "
          "forecast to an explainable, evidence-grounded and tested operational recommendation remains difficult: "
          "traffic depends on recurrent demand, neighbouring links, weather, planned events, disruptions and "
          "infrastructure condition, and a forecast alone does not establish which intervention helps. An "
          "LLM-generated signal recommendation is, by itself, not evidence that an action is safe or effective."),
    ("p", "We study a decision-support pipeline for the scenario of a permitted event near a busy corridor in which "
          "rain and a nearby collision coincide. The pipeline (i) forecasts link speeds 15, 30 and 60 minutes "
          "ahead with a context-gated graph spatiotemporal Transformer, (ii) attaches split-conformal prediction "
          "intervals, (iii) explains the forecast of the actual model with grouped Shapley values, (iv) retrieves "
          "operational guidance with a FAISS index, (v) asks a local LLM (Qwen2.5-7B-Instruct via Ollama) for "
          "schema-constrained candidate actions, (vi) applies deterministic safety constraints, and (vii) tests "
          "admissible candidates in a SUMO microscopic simulation before human review."),
    ("p", "*Proposed contributions* (stated as proposals; their effects are reported only where measured): (1) "
          "availability-aware context fusion in the graph forecaster; (2) an explicit uncertainty-and-evidence "
          "gate that decides whether advisory generation proceeds; (3) a simulation-based candidate gate with "
          "side-road protection; and (4) a traceable evaluation that links forecast quality, grounding, deferral "
          "and simulated intervention outcomes to versioned artifacts. We do not claim deployment, real-world "
          "congestion reduction or causal explanations."),

    ("h1", "Related Work", "related"),
    ("p", "*Graph traffic forecasting:* Diffusion-convolutional recurrent networks [@li2018dcrnn], spatio-temporal "
          "graph convolution [@yu2018stgcn] and Graph WaveNet [@wu2019graphwavenet] established graph neural "
          "networks for sensor-network speed forecasting; attention-based variants use graph attention "
          "[@brody2022gatv2] and Transformer encoders [@vaswani2017attention]. Our model combines GATv2 message "
          "passing with a temporal Transformer and adds an availability-aware gate over feature groups; we treat "
          "it as a project-designed architecture, not a new model family."),
    ("p", "*Uncertainty:* Split conformal prediction [@vovk2005algorithmic,angelopoulos2021gentle] gives "
          "finite-sample marginal coverage under exchangeability; for time series this assumption can fail, "
          "motivating adaptive and non-exchangeable variants [@barber2023beyond,xu2021enbpi]. We therefore report "
          "empirical coverage by horizon and scenario."),
    ("p", "*Explainability:* SHAP [@lundberg2017shap] attributes predictions to inputs; for tree baselines we use "
          "TreeSHAP, and for the graph model a grouped KernelSHAP over feature groups and graph neighbourhoods."),
    ("p", "*Retrieval-augmented LLMs:* RAG [@lewis2020rag] conditions generation on retrieved passages; we embed "
          "passages with Sentence-BERT models [@reimers2019sbert] and search them with FAISS [@johnson2019faiss]. "
          "The LLM is Qwen2.5 [@qwen2025qwen25]."),
    ("p", "*Simulation:* SUMO [@lopez2018sumo] with TraCI is widely used to evaluate signal control. We use it as a "
          "scenario-based testbed and do not claim calibration to real demand."),

    ("h1", "Problem Formulation", "problem"),
    ("p", "Let *G* = (*V*, *E*) be a directed graph whose nodes are monitored directed road links and whose edges "
          "connect a link to links that can receive its traffic. At each 5-minute step *t* every node *v* carries "
          "a feature vector *x*_{*t,v*} partitioned into groups *g* ∈ {traffic, calendar, weather, "
          "infrastructure, events, incidents} with availability indicators *m*_{*t,v,g*}. Given the last *L* = 24 "
          "steps, the task is to predict observed link speed *y*_{*t*+*h*,*v*} for *h* ∈ {3, 6, 12} steps "
          "(15/30/60 min), together with an interval [*ŷ* − *q*_{*h*}, *ŷ* + *q*_{*h*}]. A downstream advisory "
          "is admissible only if data quality, interval width, retrieved evidence, deterministic constraints and a "
          "simulation comparison all pass; otherwise the system returns a distinct DEFER or REJECT status. "
          "Training minimises a masked Huber loss over observed targets only."),

    ("h1", "Data", "data"),
    ("p", "All sources are public ({T:sources}). Speed targets come from the NYC DOT Real-Time Traffic Speed Data "
          "feed (Socrata `i4gi-tjb9`) [@nycdotspeeds], restricted to Manhattan links with geometry, for "
          "2026-01-01 to 2026-10-20. Each record carries a floating local timestamp that is localised to "
          "`America/New_York` and converted to UTC; the ambiguous daylight-saving hour is nulled rather than "
          "guessed. Records are snapped to a right-labelled 5-minute grid per link, averaged within a bin, bounded "
          "to physically plausible speeds, and forward-filled causally for at most three steps. Context comes from "
          "Open-Meteo [@openmeteo] (historical forecasts for the operational track, the finalised archive for the "
          "retrospective track), NYC 311 service requests with a declared 24-hour lag, Motor Vehicle Collisions "
          "(retrospective only; the feed lagged publication by about four months at download time) and NYC "
          "permitted events. Sampled automated traffic volume counts parameterise simulation demand only. "
          "OpenStreetMap supplies geometry for the simulated corridor."),
    ("table", "sources"),
    ("p", "Every download is logged with URL, time, HTTP status and SHA-256, and a server-side audit of dataset "
          "identity and observed date ranges precedes every download; the full-year link enumeration timed out "
          "server-side, so the link set is the 125 links citywide active since 2026-09-20, of which 26 are in "
          "Manhattan. Of 1,968,303 raw Manhattan speed records, 978,018 carry a zero speed (the feed’s "
          "no-measurement encoding) and are treated as missing, never imputed; 990,226 valid records fill an "
          "84,084-step grid over 19 links (observed fraction 0.611), seven links being dead feeds with no valid "
          "2026 record. Links with at least 50% training-period coverage enter the models: 16 links, three of "
          "which have no valid test-period observation and are reported as NOT_EVALUATED "
          "(`reports/data_audit/link_coverage_operational.csv`, "
          "`reports/experiments/link_test_support_operational.csv`)."),

    ("h1", "Proposed Methodology", "method"),
    ("h2", "Context-Gated GATv2–Temporal Transformer"),
    ("p", "For each node and time step, every feature group *g* is projected to a common width *d* = 64 and scored "
          "by a small network:"),
    ("eq", "*h*_{*t,v,g*} = ReLU(*W*_{*g*} *x*_{*t,v,g*}),   *s*_{*t,v,g*} = *w*^{⊤} tanh(*U h*_{*t,v,g*})"),
    ("p_noindent", "Scores of unavailable groups (*m*_{*t,v,g*} = 0) are masked to −∞ and a softmax over the "
          "remaining groups yields weights *α*_{*t,v,g*}; the fused representation is"),
    ("eq", "*z*_{*t,v*} = Σ_{*g*} *α*_{*t,v,g*} *h*_{*t,v,g*}"),
    ("p_noindent", "If no group is available a learned “unavailable” vector is used and the event is logged. Two "
          "GATv2 layers [@brody2022gatv2] (4 heads, residual connections, layer normalisation) propagate *z* over "
          "the fixed directed graph at every time step (implemented with PyTorch Geometric [@fey2019pyg]). Each "
          "node’s sequence then receives a learned positional embedding and passes through a 2-layer, 4-head "
          "Transformer encoder (feed-forward width 128, dropout 0.1); a linear head on the last state outputs the "
          "three horizons. Targets are standardised per link with training-period statistics and the masked Huber "
          "loss is averaged over observed targets only; batches without any observed target are skipped and "
          "counted. Optimisation: AdamW (learning rate 10^{−3}, weight decay 10^{−4}), batch size 8, gradient "
          "clipping at 1.0, early stopping on validation MAE with patience 5 and at most 30 epochs, seed 42. The "
          "temporal snapshots are held in a PyTorch Geometric Temporal [@rozemberczki2021pgt] "
          "`StaticGraphTemporalSignal`, from which training windows are drawn lazily. The gate weights are not "
          "interpreted as causal importance."),
    ("h2", "Baselines and Ablations"),
    ("p", "Persistence (last observation), a training-period historical average per link, day type and 5-minute "
          "slot, XGBoost [@chen2016xgboost] and LightGBM [@ke2017lightgbm] (one model per horizon on 12 speed lags "
          "and the same causal features), a GRU, and a temporal-only Transformer (the proposed model without "
          "message passing). Ablations remove the gate (concatenation instead), or one feature group at a time."),
    ("h2", "Uncertainty and Reliability Gate"),
    ("p", "With the selected model frozen, per-horizon absolute residuals on the calibration partition give the "
          "split-conformal quantile"),
    ("eq", "*q*_{*h*} = *r*_{(*k*)},   *k* = ⌈(*n* + 1)(1 − *α*)⌉,   *α* = 0.1"),
    ("p_noindent", "where *r*_{(*k*)} is the *k*-th smallest of the *n* calibration residuals; a per-link variant is also computed when at least 50 calibration residuals exist. The "
          "advisory gate defers when data are older than 20 minutes, more than one third of recent traffic inputs "
          "are missing, the interval is wider than a threshold chosen on calibration data (80th percentile of "
          "per-link widths), or calibration support is below 200 samples."),
    ("h2", "Explanations"),
    ("p", "For an alert (link *v*, horizon *h*, origin *t*) the explained scalar is the predicted speed in mph. "
          "Players are the target’s recent traffic (last 30 min), older traffic (30–120 min), the traffic of its "
          "graph neighbours and each context group; an absent player takes values from 16 training-period "
          "background windows. All 2^{*P*} coalitions are evaluated (exact KernelSHAP [@lundberg2017shap]). We "
          "additionally measure neighbour-edge removal and temporal-window sensitivities. Tree baselines are "
          "explained with TreeSHAP and labelled as baseline explanations."),
    ("h2", "Retrieval, LLM and Agentic Workflow"),
    ("p", "Approved documents (U.S. federal signal-timing guidance [@fhwa2008stm,mutcd2009], SUMO documentation, "
          "and a clearly labelled project-defined experimental policy) are hashed, allow-listed, chunked with a "
          "200 word-piece target and indexed with a FAISS inner-product index over normalised all-MiniLM-L6-v2 "
          "embeddings; chunks that still exceed the encoder’s 256-token window (171 of 1,633 in the built index, "
          "mostly tables of the PDF manual) are truncated by the encoder, and the count is recorded in the index "
          "manifest. A query whose best passages score below 0.35 returns INSUFFICIENT_EVIDENCE. The LLM receives "
          "forecasts, intervals, quality flags, computed attributions, retrieved passages (marked as untrusted "
          "text) and the allowed action catalogue, and must return JSON that satisfies a Pydantic schema enforced "
          "through Ollama’s structured-output option. A LangGraph state machine runs quality → forecast → "
          "uncertainty → explanation → retrieval → recommendation → safety → simulation → decision → human "
          "review, with deterministic routing to DEFER_DATA, DEFER_UNCERTAINTY, DEFER_EVIDENCE, REJECT_SCHEMA, "
          "REJECT_CONSTRAINT, REJECT_SIMULATION, PENDING_HUMAN_REVIEW or ERROR_TOOL. Only the recommendation node "
          "calls the LLM."),
    ("h2", "Safety Constraints and Simulation Gate"),
    ("p", "Allowed actions are a bounded green extension (0–10 s) of an existing green phase, selection of a "
          "pre-validated program, or monitoring only. Thirteen deterministic checks (mapping validity, signal and "
          "phase existence, action type, bounds, minimum/maximum green, clearance preservation, pedestrian and "
          "side-road protection availability, data freshness, forecast reliability, evidence support) plus a text "
          "policy filter must pass. Candidates are then applied through a protective TraCI wrapper that refuses "
          "non-green phases and out-of-bound durations, and compared with the fixed-time baseline on matched "
          "seeds; a candidate passes only if corridor delay improves by at least 1%, side-road delay rises by at "
          "most 10% and no vehicle teleports. Each flow drives one fixed free-flow route so that demand stays on "
          "the corridor, the fixed-time programs are re-timed for the routine demand with Webster’s method (SUMO "
          "`tlsCycleAdaptation.py`; a declared assumption, not NYC timing plans), and the testbed itself must "
          "first pass a baseline test: the side-street demand level is the largest at which the fixed-time "
          "baseline, on development seeds, has no teleport and at most 1% unfinished trips; without such a level "
          "no candidate is scored (NOT_EVALUATED). Pedestrian performance is not modelled and is reported as "
          "NOT_EVALUATED."),

    ("h1", "Experimental Design", "experiments"),
    ("p", "*Partitions:* The 5-minute time axis is split chronologically into training (60%), validation (15%), "
          "calibration (10%) and test (15%). A forecast origin belongs to a partition only if all of its targets "
          "fall inside it (purging); earlier history may be used as input. Scalers and link eligibility "
          "(training-partition coverage ≥ 0.5, lowered from the planned 0.6 after the coverage audit and recorded "
          "as such) use the training partition only."),
    ("p", "*Feature tracks:* The *operational* track uses traffic, calendar, archived weather *forecasts* "
          "(Open-Meteo historical-forecast API; issue times are not exposed, a disclosed limitation) and 311 "
          "requests with a declared 24-hour publication lag. The *retrospective* track replaces forecasts by "
          "reanalysis weather and adds collisions and borough-level permitted events, whose operational "
          "availability cannot be established; it is used for contextual analysis only."),
    ("p", "*Metrics:* MAE, RMSE, sMAPE and *R*^{2} per horizon on a shared valid-target mask; paired day-block "
          "bootstrap for model differences; empirical interval coverage and width by horizon, congestion category "
          "and scenario; Recall@*k*, MRR and support-status accuracy for retrieval; schema validity, "
          "invalid-citation counts, constraint violations and decision distribution for advisories; SUMO time "
          "loss, travel time, waiting time, stops, queue length, throughput, side-road delay, unfinished trips, "
          "insertion backlog and teleports; and latency of each stage."),
    ("p", "*Training budget:* Every deep model (GRU, temporal Transformer, proposed model, ablations) is trained "
          "with AdamW and early stopping as in Section {S:method}, under a recorded compute budget of 4,096 "
          "training windows per epoch, sampled afresh each epoch (`configs/training.yaml`); the budget, the "
          "resolved device and the stop reason are written into every run’s configuration, and the budget is the "
          "same for all models."),
    ("p", "*Advisory cases and policies:* Seven REPLAY cases chosen by rule from the test partition: routine rush "
          "hour (largest predicted drop at a weekday peak), rainy period (a wet weather code, present in this test "
          "partition), a stale-data stress test (inputs aged six steps), a wide-interval stress test (forced "
          "99 mph width), an out-of-scope query (insufficient evidence), and two cases on the one link with a "
          "reviewed, high-confidence mapping to the simulated corridor (its largest predicted drop and an ordinary "
          "rush-hour origin). Policies: full system; LLM without retrieval; RAG without the constraint layer; RAG "
          "with constraints but without the simulation gate. The three stress cases run under the full system "
          "only, giving 19 policy-by-case runs."),

    ("h1", "Results", "results"),
    ("p", "The tables in this section are built from the tables that `python -m smartcity.cli paper sync` "
          "generates from the result files in `reports/experiments/` (`paper/tables/`); a stage that has not "
          "produced an artifact is reported as NOT RUN and no number is claimed for it. The narrative is written "
          "only from those artifacts (`reports/verification/paper_claims.csv` maps every claim to its file)."),
    ("h2", "What Was Actually Run"),
    ("p", "All numbers in this section come from a single-day real-data pass of the released pipeline on the "
          "authors’ workstation (Windows 11, NVIDIA GeForce RTX 4050 Laptop GPU, SUMO 1.28.0, Ollama with "
          "`qwen2.5:7b`); the early stages (graph, features, baselines) were re-run during the session and the "
          "artifacts cited here are those of the final chain, with the stage log in "
          "`reports/verification/stage_log.jsonl` and run ids and hashes in `mlflow_runs.json` and "
          "`evidence_registry.csv`. Of the 26 Manhattan DOT links, seven on the West Side Highway corridor (12th "
          "Avenue, 11th Avenue and Westside Highway segments) have no valid speed observation (positive and at "
          "most 100 mph) in any 2026 record and never enter the 5-minute grid "
          "(`reports/data_audit/link_split_coverage.csv`); of the 19 gridded links, 16 pass the training-coverage "
          "rule and form the modelling set, and three of those (FDR N to the Triborough Bridge, Triborough Bridge "
          "westbound, BQE N to the Manhattan Bridge) have no valid observation inside the test partition and are "
          "reported as NOT_EVALUATED in `reports/experiments/link_test_support_operational.csv`. Of 1,968,303 raw "
          "speed records, 978,018 carry a zero speed and 59 exceed the plausibility bound; 990,226 are valid and "
          "the gridded observed fraction is 0.611. The chronological partitions over the 84,084 grid steps are "
          "60/15/10/15%: calibration covers 2026-08-08 04:20 to 09-06 08:55 UTC and the test partition 2026-09-06 "
          "09:00 to 2026-10-20 04:00 UTC (about 44 days spanning 45 calendar dates; 144,217, 144,213 and 144,205 "
          "valid targets at 15, 30 and 60 minutes, identical for every model)."),
    ("p", "To finish inside a fixed compute deadline, every deep model was trained with a recorded budget of 4,096 "
          "training windows per epoch, sampled afresh each epoch without replacement from the 50,415 training "
          "origins (about 8% of them), with early stopping on the mean validation MAE of a fixed validation subset "
          "(patience 5, at most 30 epochs) and one seed (42). The budget is identical for the GRU, the temporal "
          "Transformer, the proposed model and its ablations, and is stated here because it bounds how far each "
          "model was trained, not because it is a tuned hyper-parameter. Under it the proposed model stopped after "
          "14 epochs (best epoch 8, 2.3 minutes on the GPU, 158,403 parameters), the temporal Transformer after 14 "
          "(best 8, 1.8 minutes), the GRU after 17 (best 11, 6.0 minutes, 41,667 parameters) and the no-weather "
          "ablation ran the full 30 epochs (best 24). Figures in this subsection are from the seed-42 runs; the "
          "three-seed comparison of the deep models is in {T:seeds}."),
    ("h2", "Multi-Horizon Forecasting"),
    ("p", "{T:forecast} gives the test error on the operational track. Every learned model beats persistence and "
          "the historical average at every horizon, and the three sequence models beat the two gradient-boosted "
          "baselines on MAE at every horizon. The proposed context-gated GATv2–Transformer has the lowest MAE at "
          "30 and 60 minutes (5.33 and 6.15 mph against 5.34/6.18 for the temporal Transformer and 5.37/6.17 for "
          "the GRU), the GRU the lowest at 15 minutes (4.71 mph against 4.77 for the proposed model), and XGBoost "
          "the lowest 60-minute RMSE (8.98 against 9.05). Relative to persistence the proposed model reduces MAE "
          "by 7%, 12% and 16% at the three horizons and raises *R*^{2} from 0.55/0.46/0.30 to 0.69/0.63/0.56."),
    ("table", "forecast"),
    ("p", "The margins between the three deep models are 0.01 to 0.06 mph, which a single seed cannot separate."),
    ("p", "*Seeds:* The three deep models were therefore retrained with seeds 42, 1 and 2 on the same GPU, data, "
          "budget and code ({T:seeds}; nine runs, each evaluated on one shared valid-target mask). Two checks came "
          "first. Re-running seed 42 reproduced the GRU and the temporal Transformer exactly (same stopping epoch "
          "and validation MAE to four decimals) but not the proposed model (25 epochs and validation MAE 5.358 "
          "against 14 and 5.388): the only difference between the proposed model and the temporal Transformer is "
          "the GATv2 layer, whose scatter operations on the GPU are not bit-reproducible, so on this hardware a "
          "fixed seed does not fix the proposed model. The same seed trained on a CPU in the development container "
          "stopped at a different epoch again (21 epochs, validation MAE 5.356; its predictions are not stored, so "
          "it is not part of the comparison). Over three seeds the proposed model has a seed-mean MAE of 4.69, 5.34 "
          "and 6.15 mph (standard deviation 0.06, 0.03 and 0.02 across seeds), the GRU 4.67, 5.37 and 6.18 and the "
          "temporal Transformer 4.72, 5.38 and 6.23."),
    ("table", "seeds"),
    ("p", "A paired day-block bootstrap (44 test days) of the seed-averaged MAE difference puts the proposed model "
          "below the temporal Transformer at every horizon (by 0.035, 0.037 and 0.080 mph, intervals excluding "
          "zero) and below the GRU at 30 and 60 minutes (0.032 and 0.031 mph, intervals [0.010, 0.052] and "
          "[0.007, 0.056]), while the GRU is lower at 15 minutes (by 0.021 mph, [0.004, 0.040]). These intervals "
          "describe day-to-day variation of the test errors for the seed-averaged models; with three seeds they do "
          "not estimate between-seed variance, the per-seed ranges overlap, and one temporal-Transformer seed "
          "stopped at epoch 2, which raises that model’s 60-minute mean. The supported reading is therefore narrow: "
          "the proposed model is at least as accurate as both deep baselines and has a small, consistent advantage "
          "of 0.03–0.08 mph at 30 and 60 minutes, while the GRU is the better 15-minute forecaster; it is not a "
          "demonstration that graph attention is decisive on this sparse 16-link network."),
    ("p", "On the retrospective track (reanalysis weather plus collisions and "
          "permitted events, contextual analysis only) the proposed model reaches 4.67, 5.35 and 6.13 mph "
          "({T:forecast} is the operational table; the retrospective rows are in `forecast_metrics.csv`), a small "
          "gain at 15 and 60 minutes over the operational 4.77/5.33/6.15, with XGBoost and LightGBM at 4.89, "
          "5.61–5.65 and 6.30–6.39."),
    ("p", "*Ablations:* {T:ablation} reports the mean MAE over the three horizons and a paired day-block bootstrap "
          "(1,000 resamples, the code default, of the 44 test days that contain a valid paired target; 95% "
          "percentile interval) of the difference to the proposed model (5.419 mph). Removing the availability "
          "gate (plain concatenation) raises MAE by 0.067 mph ([0.048, 0.086]); removing the 311 infrastructure "
          "group raises it by 0.014 mph ([0.002, 0.026]); removing the operational weather forecasts *lowers* it "
          "by 0.046 mph ([−0.069, −0.021]). The last is a negative result: with this data, this budget and the "
          "re-forecast weather proxy, the weather features hurt. The no-events and no-incidents variants are "
          "NOT_APPLICABLE on the operational track, where those groups do not exist, and are listed as such rather "
          "than as ablations. An earlier execution of this stage had resampled 5-minute steps instead of days (a "
          "unit error in the day index) and produced far narrower intervals; it was found during the run, "
          "corrected in code, re-run, and the superseded file is kept with the run’s local evidence."),
    ("table", "ablation"),
    ("h2", "Uncertainty Calibration and the Reliability Gate"),
    ("p", "Split-conformal half-widths fitted on 102,301, 102,299 and 102,302 calibration residuals at 15, 30 and "
          "60 minutes are 12.1, 13.5 and 14.8 mph. On the test partition the 90% intervals reach empirical "
          "coverage of 0.909, 0.907 and 0.903 ({T:unc}), so the marginal guarantee holds, but the intervals are "
          "wide (mean widths 24.3, 26.9 and 29.5 mph, twice the conformal quantiles). Conditional coverage is "
          "uneven: 0.93 on free-flowing targets (speed ratio ≥ 0.8, *n* ≈ 98,500), 0.93 on moderate ones, and "
          "0.80, 0.79 and 0.76 at the three horizons under congestion (ratio < 0.5, *n* ≈ 23,300); 0.93–0.94 in "
          "rush hours against 0.90 outside them; 0.92–0.93 under wet weather codes (*n* ≈ 7,900) against "
          "0.90–0.91 when dry."),
    ("table", "unc"),
    ("p", "The reliability gate, whose thresholds are fixed on calibration and validation data (interval width at "
          "most 38.1 mph, the 80th percentile of validation widths; at most 34% missing recent inputs; data at "
          "most 20 minutes old; at least 200 calibration samples), defers 25.5, 25.7 and 26.1% of test forecasts "
          "at the three horizons; the retained forecasts have MAE 3.72, 4.38 and 5.25 mph against 4.77, 5.33 and "
          "6.15 for all forecasts, and coverage 0.95, 0.94 and 0.93 (`artifacts/calibration/deferral_tradeoff.csv` "
          "tabulates the trade-off at six tolerated-missing-input thresholds, 0, 10, 20, 34, 50 and 100%)."),
    ("h2", "Explanations of the Trained Model"),
    ("p", "Exact grouped KernelSHAP (all 2^{*P*} coalitions, *P* = 5 or 6 players, 528 or 1,040 model calls and "
          "1.7 to 4.2 s per explanation on the CPU, additivity gap below 10^{−3} mph) was computed on the trained "
          "proposed model for 12 test points: the six largest predicted 30-minute speed drops, one per link, and "
          "six random points, all drawn from the 132,355 of 201,616 test (origin, link) pairs whose link had a "
          "raw observation at every one of the last six input steps and an observed target (the eligibility rule "
          "was introduced after a first pass had selected a point on a link with no raw observations in the test "
          "period). Averaged over the 12 points, the mean absolute attribution is 8.22 mph for the target link’s "
          "own last 30 minutes, 2.04 for its earlier 90 minutes, 1.09 for calendar, 0.52 for graph-neighbour "
          "traffic, 0.19 for weather and 0.09 for 311 requests. In the largest alert, the George Washington Bridge "
          "lower-level plaza link at 30 minutes, the model predicts 2.25 mph against a 26.9 mph background and an "
          "observed 1.24 mph, with −21.3 mph attributed to the link’s own recent traffic; on FDR N 25th–63rd St it "
          "predicts 1.92 mph (observed 6.83) with −13.9 from recent traffic and −3.2 from the earlier window. One "
          "selected point is a clear miss: FDR S Catherine Slip to the Brooklyn Bridge predicted 27.1 mph where "
          "2.48 was observed, a drop not foreseeable from the inputs."),
    ("p", "Shortening the input history confirms the attribution: on a 20,665-target test subset the proposed "
          "model’s MAE rises from 5.43 mph with the full two hours to 6.00 (60 min), 6.29 (30), 6.54 (15) and "
          "7.11 (5 min). Removing all edges touching a link’s graph neighbours changes its predictions by "
          "1.34 mph on average for the four-neighbour Brooklyn Bridge–FDR N link (MAE 8.57 to 8.58), by 0.91 and "
          "0.87 for FDR S 25th St–Catherine Slip and FDR N Catherine Slip–25th St (MAE 5.27 to 5.17 and 8.13 to "
          "7.96, i.e., slightly better without the edges) and by 0.67 for the Brooklyn–Battery Tunnel eastbound "
          "approach, and by exactly 0.0 for West St S at Spring St, whose only remaining edges are outgoing (its "
          "upstream neighbour is a dead feed), so no message reaches it. The LightGBM TreeSHAP baseline attributes "
          "65% of its mean absolute attribution at 15 minutes to traffic lags, 16% to calendar and 4% each to "
          "weather and link identity. All of these are model sensitivities, not causal effects."),
    ("h2", "Evidence Retrieval"),
    ("p", "The approved corpus holds 15 documents (the FHWA 2008 Signal Timing Manual [@fhwa2008stm] and its "
          "chapters 5 and 6, MUTCD 2009 [@mutcd2009] chapters 4D and 4E, nine SUMO documentation pages pinned to "
          "v1.28.0 and the project-defined policy), 1,633 chunks embedded with all-MiniLM-L6-v2 into a FAISS "
          "inner-product index; 171 chunks exceed the encoder’s 256-token window and are truncated by it (recorded "
          "in `index_manifest.json`). On the 28 project-labelled queries the index reaches Recall@8 of 0.818 and "
          "MRR of 0.702, and the support-status decision (SUPPORTED against INSUFFICIENT_EVIDENCE at a 0.35 score "
          "threshold) matches the label on 27 of 28 queries (0.964, {T:ret}). The labels were drafted by the "
          "project and have not been reviewed externally."),
    ("table", "ret"),
    ("h2", "Advisory Workflow"),
    ("p", "{T:adv} lists all 19 policy-by-case runs (REPLAY mode on test-partition forecast origins). The "
          "deterministic gates fired as designed (the three stress cases were run under the full system only, the "
          "rainy period under every policy): the stale-data stress case (inputs aged six steps) ended in "
          "DEFER_DATA, the wide-interval stress case (forced 99 mph width) and the observed rainy period, whose "
          "intervals of 44–46 mph exceed the 38.1 mph cap, in DEFER_UNCERTAINTY, and the out-of-scope query in "
          "DEFER_EVIDENCE, each without an LLM call. The model was called 12 times per pass, and the stage was run "
          "three times (2026-10-20; 2026-10-21 after the simulation-gate correction; 2026-10-28 on the calibrated "
          "testbed, described below): 36 calls, one attempt each, 892 to 3,619 prompt tokens, 157 to 321 "
          "completion tokens and 15 to 126 s per call (the first, cold call slowest; 18 to 54 s in the later "
          "passes), all returning schema-valid JSON and all recommending monitoring only "
          "(`reports/experiments/llm_calls.csv`). All three passes reached the same 19 decisions."),
    ("table", "adv"),
    ("p", "Without retrieval the model cited an evidence id that does not exist in all three cases of each pass "
          "(for example `EVIDENCE_123456`), and the citation check rejected every one; with retrieval, no invalid "
          "citation occurred in nine calls per pass. On the routine rush-hour case (FDR S Catherine Slip–Brooklyn Bridge, a link "
          "without a reviewed DOT-to-SUMO mapping) the constraint layer rejected the candidate under every policy "
          "that keeps it, while the RAG-without-constraints policy passed the same candidate to human review. On "
          "the two cases on the mapped West Street link the model recommended monitoring only, which passes all "
          "13 checks (pedestrian protection NOT_EVALUATED) and ends in PENDING_HUMAN_REVIEW; because no signal "
          "change was proposed, the simulation gate was never invoked by a real advisory and the "
          "SIMULATION_PASSED path remains exercised only by the software tests. End-to-end latency is 19 to 30 s "
          "per advisory after the first call."),
    ("h2", "Simulation Testbed"),
    ("p", "The West Street corridor extracted from OpenStreetMap has 82 corridor edges, 22 signalised "
          "intersections and 25 side-street entries. Two DOT links map to the corridor with high confidence: a "
          "dead West Side feed with no usable speed data (11th Ave S Gansevoort–West St at Spring St) and the "
          "modelled West St S Spring St–Brooklyn–Battery Tunnel portal link. The scenarios’ demand and congestion "
          "flags are declared rather than derived from that link’s observed or forecast speeds, so the testbed is "
          "a transfer demonstration on a real corridor rather than a digital twin of a forecast link. Pedestrian "
          "performance is NOT_EVALUATED because the scenarios contain no pedestrian demand."),
    ("p", "*First comparison (2026-10-20, superseded):* With 1,200 vehicles per hour and direction on the corridor "
          "and 150 per side approach, both declared, and three scenarios (routine peak; event surge, demand × 1.25; "
          "an incident that at the same surge caps one corridor edge at 2.5 m/s for 20 minutes), all 45 "
          "matched-seed runs (fixed-time, actuated and forecast-informed-rule controllers, five seeds, 300 s "
          "warm-up and 3,600 s evaluation, SUMO 1.28.0, 9,645 s of wall time) completed. The corridor "
          "was oversaturated under every controller: of 6,675 (routine) or 8,350 (surge and incident) loaded "
          "vehicles per run only 1,003 to 3,441 completed their trip, 3,257 to 6,979 remained unfinished and 1,091 "
          "to 2,386 were teleported after waiting 300 s. The forecast rule’s lower time loss per completed trip in "
          "the two stress scenarios (739.0 and 806.0 s against 780.5 and 898.4 for fixed-time) came with fewer "
          "completed trips (2,014 against 2,087; 1,236 against 1,384), i.e., survivorship, and we claimed no "
          "controller ranking."),
    ("p", "*Testbed audit (2026-10-21):* To find out why, the corridor was rebuilt in the development container "
          "from the OSM editing API (Overpass is blocked there) for the box 40.700–40.737 N, 74.000–74.020 W with "
          "the same highway filter. It reproduces the workstation corridor exactly (the same 82 corridor edges, 22 "
          "signals, corridor phases, entry and exit edges and both DOT mappings; 24 of 25 side entries keep their "
          "edge id, the 25th is the same FDR Drive approach under another OSM way id), and the original design run "
          "on it reproduces the oversaturated regime (routine peak, fixed-time, seed 1: 2,981 completed, 3,294 "
          "unfinished and 928 teleports, against 2,746, 3,527 and 1,157 on the workstation). The audit found two "
          "defects behind that comparison. First, demand was written as bare from/to flows, which SUMO routes at insertion "
          "on the current travel times [@sumodocs_routing]: at the declared demand the rerouting device replaced "
          "1,853 routes and sent 1,120 of 2,189 mainline vehicles off West Street into the Lower Manhattan grid "
          "({T:simaudit}), so the 45 runs did not compare controllers on the corridor. Second, the northbound "
          "chain began on a 0.2 m stub left by junction joining, which throttled northbound insertion. Both are "
          "corrected (one fixed free-flow route per flow; the entry moves to the first corridor edge of at least "
          "20 m), and the mainline demand now comes from the only weekday NYC automated traffic count on the "
          "corridor, northbound at Gansevoort Street on 6–10 October 2014 (15 complete PM-peak hours, median "
          "1,389 veh/h), applied to both directions; the only southbound count (Bloomfield Street, 7–8 March 2015, "
          "median 2,074 veh/h) fell on a weekend and is excluded by the weekday rule. Fixed routes make the "
          "corridor more congested, not less (1,044 teleports against 680 at the declared demand), because traffic "
          "can no longer leave it."),
    ("p", "*Corrected protocol, comparison not run:* Side-street demand has no matched count, so its level was to "
          "be chosen by a rule fixed in `configs/simulation.yaml` before any comparison: on the routine peak, "
          "under the fixed-time baseline only and on three development seeds that the comparison does not use, "
          "the largest fraction of the declared 150 veh/h at which every seed has no teleport and at most 1% of "
          "loaded vehicles unfinished. With the programs netconvert generates, no level qualifies ({T:simaudit}): "
          "even with no side-street demand at all, 533 of 3,010 loaded vehicles per run remain unfinished and the "
          "mean time loss is 804 s. Counting only the movements each mainline route makes, the guessed programs "
          "give the northbound mainline 25 s of a 90 s cycle on two lanes at one signal, about 1,000 veh/h at a "
          "nominal saturation flow of 1,800 veh/h per lane and below the observed 1,389 veh/h "
          "(`simulation_signal_capacity.csv`). We therefore re-timed the fixed-time programs for the demand being "
          "tested with Webster’s method as implemented in SUMO’s `tlsCycleAdaptation.py` (tool defaults; phase "
          "order and states unchanged), a declared assumption fixed before any comparison under this protocol, "
          "and applied the same selection rule. Re-timing raises every mainline signal’s estimate to at least "
          "1,800 veh/h northbound and 2,040 southbound and removes most of the saturation: with the full declared "
          "side demand 5,220 to 5,229 trips complete per run instead of about 2,300, and with no side demand "
          "teleports stay at zero and the northbound mainline completes 1,389 trips (its hourly flow) at 195 to 197 s of time "
          "loss. No level qualifies, however: even without side demand 129 to 131 vehicles per run (4.3%) remain "
          "unfinished, and the southbound mainline loses 1,014 to 1,038 s per trip; green shares do not explain "
          "this and the audit does not identify its cause. Under the preregistered rule the corrected controller "
          "comparison is NOT RUN, and the advisory simulation gate returns NOT_EVALUATED (ERROR_TOOL with its "
          "cause) rather than judging a candidate on a testbed that cannot serve its own baseline. We did not "
          "relax the rule after seeing these results."),
    ("table", "simaudit"),
    ("p", "*2025 counts, turn lanes and a speed check:* Two further pieces of evidence changed the testbed once "
          "more, again before any controller comparison. First, NYC’s vehicle classification counts "
          "[@nycclasscounts] contain weekday counts on West Street in both directions at Spring Street–West "
          "Houston Street on 29–30 April 2025, with PM-peak medians of 2,510 (northbound) and 2,444 (southbound) "
          "veh/h, close to twice the 2014 figure; the configured rule now takes the most recent year with counts "
          "in both directions. Second, the remaining southbound delay comes from OpenStreetMap turn-lane tags, "
          "which netconvert imports as hard lane restrictions: a shared lane on the 45 m link south of Chambers "
          "Street becomes right-turn-only, through traffic must merge within 45 m, and the merge blocks the "
          "junction. With the 2014 count, no side-street demand and Webster programs, removing the restrictions "
          "lets every trip finish (southbound time loss 346–380 s instead of 1,014–1,038 s; "
          "`simulation_turnlane_check.json`). We adopt that as a declared simplification, which can overstate "
          "capacity where real lanes are turn-only."),
    ("p", "With both changes and the 2025 counts, no level passes the baseline test either ({T:simaudit}): with no "
          "side-street demand 523 to 568 of 5,368 vehicles per run remain unfinished; the northbound mainline "
          "completes 2,520–2,524 trips at 247–248 s of time loss, the southbound only 1,877–1,922 at "
          "1,199–1,226 s, and the re-timed plan gives one southbound signal an estimated 2,278 veh/h for the "
          "observed 2,444. Measured against reality, the testbed is too slow: on the eight SUMO edges mapped to the "
          "forecast link West St S Spring St–BBT portal, the simulated space-mean speed is 5.8 mph (5.79 to 5.85 "
          "over three seeds, without side-street demand), against an observed weekday PM-peak mean of 10.95 mph "
          "(16–19 h, April–October 2026, 3,692 DOT records). NYC’s Vision Zero records [@nycvzvretiming] also "
          "show West Street from Battery Place to West 57th Street re-timed for 25 mph signal progression in 2014 "
          "and 2019, whereas the testbed’s programs are uncoordinated. The controller comparison therefore remains "
          "NOT RUN; the observed speed is now an explicit calibration target for signal splits and progression, "
          "or for NYC DOT timing plans if they can be obtained."),
    ("p", "*Signal-split calibration (protocol v5).* We therefore fixed, before running anything, a calibration "
          "protocol for the one testbed input that is a declared assumption rather than an observation: the signal "
          "programs. Starting from the Webster plan for the 2025 counts without side-street demand, the corridor "
          "green of every corridor signal is scaled by a factor from a fixed grid (1.0 to 2.5), other greens are "
          "shortened down to 7 s, cycles are kept at or below 120 s and corridor greens at or below 90 s, and phase "
          "states are unchanged; each factor is run under the fixed-time baseline on the three development seeds, "
          "and among the factors that pass the unchanged admissibility rule on every seed the one whose seed-mean "
          "space-mean speed on the mapped link is closest to the observed 10.95 mph is selected if it lies within "
          "1.5 mph. The workstation ran this protocol on 23 October 2026 ({T:splitcal}; "
          "`split_calibration_v5_counts2025_calibrated_splits.json`). Widening the corridor green raises the "
          "simulated speed monotonically, from 5.82 mph at factor 1.0 (which reproduces the earlier 5.79–5.85 mph "
          "audit) to 8.10 mph at 2.5, and clears the unfinished trips: factors 2.0 and 2.5 are admissible (1/0/28 "
          "and 0/0/0 unfinished of 5,368, no teleports), the smaller ones are not. The closest admissible factor "
          "is still 2.85 mph below the target, beyond the tolerance, so no program is selected and the controller "
          "comparison, the agent re-run on a calibrated testbed and the dependent exports were not run. Speed was "
          "still rising at the largest factor in the grid, and one signal had reached the green and cycle caps "
          "from factor 1.4 on, so the preregistered range ends below the target; extending it would be a new "
          "protocol, decided before running, not a relaxation of this one. One provenance deviation is recorded: "
          "the workstation’s OpenStreetMap extract had been fetched with a different bounding box, so the "
          "configured area was re-fetched from the OSM API on 23 October; the rebuilt corridor is structurally "
          "identical to the audited one (82 edges, the same edge lists, entries, exits and 22 signals) but its "
          "content hash differs, and all v5 runs use the re-fetched network."),
    ("table", "splitcal"),
    ("p", "*Protocol v6 (run 2026-10-26): a plan within tolerance.* The authors chose a second preregistered "
          "calibration over closing the comparison or waiting for NYC DOT timing plans. Protocol v6, fixed in the "
          "configuration on 25 October 2026 before any run, keeps the v5 construction and adds what an arterial "
          "timed for progression has and the Webster plan lacks: a common cycle at every corridor signal (90 or "
          "120 s, or the per-signal Webster cycles, which range from 21 to 102 s and so admit no progression), "
          "green factors 1.0 to 3.0, and corridor-green offsets for a 25 mph platoon along the southbound chain, "
          "the mapped link’s direction; 25 cells, three development seeds, fixed-time baseline, the same "
          "admissibility rule and the same 10.95 ± 1.5 mph target, ties going to the least intervention "
          "({T:splitcal6}). The workstation ran the 75 runs on 26 October 2026 "
          "(`split_calibration_v6_counts2025_cycle_splits_offsets.json`). Splits alone never reach the target: the "
          "Webster-cycle cells reproduce v5 and top out at 8.22 mph, and a 90 s common cycle without offsets gives "
          "8.88 mph at every factor from 1.5 upward (the green bounds bind, so the factors coincide). Offsets close "
          "the gap: the 90 s cells with a 25 mph progression reach 10.08 mph, 0.87 mph below the observed speed and "
          "within tolerance, with no unfinished trip and no teleport in any seed; the 120 s cells with offsets "
          "overshoot (13.1 to 21.7 mph). The tie-break selects the least intervention, factor 1.5, and the selected "
          "program is recorded as a calibrated scenario testbed: a cycle, green share and offsets tuned to one "
          "observed speed on one link, not NYC DOT timing. Under that plan the preregistered side-street rule "
          "admits only the zero level, as before (`demand_selection.json`)."),
    ("table", "splitcal6"),
    ("p", "*Controller comparison on the calibrated testbed (2026-10-28).* With a plan selected, the comparison "
          "that the rule had blocked could run: three scenarios (routine PM peak at the 2025 counts; a configured "
          "event surge of ×1.25; the surge plus a configured 20-minute capacity reduction) under three controllers "
          "on five matched seeds, 45 runs, every one completed with zero teleports ({T:sim}). The matched pair is "
          "fixed time against the deterministic forecast-informed rule, which run on the same calibrated plan, "
          "network, demand and seeds; the rule only acts when congestion is forecast, so in the routine peak the "
          "two are identical (271.6 s mean time loss, all 4,975 trips completed in every seed). Under the surge "
          "the rule lowers the mean time loss per completed trip from 450.2 to 426.0 s (−5.4%) while completing "
          "more trips (5,910 against 5,720 of 6,712 loaded) and leaving fewer unfinished (350 against 540), with "
          "a lower mean corridor queue (180 against 197 vehicles); under the incident the figures are 465.9 to "
          "443.9 s (−4.7%), 5,919 against 5,725 completed, 341 against 536 unfinished, 183 against 203 queued. "
          "The direction is the same in every seed (time-loss gain 12.9 to 29.9 s under the surge and 14.3 to "
          "33.7 s under the incident, 148 to 250 more trips completed), so this time the lower delay is not "
          "survivorship. The actuated controller runs on netconvert’s actuated programs, not on the calibrated "
          "plan, so its rows are an uncalibrated reference and are not ranked against the pair. The result is a "
          "simulated improvement in a calibrated scenario testbed with no side-street demand, no pedestrians and "
          "340 to 540 trips still unfinished under stress; it is not a real-world gain."),
    ("table", "sim"),
    ("p", "*Agent re-run on the calibrated testbed.* The advisory stage was run a third time on 28 October 2026 so "
          "that the simulation gate, now admissible, could be reached (`llm_calls.csv`, 12 calls, 18 to 54 s, all "
          "schema-valid). It reproduced the 19 decisions of the two earlier passes: the model again recommended "
          "monitoring only on the mapped corridor under every policy, so no real advisory reached the gate and the "
          "SIMULATION_PASSED path is still exercised only by the software tests; without retrieval it again cited "
          "a non-existent evidence id in all three cases, each rejected."),
    ("h2", "Live observational run"),
    ("p", "Every forecast number above is REPLAY: the frozen model scored on the held-out partition of the archived "
          "feed. A live mode (`smartcity.cli live`) was added on 28 October 2026: it pulls the newest records of "
          "the modelled links from the public feed together with the current Open-Meteo forecast and the last two "
          "days of road-related 311 requests, stores them verbatim with their retrieval time, rebuilds the 24-step "
          "window with the training-fitted transforms, runs the frozen model once per five-minute bin, writes the "
          "forecast before its earliest target time, and scores it only after the target bin is observed; links "
          "with fewer than 12 observed bins in the window are withheld and repeated or revised feed records are "
          "counted. {T:live} reports the outcome of the collection window. It was attempted on Wednesday "
          "28 October 2026 between 15:49 and 18:05 New York time: the pipeline ran (15 speed, 15 weather and 14 311 "
          "pulls, nine forecast batches written), but the public speed feed was never less than about 1 h 40 min "
          "behind, its newest Manhattan record moving from 11:31 to 14:11, 13:36 and 15:36 local time across the "
          "pulls, with one batch published, withdrawn and republished, so every batch withheld all 16 links (at "
          "most 5 of the 24 lookback bins observed against the 12 required) and the one-hour collection was not "
          "started. The run is therefore NOT RUN, the withholding rule was not relaxed, and the feed’s "
          "publication latency is itself an operational finding: on such a day the deployed system would have "
          "issued no forecast. A second attempt on Thursday 29 October (12:29 to 17:38 New York time, 25 pulls, "
          "24 batches) found the same: the newest record moved from 10:11 to 15:36 local time and the lag never "
          "fell below about 1 h 50 min, so again no link reached the required history and the hour never started. "
          "Across the two afternoons the feed ran 1.7 to 4.3 h behind real time; under the preregistered rule a "
          "live forecast is therefore not reachable with the feed as it currently publishes, and any alternative "
          "(an origin at the newest available bin with its data age displayed, or a shorter lookback) would be a "
          "new preregistered protocol rather than a relaxation applied after the fact. Whatever a later run yields "
          "is a short window on one day, a check that the pipeline works on data that did not exist at training "
          "time, not a second test set."),
    ("table", "live"),
    ("h2", "Runtime"),
    ("p", "Training times above are on the GPU; inference of one forecast origin for all links on the CPU costs "
          "5.7 ms for the proposed model, 2.2 for the temporal Transformer, 0.7 for the GRU and about 0.1 for "
          "XGBoost; a FAISS query takes tens of milliseconds after the first (model-loading) call; the full "
          "per-link runtime table is `reports/experiments/runtime_metrics.csv`."),

    ("h1", "Discussion", "discussion"),
    ("p", "The system is designed so that each component’s contribution can be isolated: baselines and the "
          "proposed model share one test mask, ablations remove one context group or the gate at a time, and the "
          "advisory evaluation runs the same cases under four policies that switch off retrieval, the constraint "
          "layer or the simulation gate. Read together, the results support some of the proposals in Section "
          "{S:intro} and not others."),
    ("p", "*Forecasting:* The accuracy gain of the proposed model over persistence (7–16% MAE) is real and "
          "consistent across horizons, and its margin over the tree baselines is consistent in sign (0.05–0.25 mph) "
          "though at 15 min no larger than the GRU margin. Over three seeds its margin over the temporal-only "
          "Transformer (0.04–0.08 mph) and over the GRU at 30 and 60 minutes (0.03 mph) is consistent across test "
          "days, while the GRU is better at 15 minutes; these are small effects from three seeds, not a decisive "
          "architectural advantage. Two measured facts explain why the spatial layer "
          "adds little here: the graph is sparse (16 nodes with usable data, most of them limited-access highway "
          "segments whose monitored neighbours are kilometres away) and the explanations attribute 0.52 mph of "
          "mean absolute effect to neighbour traffic against 8.22 mph to the link’s own last half hour. The "
          "neighbour-removal analysis shows the layer is not inert (prediction changes of 0.7–1.3 mph on four of "
          "the five connected links, none on the fifth) but also that removing edges sometimes lowers the error, "
          "so on this network message passing is a modest and mixed contribution. The availability gate is the "
          "component the ablations do support: removing it costs 0.067 mph with an interval that excludes zero."),
    ("p", "*Context:* The weather ablation is the clearest negative result: the operational re-forecast weather "
          "features raise MAE by 0.046 mph, and the retrospective track, which uses reanalysis weather, is only "
          "marginally better than the operational one. On a highway-heavy link set over nearly ten months the "
          "weather signal reaching a 5-minute speed is weak relative to the traffic history, and a re-forecast "
          "proxy adds noise. The 311 infrastructure group helps by a small but non-zero amount. Whether the events "
          "and incidents groups help cannot be answered on the operational track, where the data to compute them "
          "were not available at prediction time."),
    ("p", "*Uncertainty:* The conformal intervals hold their marginal 90% guarantee but are wide and under-cover "
          "congested targets (0.76–0.80), which is exactly the regime an advisory cares about. The deterministic "
          "gate turns this into deferrals: at the configured missing-input threshold about a quarter of forecasts "
          "(25.5–26.1%) are withheld and the MAE of the remainder is 15–22% lower than that of the full set (3.72 "
          "against 4.77 mph at 15 min, 5.25 against 6.15 at 60 min). For an operator this is the honest "
          "trade-off; a calibration conditional on congestion state is the obvious next step."),
    ("p", "*Grounding and constraints:* The policy ablation isolates two mechanisms. Retrieval removes fabricated "
          "citations (three of three without it, none of nine with it), and the citation check catches them when "
          "they occur. The constraint layer, not the language model, decides admissibility: on an unmapped link "
          "the model produced the same candidate (monitor-only, citing the same two manual chunks) under both "
          "policies, and it is rejected with constraints and forwarded to human review without them. What the run "
          "does not show is a signal-timing recommendation surviving the whole chain into simulation: on the "
          "mapped corridor the model chose monitoring only, so the simulation gate’s acceptance rule has been "
          "exercised by tests, not by a real advisory. We report this as a gap rather than fill it with a "
          "hand-written candidate."),
    ("p", "*Simulation:* The controller comparison is the clearest example of a result that a less careful reading "
          "would have turned into a gain: in the first 45 runs the forecast-informed rule shows 5 to 10% lower "
          "time loss per completed trip in the two stress scenarios, but it completes fewer trips under an "
          "oversaturated corridor. Auditing the testbed instead of the controllers changed the diagnosis twice. "
          "The first suspect, the declared demand, was not the cause: the observed weekday West Street count "
          "(1,389 veh/h) is higher than the declared 1,200. What the audit found was a testbed that was not "
          "measuring the corridor at all, because SUMO’s insertion routing sent half of the mainline through the "
          "Lower Manhattan grid, and, once routes were fixed, a corridor whose generated signal timing gives the "
          "northbound mainline about 1,000 veh/h where 1,389 are observed. Re-timing the programs with Webster’s "
          "method serves the northbound flow but leaves a southbound delay the audit cannot explain, so the "
          "testbed still fails its own baseline. A controller comparison on such a testbed would rank signal plans "
          "by how they cope with modelling artefacts, so the preregistered selection rule stops it, and the "
          "advisory gate refuses to judge candidates on it. A comparison with observed speed confirmed the "
          "diagnosis: with recent counts the modelled corridor runs at about half the observed PM-peak speed. The "
          "lesson for simulation-gated advisory is that the gate’s testbed needs its own acceptance test, run on "
          "the baseline alone and checked against observed traffic, before any candidate is scored against it. "
          "What finally passed that test was not more green but coordination: a common cycle with 25 mph offsets "
          "along the mapped direction took the modelled link from 8.9 to 10.1 mph where every split-only cell had "
          "stalled, which is also what West Street is timed for in reality. On that plan the matched comparison "
          "does show the forecast-informed rule ahead of fixed time under stress, by about 5% of time loss with "
          "more trips completed in every seed, and we read it narrowly: a deterministic rule that extends corridor "
          "green when congestion is forecast helps a corridor that is oversaturated by a configured surge, in a "
          "testbed tuned to one observed speed, with no side-street traffic to lose. It says nothing about the "
          "language model, which never proposed the action, and nothing about a real street."),
    ("p", "*What is not claimed:* Nothing here is a deployment result, a causal explanation, or a congestion "
          "reduction on a real street. The language model never holds safety authority (constraints and the "
          "simulation gate are code), retrieved text is untrusted evidence that must be cited by chunk id, and the "
          "most permissive status the workflow can reach is approval for simulation, never deployment."),

    ("h1", "Limitations", "limitations"),
    ("p", "*Data:* The DOT link set is sparse and highway-heavy; the full-year link enumeration timed out "
          "server-side, so the study uses the 26 Manhattan links active since 2026-09-20, of which seven are dead "
          "feeds, three more have under 3% coverage, three lose their feed before or during the test partition "
          "(NOT_EVALUATED) and 16 are modelled; about half of all raw records are zero-speed no-measurement rows, "
          "treated as missing. Monitored segments do not tile the highways and the published polylines stop short "
          "of the named link ends, so the graph needs name-based continuity rules and remains sparse (16 directed "
          "edges, 6 isolated nodes before eligibility). The eligibility threshold was lowered from the planned 0.6 "
          "to 0.5 training coverage after the coverage audit and before any result on the 0.6 set existed; both "
          "are recorded. Operational weather is Open-Meteo’s historical-forecast product, a re-forecast proxy "
          "rather than an archived agency forecast. Collisions lag publication by months and are retrospective "
          "only."),
    ("p", "*Modelling and evaluation:* All deep models were trained under a recorded budget of 4,096 windows per "
          "epoch with early stopping and one chronological split. The three deep models were compared over only "
          "three seeds ({T:seeds}); the day-block bootstrap describes test-day variation of the seed-averaged "
          "errors and does not estimate between-seed variance, and the per-seed ranges overlap. On the GPU the "
          "proposed model is not bit-reproducible at a fixed seed (GATv2 scatter operations), whereas the GRU and "
          "temporal Transformer are; a reported proposed-model run can therefore be re-trained but not re-created "
          "exactly. Split conformal intervals carry a marginal guarantee under exchangeability, which traffic series "
          "violate; the measured coverage under congestion is 0.76–0.80. Explanations describe the trained model, "
          "with a background drawn from the training partition; neighbour sensitivity perturbs the graph in ways "
          "the model never saw during training, and only incoming edges can change a link’s own prediction."),
    ("p", "*Knowledge, language model and agents:* The approved corpus is small and is not NYC DOT’s signal-timing "
          "policy; the project-defined policy is labelled as such. 171 of 1,633 chunks exceed the encoder’s "
          "256-token window. The retrieval labels were drafted by the project without external review, so recall "
          "and MRR are an internal consistency check. The language model is a 7B quantised model served locally; "
          "its advisories are only as good as the evidence and the constraints that follow it. The advisory "
          "evaluation is functional (seven cases, four policies, 19 runs), not statistical, and on the mapped "
          "corridor the model proposed no signal change, so the simulation acceptance path was not exercised by a "
          "real advisory. Two defects were found during the run and fixed before the reported numbers were "
          "produced (the bootstrap day index, and a missing field that had silently prevented every LLM call in a "
          "first agent pass); both superseded runs are kept as local evidence and described in `progress.md`."),
    ("p", "*Simulation:* The SUMO testbed is a scenario built from OSM geometry with declared demand and default "
          "signal programs, not a calibrated digital twin, and contains no pedestrian demand; only one of the two "
          "mapped DOT links is a forecastable one and the scenarios’ demand and congestion flags are declared "
          "rather than derived from its observations, so the testbed is a transfer demonstration. The first "
          "45-run comparison used SUMO’s insertion routing and a stub entry edge and is superseded. Its corrected "
          "protocols use the only weekday automated count on the corridor (2014, one direction) and then "
          "two-direction classification counts from two weekdays in April 2025; side-street demand has no count. "
          "Signal programs are generated by netconvert or re-timed by Webster’s method, not NYC timing plans, and "
          "are uncoordinated although West Street is timed for 25 mph progression; lane restrictions from "
          "OpenStreetMap are dropped, which can overstate capacity. Under every protocol the testbed fails its "
          "baseline test, and with the 2025 counts it runs at 5.8 mph where the mapped link is observed at "
          "10.95 mph. The preregistered split calibration (protocol v5) raised the simulated speed to at most "
          "8.1 mph within its green-factor grid; the second protocol (v6) reached 10.08 mph with a 90 s common "
          "cycle and 25 mph southbound offsets, so the comparison ran on that plan. That plan is a calibrated "
          "scenario testbed, not NYC timing: it is tuned to one observed speed on one link, progresses one "
          "direction only, and the only admissible side-street level is zero, so side-road effects are not "
          "evaluated. The actuated controller runs on netconvert’s actuated programs rather than the calibrated "
          "plan and is an uncalibrated reference. Under the stress scenarios 340 to 540 of 6,712 trips remain "
          "unfinished with either matched controller. The reported improvement of the forecast-informed rule is a "
          "simulated result under these conditions and is not a real-world gain."),
    ("p", "*Engineering:* Data download, training, LLM inference and the simulation runs were executed on the "
          "authors’ workstation (torch 2.11.0+cu128, a recorded deviation from the lock file; from 28 October 2026 "
          "Windows Application Control blocked the unsigned `torch_scatter` and `torch_sparse` extensions, which "
          "the models do not use, so they were removed from that environment and PyTorch Geometric Temporal loads "
          "through the documented direct-module route). On 2026-10-20 "
          "the development container could not reach the data portals or the model server; on 2026-10-21 it could "
          "reach NYC Open Data, Crossref and the OSM editing API (not Overpass), and the testbed audit ran there "
          "with the same SUMO version. The container images were built and smoke-tested on the workstation only. "
          "Model weights, prediction arrays, raw data and the FAISS index are not in the repository; their hashes "
          "and run ids are. The complete, maintained list is in `reports/limitations.md`."),

    ("h1", "Conclusion and Future Work", "conclusion"),
    ("p", "We presented a complete, reproducible prototype that joins multi-horizon graph-Transformer forecasting, "
          "conformal calibration, model-faithful explanations, allow-listed retrieval, a locally hosted language "
          "model constrained by deterministic checks, and matched-seed simulation into one auditable advisory "
          "workflow on public New York City data, and we ran it end to end on nearly ten months of real DOT "
          "speeds. The measured outcome is mixed and reported as such: the proposed forecaster beats persistence "
          "by 7–16% MAE and the tree baselines at every horizon, and over three seeds it is 0.03–0.08 mph below the "
          "temporal Transformer at every horizon and the GRU at 30 and 60 minutes, with the GRU better at 15 "
          "minutes, a small advantage rather than a decisive one; the availability gate helps and the operational weather features "
          "hurt; conformal intervals hold their marginal coverage but under-cover congestion; retrieval removes "
          "fabricated citations and the constraint layer, not the model, decides admissibility; no advisory "
          "reached the simulation gate because the model chose monitoring on the mapped corridor; the first "
          "controller comparison is superseded, because an audit found that SUMO had diverted half of the corridor "
          "traffic, and the corrected comparison could only run after two preregistered calibrations, the second of "
          "which (a common cycle with 25 mph progression offsets) brought the modelled link within 0.9 mph of its "
          "observed speed; on that calibrated scenario testbed the deterministic forecast-informed rule lowers time "
          "loss by about 5% under configured stress while completing more trips in every seed, a simulated result "
          "that is not a real-world gain."),
    ("p", "Future work, in the order the evidence suggests, is training with more seeds and without the compute budget, "
          "congestion-conditional calibration, a denser sensor network on which the spatial layer can matter, a "
          "testbed with side-street demand, NYC DOT timing plans and pedestrians, the live observational run, and "
          "an externally reviewed retrieval benchmark."),
]

# IEEE-style reference text for every key in paper/references.bib that the paper cites.
REFERENCES = {
    "li2018dcrnn": "Y. Li, R. Yu, C. Shahabi, and Y. Liu, “Diffusion convolutional recurrent neural network: "
                   "Data-driven traffic forecasting,” in *Proc. Int. Conf. Learn. Represent. (ICLR)*, 2018, "
                   "arXiv:1707.01926.",
    "yu2018stgcn": "B. Yu, H. Yin, and Z. Zhu, “Spatio-temporal graph convolutional networks: A deep learning "
                   "framework for traffic forecasting,” in *Proc. Int. Joint Conf. Artif. Intell. (IJCAI)*, 2018, "
                   "pp. 3634–3640, doi: 10.24963/ijcai.2018/505.",
    "wu2019graphwavenet": "Z. Wu, S. Pan, G. Long, J. Jiang, and C. Zhang, “Graph WaveNet for deep "
                          "spatial-temporal graph modeling,” in *Proc. Int. Joint Conf. Artif. Intell. (IJCAI)*, "
                          "2019, pp. 1907–1913, doi: 10.24963/ijcai.2019/264.",
    "brody2022gatv2": "S. Brody, U. Alon, and E. Yahav, “How attentive are graph attention networks?” in *Proc. "
                      "Int. Conf. Learn. Represent. (ICLR)*, 2022, arXiv:2105.14491.",
    "vaswani2017attention": "A. Vaswani *et al.*, “Attention is all you need,” in *Advances in Neural Information "
                            "Processing Systems*, vol. 30, 2017, pp. 5998–6008.",
    "vovk2005algorithmic": "V. Vovk, A. Gammerman, and G. Shafer, *Algorithmic Learning in a Random World*. "
                           "Springer, 2005, doi: 10.1007/b106715.",
    "angelopoulos2021gentle": "A. N. Angelopoulos and S. Bates, “A gentle introduction to conformal prediction and "
                              "distribution-free uncertainty quantification,” 2021, arXiv:2107.07511.",
    "barber2023beyond": "R. F. Barber, E. J. Candès, A. Ramdas, and R. J. Tibshirani, “Conformal prediction beyond "
                        "exchangeability,” *Ann. Statist.*, vol. 51, no. 2, pp. 816–845, 2023, "
                        "doi: 10.1214/23-AOS2276.",
    "xu2021enbpi": "C. Xu and Y. Xie, “Conformal prediction interval for dynamic time-series,” in *Proc. 38th Int. "
                   "Conf. Mach. Learn. (ICML)*, PMLR, vol. 139, 2021, pp. 11559–11569.",
    "lundberg2017shap": "S. M. Lundberg and S.-I. Lee, “A unified approach to interpreting model predictions,” in "
                        "*Advances in Neural Information Processing Systems*, vol. 30, 2017, arXiv:1705.07874.",
    "lewis2020rag": "P. Lewis *et al.*, “Retrieval-augmented generation for knowledge-intensive NLP tasks,” in "
                    "*Advances in Neural Information Processing Systems*, vol. 33, 2020, arXiv:2005.11401.",
    "reimers2019sbert": "N. Reimers and I. Gurevych, “Sentence-BERT: Sentence embeddings using Siamese "
                        "BERT-networks,” in *Proc. EMNLP-IJCNLP*, 2019, pp. 3982–3992, "
                        "doi: 10.18653/v1/D19-1410.",
    "johnson2019faiss": "J. Johnson, M. Douze, and H. Jégou, “Billion-scale similarity search with GPUs,” *IEEE "
                        "Trans. Big Data*, vol. 7, no. 3, pp. 535–547, 2021, doi: 10.1109/TBDATA.2019.2921572.",
    "qwen2025qwen25": "Qwen Team, “Qwen2.5 technical report,” 2024, arXiv:2412.15115.",
    "lopez2018sumo": "P. A. Lopez *et al.*, “Microscopic traffic simulation using SUMO,” in *Proc. 21st IEEE Int. "
                     "Conf. Intell. Transp. Syst. (ITSC)*, 2018, pp. 2575–2582, doi: 10.1109/ITSC.2018.8569938.",
    "rozemberczki2021pgt": "B. Rozemberczki *et al.*, “PyTorch Geometric Temporal: Spatiotemporal signal "
                           "processing with neural machine learning models,” in *Proc. 30th ACM Int. Conf. Inf. "
                           "Knowl. Manage. (CIKM)*, 2021, pp. 4564–4573, doi: 10.1145/3459637.3482014.",
    "fey2019pyg": "M. Fey and J. E. Lenssen, “Fast graph representation learning with PyTorch Geometric,” "
                  "presented at the ICLR Workshop on Representation Learning on Graphs and Manifolds, 2019, "
                  "arXiv:1903.02428.",
    "chen2016xgboost": "T. Chen and C. Guestrin, “XGBoost: A scalable tree boosting system,” in *Proc. 22nd ACM "
                       "SIGKDD Int. Conf. Knowl. Discovery Data Mining*, 2016, pp. 785–794, "
                       "doi: 10.1145/2939672.2939785.",
    "ke2017lightgbm": "G. Ke *et al.*, “LightGBM: A highly efficient gradient boosting decision tree,” in "
                      "*Advances in Neural Information Processing Systems*, vol. 30, 2017.",
    "fhwa2008stm": "P. Koonce *et al.*, “Traffic signal timing manual,” U.S. Dept. of Transportation, Federal "
                   "Highway Administration, Rep. FHWA-HOP-08-024, 2008.",
    "mutcd2009": "U.S. Dept. of Transportation, Federal Highway Administration, *Manual on Uniform Traffic Control "
                 "Devices for Streets and Highways*, 2009 ed., 2009.",
    "nycdotspeeds": "New York City Department of Transportation, “DOT traffic speeds NBE (dataset i4gi-tjb9),” NYC "
                    "Open Data. Accessed: Oct. 20, 2026. [Online]. Available: "
                    "https://data.cityofnewyork.us/d/i4gi-tjb9",
    "openmeteo": "Open-Meteo, “Historical weather and historical forecast APIs,” CC BY 4.0. Accessed: Oct. 20, "
                 "2026. [Online]. Available: https://open-meteo.com",
    "sumodocs_routing": "Eclipse SUMO contributors, “Automatic routing / routing device (SUMO 1.28.0 "
                        "documentation),” section “Incomplete trips and flows,” 2026. Accessed: Oct. 21, 2026. "
                        "[Online]. Available: https://github.com/eclipse-sumo/sumo/blob/v1_28_0/docs/web/docs/"
                        "Demand/Automatic_Routing.md",
    "nycclasscounts": "NYC Department of Transportation, “Vehicle classification counts (2011–2025),” NYC Open "
                      "Data, dataset 96ay-ea4r, 2026. Accessed: Oct. 21, 2026.",
    "nycvzvretiming": "NYC Department of Transportation, “VZV signal timing/25 MPH signal retiming,” NYC Open Data, "
                      "dataset d8dp-wfee, 2026. Accessed: Oct. 21, 2026.",
}
