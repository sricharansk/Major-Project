"""Windowed data access on top of the PyTorch Geometric Temporal signal (lazy, no window materialisation)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from smartcity.features import build as fb
from smartcity.graph.temporal import build_signal
from smartcity.utils import read_json
from smartcity import settings


@dataclass
class ForecastData:
    X: np.ndarray            # [T, N, F]
    M: np.ndarray            # [T, N, G]
    speed: np.ndarray        # [T, N]
    times: np.ndarray        # [T]
    Y: np.ndarray            # [T, H, N] raw mph targets (NaN = unobserved)
    mu: np.ndarray           # [N] train mean
    sd: np.ndarray           # [N] train std
    edge_index: np.ndarray   # [2, E]
    meta: dict
    signal: object
    origins: dict            # split -> np.ndarray of origin indices

    @property
    def L(self):
        return self.meta["lookback_steps"]

    @property
    def horizon_steps(self):
        return self.meta["horizon_steps"]

    @property
    def horizon_minutes(self):
        return self.meta["horizon_minutes"]

    def window(self, origins: np.ndarray):
        """Return x [B,L,N,F], m [B,L,N,G], yz [B,H,N], mask [B,H,N] for the given origins."""
        L = self.L
        feats = self.signal.features  # list of [N, F] snapshots held by the PGT signal
        x = np.stack([np.stack(feats[t - L + 1:t + 1]) for t in origins])
        m = np.stack([self.M[t - L + 1:t + 1] for t in origins])
        y = self.Y[origins]
        mask = np.isfinite(y)
        yz = np.where(mask, (y - self.mu[None, None, :]) / self.sd[None, None, :], 0.0)
        return (torch.from_numpy(x), torch.from_numpy(m), torch.from_numpy(yz.astype(np.float32)),
                torch.from_numpy(mask))

    def to_mph(self, pz: np.ndarray) -> np.ndarray:
        return pz * self.sd[None, None, :] + self.mu[None, None, :]


def load_data(track: str = "operational") -> ForecastData:
    arrays, meta = fb.load(track)
    graph = read_json(settings.path("processed") / "graph.json")
    gl = graph["link_ids"]
    keep = meta["link_ids"]
    pos = {lid: i for i, lid in enumerate(gl)}
    remap = {pos[lid]: j for j, lid in enumerate(keep)}
    ei = [(remap[a], remap[b]) for a, b in zip(*graph["edge_index"]) if a in remap and b in remap]
    edge_index = np.array(ei, dtype=np.int64).T if ei else np.zeros((2, 0), np.int64)
    signal, Y = build_signal(arrays["X"], arrays["speed"], edge_index, meta["horizon_steps"])
    origins = {k: np.arange(lo, hi) for k, (lo, hi) in meta["splits"]["origins"].items()}
    mu = np.array(meta["scaler"]["speed_mean_train"], dtype=np.float32)
    sd = np.array(meta["scaler"]["speed_std_train"], dtype=np.float32)
    return ForecastData(arrays["X"], arrays["M"], arrays["speed"], arrays["times_utc"], Y, mu, sd, edge_index, meta,
                        signal, origins)
