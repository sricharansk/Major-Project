"""Causal feature tensor, availability masks, multi-horizon targets and chronological split manifest.

Output ``data/processed/features_<track>.npz``:
    X     [T, N, F]  float32  standardised inputs (unavailable -> 0, see mask)
    M     [T, N, G]  bool     feature-group availability
    speed [T, N]     float32  observed right-labelled 5-min mean speed (mph), NaN = no observation
    times_utc [T]    int64
plus ``features_<track>_meta.json`` (feature names, group slices, scaler stats fitted on TRAIN only,
split boundaries, hashes).

Tracks
    operational   : traffic, calendar, weather_forecast, infrastructure(311 with lag)
    retrospective : operational + weather_archive (replaces forecast) + incidents(collisions) + events
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from smartcity import settings
from smartcity.preprocessing import context
from smartcity.utils import read_json, sha256_file, sha256_json, write_json

GROUPS_BY_TRACK = {
    "operational": ["traffic", "calendar", "weather", "infrastructure"],
    "retrospective": ["traffic", "calendar", "weather", "events", "incidents", "infrastructure"],
}


def chronological_splits(T: int, lookback: int, max_h: int, fracs: dict) -> dict:
    """Index boundaries on the time axis and purged origin ranges.

    An origin t belongs to a partition [lo, hi) only if t >= lo and t + max_h < hi, so no target crosses a
    boundary.  Inputs may use earlier history (operationally available).
    """
    a = int(T * fracs["train"])
    b = int(T * (fracs["train"] + fracs["val"]))
    c = int(T * (fracs["train"] + fracs["val"] + fracs["calib"]))
    bounds = {"train": (0, a), "val": (a, b), "calib": (b, c), "test": (c, T)}
    origins = {}
    for k, (lo, hi) in bounds.items():
        start = max(lo, lookback - 1)
        stop = hi - max_h  # exclusive
        origins[k] = (start, max(start, stop))
    return {"bounds": bounds, "origins": origins}


def causal_ffill(a: np.ndarray, max_steps: int) -> tuple[np.ndarray, np.ndarray]:
    """Forward-fill NaNs along axis 0 for at most ``max_steps``; also return age (steps since last obs)."""
    T, N = a.shape
    out = a.copy()
    age = np.full((T, N), np.inf, dtype=np.float32)
    last = np.full(N, np.nan, dtype=np.float32)
    last_t = np.full(N, -10**9)
    for t in range(T):
        obs = np.isfinite(a[t])
        last[obs] = a[t, obs]
        last_t[obs] = t
        gap = t - last_t
        age[t] = np.where(last_t >= 0, gap, np.inf)
        fill = ~obs & (gap <= max_steps) & (last_t >= 0)
        out[t, fill] = last[fill]
    return out, age


def causal_rolling_mean(a: np.ndarray, w: int) -> np.ndarray:
    """Mean of observed values in the trailing window [t-w+1, t] (NaN-aware, uses only past)."""
    v = np.nan_to_num(a, nan=0.0)
    m = np.isfinite(a).astype(np.float32)
    cv = np.cumsum(v, axis=0)
    cm = np.cumsum(m, axis=0)
    cv = np.concatenate([np.zeros((1, a.shape[1])), cv])
    cm = np.concatenate([np.zeros((1, a.shape[1])), cm])
    idx = np.arange(a.shape[0]) + 1
    lo = np.maximum(idx - w, 0)
    s = cv[idx] - cv[lo]
    n = cm[idx] - cm[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, s / np.maximum(n, 1), np.nan).astype(np.float32)


def calendar_features(times_utc: np.ndarray) -> tuple[np.ndarray, list[str]]:
    ts = pd.to_datetime(times_utc, unit="s", utc=True).tz_convert("America/New_York")
    hours = ts.hour + ts.minute / 60.0
    dow = ts.dayofweek
    cal = USFederalHolidayCalendar()
    hol = cal.holidays(start=ts.min().date() - dt.timedelta(days=1), end=ts.max().date() + dt.timedelta(days=1))
    is_hol = pd.Index(ts.normalize().tz_localize(None)).isin(hol)
    f = np.stack([
        np.sin(2 * np.pi * hours / 24), np.cos(2 * np.pi * hours / 24),
        np.sin(2 * np.pi * dow / 7), np.cos(2 * np.pi * dow / 7),
        (dow >= 5).astype(float), is_hol.astype(float),
    ], axis=1).astype(np.float32)
    return f, ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "weekend", "us_federal_holiday"]


def build(track: str = "operational", link_ids: list[str] | None = None) -> dict:
    dcfg = settings.load("data")
    gcfg = dcfg["grid"]
    proc = settings.path("processed")
    grid = np.load(proc / "speed_grid.npz", allow_pickle=False)
    graph = read_json(proc / "graph.json")
    geoms = read_json(proc / "link_geometries.json")
    gl = list(graph["link_ids"])
    col = {lid: j for j, lid in enumerate(grid["link_ids"].tolist())}
    keep = [lid for lid in gl if lid in col]
    if link_ids is not None:
        keep = [lid for lid in keep if lid in set(link_ids)]
    times = grid["times_utc"]
    T = len(times)
    L, hsteps = gcfg["lookback_steps"], gcfg["horizon_steps"]
    splits = chronological_splits(T, L, max(hsteps), dcfg["splits"])
    a = splits["bounds"]["train"][1]
    # link eligibility uses TRAIN-period coverage only (no peeking at later partitions)
    cov = {lid: float(np.isfinite(grid["speed"][:a, col[lid]]).mean()) for lid in keep}
    dropped = {lid: c for lid, c in cov.items() if c < dcfg["study"]["min_link_coverage"]}
    keep = [lid for lid in keep if lid not in dropped]
    speed = grid["speed"][:, [col[lid] for lid in keep]]
    N = speed.shape[1]

    # ---- traffic group --------------------------------------------------------------------------
    filled, age = causal_ffill(speed, gcfg["max_ffill_steps"])
    roll = causal_rolling_mean(speed, 12)
    delta = filled - np.vstack([np.full((1, N), np.nan), filled[:-1]])
    mu = np.nanmean(speed[:a], axis=0)  # per-link TRAIN mean
    sd = np.nanstd(speed[:a], axis=0) + 1e-3
    traffic_ok = np.isfinite(filled)
    z = lambda x: (x - mu) / sd  # noqa: E731
    traffic = np.stack([
        np.nan_to_num(z(filled)), traffic_ok.astype(np.float32),
        np.minimum(np.where(np.isfinite(age), age, 288), 288) / 288.0,
        np.nan_to_num(z(roll)), np.nan_to_num(delta / sd),
    ], axis=-1)
    tnames = ["speed_z", "speed_observed_or_ffilled", "obs_age_days_frac", "rollmean_1h_z", "delta_5m_z"]

    # ---- calendar ---------------------------------------------------------------------------------
    calf, cnames = calendar_features(times)
    calendar = np.repeat(calf[:, None, :], N, axis=1)

    # ---- weather ----------------------------------------------------------------------------------
    wkind = "historical_forecast" if track == "operational" else "archive"
    wv, wavail, wnames = context.weather_on_grid(times, wkind)
    wmu = np.nanmean(wv[:a], axis=0)
    wsd = np.nanstd(wv[:a], axis=0) + 1e-6
    wz = np.nan_to_num((wv - wmu) / wsd)
    weather = np.repeat(wz[:, None, :], N, axis=1)
    wnames = [f"{wkind}_{n}" for n in wnames]

    mids = context.link_midpoints([{"link_id": lid} for lid in keep], geoms)
    groups = {"traffic": (traffic, tnames, traffic_ok), "calendar": (calendar, cnames, np.ones((T, N), bool)),
              "weather": (weather, wnames, np.repeat(wavail[:, None], N, axis=1))}
    ctx_info = {"weather_kind": wkind, "weather_available_fraction": float(wavail.mean())}

    sr, sr_av, sr_info = context.sr311_on_grid(times, mids)
    sr_scale = float(np.nanmax(sr[:a])) if np.nanmax(sr[:a]) > 0 else 1.0
    groups["infrastructure"] = (np.log1p(sr)[..., None] / np.log1p(sr_scale), ["sr311_24h_lagged_log"],
                                np.repeat(sr_av[:, None], N, axis=1))
    ctx_info["sr311"] = sr_info
    if track == "retrospective":
        col_c, col_av, col_info = context.collisions_on_grid(times, mids)
        groups["incidents"] = (np.minimum(col_c, 5)[..., None] / 5.0, ["collisions_500m_60m"],
                               np.repeat(col_av[:, None], N, axis=1))
        ev, ev_av, ev_info = context.events_on_grid(times, N)
        ev_scale = max(float(ev[:a].max()), 1.0)
        groups["events"] = (ev[..., None] / ev_scale, ["borough_events_active_next_60m"],
                            np.repeat(ev_av[:, None], N, axis=1))
        ctx_info.update(collisions=col_info, events=ev_info)

    order = GROUPS_BY_TRACK[track]
    blocks, names, slices, masks = [], [], {}, []
    k = 0
    for g in order:
        arr, nm, av = groups[g]
        arr = np.where(av[..., None], arr, 0.0).astype(np.float32)
        blocks.append(arr)
        names += nm
        slices[g] = [k, k + len(nm)]
        k += len(nm)
        masks.append(av)
    X = np.concatenate(blocks, axis=-1).astype(np.float32)
    M = np.stack(masks, axis=-1)

    out = proc / f"features_{track}.npz"
    np.savez_compressed(out, X=X, M=M, speed=speed.astype(np.float32), times_utc=times)
    schema = {"track": track, "feature_names": names, "groups": order, "group_slices": slices,
              "speed_unit": "mph", "lookback_steps": L, "horizon_steps": hsteps,
              "horizon_minutes": gcfg["horizon_minutes"], "frequency_minutes": gcfg["frequency_minutes"]}
    meta = {
        **schema,
        "feature_schema_hash": sha256_json(schema)[:16],
        "link_ids": keep, "graph_hash": graph["graph_hash"],
        "links_dropped_low_train_coverage": dropped, "train_coverage": cov,
        "splits": splits,
        "split_times_utc": {k2: [str(dt.datetime.fromtimestamp(int(times[lo]), dt.timezone.utc)),
                                 str(dt.datetime.fromtimestamp(int(times[hi - 1]), dt.timezone.utc))]
                            for k2, (lo, hi) in splits["bounds"].items()},
        "scaler": {"speed_mean_train": mu.tolist(), "speed_std_train": sd.tolist(), "fit_rows": [0, a],
                   "weather_mean_train": wmu.tolist(), "weather_std_train": wsd.tolist()},
        "context": ctx_info,
        "group_available_fraction": {g: float(M[..., i].mean()) for i, g in enumerate(order)},
        "file": str(out), "sha256": sha256_file(out),
    }
    write_json(proc / f"features_{track}_meta.json", meta)
    write_json(proc / f"split_manifest_{track}.json",
               {"splits": splits, "split_times_utc": meta["split_times_utc"], "features_sha256": meta["sha256"],
                "rule": "origin t in [lo,hi) iff t>=lo and t+max_h<hi (purged)"})
    return meta


def load(track: str = "operational") -> tuple[dict, dict]:
    proc = settings.path("processed")
    d = np.load(proc / f"features_{track}.npz", allow_pickle=False)
    meta = read_json(proc / f"features_{track}_meta.json")
    return {k: d[k] for k in d.files}, meta
