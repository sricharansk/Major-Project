"""LIVE observational mode.

The REPLAY evaluation scores the frozen model on a held-out historical partition.  This module exercises the same
model on data that did not exist when it was trained:

    pull      the newest records of the modelled links from the public speed feed (plus the current Open-Meteo
              forecast and the last two days of road-related 311 requests), stored verbatim with provenance under
              data/raw/live/<source>/ exactly like the training downloads;
    forecast  the last ``window_steps`` five-minute bins are rebuilt with the TRAIN-fitted transforms (the very
              functions the offline feature build uses), the frozen model is run once, conformal intervals are
              attached, and the forecast is written to artifacts/live/forecasts/ **before** any target time;
    score     stored forecasts whose target bin has since been observed are matched to the observation; forecasts
              generated after their target (should never happen) are excluded as LATE, unobserved targets stay
              PENDING; metrics go to reports/experiments/live_metrics.csv and artifacts/live/live_summary.json.

Every record carries ``mode = LIVE`` and the retrieval time of its sources.  Nothing here touches a traffic signal,
and nothing here changes the REPLAY artifacts.

Origin modes (``live.origin_mode`` in configs/data.yaml, or ``--origin`` on the CLI):

    wall_clock        the origin is the latest complete five-minute bin of the wall clock.  A link is forecast only
                      when its lookback holds enough observations, so a publication lag of the feed larger than about
                      an hour withholds every link (observed on 2026-10-28 and 2026-10-29, 1.7-4.3 h behind).
    latest_available  preregistered on 2026-10-29 (docs/live_latest_available_protocol.md) after those two attempts:
                      the origin is the newest bin for which the feed has published a valid observation of any
                      modelled link, so the forecast concerns the bins the feed has *not yet published*.  The same
                      lookback rule, scaler, model, intervals and gate apply; the data age of the origin is recorded
                      on every batch and link.  Scoring then requires, per target, that the target bin was first
                      retrieved *after* the forecast was written (``first_seen``); a target already published at
                      issue time is excluded as PUBLISHED_BEFORE_ISSUE.  In wall-clock terms some targets of such a
                      forecast may already lie in the past; that count is reported, never hidden.
"""

from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import math
import time
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from smartcity import settings
from smartcity.features import build as fb
from smartcity.preprocessing import context
from smartcity.preprocessing.speeds import clean_speeds, to_grid
from smartcity.utils import read_json, utcnow, write_json

ROOT = settings.ROOT
ART = ROOT / "artifacts" / "live"
FORECASTS = ART / "forecasts"
EXP = ROOT / "reports" / "experiments"
NYC = ZoneInfo("America/New_York")
STEP_S = 300
MODE = "LIVE"
ORIGIN_MODES = ("wall_clock", "latest_available")


def _cfg() -> dict:
    return settings.load("data").get("live", {})


def raw_live(source: str) -> Path:
    p = settings.path("raw") / "live" / source
    p.mkdir(parents=True, exist_ok=True)
    return p


def _rel(p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(p)


def floor_origin(now: dt.datetime) -> dt.datetime:
    """Latest complete right-labelled bin: label t aggregates observations in [t - 5 min, t)."""
    ts = int(now.timestamp()) // STEP_S * STEP_S
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc)


def latest_available_origin(grid: dict | None, link_ids: list[str]) -> dt.datetime | None:
    """Label of the newest right-labelled bin in which any of ``link_ids`` has a valid published observation."""
    if grid is None:
        return None
    lidx = [j for j, lid in enumerate(grid["link_ids"].tolist()) if lid in set(link_ids)]
    if not lidx:
        return None
    sp = np.asarray(grid["speed"])[:, lidx]
    rows = np.where(np.isfinite(sp).any(axis=1))[0]
    if rows.size == 0:
        return None
    return dt.datetime.fromtimestamp(int(grid["times_utc"][rows[-1]]), dt.timezone.utc)


def _stamp(f: Path) -> dt.datetime | None:
    try:
        return dt.datetime.strptime(Path(f).name.split(".")[0].split("_")[-1], "%Y%m%dT%H%M%SZ").replace(
            tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def first_seen_map(link_ids: list[str], files: list[Path] | None = None) -> dict:
    """``{(link_id, bin_ts): retrieval time}``: the pull in which each (link, bin) first carried a valid observation.

    The pull files are named after their retrieval time, so this is the publication-side timestamp the scoring uses
    to prove that a target was not yet available when its forecast was written."""
    files = sorted(raw_live("speeds").glob("speeds_*.json.gz")) if files is None else sorted(files)
    seen: dict = {}
    for f in files:
        stamp = _stamp(f)
        if stamp is None:
            continue
        g, _ = live_grid(link_ids, [f])
        if g is None:
            continue
        sp = np.asarray(g["speed"])
        lids = g["link_ids"].tolist()
        for i, t in enumerate(g["times_utc"].tolist()):
            for j, lid in enumerate(lids):
                if np.isfinite(sp[i, j]) and (lid, int(t)) not in seen:
                    seen[(lid, int(t))] = stamp
    return seen


def _local_naive(t: dt.datetime) -> str:
    return t.astimezone(NYC).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S")


def _parse(s: str) -> dt.datetime:
    d = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


# ------------------------------------------------------------------------------------------------------------------
# pull
# ------------------------------------------------------------------------------------------------------------------

def pull(link_ids: list[str], now: dt.datetime | None = None, weather: bool = True, sr311: bool = True) -> dict:
    """Retrieve the newest records; every response is stored verbatim with a fetch-log line (provenance)."""
    from smartcity.ingestion import fetch

    fetch.RAW = settings.path("raw")  # data/raw/live/<source>/ regardless of the working directory
    cfg = _cfg()
    now = now or utcnow()
    tag = now.strftime("%Y%m%dT%H%M%SZ")
    out: dict = {"retrieved_at_utc": now.isoformat(), "files": {}, "errors": {}}

    start = now - dt.timedelta(hours=float(cfg.get("history_hours", 4.0)))
    ids = ", ".join(f"'{i}'" for i in link_ids)
    where = f"data_as_of >= '{_local_naive(start)}' AND link_id in ({ids})"
    params = {"$select": "id, speed, travel_time, status, data_as_of, link_id, borough, link_name, owner",
              "$where": where, "$order": "data_as_of, id", "$limit": fetch.PAGE}
    status, body, url = fetch.http_get(f"{fetch.SOCRATA}/resource/{fetch.DATASETS['speeds']}.json", params)
    rows = json.loads(body)
    if not isinstance(rows, list):
        raise RuntimeError(f"unexpected speed-feed response: {str(rows)[:300]}")
    p = fetch.store("live/speeds", f"speeds_{tag}", url, params, status, body, len(rows))
    out["files"]["speeds"] = _rel(p)
    out["speeds_rows"] = len(rows)
    out["speeds_latest_data_as_of_local"] = max((r.get("data_as_of") or "" for r in rows), default=None)

    if weather:
        pt = cfg.get("weather_point", {"lat": 40.7549, "lon": -73.9840})
        wp = {"latitude": pt["lat"], "longitude": pt["lon"], "hourly": ",".join(context.WEATHER_VARS),
              "timezone": "UTC", "past_days": 1, "forecast_days": 1}
        try:
            st, wb, wurl = fetch.http_get("https://api.open-meteo.com/v1/forecast", wp, timeout=120)
            p = fetch.store("live/weather", f"forecast_{tag}", wurl, wp, st, wb, None)
            out["files"]["weather"] = _rel(p)
        except Exception as exc:  # the forecast still runs with the weather group marked unavailable
            out["errors"]["weather"] = f"{type(exc).__name__}: {exc}"[:300]

    if sr311:
        ctx = settings.load("data")["context"]
        hours = int(ctx.get("sr311_publication_lag_hours", 24)) + int(ctx["sr311_window_hours"]) + 1
        types = ", ".join(f"'{t}'" for t in fetch.SR311_TYPES)
        sp = {"$select": "unique_key, created_date, complaint_type, borough, latitude, longitude",
              "$where": f"created_date >= '{_local_naive(now - dt.timedelta(hours=hours))}' "
                        f"AND complaint_type in ({types}) AND borough = 'MANHATTAN'",
              "$order": "unique_key", "$limit": fetch.PAGE}
        try:
            st, sb, surl = fetch.http_get(f"{fetch.SOCRATA}/resource/{fetch.DATASETS['sr311']}.json", sp)
            srows = json.loads(sb)
            p = fetch.store("live/sr311", f"sr311_{tag}", surl, sp, st, sb, len(srows) if isinstance(srows, list) else None)
            out["files"]["sr311"] = _rel(p)
            out["sr311_rows"] = len(srows) if isinstance(srows, list) else None
        except Exception as exc:
            out["errors"]["sr311"] = f"{type(exc).__name__}: {exc}"[:300]

    write_json(ART / "last_pull.json", out)
    return out


# ------------------------------------------------------------------------------------------------------------------
# raw live records -> grid
# ------------------------------------------------------------------------------------------------------------------

def _read_rows(files: list[Path]) -> pl.DataFrame:
    frames = []
    for f in files:
        with gzip.open(f, "rb") as fh:
            rows = json.loads(fh.read())
        if rows:
            df = pl.DataFrame(rows, infer_schema_length=None).with_columns(pl.all().cast(pl.Utf8))
            frames.append(df.with_columns(pl.lit(Path(f).name).alias("_raw_file")))
    return pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame()


def merge_live_speeds(files: list[Path]) -> tuple[pl.DataFrame, dict]:
    """Concatenate live speed pulls, detect repeated and revised records, then apply the training cleaning rules.

    Consecutive pulls overlap on purpose.  A (link_id, data_as_of) pair seen more than once is a *repeat*; a repeat
    whose speed differs between pulls is a *revision*.  Both are counted; the first occurrence is kept, which is the
    rule the offline preprocessing applies (``clean_speeds``).
    """
    raw = _read_rows(files)
    if raw.is_empty():
        return raw, {"files": len(files), "rows": 0, "repeated_records": 0, "revised_records": 0}
    g = raw.group_by(["link_id", "data_as_of"]).agg(pl.len().alias("n"), pl.col("speed").n_unique().alias("nu"))
    stats = {"files": len(files), "rows": raw.height, "unique_records": g.height,
             "repeated_records": int((g["n"] > 1).sum()), "revised_records": int((g["nu"] > 1).sum())}
    clean, cstats = clean_speeds(raw)
    stats.update({k: cstats[k] for k in ("valid_rows", "speed_zero_or_negative", "speed_above_max", "tz_unresolved",
                                         "duplicates_removed") if k in cstats})
    stats["latest_observation_utc"] = cstats.get("ts_max_utc")
    return clean, stats


def live_grid(link_ids: list[str], files: list[Path] | None = None) -> tuple[dict | None, dict]:
    """Right-labelled 5-minute grid of every live speed pull (or of ``files``) for the modelled links."""
    files = sorted(raw_live("speeds").glob("speeds_*.json.gz")) if files is None else files
    clean, stats = merge_live_speeds(files)
    if clean.is_empty() or int(clean["valid"].sum()) == 0:
        return None, stats
    return to_grid(clean, STEP_S // 60, list(link_ids)), stats


def place_on_axis(grid: dict | None, times: np.ndarray, link_ids: list[str]) -> np.ndarray:
    """Speeds of ``link_ids`` on the requested time axis (NaN where no observation)."""
    out = np.full((len(times), len(link_ids)), np.nan, dtype=np.float32)
    if grid is None:
        return out
    tidx = {int(t): i for i, t in enumerate(grid["times_utc"].tolist())}
    lidx = {lid: j for j, lid in enumerate(grid["link_ids"].tolist())}
    for i, t in enumerate(times.tolist()):
        r = tidx.get(int(t))
        if r is None:
            continue
        for j, lid in enumerate(link_ids):
            c = lidx.get(lid)
            if c is not None:
                out[i, j] = grid["speed"][r, c]
    return out


# ------------------------------------------------------------------------------------------------------------------
# features for one origin
# ------------------------------------------------------------------------------------------------------------------

def live_features(speed: np.ndarray, times: np.ndarray, meta: dict, weather_df: pl.DataFrame | None,
                  sr311_raw: pl.DataFrame | None, link_mid: np.ndarray | None, sr311_scale: float | None,
                  max_ffill_steps: int) -> tuple[np.ndarray, np.ndarray, dict]:
    """Feature tensor for the live window with the stored TRAIN scaler.  Same block functions as the offline build.

    Returns X [T, N, F], M [T, N, G] and a small availability report.  Raises when the assembled feature names differ
    from the frozen model's schema (a schema mismatch must never be forecast through silently).
    """
    N = speed.shape[1]
    sc = meta["scaler"]
    mu = np.array(sc["speed_mean_train"], dtype=np.float32)
    sd = np.array(sc["speed_std_train"], dtype=np.float32)
    traffic, traffic_ok, tnames = fb.traffic_block(speed, mu, sd, max_ffill_steps)
    calf, cnames = fb.calendar_features(times)
    calendar = np.repeat(calf[:, None, :], N, axis=1)
    wkind = meta.get("context", {}).get("weather_kind", "historical_forecast")
    wv, wav, wnames = context.weather_on_grid(times, wkind, df=weather_df if weather_df is not None else pl.DataFrame())
    weather, wnames = fb.weather_block(wv, np.array(sc["weather_mean_train"], dtype=np.float32),
                                       np.array(sc["weather_std_train"], dtype=np.float32), N, wkind, wnames)
    groups = {"traffic": (traffic, tnames, traffic_ok), "calendar": (calendar, cnames, np.ones((len(times), N), bool)),
              "weather": (weather, wnames, np.repeat(wav[:, None], N, axis=1))}
    report = {"weather_available": bool(wav[-1]), "sr311_available": False}
    if "infrastructure" in meta["groups"]:
        if sr311_raw is not None and not sr311_raw.is_empty() and link_mid is not None and sr311_scale:
            sr, sr_av, _ = context.sr311_on_grid(times, link_mid, raw=sr311_raw)
        else:
            sr, sr_av = np.zeros((len(times), N), np.float32), np.zeros(len(times), bool)
        infra, inames = fb.infrastructure_block(sr, sr311_scale or 1.0)
        groups["infrastructure"] = (infra, inames, np.repeat(sr_av[:, None], N, axis=1))
        report["sr311_available"] = bool(sr_av[-1])
    X, M, names, slices = fb.assemble(groups, meta["groups"])
    if names != meta["feature_names"]:
        raise RuntimeError(f"feature schema mismatch: live {names} vs model {meta['feature_names']}")
    return X, M, report


def _sr311_scale(data) -> float | None:
    """TRAIN maximum of the lagged 311 count.  Newer feature builds store it; older ones are recomputed once from
    the archived download over the training rows and cached (never guessed)."""
    sc = data.meta["scaler"]
    if sc.get("sr311_scale_train"):
        return float(sc["sr311_scale_train"])
    cache = ART / "context_scales.json"
    if cache.exists():
        js = read_json(cache)
        if js.get("feature_schema_hash") == data.meta["feature_schema_hash"]:
            return js.get("sr311_scale_train")
    try:
        geoms = read_json(settings.path("processed") / "link_geometries.json")
        mids = context.link_midpoints([{"link_id": lid} for lid in data.meta["link_ids"]], geoms)
        a = int(data.meta["splits"]["bounds"]["train"][1])
        sr, _, info = context.sr311_on_grid(data.times[:a], mids)
        scale = float(np.nanmax(sr)) if sr.size and np.nanmax(sr) > 0 else 1.0
        write_json(cache, {"feature_schema_hash": data.meta["feature_schema_hash"], "sr311_scale_train": scale,
                           "computed_at_utc": utcnow().isoformat(), "rows": info})
        return scale
    except Exception:
        return None


def _latest(files: list[Path], not_before: dt.datetime | None = None) -> list[Path]:
    files = sorted(files)
    if not_before is None:
        return files
    keep = []
    for f in files:
        try:
            stamp = dt.datetime.strptime(Path(f).name.split(".")[0].split("_")[-1], "%Y%m%dT%H%M%SZ").replace(
                tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if stamp >= not_before:
            keep.append(f)
    return keep


# ------------------------------------------------------------------------------------------------------------------
# forecast
# ------------------------------------------------------------------------------------------------------------------

def forecast(now: dt.datetime | None = None, origin_mode: str | None = None) -> dict:
    """One LIVE forecast batch, written before any of its targets is published.

    ``origin_mode`` ``wall_clock`` forecasts from the latest complete bin of the clock; ``latest_available`` from the
    newest bin the feed has published (see the module docstring).  Defaults to ``live.origin_mode`` in the config."""
    import torch

    from smartcity.api import service
    from smartcity.uncertainty.conformal import gate

    cfg = _cfg()
    data, model, cal, sel = service.loaded()
    meta = data.meta
    ids = list(meta["link_ids"])
    L = int(meta["lookback_steps"])
    now = now or utcnow()
    origin_mode = origin_mode or str(cfg.get("origin_mode", "wall_clock"))
    if origin_mode not in ORIGIN_MODES:
        raise ValueError(f"origin_mode must be one of {ORIGIN_MODES}, got {origin_mode!r}")
    wall_origin = floor_origin(now)
    since = wall_origin - dt.timedelta(hours=float(cfg.get("history_hours", 4.0)) + 1)
    if origin_mode == "latest_available":
        # the newest published bin may be hours old: look at every pull of the last (history + lag) window
        since = wall_origin - dt.timedelta(hours=float(cfg.get("history_hours", 4.0)) + float(cfg.get("max_origin_lag_hours", 6.0)))
    sfiles = _latest(raw_live("speeds").glob("speeds_*.json.gz"), since)
    grid, sstats = live_grid(ids, sfiles)
    if grid is None:
        raise SystemExit("NOT_RUN: no valid live speed records (run `live pull` first)")
    if origin_mode == "latest_available":
        origin = latest_available_origin(grid, ids)
        if origin is None:
            raise SystemExit("NOT_RUN: no published observation of any modelled link in the pulled records")
        origin = min(origin, wall_origin)
    else:
        origin = wall_origin
    latest_published = latest_available_origin(grid, ids)  # newest bin with a published observation, any link
    out_p = FORECASTS / f"live-{origin:%Y%m%dT%H%MZ}.json"
    if out_p.exists():
        rec = read_json(out_p)
        rec["note"] = "already forecast for this origin; nothing rewritten"
        return rec

    W = int(cfg.get("window_steps", L + 18))
    times = np.array([int(origin.timestamp()) - STEP_S * (W - 1 - i) for i in range(W)], dtype=np.int64)
    speed = place_on_axis(grid, times, ids)

    wfiles = _latest(raw_live("weather").glob("forecast_*.json.gz"))
    wdf = context.load_weather("historical_forecast", files=wfiles[-1:]) if wfiles else None
    rfiles = _latest(raw_live("sr311").glob("sr311_*.json.gz"))
    sr_raw = _read_rows(rfiles[-1:]) if rfiles else None
    mids = None
    try:
        geoms = read_json(settings.path("processed") / "link_geometries.json")
        mids = context.link_midpoints([{"link_id": lid} for lid in ids], geoms)
    except Exception:
        pass
    X, M, avail = live_features(speed, times, meta, wdf, sr_raw, mids, _sr311_scale(data),
                                int(settings.load("data")["grid"]["max_ffill_steps"]))

    dev = next(model.parameters()).device
    x = torch.from_numpy(X[-L:][None]).float().to(dev)
    m = torch.from_numpy(M[-L:][None]).to(dev)
    ei = torch.from_numpy(data.edge_index).to(dev)
    with torch.no_grad():
        z = model(x, m, ei).cpu().numpy()[0]  # [H, N]
    P = z * data.sd[None, :] + data.mu[None, :]

    gate_cfg = dict(settings.load("uncertainty")["gate"])
    gate_cfg.update(cal.get("gate_config") or {})
    n_cal = {str(h): int(n) for h, n in (cal.get("n_calibration") or {}).items()}
    min_obs = int(cfg.get("min_observed_steps", 12))
    generated = utcnow()
    origin_lag_min = round((generated - origin).total_seconds() / 60.0, 1)
    links, n_forecast, n_withheld = [], 0, 0
    for n, lid in enumerate(ids):
        obs_idx = np.where(np.isfinite(speed[:, n]))[0]
        last_t = int(times[obs_idx[-1]]) if obs_idx.size else None
        age_min = (int(origin.timestamp()) - last_t) / 60.0 if last_t is not None else None
        n_obs = int(np.isfinite(speed[-L:, n]).sum())
        missing_frac = float(1.0 - M[-L:, n, meta["groups"].index("traffic")].mean())
        row = {"link_id": lid, "data_as_of_utc": dt.datetime.fromtimestamp(last_t, dt.timezone.utc).isoformat()
               if last_t is not None else None, "data_age_minutes": age_min,
               "issue_lag_minutes": round((generated.timestamp() - last_t) / 60.0, 1) if last_t is not None else None,
               "observed_steps_in_window": n_obs,
               "input_missing_fraction": round(missing_frac, 4),
               "last_observed_speed_mph": float(speed[obs_idx[-1], n]) if obs_idx.size else None}
        if n_obs < min_obs:
            n_withheld += 1
            row.update(status="INSUFFICIENT_HISTORY", reasons=[f"{n_obs} of {L} lookback bins observed < {min_obs}"],
                       eligible_for_advisory=False, horizons=[])
            links.append(row)
            continue
        hz, widths = [], {}
        for k, h in enumerate(meta["horizon_minutes"]):
            ql = (cal.get("q_by_horizon_link_mph") or {}).get(str(h), [None] * len(ids))[n]
            q = float(ql) if ql is not None else float(cal["q_by_horizon_mph"][str(h)])
            widths[h] = 2 * q
            pred = float(P[k, n])
            hz.append({"horizon_minutes": int(h), "target_utc": (origin + dt.timedelta(minutes=int(h))).isoformat(),
                       "predicted_speed_mph": pred, "displayed_speed_mph": max(0.0, pred),
                       "lower_mph": pred - q, "upper_mph": pred + q, "interval_level": 1 - float(cal["alpha"])})
        ok, reasons = gate(widths, missing_frac, age_min, n_cal, gate_cfg)
        row.update(status="FORECAST", eligible_for_advisory=bool(ok), reasons=reasons, horizons=hz)
        n_forecast += 1
        links.append(row)

    first_target = origin + dt.timedelta(minutes=int(min(meta["horizon_minutes"])))
    n_past = sum(1 for h in meta["horizon_minutes"] if generated >= origin + dt.timedelta(minutes=int(h)))
    label = (f"LIVE (latest-available origin, data age {origin_lag_min:.0f} min at issue)"
             if origin_mode == "latest_available" else "LIVE")
    rec = {"mode": MODE, "origin_mode": origin_mode, "label": label,
           "forecast_batch_id": f"live-{uuid.uuid4().hex[:10]}", "origin_utc": origin.isoformat(),
           "generated_at_utc": generated.isoformat(), "origin_lag_minutes": origin_lag_min,
           "latest_published_bin_utc": latest_published.isoformat() if latest_published else None,
           "generated_before_first_target": generated < first_target,
           "generated_before_first_target_published": latest_published is None or first_target > latest_published,
           "n_targets_in_past_at_issue": n_past,
           "model_version": sel["proposed_run_id"], "graph_hash": meta["graph_hash"],
           "feature_schema_hash": meta["feature_schema_hash"], "speed_unit": "mph",
           "lookback_steps": L, "window_steps": W, "horizon_minutes": list(meta["horizon_minutes"]),
           "sources": {"speeds": {**sstats, "n_files": len(sfiles), "files": [_rel(f) for f in sfiles]},
                       "weather": {"file": _rel(wfiles[-1]) if wfiles else None, "kind_in_training": "historical_forecast",
                                   "kind_live": "open-meteo forecast API (current issue)", "available_at_origin":
                                   avail["weather_available"]},
                       "sr311": {"file": _rel(rfiles[-1]) if rfiles else None, "available_at_origin": avail["sr311_available"]}},
           "n_links": len(ids), "n_forecast": n_forecast, "n_withheld": n_withheld,
           "n_eligible_for_advisory": sum(1 for r in links if r.get("eligible_for_advisory")),
           "links": links,
           "warnings": ["LIVE: forecasts from newly retrieved public records; scored only after their targets are observed",
                        *([f"latest-available origin: the feed's newest published bin was {origin_lag_min:.0f} min old at issue; "
                           f"{n_past} of {len(meta['horizon_minutes'])} target times already lay in the past on the wall clock; "
                           "a target is scored only if its bin was first retrieved after this forecast was written"]
                          if origin_mode == "latest_available" else []),
                        "weather group uses the current Open-Meteo forecast where training used the archived historical forecast",
                        "no connection to any traffic signal"]}
    write_json(out_p, rec)
    with open(ART / "forecast_log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"origin_utc": rec["origin_utc"], "generated_at_utc": rec["generated_at_utc"],
                             "origin_mode": origin_mode, "origin_lag_minutes": origin_lag_min,
                             "file": _rel(out_p), "n_forecast": n_forecast, "n_withheld": n_withheld}) + "\n")
    return rec


# ------------------------------------------------------------------------------------------------------------------
# score
# ------------------------------------------------------------------------------------------------------------------

def score_records(records: list[dict], grid: dict | None, latest_obs: dt.datetime | None,
                  first_seen: dict | None = None) -> list[dict]:
    """One row per (batch, link, horizon) with its status: SCORED, PENDING, TARGET_UNOBSERVED, LATE,
    PUBLISHED_BEFORE_ISSUE or WITHHELD.

    Wall-clock batches exclude a forecast generated at or after its target time (LATE).  Latest-available batches
    forecast bins the feed had not yet published, so the clock rule does not apply; instead the target's first
    retrieval time (``first_seen``) must be later than the forecast's generation time, else the row is excluded as
    PUBLISHED_BEFORE_ISSUE.  When ``first_seen`` is given the same publication check is also applied to wall-clock
    batches (it can only exclude more)."""
    tidx = {int(t): i for i, t in enumerate(grid["times_utc"].tolist())} if grid else {}
    lidx = {lid: j for j, lid in enumerate(grid["link_ids"].tolist())} if grid else {}
    rows = []
    for rec in records:
        gen = _parse(rec["generated_at_utc"])
        omode = rec.get("origin_mode", "wall_clock")
        for ln in rec["links"]:
            base = {"forecast_batch_id": rec["forecast_batch_id"], "origin_utc": rec["origin_utc"], "origin_mode": omode,
                    "origin_lag_minutes": rec.get("origin_lag_minutes"), "link_id": ln["link_id"],
                    "eligible_for_advisory": ln.get("eligible_for_advisory", False),
                    "data_age_minutes": ln.get("data_age_minutes"), "last_observed_speed_mph": ln.get("last_observed_speed_mph")}
            if not ln.get("horizons"):
                rows.append({**base, "horizon_minutes": None, "status": "WITHHELD", "reason": ";".join(ln.get("reasons", []))})
                continue
            for hz in ln["horizons"]:
                target = _parse(hz["target_utc"])
                fs = (first_seen or {}).get((ln["link_id"], int(target.timestamp())))
                r = {**base, "horizon_minutes": hz["horizon_minutes"], "target_utc": hz["target_utc"],
                     "predicted_speed_mph": hz["predicted_speed_mph"], "lower_mph": hz["lower_mph"], "upper_mph": hz["upper_mph"],
                     "observed_speed_mph": None, "abs_error_mph": None, "covered": None, "persistence_abs_error_mph": None,
                     "target_in_past_at_issue": bool(gen >= target),
                     "target_first_seen_utc": fs.isoformat() if fs is not None else None}
                if omode == "wall_clock" and gen >= target:
                    r.update(status="LATE", reason="generated at or after the target time; excluded")
                elif latest_obs is None or target > latest_obs:
                    r.update(status="PENDING", reason="target not yet observed")
                else:
                    i, j = tidx.get(int(target.timestamp())), lidx.get(ln["link_id"])
                    y = grid["speed"][i, j] if (i is not None and j is not None) else np.nan
                    if not np.isfinite(y):
                        r.update(status="TARGET_UNOBSERVED", reason="no valid observation in the target bin")
                    elif fs is not None and fs <= gen:
                        r.update(status="PUBLISHED_BEFORE_ISSUE",
                                 reason=f"target bin first retrieved {fs.isoformat()} before the forecast was written; excluded")
                    elif omode == "latest_available" and fs is None:
                        r.update(status="PUBLISHED_BEFORE_ISSUE",
                                 reason="no retrieval record for the target bin; cannot prove it was unpublished at issue")
                    else:
                        y = float(y)
                        r.update(status="SCORED", reason="", observed_speed_mph=y,
                                 abs_error_mph=abs(hz["predicted_speed_mph"] - y),
                                 covered=bool(hz["lower_mph"] <= y <= hz["upper_mph"]),
                                 persistence_abs_error_mph=abs(ln["last_observed_speed_mph"] - y)
                                 if ln.get("last_observed_speed_mph") is not None else None)
                rows.append(r)
    return rows


def metrics_by_horizon(rows: list[dict], horizons: list[int]) -> list[dict]:
    out = []
    for h in horizons:
        hr = [r for r in rows if r.get("horizon_minutes") == h]
        sc = [r for r in hr if r["status"] == "SCORED"]
        el = [r for r in sc if r.get("eligible_for_advisory")]
        err = np.array([r["abs_error_mph"] for r in sc], dtype=float)
        pers = np.array([r["persistence_abs_error_mph"] for r in sc if r["persistence_abs_error_mph"] is not None], dtype=float)
        out.append({"mode": MODE, "horizon_minutes": h, "n_forecast": len(hr), "n_scored": len(sc),
                    "n_pending": sum(r["status"] == "PENDING" for r in hr),
                    "n_target_unobserved": sum(r["status"] == "TARGET_UNOBSERVED" for r in hr),
                    "n_late": sum(r["status"] == "LATE" for r in hr),
                    "n_published_before_issue": sum(r["status"] == "PUBLISHED_BEFORE_ISSUE" for r in hr),
                    "n_target_in_past_at_issue": sum(bool(r.get("target_in_past_at_issue")) for r in sc),
                    "mean_origin_lag_minutes": float(np.mean([r["origin_lag_minutes"] for r in sc
                                                              if r.get("origin_lag_minutes") is not None]))
                    if any(r.get("origin_lag_minutes") is not None for r in sc) else None,
                    "mae_mph": float(err.mean()) if err.size else None,
                    "rmse_mph": float(math.sqrt((err ** 2).mean())) if err.size else None,
                    "coverage": float(np.mean([r["covered"] for r in sc])) if sc else None,
                    "mean_interval_width_mph": float(np.mean([r["upper_mph"] - r["lower_mph"] for r in sc])) if sc else None,
                    "persistence_mae_mph": float(pers.mean()) if pers.size else None,
                    "n_scored_eligible": len(el),
                    "mae_eligible_mph": float(np.mean([r["abs_error_mph"] for r in el])) if el else None})
    return out


def score(now: dt.datetime | None = None) -> dict:
    """Match stored LIVE forecasts to observations retrieved since; write the metrics files and the summary."""
    now = now or utcnow()
    files = sorted(FORECASTS.glob("live-*.json"))
    if not files:
        summ = {"mode": MODE, "status": "NOT_RUN", "reason": "no live forecast stored", "scored_at_utc": now.isoformat()}
        write_json(ART / "live_summary.json", summ)
        return summ
    records = [read_json(f) for f in files]
    ids = [ln["link_id"] for ln in records[-1]["links"]]
    grid, sstats = live_grid(ids)
    latest = _parse(sstats["latest_observation_utc"]) if sstats.get("latest_observation_utc") else None
    latest_label = floor_origin(latest) + dt.timedelta(seconds=STEP_S) if latest else None  # bin that holds the last obs
    sfiles = sorted(raw_live("speeds").glob("speeds_*.json.gz"))
    first_seen = first_seen_map(ids, sfiles)
    rows = score_records(records, grid, latest_label, first_seen)
    horizons = list(records[-1]["horizon_minutes"])
    mets = metrics_by_horizon(rows, horizons)

    ART.mkdir(parents=True, exist_ok=True)
    cols = ["forecast_batch_id", "origin_utc", "origin_mode", "origin_lag_minutes", "link_id", "horizon_minutes",
            "target_utc", "status", "reason", "predicted_speed_mph", "lower_mph", "upper_mph", "observed_speed_mph",
            "abs_error_mph", "covered", "persistence_abs_error_mph", "eligible_for_advisory", "data_age_minutes",
            "last_observed_speed_mph", "target_in_past_at_issue", "target_first_seen_utc"]
    with open(ART / "scored.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    EXP.mkdir(parents=True, exist_ok=True)
    with open(EXP / "live_metrics.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(mets[0].keys()))
        w.writeheader()
        w.writerows(mets)

    n_scored = sum(m["n_scored"] for m in mets)
    modes = sorted({r.get("origin_mode", "wall_clock") for r in records})
    lags = [r["origin_lag_minutes"] for r in records if r.get("origin_lag_minutes") is not None]
    summ = {"mode": MODE, "origin_modes": modes, "status": "OK" if n_scored else "PARTIAL",
            "reason": "" if n_scored else "forecasts saved; no target observed yet",
            "scored_at_utc": now.isoformat(), "n_batches": len(records),
            "first_origin_utc": records[0]["origin_utc"], "last_origin_utc": records[-1]["origin_utc"],
            "generated_before_first_target_all": all(r.get("generated_before_first_target") for r in records),
            "generated_before_first_target_published_all": all(r.get("generated_before_first_target_published", True)
                                                               for r in records),
            "mean_origin_lag_minutes": float(np.mean(lags)) if lags else None,
            "max_origin_lag_minutes": float(np.max(lags)) if lags else None,
            "n_published_before_issue": sum(m["n_published_before_issue"] for m in mets),
            "n_scored_target_in_past_at_issue": sum(m["n_target_in_past_at_issue"] for m in mets),
            "model_version": records[-1]["model_version"], "n_links": len(ids),
            "latest_observation_utc": sstats.get("latest_observation_utc"), "speed_pull_stats": sstats,
            "n_rows": len(rows), "n_scored": n_scored, "n_late": sum(m["n_late"] for m in mets),
            "n_pending": sum(m["n_pending"] for m in mets), "n_withheld": sum(r["status"] == "WITHHELD" for r in rows),
            "metrics_by_horizon": mets,
            "note": "LIVE observational run on newly retrieved public records; a short window, not a second test set"
                    + ("; latest-available origin: forecasts concern bins the feed had not yet published, scored only "
                       "when the target bin was first retrieved after the forecast was written"
                       if "latest_available" in modes else "")}
    write_json(ART / "live_summary.json", summ)
    return summ


# ------------------------------------------------------------------------------------------------------------------
# run loop
# ------------------------------------------------------------------------------------------------------------------

def run(polls: int, interval_s: int = 300, settle: bool = True, link_ids: list[str] | None = None,
        origin_mode: str | None = None, settle_max_hours: float | None = None) -> dict:
    """pull -> forecast -> score, ``polls`` times at ``interval_s``; then keep pulling (no new forecasts) until the
    last batch's longest horizon has been observed, and score once more.

    With a latest-available origin a poll that finds no newer published bin writes no new batch (the origin's file
    already exists), and the settle phase waits until the feed has *published* the last batch's longest target, or
    until ``settle_max_hours`` (config ``live.settle_max_hours``, default 4) of wall time have passed."""
    from smartcity.api import service

    cfg = _cfg()
    data, _, _, _ = service.loaded()
    ids = link_ids or list(data.meta["link_ids"])
    origin_mode = origin_mode or str(cfg.get("origin_mode", "wall_clock"))
    last_rec, n_new = None, 0
    for i in range(polls):
        t0 = time.time()
        p = pull(ids)
        rec = forecast(origin_mode=origin_mode)
        s = score()
        new = not rec.get("note")
        n_new += int(new)
        last_rec = rec
        print(f"poll {i + 1}/{polls}: {p['speeds_rows']} speed rows (newest {p.get('speeds_latest_data_as_of_local')} local); "
              f"origin {rec['origin_utc']} [{origin_mode}, lag {rec.get('origin_lag_minutes')} min]"
              f"{' new batch' if new else ' already forecast'}: {rec['n_forecast']} forecast, {rec['n_withheld']} withheld; "
              f"batches {n_new}, scored so far {s.get('n_scored', 0)}", flush=True)
        if i < polls - 1:
            time.sleep(max(0.0, interval_s - (time.time() - t0)))
    if settle and last_rec is not None:
        horizon = max(last_rec["horizon_minutes"])
        last_target = _parse(last_rec["origin_utc"]) + dt.timedelta(minutes=horizon)
        if origin_mode == "latest_available":
            max_h = float(settle_max_hours if settle_max_hours is not None else cfg.get("settle_max_hours", 4.0))
            hard_stop = utcnow() + dt.timedelta(hours=max_h)
            while utcnow() < hard_stop:
                time.sleep(2 * interval_s)
                pull(ids, weather=False, sr311=False)
                s = score()
                grid, _ = live_grid(ids)
                pub = latest_available_origin(grid, ids)
                print(f"settling (latest published bin {pub.isoformat() if pub else None}, need > {last_target.isoformat()}, "
                      f"hard stop {hard_stop:%H:%M}Z): scored {s.get('n_scored', 0)}, pending {s.get('n_pending', 0)}", flush=True)
                if pub is not None and pub >= last_target + dt.timedelta(seconds=STEP_S):
                    break
        else:
            deadline = last_target + dt.timedelta(minutes=15)
            while utcnow() < deadline:
                time.sleep(interval_s)
                pull(ids, weather=False, sr311=False)
                s = score()
                print(f"settling until {deadline:%H:%M}Z: scored {s.get('n_scored', 0)}, pending {s.get('n_pending', 0)}", flush=True)
    return score()
