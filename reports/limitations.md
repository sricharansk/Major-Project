# Limitations

Living document. Items are stated as they are at the time of the last real-data run; anything that changes is
updated here and in `reports/verification/final_status.md`. Nothing here is softened.

## Data

1. **Link selection.** NYC DOT real-time speed links are a sparse, highway-heavy set chosen by the agency, not a
   full street network. Many Manhattan links are the FDR Drive, West Side Highway and bridge approaches. Graph
   neighbours are therefore often far apart, which limits what a spatial layer can learn. Link set in this run:
   `data/raw/speeds_links/links_since_2026-09-20.json.gz`: 125 links citywide with geometry, of which 26 are in
   Manhattan (the full-year group-by timed out server-side six times, so the set is "links active since
   2026-09-20", recorded in the fetch log). After the training-coverage eligibility rule, 19 Manhattan links form the
   modelling grid.
2. **Observation window.** Speeds cover 2026-01-01 to 2026-10-20 only; seasonality beyond that is not learned.
3. **Collision publication lag.** The collisions dataset's latest `crash_date` was 2026-06-11 at download time
   (about four months of lag), so collisions are retrospective-only and absent from the test period. The
   retrospective track's incident features are therefore evaluated on a period without them.
4. **Weather.** The operational track uses Open-Meteo's historical-forecast product as a proxy for the forecast
   that would have been available at the time; it is a model re-forecast, not an archived agency forecast, so
   operational weather knowledge is approximated, not reproduced. The retrospective track uses the finalised archive.
5. **Events.** The historical permitted-events dataset has free-text locations and no announcement timestamp; it is
   used only retrospectively and matched by street name, which is approximate.
6. **Volume.** ATR counts are sampled, not continuous; they only parameterise SUMO demand.
7. **Daylight-saving ambiguity.** The repeated 01:00-02:00 local hour on the fall-back day is nulled, not resolved.
7a. **Zero speeds in the feed.** About half of the raw Manhattan speed records (978,018 of 1,968,303 in the 2026
   download) carry `speed <= 0`. The feed uses 0 where no travel time was measured in the interval, so these records
   are treated as missing (never imputed as 0 mph); the observed fraction of the 5-minute grid is 0.611. This is
   recorded by `data preprocess` and is the main reason the missing-indicator features and the causal fill limit
   matter.
7b. **Sparse graph and unreliable polylines.** With the endpoint rule alone the 26 Manhattan links yield 4 edges and
   20 isolated nodes, and the corridor rule added one more, because DOT segments do not tile the highways and the
   published `link_points` polylines often stop short of the named end of a link ("FDR S 63rd - 25th St" is 1.5 km
   of geometry for a 3 km segment and ends 1.5 km before "FDR S 25th St - Catherine Slip" starts). The
   named-endpoint rule therefore joins links whose names state a shared endpoint (`configs/graph.yaml`,
   `named_join_m`), guarded by direction, heading and distance checks; every edge's rule, gap and matched tokens are
   in `reports/data_audit/graph_edges.csv`, and the 26 names with their degrees are in
   `reports/data_audit/manhattan_links.csv`. Links that are tunnels, bridges or isolated highway stubs (Lincoln
   Tunnel tubes, QMT, BBT westbound, GWB, the Triborough connectors) have no monitored neighbour and stay isolated
   whatever the rule. The graph-vs-no-graph ablation must be read with this sparsity in mind.

## Modelling and evaluation

8. **Single seed, single split.** One chronological split and one seed per model; seed variance is not reported.
   Paired comparisons use a day-block bootstrap, which is the only variance estimate provided.
9. **Tree baselines are strided.** XGBoost/LightGBM train on a strided subsample of train origins
   (`max_train_rows`), recorded in each run's config; this may disadvantage them slightly.
10. **Conformal coverage is marginal.** Split conformal guarantees marginal coverage under exchangeability, which
    traffic time series violate; per-link intervals are only produced where the calibration sample is large enough.
11. **Explanations describe the model**, not traffic causality. KernelSHAP over feature groups is exact at the group
    level but uses a background drawn from the calibration partition; neighbour sensitivity perturbs inputs the
    model may never have seen jointly.

## Knowledge, LLM and agents

12. **Corpus size.** The approved corpus is small (U.S. federal guidance, SUMO documentation, a project-defined
    policy). It is not NYC DOT's signal-timing policy, which is not published in a retrievable form; the
    project-defined policy is labelled as such and must not be read as an agency rule.
13. **Retrieval labels** in `knowledge/retrieval_eval_queries.csv` were drafted by the project and are marked
    `drafted_by_project_unreviewed`; recall/MRR are therefore an internal consistency check, not an external benchmark.
14. **LLM.** A 7B quantised model (`qwen2.5:7b`, Q4_K_M) run through Ollama on the author's workstation; outputs are
    schema-validated but their content is only as good as the retrieved evidence and the constraints that follow.
    The LLM is never the safety boundary.
15. **Agent evaluation cases** are a handful of REPLAY cases chosen by rule from the test partition (highest
    congestion, stale-data stress, wide-interval stress, insufficient-evidence probe); it is a functional
    evaluation of the workflow, not a statistical one.

## Simulation

16. **Not a digital twin.** The SUMO network is OSM geometry for one corridor with demand from matched ATR counts
    where available and declared assumptions otherwise (`simulation/scenarios/prepared.json`); signal programs are
    netconvert defaults, not NYC DOT's plans. Simulation gains are relative between controllers on the same seeds
    and say nothing about the real street.
17. **Pedestrians.** Scenarios contain no pedestrian demand, so pedestrian impact is NOT_EVALUATED, which is
    reported rather than assumed neutral.
18. **Link-to-signal mapping** is automatic with a review flag; only `high` confidence, reviewed mappings are
    eligible for advisories.

## Engineering and reproducibility

19. **Hardware split.** Data download, LLM inference and (in the real-data run) training ran on the author's
    workstation (Windows, RTX 4050, CUDA 12.8, torch 2.11.0+cu128), which deviates from `requirements.lock`
    (torch 2.14.1, CUDA 13 build) because the installed driver supports at most CUDA 12.8. The deviation is
    recorded in `reports/verification/environment.json` of that run.
20. **Cloud container restrictions.** The development container could not reach NYC Open Data, Hugging Face or
    the workstation's Ollama; the recorded-request batch executor (`scripts/ollama_batch.py`) exists for that reason.
21. **Docker build** is verified only where `reports/verification/docker_smoke.json` says so; otherwise it is
    BLOCKED with the reason recorded.
22. **Bibliography.** `paper/REFERENCES_STATUS.md` records the publisher-record check of every entry (2026-10-20);
    the FHWA 2008 Signal Timing Manual and the 2009 MUTCD are superseded editions, cited because they are the
    public-domain texts the corpus holds.
