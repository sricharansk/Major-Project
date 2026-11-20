"""Text of the IEEE conference paper (rebuilt edition), read by paper/word/build_ieee_paper.py.

Markup inside strings: *italic*, **bold**, `mono`, _{subscript}, ^{superscript}, [@key] citation,
{T:id} table number, {F:id} figure number, {S:key} section number. Every number in the prose was copied from the
project's result files (reports/experiments/, artifacts/); tables and figures are generated from those files.
"""

TITLE = ("Predictive Analytics for Smart City Infrastructure: Multi-Horizon Traffic Forecasting and an Explainable "
         "Agentic Signal Advisory with Graph Transformers and Retrieval-Augmented Generation")

AUTHORS = [
    {"name": "S K Sricharan",
     "lines": [("i", "M.Tech. Artificial Intelligence and Machine Learning,"),
               ("i", "School of Computer Science and Engineering (SCOPE)"),
               ("i", "Vellore Institute of Technology, Chennai"),
               ("", "Chennai, India"),
               ("", "sksricharan2003@gmail.com")]},
    {"name": "Dr. R. Srinivasa Perumal∗",
     "lines": [("", "Associate Professor"),
               ("i", "School of Computer Science and Engineering (SCOPE)"),
               ("i", "Vellore Institute of Technology, Chennai"),
               ("", "Chennai, India"),
               ("", "r.srinivasaperumal@vit.ac.in"),
               ("", "∗Corresponding author")]},
]

ABSTRACT = (
    "City traffic centres need forecasts that state how certain they are, and advice that can never bypass "
    "engineering rules. This paper presents an end-to-end predictive analytics system for 26 road links in "
    "Manhattan, New York City, built only on public data. A context-gated graph transformer, with two GATv2 layers "
    "over a directed link graph followed by a temporal Transformer encoder, predicts link speed 15, 30 and 60 minutes "
    "ahead. Split-conformal intervals and a reliability gate decide when a forecast is fit to act on, grouped SHAP "
    "values explain each alert, and an agentic workflow joins a locally hosted language model with retrieval over "
    "public signal-timing manuals, deterministic safety checks and a calibrated SUMO corridor testbed. On a 44-day "
    "held-out test period the model reduces mean absolute error relative to persistence by 7%, 12% and 16% at the "
    "three horizons, yet across three random seeds its margin over a GRU is only a few hundredths of a mph. "
    "The intervals reach 0.90 to 0.91 coverage overall but only 0.76 to 0.80 in congestion. In simulation, a "
    "forecast-triggered green extension lowers corridor delay by 4.7% to 5.4% in surge and incident scenarios. "
    "Over three live afternoons the model did not beat persistence at 15 and 30 minutes, and we report this "
    "negative result in full."
)

KEYWORDS = ["Conformal prediction", "explainable artificial intelligence", "graph neural networks",
            "large language models", "retrieval-augmented generation", "traffic forecasting",
            "traffic signal control"]

# ------------------------------------------------------------------------------------------------------------
# body blocks: ("h1", title, key) ("h2", title) ("p", text) ("pn", text: no first-line indent) ("eq", text)
# ("table", id) ("fig", id, file, width_in, caption, full_width)

BODY = [
    ("h1", "Introduction", "intro"),
    ("p", "Congestion in dense city centres is costly in time, fuel and emissions, and most of it is managed at "
          "signalised intersections. Agencies already publish large volumes of open data on link speeds, weather, "
          "service requests and incidents, but turning that data into decisions an engineer can trust is still "
          "hard. A forecast that is only a number gives no hint of when it is likely to be wrong, a black-box "
          "model gives no reason that an operator can check, and a language model that suggests signal changes "
          "can invent facts unless it is tied to evidence and to hard rules [@ji2023hallucination]."),
    ("p", "Short-term traffic forecasting has moved from statistical time-series models to deep sequence models and, "
          "more recently, to graph neural networks that treat the road network as a graph "
          "[@vlahogianni2014shortterm, jiang2022gnnsurvey]. Most of this work, however, reports accuracy on "
          "fixed benchmark files and stops at the point forecast. Fewer studies ask whether the uncertainty is "
          "calibrated, whether the explanation is faithful, or whether the model still helps when it meets a "
          "real, delayed data feed. Signal control research, in turn, usually evaluates controllers in simulation "
          "without tying them to a forecasting model that has been tested on observed data."),
    ("p", "This paper connects these pieces in one auditable system and evaluates each piece separately and "
          "honestly. Every output carries one of three labels: **LIVE** for forecasts made from the public feed "
          "before the target was observed, **REPLAY** for evaluation on held-out history, and **SIMULATION** for "
          "results from the microscopic simulator. No signal is changed in the real world; the system only "
          "advises, and every advisory ends in human review."),
    ("p", "{F:arch} gives an overview of the system. The main contributions are as follows."),
    ("pn", "1) **Context-gated graph transformer.** A forecaster that projects six feature groups into a common "
           "space, weights them with an availability-masked softmax gate, mixes information across links with "
           "two GATv2 layers and models time with a Transformer encoder, predicting 15, 30 and 60 minutes ahead."),
    ("pn", "2) **Calibrated uncertainty with a reliability gate.** Split-conformal intervals per horizon and a "
           "gate on interval width, missing data, data age and calibration support that defers unreliable "
           "forecasts instead of passing them on."),
    ("pn", "3) **Explainable, safety-gated agentic advisory.** A fixed state machine in which a local language model "
           "drafts a schema-checked advisory from retrieved public guidance, and deterministic constraints and a "
           "calibrated simulation gate decide what may reach a human reviewer."),
    ("pn", "4) **Three-way evaluation with negative results kept.** A held-out test with multiple seeds and "
           "bootstrap intervals, a 45-run simulation study on a calibrated corridor, and a live test on three "
           "afternoons, in which the model did not beat persistence at short horizons."),
    ("p", "Section {S:related} reviews related work. Section {S:data} describes the study area and data, Section "
          "{S:method} the method and Section {S:setup} the experimental setup. Section {S:results} reports and "
          "discusses the results, Section {S:limits} states the limitations and Section {S:concl} concludes."),

    ("fig", "arch", "fig01_architecture.png", 7.0,
     "Architecture of the proposed system. The upper row produces calibrated forecasts; the lower row turns a "
     "reliable alert into an explained, evidence-grounded and rule-checked advisory that always ends in human "
     "review. Any failed check exits early with a named status.", True),
    # ------------------------------------------------------------------------------------------------------
    ("h1", "Related Work", "related"),
    ("h2", "Statistical and Deep Sequence Forecasting"),
    ("p", "Early short-term forecasting relied on autoregressive and Kalman-type models, which work well on "
          "stable motorway flow but struggle with the abrupt changes of urban streets. Vlahogianni *et al.* "
          "[@vlahogianni2014shortterm] surveyed this line of work and set out its open challenges, among them "
          "network-level prediction and the use of richer data sources. Deep learning entered with stacked autoencoders "
          "trained on large flow archives [@lv2014bigdata] and with recurrent networks; Ma *et al.* "
          "[@ma2015lstm] showed that an LSTM captures long temporal dependencies in speed data better than "
          "classical models. Gated recurrent units [@cho2014gru] offer similar accuracy with fewer parameters and "
          "remain a strong baseline. Gradient-boosted trees such as XGBoost [@chen2016xgboost] and LightGBM "
          "[@ke2017lightgbm] are also competitive on tabular lag features and are fast to train, which is why "
          "both appear as baselines in this study."),
    ("h2", "Graph-Based Spatiotemporal Models"),
    ("p", "Graph neural networks model the influence of neighbouring roads directly. DCRNN [@li2018dcrnn] treats "
          "traffic as a diffusion process on a directed graph inside a recurrent encoder-decoder, and STGCN "
          "[@yu2018stgcn] replaces recurrence with graph and temporal convolutions. Graph WaveNet "
          "[@wu2019graphwavenet] learns an adaptive adjacency matrix with dilated convolutions, and AGCRN "
          "[@bai2020agcrn] learns node-specific parameters together with the graph. Attention has become central: "
          "ASTGCN [@guo2019astgcn] adds spatial and temporal attention to graph convolution, and GMAN "
          "[@zheng2020gman] stacks multi-attention blocks in an encoder-decoder for long horizons. Graph attention "
          "networks [@velickovic2017gat] compute neighbour weights from node features, and GATv2 "
          "[@brody2022gatv2] fixes their static-attention limitation, which is the variant we use. The Transformer "
          "[@vaswani2017attention] has replaced recurrence for sequence modelling in many domains. Jiang and Luo "
          "[@jiang2022gnnsurvey] survey this fast-growing family of models. In much of this literature, "
          "evaluation is carried out on fixed benchmark files, and external context or live data are rarely used."),
    ("h2", "Uncertainty Quantification"),
    ("p", "Conformal prediction [@vovk2005algorithmic] gives prediction intervals with a finite-sample coverage "
          "guarantee under exchangeability, and the split variant needs only a held-out calibration set "
          "[@angelopoulos2021gentle]. Traffic data are not exchangeable over time, so coverage can drift. EnbPI "
          "[@xu2021enbpi] builds intervals for dynamic time series from bootstrap ensembles, adaptive conformal "
          "inference [@gibbs2021aci] adjusts the miscoverage level online, and Barber *et al.* "
          "[@barber2023beyond] bound the coverage loss under distribution shift. We use plain split conformal "
          "per horizon and measure where its coverage breaks down rather than assuming it holds."),
    ("h2", "Explainable Machine Learning"),
    ("p", "Local surrogate methods such as LIME [@ribeiro2016lime] explain a single prediction with a simple local "
          "model. SHAP [@lundberg2017shap] unifies several attribution methods through Shapley values, and "
          "TreeSHAP [@lundberg2020treeshap] computes them exactly for tree ensembles. For deep spatiotemporal "
          "models, feature-level attributions are hard to read because inputs number in the thousands. We "
          "therefore compute exact Shapley values over a small set of meaningful feature groups and check them "
          "against two perturbation tests."),
    ("h2", "Language-Model Agents and Retrieval"),
    ("p", "Retrieval-augmented generation [@lewis2020rag] grounds a language model in passages retrieved from a "
          "document store, which reduces but does not remove hallucination [@ji2023hallucination]. Dense "
          "retrieval with sentence embeddings [@reimers2019sbert] and a vector index [@johnson2019faiss] is now "
          "standard. ReAct [@yao2023react] lets a model interleave reasoning and tool calls; in a safety-relevant "
          "setting we take the opposite approach and fix the control flow in code, allowing the model a single, "
          "schema-bound step."),
    ("h2", "Signal Control and Simulation"),
    ("p", "Signal timing practice is codified in the FHWA Signal Timing Manual [@fhwa2008stm] and the MUTCD "
          "[@mutcd2009]. Reinforcement-learning controllers such as IntelliLight [@wei2018intellilight] learn "
          "phase decisions in simulation, and SUMO [@lopez2018sumo] is a widely used open microscopic "
          "simulator for such studies. A recurring weakness is that the simulated network is rarely calibrated "
          "against observed speeds, so gains may reflect the testbed rather than the controller. Our simulation "
          "gate is only used after a preregistered calibration against an observed corridor speed."),
    ("h2", "Research Gap"),
    ("p", "{T:related} compares representative studies with this work. To our knowledge, no previous study "
          "combines a graph forecaster on open city data with calibrated intervals, grouped explanations, a "
          "retrieval-grounded advisory under hard constraints, a calibrated simulation check and a live test, "
          "while reporting the parts that did not work."),
    ("table", "related"),

    # ------------------------------------------------------------------------------------------------------
    ("h1", "Study Area and Data", "data"),
    ("h2", "Study Area"),
    ("p", "The study covers Manhattan, New York City, where the city transport department publishes real-time "
          "speeds for directed road links such as avenues, the FDR Drive, the West Side Highway and tunnel and "
          "bridge approaches. Of 26 Manhattan links in the feed, seven had no valid record in 2026, leaving 19 "
          "links on the study grid. The 16 links with at least half of their training period observed enter the "
          "models ({F:area}). A directed graph joins two links when the end of one lies within 150 m of the start of "
          "the next with a compatible heading, or when the link names state a shared endpoint; this gives 16 "
          "accepted edges, each with a recorded reason."),
    ("fig", "area", "fig05_study_area.png", 3.38,
     "Monitored Manhattan road links (red) shown on the project dashboard. The links cover the main avenues, the "
     "FDR Drive, the West Side Highway and river-crossing approaches.", False),
    ("h2", "Data Sources"),
    ("p", "All inputs are public ({T:sources}). Link speed is the forecasting target [@nycdotspeeds]. Weather comes "
          "from Open-Meteo [@openmeteo]: archived forecasts are used for the operational track, so the model only "
          "sees what a forecaster would have known, and reanalysis is kept for a retrospective track. Service "
          "requests (311) are used with a 24 h lag that matches their publication delay. Collisions and permitted "
          "events are published too late for operational use and are kept for retrospective analysis only. "
          "Automated volume counts [@nycclasscounts] and OpenStreetMap geometry are used only to build the "
          "simulation corridor."),
    ("table", "sources"),
    ("h2", "Preprocessing and Quality Control"),
    ("p", "The study window is 1 January to 20 October 2026. Each download is logged with its source, time and "
          "checksum, and a server-side audit confirms dataset identity before use. Timestamps are converted from "
          "local time to UTC, and the ambiguous daylight-saving hour is dropped instead of guessed. Of 1,968,303 "
          "raw Manhattan speed records, **978,018 report a speed of zero**, which in this feed means that no "
          "measurement was taken; these records are treated as missing and never imputed. The remaining 990,226 "
          "records are averaged onto a 5-minute grid of 84,084 steps per link, with an observed fraction of "
          "0.611, and gaps of at most three steps are forward-filled using past values only."),
    ("h2", "Chronological Split"),
    ("p", "Data are split in time order into training (60%), validation (15%), conformal calibration (10%) and test "
          "(15%) partitions, with a purge gap so that no input window or target crosses a boundary. The test "
          "partition runs for 44 days, from 6 September to 20 October 2026, with 144,217, 144,213 and 144,205 "
          "valid targets at 15, 30 and 60 minutes. Three of the 16 modelled links have no valid test observation "
          "and are reported as not evaluated rather than silently dropped."),

    # ------------------------------------------------------------------------------------------------------
    ("h1", "Methodology", "method"),
    ("h2", "System Overview"),
    ("p", "{F:arch} shows the full system. Public sources pass through an audited ingestion stage into a feature "
          "and graph builder. The forecaster produces speeds at three horizons, which are wrapped in conformal "
          "intervals and checked by a reliability gate. Alerts that pass are explained with grouped Shapley "
          "values and handed to the advisory workflow, which retrieves evidence, drafts an advisory, applies "
          "safety constraints and, for signal changes, a simulation gate, before a human reviewer sees the "
          "result. A dashboard and an API expose every stage with its mode label."),
    ("h2", "Problem Formulation"),
    ("p", "Let *G* = (*V*, *E*) be the directed link graph. At each 5-minute step *t*, link *v* has a feature vector "
          "*x*_{t,v} split into groups *g* with availability flags *m*_{t,v,g} ∈ {0, 1}. Given the last *L* = 24 "
          "steps (two hours), the task is to predict the observed speed *y*_{t+h,v} for *h* ∈ {3, 6, 12} steps:"),
    ("eq", "*ŷ*_{t+h,v} = *f*_{θ}(*X*_{t−L+1:t}, *G*),  *h* ∈ {3, 6, 12}"),
    ("p", "together with an interval [*ŷ* − *q*_{h}, *ŷ* + *q*_{h}]. An advisory may only be formed when data "
          "quality, interval width, evidence, constraints and simulation all pass; otherwise a distinct defer or "
          "reject status is returned."),
    ("h2", "Context-Gated Graph Transformer"),
    ("p", "The forecaster is drawn in {F:model}. Six feature groups are used on the operational track: the link's "
          "own speed over the last 30 minutes, its speed from 30 to 120 minutes ago, the speeds of its graph "
          "neighbours, calendar terms, weather and lagged 311 counts. Each group is projected to *d* = 64 "
          "dimensions, *h*_{t,v,g} = ReLU(*W*_{g}*x*_{t,v,g}). A scoring network then gives each group a weight, "
          "and groups that are missing at that step are masked out before the softmax:"),
    ("eq", "*α*_{t,v,g} = softmax_{g: m=1}(*w*^{⊤} tanh(*U* *h*_{t,v,g})),  *z*_{t,v} = Σ_{g} *α*_{t,v,g} *h*_{t,v,g}"),
    ("p", "This **availability-masked gate** lets the model keep working when a context source is late, which is "
          "common with open city data. Two **GATv2** layers with four heads, residual connections and layer "
          "normalisation then pass *z* along the directed graph at every step [@brody2022gatv2, fey2019pyg, "
          "rozemberczki2021pgt]. Each link's sequence receives a positional embedding and enters a two-layer, "
          "four-head **Transformer encoder** (feed-forward width 128, dropout 0.1), and a linear head on the "
          "last state outputs the three horizons. The model has 158,403 parameters. Targets are standardised per "
          "link and the loss is a Huber loss averaged only over observed targets *O*:"),
    ("eq", "ℒ(*θ*) = (1/|*O*|) Σ_{(t,v,h)∈O} Huber_{δ}(*y*_{t+h,v} − *ŷ*_{t+h,v})"),
    ("fig", "model", "fig02_forecaster.png", 3.2,
     "Context-gated graph transformer. Feature groups are projected, weighted by an availability-masked gate, "
     "mixed across links by two GATv2 layers and across time by a Transformer encoder, with one head per horizon.",
     False),
    ("h2", "Baselines"),
    ("p", "Six baselines share the same targets and the same mask of valid test points: persistence (last observed "
          "speed), a historical average per link, day type and 5-minute slot, XGBoost and LightGBM with one model "
          "per horizon on twelve lags and the same causal features, a GRU with 41,667 parameters, and a "
          "temporal-only Transformer that equals the proposed model without the graph layers. Ablations remove "
          "the gate (plain concatenation) or one feature group at a time."),
    ("h2", "Conformal Intervals and Reliability Gate"),
    ("p", "With the model frozen, the absolute residuals on the calibration partition give, for each horizon, the "
          "split-conformal quantile [@angelopoulos2021gentle]"),
    ("eq", "*q*_{h} = the ⌈(*n* + 1)(1 − *α*)⌉-th smallest of |*y*_{i} − *ŷ*_{i}|,  *α* = 0.1"),
    ("p", "which gives half-widths of 12.1, 13.5 and 14.8 mph. The **reliability gate** defers a forecast when its "
          "interval is wider than 38.1 mph (the 80th percentile of per-link calibration widths), more than 34% of "
          "recent inputs are missing, the newest data are older than 20 minutes, or fewer than 200 calibration "
          "samples support the link."),
    ("h2", "Grouped Explanations"),
    ("p", "For an alert, the quantity explained is the predicted speed in mph. The players are the six feature "
          "groups; a group that is switched off takes its values from 16 background windows drawn from the "
          "training period. Because there are only six players, all 2^{6} coalitions can be evaluated, so the "
          "Shapley values [@lundberg2017shap] are exact rather than sampled:"),
    ("eq", "*φ*_{i} = Σ_{S⊆P∖{i}} [|*S*|!(|*P*|−|*S*|−1)!/|*P*|!] (*v*(*S*∪{*i*}) − *v*(*S*))"),
    ("p", "Two further checks test whether the explanations agree with the model's behaviour: removing a link's "
          "graph edges, and shortening the history window from two hours down to five minutes."),
    ("h2", "Retrieval and Agentic Advisory Workflow"),
    ("p", "The knowledge base holds 15 public documents: the FHWA Signal Timing Manual [@fhwa2008stm], two MUTCD "
          "chapters on signals [@mutcd2009], nine pages of SUMO documentation and a clearly "
          "labelled project policy that lists the allowed actions. They are split into 1,633 chunks, embedded "
          "with a MiniLM sentence encoder [@reimers2019sbert] and indexed with FAISS [@johnson2019faiss]. A query "
          "whose best passage scores below a fixed threshold returns *insufficient evidence*."),
    ("p", "The workflow in {F:flow} is a fixed state machine. Only the recommendation step calls the language model, "
          "an open-weight instruction-tuned model of about seven billion parameters that runs locally, so no "
          "data leave the machine. The model receives the forecast, interval, quality flags, attributions, "
          "retrieved passages (marked as untrusted text) and the action catalogue, and must return JSON that "
          "matches a strict schema and cites only retrieved passages. Every other step is deterministic code."),
    ("fig", "flow", "fig03_workflow.png", 3.2,
     "Advisory workflow. Each step can end the run with a named status; only the recommendation step uses the "
     "language model, and a completed run always waits for a human decision.", False),
    ("h2", "Safety Constraints and Simulation Testbed"),
    ("p", "Allowed actions are a green extension of 0 to 10 s on an existing green phase, a switch to a pre-validated "
          "program, or monitoring only. Thirteen deterministic checks cover the link-to-simulation mapping, signal "
          "and phase existence, action type, bounds, minimum and maximum green, clearance intervals, data freshness, "
          "forecast reliability and evidence support. A candidate that passes is then run in SUMO "
          "[@lopez2018sumo] against the fixed-time plan on matched seeds, and must cut corridor delay by at least "
          "1% without raising side-road delay by more than 10% or causing any teleport."),
    ("p", "The testbed is the West Street corridor in lower Manhattan, built from OpenStreetMap with 82 edges, 22 "
          "signals and 25 side entries, and loaded with 2025 counts of 2,510 and 2,444 vehicles per hour in the "
          "two directions [@nycclasscounts]. The city does not publish its timing plans, so signals start from "
          "Webster-style timing; the city's records do show that West Street was retimed for 25 mph signal "
          "progression [@nycvzvretiming], which motivates the offsets tested below. Before any controller is compared, the testbed must reproduce the observed "
          "weekday evening-peak speed of 10.95 mph on the matching link within ±1.5 mph, using a grid of cycle "
          "lengths, green factors and offsets fixed in advance."),
    ("h2", "Implementation"),
    ("p", "The system is written in Python as one package of nineteen sub-packages grouped into six layers ({F:modules}). "
          "Typed record contracts are shared by all layers, a single command-line entry point runs every stage, "
          "and each run writes its configuration, data hashes and metrics so that every reported number can be "
          "traced back to the run that produced it. The graph layers use PyTorch Geometric [@fey2019pyg], the "
          "workflow is a state graph with a human-review interrupt, and a twelve-page dashboard presents the "
          "results with their mode labels."),
    ("fig", "modules", "fig04_modules.png", 3.2,
     "Code structure of the implementation. Modules are grouped by role, from data handling to delivery; "
     "contracts and settings are shared.", False),

    # ------------------------------------------------------------------------------------------------------
    ("h1", "Experimental Setup", "setup"),
    ("p", "{T:setup} lists the training settings. All learned models were trained on the same windows with early "
          "stopping on validation MAE. The main comparison uses one reference run per model; the three deep "
          "models were then retrained with seeds 1, 2 and 42 under the same budget, and differences were tested "
          "with a paired day-block bootstrap over the 44 test days. Accuracy is measured with mean absolute "
          "error (MAE), root mean squared error (RMSE) and *R*^{2}, all in mph on observed targets only:"),
    ("eq", "MAE = (1/*N*) Σ_{i} |*y*_{i} − *ŷ*_{i}|,  RMSE = ((1/*N*) Σ_{i} (*y*_{i} − *ŷ*_{i})^{2})^{1/2}"),
    ("table", "setup"),
    ("p", "Intervals are judged by empirical coverage against the nominal 90% and by mean width. Retrieval is "
          "judged on 28 labelled queries by Recall@8, mean reciprocal rank (MRR) and accuracy of the "
          "supported/unsupported status. The advisory workflow is run on seven replay cases under four policies, "
          "and the simulation compares controllers on five matched seeds per scenario."),
    ("p", "For the **live test**, forecasts were issued from the public feed after training and saved before their "
          "targets were published, then scored once the targets appeared. A strict real-time protocol could not "
          "run, because the feed published data 1.7 to 4.3 hours late, so a preregistered *latest-available* "
          "protocol was used: each forecast starts from the newest bin the feed has published. The test ran on "
          "three weekday afternoons with three forecast batches each."),

    # ------------------------------------------------------------------------------------------------------
    ("h1", "Results and Discussion", "results"),
    ("h2", "Forecast Accuracy"),
    ("p", "{T:forecast} and {F:mae} give the test errors. All learned models clearly beat persistence and the "
          "historical average. The proposed model has the lowest MAE at 30 and 60 minutes (5.33 and 6.16 mph), "
          "**7%, 12% and 16% below persistence** at the three horizons, with *R*^{2} of 0.69, 0.63 and 0.56 "
          "against 0.55, 0.46 and 0.30 for persistence. At 15 minutes the GRU is best (4.72 mph). The gap between "
          "persistence and the learned models grows with the horizon, which shows that recent speed alone "
          "carries most of the short-term signal while the learned context matters more further ahead."),
    ("table", "forecast"),
    ("fig", "mae", "fig06_mae.png", 3.38,
     "Test MAE of all models at the three horizons (REPLAY). The vertical axis starts at 4 mph to make the "
     "differences between learned models visible.", False),
    ("h2", "Robustness Across Seeds"),
    ("p", "A single run can flatter a model, so the three deep models were retrained with three seeds ({T:seeds}, "
          "{F:seeds}). The proposed model is significantly better than the temporal Transformer at every horizon, "
          "which credits the graph layers, but its edge over the GRU is small: the GRU is better at 15 minutes "
          "(difference −0.021 mph, 95% interval [−0.040, −0.004]) and worse at 30 and 60 minutes by about 0.03 mph. "
          "**The accuracy gain is therefore real but small**, and a simpler recurrent model remains a fair choice "
          "for the shortest horizon. The graph layers use non-deterministic scatter operations, so runs with the "
          "same seed are not bit-identical; the later stages all use the seed-42 reference model."),
    ("table", "seeds"),
    ("fig", "seeds", "fig07_seeds.png", 3.38,
     "Test MAE over seeds 1, 2 and 42. Small markers are single runs; large markers show the mean and one "
     "standard deviation.", False),
    ("h2", "Ablation and Sensitivity"),
    ("p", "Removing the availability gate raises the mean MAE by 0.067 mph (95% interval [0.048, 0.086]) and "
          "removing the 311 group by 0.014 mph, so both help slightly ({F:ablation}a). Removing weather, however, "
          "**lowers** the error by 0.046 mph: on this test period the weather forecasts added noise rather than "
          "signal, and we report this as a negative finding. Shortening the history window raises the error "
          "steadily, from 5.43 mph with two hours to 7.11 mph with five minutes ({F:ablation}b), so the model does "
          "use its full window."),
    ("fig", "ablation", "fig08_ablation_window.png", 3.38,
     "(a) Change in mean test MAE when a component is removed, with 95% day-block bootstrap intervals. (b) MAE "
     "when the link's own history is cut to shorter windows.", False),
    ("h2", "Uncertainty and the Reliability Gate"),
    ("p", "The conformal intervals reach 0.909, 0.907 and 0.903 coverage at the three horizons, close to the "
          "nominal 0.90 ({T:unc}). Coverage is not uniform, though ({F:unc}a). It is about 0.93 in free flow and "
          "moderate traffic but falls to **0.80, 0.79 and 0.76 in congestion**, exactly where advice matters most, "
          "because the intervals have one width per horizon. Rush hours (0.93 to 0.94) and wet periods (0.92 to "
          "0.93) are slightly over-covered. The reliability gate defers about a quarter of forecasts; on the "
          "retained ones the MAE falls to 3.72, 4.38 and 5.25 mph and coverage rises to 0.93 to 0.95 "
          "({F:unc}b). The gate thus trades coverage of the network for reliability of what is passed on."),
    ("table", "unc"),
    ("fig", "unc", "fig09_uncertainty.png", 3.38,
     "(a) Empirical coverage of the 90% intervals by traffic state; the dashed line is the nominal level. (b) "
     "MAE of retained forecasts against the share deferred, for the gate's missing-data threshold.", False),
    ("h2", "Explanations"),
    ("p", "Across twelve explained alerts, the link's own last 30 minutes dominate the attributions (mean absolute "
          "value 8.22 mph), followed by its older history (2.04), calendar (1.09) and neighbours (0.52), with "
          "weather (0.19) and 311 (0.09) close to zero ({F:shap}a). This agrees with the ablation, in which weather "
          "did not help. In one alert on a bridge approach the model predicted 2.25 mph against a background of "
          "26.9 mph (observed 1.24 mph), and the recent-history group accounted for −21.3 mph of that drop, a "
          "reading an operator can check against the raw series. Removing a link's graph edges changes its "
          "predictions by 0.67 to 1.34 mph, and not at all for the West Street link. The "
          "LightGBM baseline, explained with TreeSHAP, gives a similar ranking ({F:shap}b): about 65% of the "
          "attribution goes to traffic lags and 16% to calendar terms."),
    ("fig", "shap", "fig10_shap.png", 3.38,
     "(a) Mean absolute grouped Shapley value of the proposed model over twelve alerts. (b) Share of TreeSHAP "
     "attribution by group for the LightGBM baseline at each horizon.", False),
    ("h2", "Retrieval and Advisory Workflow"),
    ("p", "On 28 labelled queries, retrieval reaches **Recall@8 of 0.841** and an MRR of 0.748, and the "
          "supported/unsupported status is right for 27 of 28 queries (0.964). The labels were reviewed by the "
          "first author and not by an independent annotator, which limits how far these figures can be "
          "generalised."),
    ("p", "{T:adv} summarises 19 advisory runs (seven cases under the full system and four under each of three "
          "reduced policies), repeated in three passes with 36 language-model calls in total. Every call returned "
          "valid JSON and every pass reached the same 19 decisions. Without retrieval, the model invented an "
          "evidence identifier in all three cases where it drafted an advisory, and the citation check rejected "
          "each one; with retrieval, none of nine drafts cited a missing passage. Without the constraint layer, "
          "an advisory for a link that has no mapping to the simulator reached human review, whereas the full "
          "system rejected it. In the full system, wide intervals, stale data and missing evidence ended runs "
          "early as intended, and the two corridor cases ended as monitor-only advisories pending human review. "
          "**No real advisory reached the simulation gate**, so the gate has only been exercised by the "
          "controller study below. After the first call, an advisory took 19 to 30 s."),
    ("table", "adv"),
    ("h2", "Simulation Calibration"),
    ("p", "The testbed did not match reality at first. With Webster-style timing the corridor ran at 5.82 mph "
          "against the observed 10.95 mph, and scaling the green split alone never rose above 8.22 mph "
          "({F:calib}). A common 90 s cycle reached 8.88 mph, and adding offsets for a 25 mph southbound platoon "
          "brought it to **10.08 mph, inside the ±1.5 mph band**; this cell (green factor 1.5) was selected by the "
          "preregistered rule. A 120 s cycle overshot to 13.1 to 21.7 mph. The calibrated network is a scenario "
          "testbed tuned to one speed on one link, not a model of the city's actual timing plans. An earlier "
          "version of the testbed wrote demand as origin-destination flows, which the simulator re-routes on "
          "current travel times [@sumodocs_routing], so part of the traffic left the corridor; an audit found "
          "this, and all runs reported here use fixed free-flow routes on the corridor."),
    ("fig", "calib", "fig11_calibration.png", 3.38,
     "Calibration of the SUMO corridor (SIMULATION): mean simulated speed on the mapped link against the green "
     "factor for each timing family. Filled markers are admissible cells; the band is the observed speed ±1.5 mph.",
     False),
    ("h2", "Controller Comparison in Simulation"),
    ("p", "On the calibrated corridor, three controllers were run in three scenarios with five matched seeds, 45 "
          "runs in all, none with a teleport ({T:sim}, {F:ctrl}). The forecast rule extends corridor green by 5 s "
          "when the forecast flags congestion. In the routine peak it is never triggered, so it equals fixed time "
          "(271.6 s time loss per trip). Under the event surge it lowers time loss from 450.2 s to 426.0 s "
          "(**−5.4%**) and completes 5,910 trips instead of 5,720; in the incident scenario time loss falls from "
          "465.9 s to 443.9 s (**−4.7%**) with 5,919 trips completed instead of 5,725. The rule wins in every seed, "
          "by 12.9 to 33.7 s, and it is not a survivorship effect, because more trips finish rather than fewer. "
          "The actuated controller uses the simulator's own uncalibrated programs and is shown only as a "
          "reference. These are simulation results on a calibrated scenario testbed without side-street demand or "
          "pedestrians; they are **not evidence of a real-world gain**."),
    ("table", "sim"),
    ("fig", "ctrl", "fig12_controllers.png", 3.38,
     "Fixed time against the forecast-triggered rule on the calibrated corridor (SIMULATION, five seeds). (a) "
     "Time loss per completed trip with the range over seeds. (b) Completed trips per run.", False),
    ("h2", "Live Test"),
    ("p", "{T:live} and {F:live} give the live results, and {F:dash}b shows how the dashboard labels a live "
          "batch. On the first afternoon the model beat persistence at all three horizons. On the second it lost "
          "at 15 and 30 minutes, and on the third it lost at every horizon. Pooled over 274 scored forecasts "
          "(two of 276 targets were never published), the MAE is 4.79, 4.94 and 5.48 mph against 4.63, 4.42 and "
          "5.46 mph for persistence: **persistence is ahead at 15 and 30 minutes and level at 60 minutes**. "
          "Coverage held up better, at 0.880, 0.901 and 0.912. The forecasts started from data that were already "
          "100 to 130 minutes old, and at that age the most recent observed speed is a hard baseline to beat. "
          "Restricted to the links eligible for advice, the model's MAE is lower (3.88, 4.22 and 4.70 mph), but "
          "with nine afternoon batches this is not a second test set. **The test-set gain did not carry over to "
          "the live feed at its present delay**, and we report this as the main live finding."),
    ("table", "live"),
    ("fig", "live", "fig13_live.png", 3.38,
     "Live MAE of the proposed model and of persistence on three afternoons (A1 to A3) and pooled (LIVE, "
     "latest-available origin).", False),
    ("h2", "Dashboard and Run Time"),
    ("p", "The dashboard ({F:dash}) shows each forecast with its interval, data age and mode label, and lists every "
          "advisory with its decision and reasons. On a CPU, one forecast for all links takes 5.7 ms with the "
          "proposed model, 2.2 ms with the temporal Transformer and 0.7 ms with the GRU, and a retrieval query takes "
          "tens of milliseconds. The language-model step dominates the latency of an advisory, which is "
          "acceptable for monitor-only advice but would need attention for faster control loops."),
    ("fig", "dash", "fig14_dashboard.png", 7.0,
     "Project dashboard. (a) Multi-horizon forecast for one link with 90% intervals at 15, 30 and 60 minutes "
     "(REPLAY). (b) Live monitoring banner stating the data age and protocol of a batch (LIVE). (c) Audit table of "
     "advisory runs with their decisions and recorded reasons (REPLAY).",
     True),
    ("h2", "Discussion"),
    ("p", "Three lessons stand out. First, graph structure helps, but modestly: the graph layers beat a temporal "
          "Transformer reliably, yet a GRU stays within a few hundredths of a mph. Second, calibration in "
          "aggregate hides failure in the tail; coverage drops below 0.80 in congestion, which argues for "
          "state-dependent or adaptive intervals [@gibbs2021aci, barber2023beyond]. Third, the most useful "
          "parts of the advisory are the deterministic ones. Retrieval stopped invented citations, and the "
          "constraint layer caught an advisory that retrieval alone let through. The live test shows that "
          "accuracy on held-out history does not guarantee value on a delayed feed, and that a fair live "
          "comparison must keep persistence in view."),

    # ------------------------------------------------------------------------------------------------------
    ("h1", "Limitations", "limits"),
    ("p", "The study covers 13 evaluated links in one borough over one test period, so the results may not "
          "transfer to other networks or seasons. The open speed feed is delayed and patchy, with half of the raw "
          "records carrying no measurement. The intervals assume exchangeability, which traffic violates, and they "
          "under-cover congestion. Explanations cover twelve alerts and describe the model, not causes on the "
          "street. Retrieval labels were reviewed by the first author only. The simulation testbed is calibrated "
          "to one observed speed, has no side-street demand or pedestrians and uses assumed timing plans, so its "
          "gains are illustrative. The live test spans three afternoons and nine batches. Finally, nothing was "
          "deployed on real signals, and every advisory stops at human review."),

    # ------------------------------------------------------------------------------------------------------
    ("h1", "Conclusion and Future Work", "concl"),
    ("p", "This paper presented an auditable predictive analytics system for city traffic built on open data. A "
          "context-gated graph transformer lowers forecast error against persistence by 7% to 16% on a held-out "
          "period and consistently beats a temporal Transformer, although its margin over a GRU is small. "
          "Conformal intervals with a reliability gate make the forecasts safer to use but under-cover congestion. "
          "Grouped Shapley values give readable explanations that agree with the ablations. A retrieval-grounded "
          "language model, bounded by deterministic constraints and a calibrated simulation gate, produced valid, "
          "cited and conservative advisories, and a forecast-triggered rule cut simulated delay by about 5% under "
          "stress. Live, at the feed's present delay, the model did not beat persistence at short horizons."),
    ("p", "Future work will add state-dependent and adaptive conformal intervals, test on more links and longer "
          "live periods with a lower-latency feed, include side-street and pedestrian demand in the testbed, and "
          "invite independent reviewers to label retrieval queries and judge advisories."),
]

# ------------------------------------------------------------------------------------------------------------
REFERENCES = {
    "vlahogianni2014shortterm": "E. I. Vlahogianni, M. G. Karlaftis, and J. C. Golias, “Short-term traffic forecasting: "
    "Where we are and where we’re going,” *Transp. Res. Part C: Emerg. Technol.*, vol. 43, pp. 3–19, 2014, doi: "
    "10.1016/j.trc.2014.01.005.",
    "jiang2022gnnsurvey": "W. Jiang and J. Luo, “Graph neural network for traffic forecasting: A survey,” *Expert Syst. "
    "Appl.*, vol. 207, Art. no. 117921, 2022, doi: 10.1016/j.eswa.2022.117921.",
    "ji2023hallucination": "Z. Ji *et al.*, “Survey of hallucination in natural language generation,” *ACM Comput. "
    "Surv.*, vol. 55, no. 12, pp. 1–38, 2023, doi: 10.1145/3571730.",
    "lv2014bigdata": "Y. Lv, Y. Duan, W. Kang, Z. Li, and F.-Y. Wang, “Traffic flow prediction with big data: A deep "
    "learning approach,” *IEEE Trans. Intell. Transp. Syst.*, 2014, doi: 10.1109/TITS.2014.2345663.",
    "ma2015lstm": "X. Ma, Z. Tao, Y. Wang, H. Yu, and Y. Wang, “Long short-term memory neural network for traffic speed "
    "prediction using remote microwave sensor data,” *Transp. Res. Part C: Emerg. Technol.*, vol. 54, pp. 187–197, "
    "2015, doi: 10.1016/j.trc.2015.03.014.",
    "cho2014gru": "K. Cho *et al.*, “Learning phrase representations using RNN encoder–decoder for statistical machine "
    "translation,” in *Proc. Conf. Empirical Methods Natural Lang. Process. (EMNLP)*, 2014, pp. 1724–1734, doi: "
    "10.3115/v1/D14-1179.",
    "chen2016xgboost": "T. Chen and C. Guestrin, “XGBoost: A scalable tree boosting system,” in *Proc. 22nd ACM SIGKDD "
    "Int. Conf. Knowl. Discovery Data Mining*, 2016, pp. 785–794, doi: 10.1145/2939672.2939785.",
    "ke2017lightgbm": "G. Ke *et al.*, “LightGBM: A highly efficient gradient boosting decision tree,” in *Advances in "
    "Neural Information Processing Systems*, vol. 30, 2017.",
    "li2018dcrnn": "Y. Li, R. Yu, C. Shahabi, and Y. Liu, “Diffusion convolutional recurrent neural network: Data-driven "
    "traffic forecasting,” in *Proc. Int. Conf. Learn. Represent. (ICLR)*, 2018, arXiv:1707.01926.",
    "yu2018stgcn": "B. Yu, H. Yin, and Z. Zhu, “Spatio-temporal graph convolutional networks: A deep learning framework "
    "for traffic forecasting,” in *Proc. Int. Joint Conf. Artif. Intell. (IJCAI)*, 2018, pp. 3634–3640, doi: "
    "10.24963/ijcai.2018/505.",
    "wu2019graphwavenet": "Z. Wu, S. Pan, G. Long, J. Jiang, and C. Zhang, “Graph WaveNet for deep spatial-temporal "
    "graph modeling,” in *Proc. Int. Joint Conf. Artif. Intell. (IJCAI)*, 2019, pp. 1907–1913, doi: "
    "10.24963/ijcai.2019/264.",
    "bai2020agcrn": "L. Bai, L. Yao, C. Li, X. Wang, and C. Wang, “Adaptive graph convolutional recurrent network for "
    "traffic forecasting,” 2020, arXiv:2007.02842.",
    "guo2019astgcn": "S. Guo, Y. Lin, N. Feng, C. Song, and H. Wan, “Attention based spatial-temporal graph "
    "convolutional networks for traffic flow forecasting,” in *Proc. AAAI Conf. Artif. Intell.*, vol. 33, no. 1, "
    "2019, pp. 922–929, doi: 10.1609/aaai.v33i01.3301922.",
    "zheng2020gman": "C. Zheng, X. Fan, C. Wang, and J. Qi, “GMAN: A graph multi-attention network for traffic "
    "prediction,” in *Proc. AAAI Conf. Artif. Intell.*, vol. 34, no. 1, 2020, pp. 1234–1241, doi: "
    "10.1609/aaai.v34i01.5477.",
    "velickovic2017gat": "P. Veličković, G. Cucurull, A. Casanova, A. Romero, P. Liò, and Y. Bengio, “Graph attention "
    "networks,” 2017, arXiv:1710.10903.",
    "brody2022gatv2": "S. Brody, U. Alon, and E. Yahav, “How attentive are graph attention networks?” in *Proc. Int. "
    "Conf. Learn. Represent. (ICLR)*, 2022, arXiv:2105.14491.",
    "vaswani2017attention": "A. Vaswani *et al.*, “Attention is all you need,” in *Advances in Neural Information "
    "Processing Systems*, vol. 30, 2017, pp. 5998–6008.",
    "vovk2005algorithmic": "V. Vovk, A. Gammerman, and G. Shafer, *Algorithmic Learning in a Random World*. New York, "
    "NY, USA: Springer, 2005, doi: 10.1007/b106715.",
    "angelopoulos2021gentle": "A. N. Angelopoulos and S. Bates, “A gentle introduction to conformal prediction and "
    "distribution-free uncertainty quantification,” 2021, arXiv:2107.07511.",
    "xu2021enbpi": "C. Xu and Y. Xie, “Conformal prediction interval for dynamic time-series,” in *Proc. 38th Int. Conf. "
    "Mach. Learn. (ICML)*, PMLR, vol. 139, 2021, pp. 11559–11569.",
    "gibbs2021aci": "I. Gibbs and E. Candès, “Adaptive conformal inference under distribution shift,” 2021, "
    "arXiv:2106.00170.",
    "barber2023beyond": "R. F. Barber, E. J. Candès, A. Ramdas, and R. J. Tibshirani, “Conformal prediction beyond "
    "exchangeability,” *Ann. Statist.*, vol. 51, no. 2, pp. 816–845, 2023, doi: 10.1214/23-AOS2276.",
    "ribeiro2016lime": "M. T. Ribeiro, S. Singh, and C. Guestrin, “‘Why should I trust you?’: Explaining the predictions "
    "of any classifier,” in *Proc. 22nd ACM SIGKDD Int. Conf. Knowl. Discovery Data Mining*, 2016, pp. 1135–1144, "
    "doi: 10.1145/2939672.2939778.",
    "lundberg2017shap": "S. M. Lundberg and S.-I. Lee, “A unified approach to interpreting model predictions,” in "
    "*Advances in Neural Information Processing Systems*, vol. 30, 2017, arXiv:1705.07874.",
    "lundberg2020treeshap": "S. M. Lundberg *et al.*, “From local explanations to global understanding with "
    "explainable AI for trees,” *Nat. Mach. Intell.*, vol. 2, no. 1, pp. 56–67, 2020, doi: "
    "10.1038/s42256-019-0138-9.",
    "lewis2020rag": "P. Lewis *et al.*, “Retrieval-augmented generation for knowledge-intensive NLP tasks,” in "
    "*Advances in Neural Information Processing Systems*, vol. 33, 2020, arXiv:2005.11401.",
    "reimers2019sbert": "N. Reimers and I. Gurevych, “Sentence-BERT: Sentence embeddings using Siamese BERT-networks,” "
    "in *Proc. EMNLP-IJCNLP*, 2019, pp. 3982–3992, doi: 10.18653/v1/D19-1410.",
    "johnson2019faiss": "J. Johnson, M. Douze, and H. Jégou, “Billion-scale similarity search with GPUs,” *IEEE Trans. "
    "Big Data*, vol. 7, no. 3, pp. 535–547, 2021, doi: 10.1109/TBDATA.2019.2921572.",
    "yao2023react": "S. Yao *et al.*, “ReAct: Synergizing reasoning and acting in language models,” in *Proc. Int. Conf. "
    "Learn. Represent. (ICLR)*, 2023, arXiv:2210.03629.",
    "fhwa2008stm": "P. Koonce *et al.*, “Traffic signal timing manual,” U.S. Dept. of Transportation, Federal Highway "
    "Administration, Washington, DC, USA, Rep. FHWA-HOP-08-024, 2008.",
    "mutcd2009": "U.S. Dept. of Transportation, Federal Highway Administration, *Manual on Uniform Traffic Control "
    "Devices for Streets and Highways*, 2009 ed. Washington, DC, USA, 2009.",
    "wei2018intellilight": "H. Wei, G. Zheng, H. Yao, and Z. Li, “IntelliLight: A reinforcement learning approach for "
    "intelligent traffic light control,” in *Proc. 24th ACM SIGKDD Int. Conf. Knowl. Discovery Data Mining*, 2018, "
    "pp. 2496–2505, doi: 10.1145/3219819.3220096.",
    "lopez2018sumo": "P. A. Lopez *et al.*, “Microscopic traffic simulation using SUMO,” in *Proc. 21st IEEE Int. Conf. "
    "Intell. Transp. Syst. (ITSC)*, 2018, pp. 2575–2582, doi: 10.1109/ITSC.2018.8569938.",
    "nycdotspeeds": "New York City Department of Transportation, “DOT traffic speeds NBE,” NYC Open Data, dataset "
    "i4gi-tjb9. Accessed: Oct. 20, 2026. [Online]. Available: https://data.cityofnewyork.us/d/i4gi-tjb9",
    "openmeteo": "Open-Meteo, “Historical weather and historical forecast APIs,” CC BY 4.0. Accessed: Oct. 20, 2026. "
    "[Online]. Available: https://open-meteo.com",
    "nycclasscounts": "New York City Department of Transportation, “Vehicle classification counts (2011–2025),” NYC "
    "Open Data, dataset 96ay-ea4r. Accessed: Oct. 21, 2026.",
    "fey2019pyg": "M. Fey and J. E. Lenssen, “Fast graph representation learning with PyTorch Geometric,” presented at "
    "the ICLR Workshop Represent. Learn. Graphs Manifolds, 2019, arXiv:1903.02428.",
    "rozemberczki2021pgt": "B. Rozemberczki *et al.*, “PyTorch Geometric Temporal: Spatiotemporal signal processing "
    "with neural machine learning models,” in *Proc. 30th ACM Int. Conf. Inf. Knowl. Manage. (CIKM)*, 2021, "
    "pp. 4564–4573, doi: 10.1145/3459637.3482014.",
    "sumodocs_routing": "Eclipse SUMO contributors, “Automatic routing / routing device (SUMO 1.28.0 documentation),” "
    "section “Incomplete trips and flows,” 2026. Accessed: Oct. 21, 2026. [Online]. Available: "
    "https://github.com/eclipse-sumo/sumo/blob/v1_28_0/docs/web/docs/Demand/Automatic_Routing.md",
    "nycvzvretiming": "New York City Department of Transportation, “VZV signal timing / 25 MPH signal retiming,” NYC "
    "Open Data, dataset d8dp-wfee. Accessed: Oct. 21, 2026.",
}
