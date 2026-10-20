"""XGBoost / LightGBM per-horizon tabular baselines built from the same causal feature tensor."""

from __future__ import annotations

import numpy as np

N_LAGS = 12


def tabular(X: np.ndarray, speed_z_idx: int, origins: np.ndarray, feature_names: list[str]):
    """Rows = (origin, link).  Columns = 12 lags of speed_z + all features at origin + link index.

    Only information at or before the origin is used (lags look backwards).
    """
    K, N = len(origins), X.shape[1]
    lags = np.stack([X[origins - k, :, speed_z_idx] for k in range(N_LAGS)], axis=-1)  # [K, N, 12]
    cur = X[origins]  # [K, N, F]
    link = np.broadcast_to(np.arange(N)[None, :, None], (K, N, 1)).astype(np.float32)
    feats = np.concatenate([lags, cur, link], axis=-1).reshape(K * N, -1)
    names = [f"speed_z_lag{k}" for k in range(N_LAGS)] + list(feature_names) + ["link_index"]
    return feats.astype(np.float32), names


def group_of(name: str, group_slices: dict, feature_names: list[str]) -> str:
    if name.startswith("speed_z_lag"):
        return "traffic"
    if name == "link_index":
        return "link_identity"
    idx = feature_names.index(name)
    for g, (a, b) in group_slices.items():
        if a <= idx < b:
            return g
    return "other"


def fit_xgb(Xtr, ytr, Xva, yva, cfg, seed):
    import xgboost as xgb

    m = xgb.XGBRegressor(n_estimators=cfg["n_estimators"], learning_rate=cfg["learning_rate"],
                         max_depth=cfg["max_depth"], subsample=0.8, colsample_bytree=0.8, tree_method="hist",
                         early_stopping_rounds=cfg["early_stopping_rounds"], random_state=seed, n_jobs=4)
    m.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
    return m


def fit_lgbm(Xtr, ytr, Xva, yva, cfg, seed):
    import lightgbm as lgb

    m = lgb.LGBMRegressor(n_estimators=cfg["n_estimators"], learning_rate=cfg["learning_rate"],
                          max_depth=cfg["max_depth"], num_leaves=63, subsample=0.8, subsample_freq=1,
                          colsample_bytree=0.8, random_state=seed, n_jobs=4, verbose=-1)
    m.fit(Xtr, ytr, eval_set=[(Xva, yva)],
          callbacks=[lgb.early_stopping(cfg["early_stopping_rounds"], verbose=False)])
    return m
