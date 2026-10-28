"""LIVE mode: window placement, duplicate/revision detection, feature parity with the offline build, scoring rules."""

from __future__ import annotations

import datetime as dt
import gzip
import json

import numpy as np
import pytest

from smartcity.features import build as fb
from smartcity.live import pipeline as lp

UTC = dt.timezone.utc
NAMES = ["speed_z", "speed_observed_or_ffilled", "obs_age_days_frac", "rollmean_1h_z", "delta_5m_z",
         "hour_sin", "hour_cos", "dow_sin", "dow_cos", "weekend", "us_federal_holiday",
         *[f"historical_forecast_{n}" for n in ["precip_mm", "rain_mm", "snow_cm", "temp_c", "wind_kmh", "wet_code",
                                               "visibility_km", "cloud_pct"]],
         "sr311_24h_lagged_log"]


def _meta(n_links: int) -> dict:
    return {"link_ids": [f"L{i}" for i in range(n_links)], "lookback_steps": 24, "horizon_minutes": [15, 30, 60],
            "groups": ["traffic", "calendar", "weather", "infrastructure"], "feature_names": NAMES,
            "feature_schema_hash": "x", "graph_hash": "g", "context": {"weather_kind": "historical_forecast"},
            "scaler": {"speed_mean_train": [20.0] * n_links, "speed_std_train": [5.0] * n_links,
                       "weather_mean_train": [0.0] * 8, "weather_std_train": [1.0] * 8, "sr311_scale_train": 3.0}}


def test_floor_origin_is_the_latest_complete_bin():
    now = dt.datetime(2026, 10, 28, 14, 7, 31, tzinfo=UTC)
    assert lp.floor_origin(now) == dt.datetime(2026, 10, 28, 14, 5, tzinfo=UTC)
    assert lp.floor_origin(dt.datetime(2026, 10, 28, 14, 5, tzinfo=UTC)) == dt.datetime(2026, 10, 28, 14, 5, tzinfo=UTC)


def _write_pull(path, rows):
    with gzip.open(path, "wb") as fh:
        fh.write(json.dumps(rows).encode())


def test_merge_live_speeds_counts_repeats_and_revisions(tmp_path):
    base = {"id": "1", "travel_time": "100", "status": "0", "borough": "Manhattan", "link_name": "x", "owner": "DOT"}
    a = [dict(base, link_id="L0", data_as_of="2026-10-28T10:00:00.000", speed="12.4"),
         dict(base, link_id="L0", data_as_of="2026-10-28T10:05:00.000", speed="11.0"),
         dict(base, link_id="L1", data_as_of="2026-10-28T10:05:00.000", speed="0")]  # invalid speed
    b = [dict(base, link_id="L0", data_as_of="2026-10-28T10:05:00.000", speed="11.0"),   # repeat, same value
         dict(base, link_id="L0", data_as_of="2026-10-28T10:00:00.000", speed="13.9"),   # repeat, revised value
         dict(base, link_id="L0", data_as_of="2026-10-28T10:10:00.000", speed="9.5")]
    _write_pull(tmp_path / "speeds_20261028T101000Z.json.gz", a)
    _write_pull(tmp_path / "speeds_20261028T101500Z.json.gz", b)
    clean, stats = lp.merge_live_speeds(sorted(tmp_path.glob("*.json.gz")))
    assert stats["rows"] == 6 and stats["unique_records"] == 4
    assert stats["repeated_records"] == 2 and stats["revised_records"] == 1
    assert stats["duplicates_removed"] == 2 and stats["speed_zero_or_negative"] == 1
    first = clean.filter((clean["link_id"] == "L0") & (clean["data_as_of"] == "2026-10-28T10:00:00.000"))
    assert first.height == 1 and float(first["speed_mph"][0]) == 12.4  # first occurrence kept, as offline


def test_place_on_axis_and_grid(tmp_path):
    base = {"id": "1", "travel_time": "100", "status": "0", "borough": "Manhattan", "link_name": "x", "owner": "DOT"}
    # 09:57 local EDT = 13:57 UTC -> bin label 14:00 UTC
    rows = [dict(base, link_id="L0", data_as_of="2026-10-28T09:57:00.000", speed="12.0"),
            dict(base, link_id="L0", data_as_of="2026-10-28T09:58:30.000", speed="14.0"),
            dict(base, link_id="L1", data_as_of="2026-10-28T10:03:00.000", speed="30.0")]
    _write_pull(tmp_path / "speeds_20261028T141000Z.json.gz", rows)
    grid, stats = lp.live_grid(["L0", "L1"], sorted(tmp_path.glob("*.json.gz")))
    origin = dt.datetime(2026, 10, 28, 14, 5, tzinfo=UTC)
    times = np.array([int(origin.timestamp()) - 300 * (2 - i) for i in range(3)], dtype=np.int64)  # 13:55, 14:00, 14:05
    sp = lp.place_on_axis(grid, times, ["L0", "L1"])
    assert sp.shape == (3, 2)
    assert sp[1, 0] == pytest.approx(13.0) and np.isnan(sp[0, 0]) and np.isnan(sp[2, 0])
    assert sp[2, 1] == pytest.approx(30.0) and np.isnan(sp[1, 1])
    assert stats["latest_observation_utc"].startswith("2026-10-28 14:03")


def test_live_features_use_the_offline_blocks_and_the_frozen_schema():
    meta = _meta(3)
    W = 42
    rng = np.random.default_rng(0)
    origin = int(dt.datetime(2026, 10, 28, 14, 5, tzinfo=UTC).timestamp())
    times = np.array([origin - 300 * (W - 1 - i) for i in range(W)], dtype=np.int64)
    speed = (20 + 5 * rng.standard_normal((W, 3))).astype(np.float32)
    speed[5:9, 0] = np.nan
    speed[:, 2] = np.nan  # a dark link
    X, M, rep = lp.live_features(speed, times, meta, None, None, None, 3.0, max_ffill_steps=3)
    assert X.shape == (W, 3, len(NAMES)) and M.shape == (W, 3, 4)
    traffic, ok, _ = fb.traffic_block(speed, np.array(meta["scaler"]["speed_mean_train"], np.float32),
                                      np.array(meta["scaler"]["speed_std_train"], np.float32), 3)
    np.testing.assert_allclose(X[..., :5], np.where(ok[..., None], traffic, 0.0), rtol=0, atol=1e-6)
    assert M[..., 0].tolist() == ok.tolist()
    assert M[..., 1].all()                       # calendar always available
    assert not M[..., 2].any() and not M[..., 3].any()  # no weather / 311 pulled -> masked, zeroed
    assert not X[..., 11:].any()
    assert rep == {"weather_available": False, "sr311_available": False}
    assert not ok[:, 2].any() and not X[:, 2, :5].any()  # dark link: traffic group masked and zeroed, as offline
    assert (traffic[:, 2, 2] == 1.0).all()                 # (its age feature is capped at one day before masking)
    bad = dict(meta, feature_names=NAMES[:-1])
    with pytest.raises(RuntimeError, match="feature schema mismatch"):
        lp.live_features(speed, times, bad, None, None, None, 3.0, max_ffill_steps=3)


def _record(origin: dt.datetime, generated: dt.datetime, pred=(10.0, 11.0, 12.0), q=2.0):
    hz = [{"horizon_minutes": h, "target_utc": (origin + dt.timedelta(minutes=h)).isoformat(),
           "predicted_speed_mph": p, "displayed_speed_mph": max(0.0, p), "lower_mph": p - q, "upper_mph": p + q,
           "interval_level": 0.9} for h, p in zip((15, 30, 60), pred)]
    return {"forecast_batch_id": "live-abc", "origin_utc": origin.isoformat(), "generated_at_utc": generated.isoformat(),
            "horizon_minutes": [15, 30, 60],
            "links": [{"link_id": "L0", "status": "FORECAST", "eligible_for_advisory": True, "data_age_minutes": 5.0,
                       "last_observed_speed_mph": 9.0, "horizons": hz},
                      {"link_id": "L1", "status": "INSUFFICIENT_HISTORY", "eligible_for_advisory": False,
                       "reasons": ["3 of 24 lookback bins observed < 12"], "horizons": []}]}


def _grid(origin: dt.datetime, values: dict):
    times = [int(origin.timestamp()) + 300 * k for k in range(13)]
    speed = np.full((13, 2), np.nan, np.float32)
    for k, v in values.items():
        speed[k, 0] = v
    return {"times_utc": np.array(times, dtype=np.int64), "link_ids": np.array(["L0", "L1"]), "speed": speed}


def test_score_records_statuses_and_metrics():
    origin = dt.datetime(2026, 10, 28, 14, 0, tzinfo=UTC)
    rec = _record(origin, origin + dt.timedelta(seconds=40))
    grid = _grid(origin, {3: 11.5})  # +15 min observed (11.5), +30 min bin empty, +60 min not yet reached
    latest_label = origin + dt.timedelta(minutes=35)
    rows = lp.score_records([rec], grid, latest_label)
    by = {(r["link_id"], r.get("horizon_minutes")): r for r in rows}
    assert by[("L1", None)]["status"] == "WITHHELD"
    assert by[("L0", 15)]["status"] == "SCORED" and by[("L0", 15)]["abs_error_mph"] == pytest.approx(1.5)
    assert by[("L0", 15)]["covered"] is True and by[("L0", 15)]["persistence_abs_error_mph"] == pytest.approx(2.5)
    assert by[("L0", 30)]["status"] == "TARGET_UNOBSERVED"
    assert by[("L0", 60)]["status"] == "PENDING"
    m = {x["horizon_minutes"]: x for x in lp.metrics_by_horizon(rows, [15, 30, 60])}
    assert m[15]["n_scored"] == 1 and m[15]["mae_mph"] == pytest.approx(1.5) and m[15]["coverage"] == 1.0
    assert m[15]["persistence_mae_mph"] == pytest.approx(2.5) and m[15]["mean_interval_width_mph"] == pytest.approx(4.0)
    assert m[30]["n_scored"] == 0 and m[30]["mae_mph"] is None and m[30]["n_target_unobserved"] == 1
    assert m[60]["n_pending"] == 1 and m[60]["n_scored_eligible"] == 0


def test_late_forecasts_are_never_scored():
    origin = dt.datetime(2026, 10, 28, 14, 0, tzinfo=UTC)
    rec = _record(origin, origin + dt.timedelta(minutes=16))  # generated after the 15-min target
    grid = _grid(origin, {3: 11.5, 6: 12.0, 12: 13.0})
    rows = lp.score_records([rec], grid, origin + dt.timedelta(minutes=65))
    st = {r["horizon_minutes"]: r["status"] for r in rows if r["horizon_minutes"]}
    assert st == {15: "LATE", 30: "SCORED", 60: "SCORED"}
    m = {x["horizon_minutes"]: x for x in lp.metrics_by_horizon(rows, [15, 30, 60])}
    assert m[15]["n_late"] == 1 and m[15]["n_scored"] == 0 and m[60]["mae_mph"] == pytest.approx(1.0)


def test_score_without_forecasts_reports_not_run(tmp_path, monkeypatch):
    monkeypatch.setattr(lp, "ART", tmp_path / "live")
    monkeypatch.setattr(lp, "FORECASTS", tmp_path / "live" / "forecasts")
    s = lp.score(dt.datetime(2026, 10, 28, 15, 0, tzinfo=UTC))
    assert s["status"] == "NOT_RUN" and s["mode"] == "LIVE"
    assert json.loads((tmp_path / "live" / "live_summary.json").read_text())["status"] == "NOT_RUN"


class _StubModel:
    """Stands in for the frozen network: returns +0.5 standardised units for every link and horizon."""

    def __init__(self):
        import torch

        self._p = torch.nn.Parameter(torch.zeros(1))

    def parameters(self):
        return iter([self._p])

    def __call__(self, x, m, ei, node_drop=None):
        import torch

        B, L, N, _ = x.shape
        assert x.dtype == torch.float32 and m.dtype == torch.bool and L == 24
        return torch.full((B, 3, N), 0.5)


class _StubData:
    def __init__(self, meta):
        self.meta = meta
        self.mu = np.array(meta["scaler"]["speed_mean_train"], np.float32)
        self.sd = np.array(meta["scaler"]["speed_std_train"], np.float32)
        self.edge_index = np.zeros((2, 0), np.int64)
        self.times = np.arange(0, 300 * 100, 300, dtype=np.int64)


def test_forecast_and_score_end_to_end_with_a_stub_model(tmp_path, monkeypatch):
    from smartcity.api import service

    meta = _meta(2)
    cal = {"alpha": 0.1, "q_by_horizon_mph": {"15": 2.0, "30": 3.0, "60": 4.0}, "n_calibration": {"15": 500, "30": 500, "60": 500},
           "gate_config": {"max_interval_width_mph": None, "max_input_missing_fraction": 0.34, "max_data_age_minutes": 20,
                           "min_calibration_samples": 200}}
    monkeypatch.setattr(service, "loaded", lambda: (_StubData(meta), _StubModel(), cal, {"proposed_run_id": "stub-run"}))
    monkeypatch.setattr(lp, "ART", tmp_path / "live")
    monkeypatch.setattr(lp, "FORECASTS", tmp_path / "live" / "forecasts")
    monkeypatch.setattr(lp, "EXP", tmp_path / "experiments")
    raw = tmp_path / "raw"
    monkeypatch.setattr(lp, "raw_live", lambda source: (raw / source).mkdir(parents=True, exist_ok=True) or raw / source)

    now = dt.datetime(2026, 10, 28, 18, 7, tzinfo=UTC)          # origin 18:05 UTC
    base = {"id": "1", "travel_time": "100", "status": "0", "borough": "Manhattan", "link_name": "x", "owner": "DOT"}
    rows = []
    for k in range(48):                                          # L0: an observation every 5 min for 4 h, 14:00..17:59 local-UTC
        t = now - dt.timedelta(minutes=5 * k + 3)                # inside bin label floor(t)+5
        local = t.astimezone(lp.NYC).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S.000")
        rows.append(dict(base, link_id="L0", data_as_of=local, speed=str(18 + (k % 3))))
    rows.append(dict(base, link_id="L1", data_as_of=(now - dt.timedelta(minutes=2)).astimezone(lp.NYC).replace(tzinfo=None)
                     .strftime("%Y-%m-%dT%H:%M:%S.000"), speed="25"))  # L1: a single observation -> withheld
    (raw / "speeds").mkdir(parents=True, exist_ok=True)
    _write_pull(raw / "speeds" / f"speeds_{now:%Y%m%dT%H%M%SZ}.json.gz", rows)

    monkeypatch.setattr(lp, "utcnow", lambda: now + dt.timedelta(seconds=20))  # the wall clock when the batch is written
    rec = lp.forecast(now)
    assert rec["mode"] == "LIVE" and rec["origin_utc"] == "2026-10-28T18:05:00+00:00"
    assert rec["generated_at_utc"] == "2026-10-28T18:07:20+00:00"
    assert rec["n_forecast"] == 1 and rec["n_withheld"] == 1 and rec["generated_before_first_target"] is True
    l0, l1 = rec["links"]
    assert l1["status"] == "INSUFFICIENT_HISTORY" and l1["horizons"] == []
    assert l0["status"] == "FORECAST" and l0["data_age_minutes"] == 0.0 and l0["eligible_for_advisory"] is True
    assert [h["predicted_speed_mph"] for h in l0["horizons"]] == pytest.approx([22.5, 22.5, 22.5])  # 20 + 0.5 * 5
    assert l0["horizons"][0]["lower_mph"] == pytest.approx(20.5) and l0["horizons"][2]["upper_mph"] == pytest.approx(26.5)
    assert l0["horizons"][1]["target_utc"] == "2026-10-28T18:35:00+00:00"
    assert rec["sources"]["weather"]["available_at_origin"] is False and rec["sources"]["sr311"]["available_at_origin"] is False
    assert (tmp_path / "live" / "forecasts" / "live-20261028T1805Z.json").exists()
    again = lp.forecast(now + dt.timedelta(seconds=30))
    assert again.get("note", "").startswith("already forecast")

    s = lp.score(now)
    assert s["status"] == "PARTIAL" and s["n_pending"] == 3 and s["n_scored"] == 0 and s["n_withheld"] == 1

    later = now + dt.timedelta(minutes=40)                       # 18:20 and 18:35 targets observed, 19:05 not yet
    obs = []
    for t in (dt.datetime(2026, 10, 28, 18, 17, tzinfo=UTC), dt.datetime(2026, 10, 28, 18, 33, tzinfo=UTC)):
        obs.append(dict(base, link_id="L0", data_as_of=t.astimezone(lp.NYC).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S.000"),
                        speed="21.0"))
    _write_pull(raw / "speeds" / f"speeds_{later:%Y%m%dT%H%M%SZ}.json.gz", obs)
    s = lp.score(later)
    assert s["status"] == "OK" and s["n_scored"] == 2 and s["n_pending"] == 1 and s["n_late"] == 0
    m = {x["horizon_minutes"]: x for x in s["metrics_by_horizon"]}
    assert m[15]["mae_mph"] == pytest.approx(1.5) and m[15]["coverage"] == 1.0 and m[60]["n_pending"] == 1
    assert (tmp_path / "experiments" / "live_metrics.csv").exists() and (tmp_path / "live" / "scored.csv").exists()
