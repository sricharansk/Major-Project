"""Forecast metrics on a shared valid-target mask."""

from __future__ import annotations

import numpy as np


def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    """y, p 1-D over valid targets.  sMAPE = mean(|p-y| / ((|y|+|p|)/2)) * 100, pairs with both zero dropped."""
    n = int(y.size)
    if n == 0:
        return {"n": 0, "mae": None, "rmse": None, "smape": None, "r2": None}
    err = p - y
    denom = (np.abs(y) + np.abs(p)) / 2
    ok = denom > 0
    var = np.var(y)
    return {
        "n": n,
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "smape": float(np.mean(np.abs(err[ok]) / denom[ok]) * 100) if ok.any() else None,
        "r2": float(1 - np.mean(err**2) / var) if var > 1e-9 else None,
    }


def by_horizon(Y: np.ndarray, P: np.ndarray, horizon_minutes: list[int], mask: np.ndarray | None = None) -> dict:
    """Y, P: [K, H, N].  mask defaults to finite(Y)."""
    if mask is None:
        mask = np.isfinite(Y)
    out = {}
    for k, hm in enumerate(horizon_minutes):
        m = mask[:, k] & np.isfinite(P[:, k])
        out[hm] = metrics(Y[:, k][m], P[:, k][m])
    return out


def day_block_bootstrap_mae_diff(Y, Pa, Pb, day_index, n_boot=1000, seed=0) -> dict:
    """Paired MAE(a) - MAE(b) with day-level block bootstrap (respects within-day dependence)."""
    rng = np.random.default_rng(seed)
    days = np.unique(day_index)
    per_day = []
    for d in days:
        sel = day_index == d
        m = np.isfinite(Y[sel]) & np.isfinite(Pa[sel]) & np.isfinite(Pb[sel])
        if m.sum() == 0:
            continue
        ea = np.abs(Pa[sel][m] - Y[sel][m]).sum()
        eb = np.abs(Pb[sel][m] - Y[sel][m]).sum()
        per_day.append((ea, eb, m.sum()))
    if not per_day:
        return {"n_days": 0}
    arr = np.array(per_day, dtype=float)
    point = (arr[:, 0].sum() - arr[:, 1].sum()) / arr[:, 2].sum()
    boots = []
    for _ in range(n_boot):
        s = arr[rng.integers(0, len(arr), len(arr))]
        boots.append((s[:, 0].sum() - s[:, 1].sum()) / s[:, 2].sum())
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"n_days": len(arr), "mae_diff": float(point), "ci95": [float(lo), float(hi)]}
