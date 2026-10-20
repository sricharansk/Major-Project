"""Clean NYC DOT link speeds and aggregate them onto a right-labelled 5-minute grid.

Rules (documented in docs/data_dictionary.md):
* ``data_as_of`` is a floating timestamp published in NYC local time -> converted to UTC; DST-unresolvable
  rows are dropped and counted.
* ``speed`` is in mph (dataset documentation); kept in mph internally.
* speed <= 0 or > 100 mph is treated as an invalid observation (counted, not imputed).
* duplicates on (link_id, data_as_of) keep the first occurrence (counted).
* a grid cell with no valid observation stays NaN ("no observation" is never encoded as zero speed).
"""

from __future__ import annotations

import numpy as np
import polars as pl

from smartcity import settings
from smartcity.preprocessing.raw import read_socrata
from smartcity.preprocessing.timeutil import local_naive_to_utc, right_labelled_bin
from smartcity.utils import sha256_file, write_json

MAX_VALID_MPH = 100.0


def clean_speeds(raw: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    stats: dict = {"raw_rows": raw.height}
    df = raw.with_columns(
        pl.col("speed").cast(pl.Float64, strict=False).alias("speed_mph"),
        pl.col("travel_time").cast(pl.Float64, strict=False).alias("travel_time_s"),
        pl.col("link_id").cast(pl.Utf8),
        *local_naive_to_utc("data_as_of", "ts_utc"),
    )
    stats["tz_unresolved"] = int(df["ts_utc_tz_unresolved"].sum())
    stats["unparseable_time"] = int(df["ts_utc"].is_null().sum()) - stats["tz_unresolved"]
    df = df.filter(pl.col("ts_utc").is_not_null())
    before = df.height
    df = df.unique(subset=["link_id", "data_as_of"], keep="first", maintain_order=True)
    stats["duplicates_removed"] = before - df.height
    stats["speed_null"] = int(df["speed_mph"].is_null().sum())
    stats["speed_zero_or_negative"] = int((df["speed_mph"] <= 0).sum())
    stats["speed_above_max"] = int((df["speed_mph"] > MAX_VALID_MPH).sum())
    df = df.with_columns(
        (pl.col("speed_mph").is_not_null() & (pl.col("speed_mph") > 0) & (pl.col("speed_mph") <= MAX_VALID_MPH))
        .alias("valid")
    )
    stats["valid_rows"] = int(df["valid"].sum())
    stats["links"] = df["link_id"].n_unique()
    stats["ts_min_utc"] = str(df["ts_utc"].min())
    stats["ts_max_utc"] = str(df["ts_utc"].max())
    keep = [c for c in ["link_id", "id", "link_name", "borough", "owner", "data_as_of", "ts_utc", "speed_mph",
                        "travel_time_s", "status", "valid", "_raw_file"] if c in df.columns]
    return df.select(keep).sort(["link_id", "ts_utc"]), stats


def to_grid(clean: pl.DataFrame, minutes: int, link_ids: list[str] | None = None) -> dict:
    v = clean.filter(pl.col("valid")).with_columns(right_labelled_bin("ts_utc", minutes))
    agg = v.group_by(["link_id", "bin_utc"]).agg(
        pl.col("speed_mph").mean().alias("speed"),
        pl.col("travel_time_s").mean().alias("tt"),
        pl.len().alias("n_obs"),
    )
    if link_ids is None:
        link_ids = sorted(agg["link_id"].unique().to_list())
    t0, t1 = agg["bin_utc"].min(), agg["bin_utc"].max()
    times = pl.datetime_range(t0, t1, interval=f"{minutes}m", eager=True, time_zone="UTC")
    T, N = len(times), len(link_ids)
    tindex = {t: i for i, t in enumerate(times.to_list())}
    lindex = {lid: j for j, lid in enumerate(link_ids)}
    speed = np.full((T, N), np.nan, dtype=np.float32)
    tt = np.full((T, N), np.nan, dtype=np.float32)
    nobs = np.zeros((T, N), dtype=np.int16)
    for lid, b, s, t, n in agg.select(["link_id", "bin_utc", "speed", "tt", "n_obs"]).iter_rows():
        j = lindex.get(lid)
        if j is None:
            continue
        i = tindex[b]
        speed[i, j], tt[i, j], nobs[i, j] = s, t, n
    return {
        "times_utc": np.array([t.timestamp() for t in times.to_list()], dtype=np.int64),
        "link_ids": np.array(link_ids),
        "speed": speed,
        "travel_time": tt,
        "n_obs": nobs,
    }


def run() -> dict:
    grid_cfg = settings.load("data")["grid"]
    raw = read_socrata("speeds")
    if raw.is_empty():
        raise SystemExit("NOT_RUN: no raw speed files under data/raw/speeds (run the downloader first)")
    clean, stats = clean_speeds(raw)
    interim = settings.path("interim")
    clean.write_parquet(interim / "speeds_clean.parquet")
    grid = to_grid(clean, grid_cfg["frequency_minutes"])
    out = settings.path("processed") / "speed_grid.npz"
    np.savez_compressed(out, **grid)
    observed = np.isfinite(grid["speed"])
    stats.update(
        grid_steps=int(grid["speed"].shape[0]),
        grid_links=int(grid["speed"].shape[1]),
        grid_observed_fraction=float(observed.mean()),
        grid_file=str(out),
        grid_sha256=sha256_file(out),
        bin_label="right: label t aggregates [t-5min, t)",
        speed_unit="mph",
    )
    write_json(settings.ROOT / "reports" / "data_audit" / "speeds_preprocessing.json", stats)
    return stats
