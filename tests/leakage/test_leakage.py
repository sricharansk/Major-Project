"""Leakage tests on the split logic, scaler fitting and context availability rules."""

import numpy as np

from smartcity.features.build import causal_ffill, causal_rolling_mean, chronological_splits
from smartcity.preprocessing import context


def test_no_training_target_crosses_boundary():
    s = chronological_splits(5000, 24, 12, {"train": 0.6, "val": 0.15, "calib": 0.1, "test": 0.15})
    for k, (lo, hi) in s["origins"].items():
        assert hi - 1 + 12 < s["bounds"][k][1]
    assert s["origins"]["train"][1] - 1 + 12 < s["origins"]["val"][0] + 1


def test_features_at_t_do_not_change_when_future_changes():
    rng = np.random.default_rng(0)
    a = rng.normal(size=(50, 3)).astype(np.float32)
    b = a.copy()
    b[30:] = 999.0
    for fn in (lambda x: causal_ffill(x, 3)[0], lambda x: causal_rolling_mean(x, 12)):
        assert np.allclose(fn(a)[:30], fn(b)[:30], equal_nan=True)


def test_missing_label_not_imputed():
    from smartcity.graph.temporal import build_signal

    speed = np.array([[10.0], [np.nan], [12.0], [np.nan]], dtype=np.float32)
    _, Y = build_signal(np.zeros((4, 1, 2), np.float32), speed, np.zeros((2, 0), np.int64), [1])
    assert np.isnan(Y[0, 0, 0]) and Y[1, 0, 0] == 12.0 and np.isnan(Y[2, 0, 0])


def test_windowed_counts_only_use_past_records():
    times = np.array([1000, 2000, 3000], dtype=np.int64)
    mids = np.array([[40.75, -73.98]])
    ev_t = np.array([2500], dtype=np.int64)
    c = context._windowed_counts(times, mids, ev_t, np.array([40.75]), np.array([-73.98]), 100, 3600, 0)
    assert c[:, 0].tolist() == [0, 0, 1]  # a record at 2500 is invisible at t=2000


def test_311_lag_shifts_availability():
    times = np.array([0, 3600 * 30], dtype=np.int64)
    mids = np.array([[40.75, -73.98]])
    ev_t = np.array([3600], dtype=np.int64)
    lag, win = 24 * 3600, 24 * 3600
    c = context._windowed_counts(times, mids, ev_t, np.array([40.75]), np.array([-73.98]), 100, lag + win, lag)
    assert c[0, 0] == 0 and c[1, 0] == 1


def test_operational_weather_uses_forecast_not_archive():
    from smartcity.features.build import GROUPS_BY_TRACK

    assert "incidents" not in GROUPS_BY_TRACK["operational"]
    assert "events" not in GROUPS_BY_TRACK["operational"]
