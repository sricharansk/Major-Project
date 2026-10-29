# Preregistered protocol: LIVE run with a latest-available origin

Registered 2026-10-29, before any run under it. Decided by the project owner after two wall-clock LIVE attempts
(2026-10-28 and 2026-10-29) in which the NYC DOT speed feed (`i4gi-tjb9`) was 1.7 to 4.3 hours behind real time on
weekday afternoons, so the forecaster correctly withheld every link (fewer than 12 of the 24 lookback bins observed)
and no live forecast was issued. Those two attempts stay recorded as NOT RUN; this protocol does not replace them.

## What changes and what does not

| | wall-clock origin (section 26 as implemented in PR #28) | latest-available origin (this protocol) |
|---|---|---|
| Origin bin | latest complete 5-minute bin of the clock | newest 5-minute bin in which the feed has published a valid observation of any modelled link, never later than the clock |
| Model, scaler, features, intervals, gate, lookback rule (12 of 24 bins per link) | unchanged | **unchanged** |
| Forecast file | written before its first target *time* | written before its first target bin is *published*; the origin's data age at issue is stored on the batch and on every link |
| What is scored | a target whose bin is later observed, unless the forecast was generated after the target time (LATE) | a target whose bin was **first retrieved after the forecast was written** (`first_seen` from the pull logs); a bin retrievable at issue time is excluded as PUBLISHED_BEFORE_ISSUE, and a bin with no retrieval record is excluded too |
| Wall-clock meaning | the forecast is about the future | the forecast is about bins the feed has not yet published; some target times may already lie in the past. The count of such scored targets is reported, and every displayed forecast carries its data age |

Nothing in the scoring arithmetic changes: MAE, RMSE, coverage of the 90 % intervals, mean width and the persistence
baseline (last observed speed at the origin) are computed exactly as in the wall-clock mode.

## Run plan (fixed before the run)

1. Workstation, branch `claude/laptop-live` from `origin/main`; `tests/unit/test_live.py` must pass.
2. `python -m smartcity.cli live run --polls 24 --interval-s 300 --origin latest-available --settle-max-hours 4`
   on any weekday between about 12:00 and 18:00 New York time. Twenty-four polls at five minutes is a two-hour
   collection window; a poll that finds no newer published bin writes no new batch (the origin's file already
   exists), so the number of batches equals the number of distinct origins the feed published during the window.
3. The settle phase pulls every ten minutes (no new forecasts) until the feed has published the last batch's
   60-minute target bin, or until four hours of wall time have passed, whichever is first; then `live score`.
4. `report export`, `paper sync`, commit `artifacts/live`, `reports/experiments/live_metrics.csv`,
   `reports/verification`, `paper/tables`, `data/raw/live/*/fetch_log.jsonl`; push; hand back.

## Outcome rule (fixed before the run)

* **OK**: at least one scored target at every horizon (15, 30, 60 min) with `n_published_before_issue = 0`
  violations of the publication check among scored rows (an excluded row is not a violation; a scored row can never
  be one by construction, and the count is reported).
* **PARTIAL**: forecasts issued but some horizon has no scored target when the settle phase ends.
* **NOT_RUN**: no batch could forecast any link (the published history itself holds fewer than 12 of 24 bins).

The result, whatever it is, is reported as a short observational window on one day with a stated data age, never as
a second test set and never as a real-time forecast. The wall-clock protocol remains the one the system would need
for real-time use and remains NOT RUN until the feed's latency allows it.

## Why this is not a relaxation

The lookback requirement, model and scoring are the same; only the anchor of the window moves from the clock to the
feed's own newest bin. The leakage guard becomes stricter rather than looser: a target is scored only with evidence
(the retrieval log) that it was not yet published when the forecast was written. The cost is in interpretation,
stated above and on every artifact: a forecast with a two-hour data age is not a forecast an operator could act on
two hours earlier.
