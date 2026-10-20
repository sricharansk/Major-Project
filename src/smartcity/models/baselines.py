"""Persistence and training-period historical-average baselines."""

from __future__ import annotations

import numpy as np
import pandas as pd


def last_observed(speed: np.ndarray) -> np.ndarray:
    """Unlimited causal forward fill (value at t = most recent observation at or before bin t)."""
    df = pd.DataFrame(speed)
    return df.ffill().to_numpy(dtype=np.float32)


def persistence(speed: np.ndarray, origins: np.ndarray, horizon_steps: list[int], fallback: np.ndarray) -> np.ndarray:
    """pred[k, h, n] = last observed speed at origin (same for every horizon); fallback = per-link train mean."""
    lo = last_observed(speed)[origins]  # [K, N]
    lo = np.where(np.isfinite(lo), lo, fallback[None, :])
    return np.repeat(lo[:, None, :], len(horizon_steps), axis=1)


class HistoricalAverage:
    """Mean training speed per (link, weekday/weekend-or-holiday, 5-minute slot of NYC local day)."""

    def __init__(self, freq_min: int = 5):
        self.freq = freq_min

    def _keys(self, times_utc: np.ndarray):
        ts = pd.to_datetime(times_utc, unit="s", utc=True).tz_convert("America/New_York")
        slot = (ts.hour * 60 + ts.minute) // self.freq
        daytype = (ts.dayofweek >= 5).astype(int)
        return np.asarray(daytype * (1440 // self.freq) + slot)

    def fit(self, speed: np.ndarray, times_utc: np.ndarray, train_end: int):
        keys = self._keys(times_utc[:train_end])
        nk = 2 * (1440 // self.freq)
        s = speed[:train_end]
        obs = np.isfinite(s)
        sums = np.zeros((nk, s.shape[1]))
        cnts = np.zeros((nk, s.shape[1]))
        np.add.at(sums, keys, np.nan_to_num(s))
        np.add.at(cnts, keys, obs)
        self.link_mean = np.nanmean(s, axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            self.table = np.where(cnts > 0, sums / np.maximum(cnts, 1), self.link_mean[None, :])
        self.support = cnts
        return self

    def predict(self, times_utc: np.ndarray, origins: np.ndarray, horizon_steps: list[int]) -> np.ndarray:
        out = []
        for h in horizon_steps:
            tgt = times_utc[origins] + h * self.freq * 60
            out.append(self.table[self._keys(tgt)])
        return np.stack(out, axis=1).astype(np.float32)
