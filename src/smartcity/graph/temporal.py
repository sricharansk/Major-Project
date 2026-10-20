"""PyTorch Geometric Temporal integration: the processed tensors as a ``StaticGraphTemporalSignal``.

Each snapshot t carries node features X[t] ([N, F]), the static directed edge_index, and the multi-horizon
target y[t] ([N, H]; NaN where the target was not observed).  The deep-model data loader draws its windows
from this signal object, so PGT is on the training path rather than merely imported.

If ``torch_geometric_temporal``'s package ``__init__`` cannot be imported (it eagerly imports layers that need
compiled ``torch_sparse``), the signal module itself — which has no compiled dependencies — is loaded
directly from the installed package.  This is recorded in the environment report.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import numpy as np

IMPORT_ROUTE = "unresolved"


def _signal_class():
    global IMPORT_ROUTE
    try:
        from torch_geometric_temporal.signal import StaticGraphTemporalSignal  # type: ignore

        IMPORT_ROUTE = "package"
        return StaticGraphTemporalSignal
    except ModuleNotFoundError:
        spec = importlib.util.find_spec("torch_geometric_temporal")
        if spec is None or not spec.submodule_search_locations:
            raise
        path = Path(list(spec.submodule_search_locations)[0]) / "signal" / "static_graph_temporal_signal.py"
        mspec = importlib.util.spec_from_file_location("pgt_static_graph_temporal_signal", path)
        mod = importlib.util.module_from_spec(mspec)
        mspec.loader.exec_module(mod)  # type: ignore[union-attr]
        IMPORT_ROUTE = f"direct-module:{path.name}"
        return mod.StaticGraphTemporalSignal


def build_signal(X: np.ndarray, speed: np.ndarray, edge_index: np.ndarray, horizon_steps: list[int]):
    """Return (signal, targets[T, H, N]).  Snapshots beyond the last valid target have NaN targets."""
    T, N, _ = X.shape
    H = len(horizon_steps)
    Y = np.full((T, H, N), np.nan, dtype=np.float32)
    for k, h in enumerate(horizon_steps):
        Y[: T - h, k, :] = speed[h:]
    cls = _signal_class()
    features = [X[t] for t in range(T)]
    targets = [Y[t].T for t in range(T)]  # [N, H]
    edge_weight = np.ones(edge_index.shape[1], dtype=np.float32)
    return cls(edge_index=edge_index, edge_weight=edge_weight, features=features, targets=targets), Y
