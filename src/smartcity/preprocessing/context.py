"""Contextual sources aligned to the 5-minute grid, with explicit availability semantics.

Availability policy (see docs/methodology.md, "Operational availability"):

=================  =============================================  =====================
Source             Value used at forecast origin t                Track
=================  =============================================  =====================
weather_forecast   archived forecast for the hour containing t     operational (proxy)
weather_archive    reanalysis for the hour ending at/before t      retrospective only
collisions         crashes with crash time in (t-60min, t]          retrospective only
311 requests       requests created in (t-24h-lag, t-lag]           operational w/ lag
permitted events   events scheduled to be active during [t, t+60]   see events audit
=================  =============================================  =====================
"""

from __future__ import annotations

import datetime as dt
import json

import numpy as np
import polars as pl

from smartcity import settings
from smartcity.preprocessing.raw import raw_dir, read_json_gz, read_socrata
from smartcity.preprocessing.timeutil import local_naive_to_utc

WEATHER_VARS = ["temperature_2m", "precipitation", "rain", "snowfall", "weather_code", "wind_speed_10m",
                "visibility", "cloud_cover"]


def load_weather(kind: str, files: list | None = None) -> pl.DataFrame | None:
    """Hourly Open-Meteo frame from the archived raw responses of ``kind`` (or from explicit ``files``, which LIVE
    mode uses for the forecast it just retrieved; the response layout is the same)."""
    files = sorted(raw_dir("weather").glob(f"{kind}_*.json.gz")) if files is None else list(files)
    if not files:
        return None
    frames = []
    for f in files:
        js = read_json_gz(f)
        h = js.get("hourly") or {}
        if not h.get("time"):
            continue
        df = pl.DataFrame({k: h.get(k, [None] * len(h["time"])) for k in ["time", *WEATHER_VARS]}, strict=False)
        frames.append(df)
    if not frames:
        return None
    df = pl.concat(frames, how="diagonal_relaxed").unique("time", keep="last")
    return df.with_columns(
        pl.col("time").str.strptime(pl.Datetime("us"), "%Y-%m-%dT%H:%M").dt.replace_time_zone("UTC").alias("hour_utc")
    ).sort("hour_utc")


def weather_on_grid(times_utc: np.ndarray, kind: str, df: pl.DataFrame | None = None,
                    ) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Return values [T, V] and availability [T].

    Open-Meteo hourly precipitation is the sum over the *preceding* hour, labelled at the hour end, so at
    origin t the latest completed hour is floor(t, 1h).  For the archived forecast, the value for the hour
    containing t is used (issue time is not exposed by the API -> disclosed limitation).  ``df`` overrides the
    archived files (LIVE mode passes the forecast it just retrieved, aligned the same way).
    """
    df = load_weather(kind) if df is None else df
    names = ["precip_mm", "rain_mm", "snow_cm", "temp_c", "wind_kmh", "wet_code", "visibility_km", "cloud_pct"]
    T = len(times_utc)
    if df is None or df.is_empty():
        return np.full((T, len(names)), np.nan, np.float32), np.zeros(T, bool), names
    hours = np.array([int(t.timestamp()) for t in df["hour_utc"].to_list()], dtype=np.int64)
    if kind == "archive":
        key = (times_utc // 3600) * 3600  # hour ending at/before t
    else:
        key = (times_utc // 3600) * 3600 + 3600  # hour containing t (forecast for hour ending t_ceil)
    idx = np.searchsorted(hours, key)
    ok = (idx < len(hours)) & (hours[np.minimum(idx, len(hours) - 1)] == key)
    idx = np.minimum(idx, len(hours) - 1)

    def col(name):
        return np.array(df[name].cast(pl.Float64, strict=False).fill_null(np.nan).to_list(), dtype=np.float64)

    code = col("weather_code")
    vals = np.stack([
        col("precipitation"), col("rain"), col("snowfall"), col("temperature_2m"), col("wind_speed_10m"),
        (code >= 51).astype(float) * np.where(np.isnan(code), np.nan, 1.0),  # WMO 51+ = drizzle/rain/snow
        col("visibility") / 1000.0, col("cloud_cover"),
    ], axis=1)[idx]
    vals[~ok] = np.nan
    avail = ok & ~np.isnan(vals[:, 0])
    return vals.astype(np.float32), avail, names


def _points_near(link_mid: np.ndarray, lat: np.ndarray, lon: np.ndarray, radius_m: float) -> np.ndarray:
    """Boolean [N, M]: record m within radius of link midpoint n (equirectangular approx, fine at city scale)."""
    k = 111320.0
    dy = (lat[None, :] - link_mid[:, 0:1]) * k
    dx = (lon[None, :] - link_mid[:, 1:2]) * k * np.cos(np.radians(40.75))
    return (dx * dx + dy * dy) <= radius_m**2


def _windowed_counts(times_utc, link_mid, ev_t, ev_lat, ev_lon, radius, lo_s, hi_s):
    """counts[T, N] of records with time in (t - lo_s, t - hi_s] near each link."""
    T, N = len(times_utc), len(link_mid)
    out = np.zeros((T, N), np.float32)
    if len(ev_t) == 0:
        return out
    order = np.argsort(ev_t)
    ev_t, ev_lat, ev_lon = ev_t[order], ev_lat[order], ev_lon[order]
    near = _points_near(link_mid, ev_lat, ev_lon, radius)  # [N, M]
    a = np.searchsorted(ev_t, times_utc - lo_s, side="right")
    b = np.searchsorted(ev_t, times_utc - hi_s, side="right")
    cum = np.concatenate([np.zeros((N, 1)), np.cumsum(near, axis=1)], axis=1)  # [N, M+1]
    out[:] = (cum[:, b] - cum[:, a]).T
    return out


def collisions_on_grid(times_utc, link_mid) -> tuple[np.ndarray, np.ndarray, dict]:
    cfg = settings.load("data")["context"]
    raw = read_socrata("collisions")
    if raw.is_empty():
        return np.zeros((len(times_utc), len(link_mid)), np.float32), np.zeros(len(times_utc), bool), {"rows": 0}
    df = raw.with_columns(
        (pl.col("crash_date").str.slice(0, 10) + "T" + pl.col("crash_time").str.zfill(5)).alias("crash_local"),
        pl.col("latitude").cast(pl.Float64, strict=False), pl.col("longitude").cast(pl.Float64, strict=False),
    ).with_columns(*local_naive_to_utc("crash_local", "crash_utc"))
    df = df.unique("collision_id")
    geo = df.filter(pl.col("latitude").is_between(40.4, 41.0) & pl.col("longitude").is_between(-74.3, -73.6)
                    & pl.col("crash_utc").is_not_null())
    t = np.array([int(x.timestamp()) for x in geo["crash_utc"].to_list()], dtype=np.int64)
    counts = _windowed_counts(times_utc, link_mid, t, geo["latitude"].to_numpy(), geo["longitude"].to_numpy(),
                              cfg["collision_radius_m"], 3600, 0)
    tmin, tmax = (t.min(), t.max()) if len(t) else (0, 0)
    avail = (times_utc >= tmin) & (times_utc <= tmax + 86400)
    return counts, avail, {"rows": df.height, "geocoded": geo.height}


def sr311_on_grid(times_utc, link_mid, raw: pl.DataFrame | None = None) -> tuple[np.ndarray, np.ndarray, dict]:
    """Lagged 24 h count of road-related 311 requests within the configured radius of each link midpoint.

    ``raw`` overrides the archived download (LIVE mode passes the records it just retrieved); the lag, window and
    radius come from the data config either way.
    """
    cfg = settings.load("data")["context"]
    raw = read_socrata("sr311") if raw is None else raw
    T, N = len(times_utc), len(link_mid)
    if raw.is_empty():
        return np.zeros((T, N), np.float32), np.zeros(T, bool), {"rows": 0}
    df = raw.unique("unique_key").with_columns(
        *local_naive_to_utc("created_date", "created_utc"),
        pl.col("latitude").cast(pl.Float64, strict=False), pl.col("longitude").cast(pl.Float64, strict=False),
    )
    geo = df.filter(pl.col("latitude").is_between(40.4, 41.0) & pl.col("created_utc").is_not_null())
    t = np.array([int(x.timestamp()) for x in geo["created_utc"].to_list()], dtype=np.int64)
    lag = int(cfg.get("sr311_publication_lag_hours", 24)) * 3600
    win = cfg["sr311_window_hours"] * 3600
    counts = _windowed_counts(times_utc, link_mid, t, geo["latitude"].to_numpy(), geo["longitude"].to_numpy(),
                              cfg["sr311_radius_m"], lag + win, lag)
    tmin = t.min() if len(t) else 0
    avail = times_utc >= tmin + lag + win
    return counts, avail, {"rows": df.height, "geocoded": geo.height, "assumed_publication_lag_h": lag // 3600}


def events_on_grid(times_utc, n_nodes) -> tuple[np.ndarray, np.ndarray, dict]:
    """Borough-level count of permitted events scheduled to be active within [t, t+60min].

    Permitted-event records carry free-text locations only (no coordinates), so the feature is borough-level
    and identical for all links; this coarseness is a disclosed limitation.  Historical availability of a
    permit *before* t cannot be reconstructed from the public tables; the feature is therefore placed in the
    retrospective track unless the audit establishes otherwise.
    """
    T = len(times_utc)
    frames = [read_socrata(s) for s in ("events_hist", "events")]
    frames = [f for f in frames if not f.is_empty()]
    if not frames:
        return np.zeros((T, n_nodes), np.float32), np.zeros(T, bool), {"rows": 0}
    df = pl.concat(frames, how="diagonal_relaxed")
    key = "event_id" if "event_id" in df.columns else df.columns[0]
    df = df.unique(key).with_columns(*local_naive_to_utc("start_date_time", "start_utc"),
                                     *local_naive_to_utc("end_date_time", "end_utc"))
    df = df.filter(pl.col("start_utc").is_not_null() & pl.col("end_utc").is_not_null())
    s = np.array([int(x.timestamp()) for x in df["start_utc"].to_list()], dtype=np.int64)
    e = np.array([int(x.timestamp()) for x in df["end_utc"].to_list()], dtype=np.int64)
    # active in [t, t+3600]: start <= t+3600 and end >= t
    s_sorted, e_sorted = np.sort(s), np.sort(e)
    started = np.searchsorted(s_sorted, times_utc + 3600, side="right")
    ended = np.searchsorted(e_sorted, times_utc, side="left")
    active = (started - ended).astype(np.float32)
    avail = (times_utc >= s.min()) & (times_utc <= s.max()) if len(s) else np.zeros(T, bool)
    return np.repeat(active[:, None], n_nodes, axis=1), avail, {"rows": df.height,
                                                               "min_start": str(dt.datetime.fromtimestamp(s.min(), dt.timezone.utc)) if len(s) else None}


def link_midpoints(graph_nodes: list[dict], geoms: dict) -> np.ndarray:
    mids = []
    for n in graph_nodes:
        pts = geoms[n["link_id"]]
        mids.append(pts[len(pts) // 2])
    return np.array(mids, dtype=np.float64)


def summary_json(d: dict) -> str:
    return json.dumps(d, default=str)
