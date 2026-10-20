import numpy as np

from smartcity.features.build import causal_ffill, causal_rolling_mean, chronological_splits
from smartcity.models.baselines import HistoricalAverage, persistence
from smartcity.training.metrics import metrics


def test_causal_ffill_bounded():
    a = np.array([[1.0], [np.nan], [np.nan], [np.nan], [np.nan], [5.0]], dtype=np.float32)
    f, age = causal_ffill(a, 2)
    assert f[1, 0] == 1 and f[2, 0] == 1 and np.isnan(f[3, 0]) and np.isnan(f[4, 0]) and f[5, 0] == 5
    assert age[3, 0] == 3 and age[5, 0] == 0


def test_rolling_mean_uses_only_past():
    a = np.array([[1.0], [3.0], [np.nan], [100.0]], dtype=np.float32)
    r = causal_rolling_mean(a, 2)
    assert r[1, 0] == 2.0 and r[2, 0] == 3.0 and r[3, 0] == 100.0


def test_splits_are_purged_and_ordered():
    s = chronological_splits(1000, 24, 12, {"train": 0.6, "val": 0.15, "calib": 0.1, "test": 0.15})
    o = s["origins"]
    b = s["bounds"]
    assert o["train"][0] == 23
    for k in ("train", "val", "calib", "test"):
        lo, hi = o[k]
        assert lo >= b[k][0] and (hi - 1) + 12 < b[k][1]
    assert o["train"][1] - 1 + 12 < b["val"][0]


def test_persistence_and_ha():
    speed = np.array([[10.0, np.nan], [12.0, np.nan], [np.nan, 30.0]], dtype=np.float32)
    p = persistence(speed, np.array([2]), [1, 2], fallback=np.array([0.0, 0.0]))
    assert p.shape == (1, 2, 2) and p[0, 0, 0] == 12.0 and p[0, 1, 1] == 30.0
    times = np.array([0, 300, 600], dtype=np.int64)
    ha = HistoricalAverage().fit(speed, times, 3)
    assert ha.predict(times, np.array([0]), [1]).shape == (1, 1, 2)


def test_metrics():
    m = metrics(np.array([10.0, 20.0]), np.array([12.0, 18.0]))
    assert m["mae"] == 2.0 and m["n"] == 2
