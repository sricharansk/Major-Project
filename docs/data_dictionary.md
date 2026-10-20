# Data dictionary

## Speed target (NYC DOT Traffic Speeds, i4gi-tjb9)
| field | meaning / handling |
|---|---|
| `link_id` | node identifier (directed DOT link) |
| `data_as_of` | floating NYC-local timestamp -> interpreted as America/New_York -> UTC (`ts_utc`); DST-ambiguous / non-existent local times dropped and counted |
| `speed` | mph (dataset documentation); kept in mph; <=0 or >100 treated as invalid (counted, never imputed as a label) |
| `travel_time` | seconds; derived from the same source as speed, not an independent sensor |
| `link_points` | space-separated `lat,lon` polyline in travel direction; truncated pairs dropped; fallback `encoded_poly_line` |

Grid: 5-minute bins, right-labelled (label t aggregates observations in [t-5 min, t)); a forecast at origin t uses
bins <= t only. Empty bins stay NaN ("no observation" is not zero speed). `n_obs` per bin is stored.

## Feature groups (features/build.py)
| group | features | availability |
|---|---|---|
| traffic | speed z-score (causal ffill <= 3 steps), observed flag, observation age, 1-h rolling mean, 5-min delta | observed or ffilled |
| calendar | hour/day-of-week sin/cos, weekend, US federal holiday (rule-based calendar) | always |
| weather | precip, rain, snow, temp, wind, wet weather-code flag, visibility, cloud (operational: archived forecasts; retrospective: reanalysis) | hour present |
| infrastructure | 311 requests (selected complaint types) within 500 m in the 24 h ending 24 h before t (declared lag) | after first lagged window |
| incidents (retrospective) | collisions within 500 m in the last 60 min | collision table coverage |
| events (retrospective) | borough-level count of permitted events active in [t, t+60 min] | event table coverage |

Targets: observed speed at t+15/30/60 min; missing targets are masked, never imputed.
Congestion categories (project-defined): ratio to training-period link mean >= 0.8 free, 0.5-0.8 moderate, < 0.5 congested.
