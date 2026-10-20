# Availability and leakage audit

What each source can legitimately contribute at prediction time, and how the code enforces it. Row counts and
coverage percentages are produced by `data preprocess` (`data/processed/coverage_*.csv`) and are not repeated here
by hand.

| Source | Observation time known? | Available at prediction time? | Operational track | Retrospective track | Enforcement |
|---|---|---|---|---|---|
| DOT speeds (i4gi-tjb9) | yes (`data_as_of`, NYC local, converted to UTC) | yes, with feed latency | lags up to origin only | same | right-labelled 5-min bins; causal ffill <= 3 steps; purge gaps between splits (`tests/leakage`) |
| Open-Meteo archive | yes (hourly UTC) | **no** (archive is finalised later) | excluded | used | `weather_kind` recorded per track in the feature meta |
| Open-Meteo historical forecast | yes | yes (proxy for the forecast issued at the time) | used | excluded | `features/build.py` selects `historical_forecast` for the operational track |
| 311 (erm2-nwe9) | `created_date` yes | partially (publication lag) | 24 h declared lag | 24 h lag | lag applied in `features/build.py` |
| Collisions (h9gi-nx95) | `crash_date`/`crash_time` yes | **no** (approx. 4-month publication lag) | excluded | included | track allowlist in `configs/data.yaml` |
| Permitted events, current (tvpp-9vvx) | start/end yes | yes for future scheduled events | not used for history | | current feed does not reconstruct the past |
| Permitted events, historical (bkfu-528j) | start/end yes; announcement time unknown | unknown | excluded | included | |
| ATR volume (7ym2-wayt) | yes | sampled, sparse | not a feature | not a feature | SUMO demand only |
| OSM (Overpass) | snapshot | static | geometry only | | |

## Leakage checks (automated)

`tests/leakage/test_leakage.py`: no training target crosses a partition boundary; features at origin t do not change
when future records change; missing labels are not imputed; windowed counts use only past records; the 311 lag
shifts availability; the operational track contains neither incidents nor events (and uses forecast weather).

## Timestamp handling

Socrata timestamps are floating local; conversion uses `America/New_York` with `ambiguous=NaT` and
`nonexistent=NaT`, so the DST transitions produce nulls rather than guesses. Weather is already UTC.
