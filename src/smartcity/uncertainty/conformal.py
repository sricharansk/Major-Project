"""Per-horizon split conformal intervals and the reliability (advisory-eligibility) gate.

Calibration uses the frozen model's predictions on the *calibration* partition only.  Standard split-conformal
guarantees assume exchangeability, which traffic time series can violate, so only *empirical* coverage on
the test partition is reported (by horizon, congestion level and scenario).
"""

from __future__ import annotations

import csv
import math

import numpy as np

from smartcity import settings
from smartcity.utils import write_json


def conformal_quantile(residuals: np.ndarray, alpha: float) -> float:
    """Finite-sample split-conformal quantile: the ceil((n+1)(1-alpha))-th smallest absolute residual."""
    r = np.sort(np.abs(residuals[np.isfinite(residuals)]))
    n = r.size
    if n == 0:
        raise ValueError("no calibration residuals")
    k = math.ceil((n + 1) * (1 - alpha))
    if k > n:
        return float("inf")
    return float(r[k - 1])


def calibrate(Y_cal: np.ndarray, P_cal: np.ndarray, horizon_minutes: list[int], alpha: float) -> dict:
    q, n = {}, {}
    for k, h in enumerate(horizon_minutes):
        res = (Y_cal[:, k] - P_cal[:, k]).ravel()
        res = res[np.isfinite(res)]
        q[h] = conformal_quantile(res, alpha)
        n[h] = int(res.size)
    return {"alpha": alpha, "nominal_coverage": 1 - alpha, "q_by_horizon_mph": q, "n_calibration": n,
            "method": "split conformal, absolute residual, per horizon"}


def coverage(Y, P, q_by_h: dict, horizon_minutes, groups: np.ndarray | None = None, group_names=None) -> list[dict]:
    rows = []
    for k, h in enumerate(horizon_minutes):
        y, p = Y[:, k], P[:, k]
        ok = np.isfinite(y) & np.isfinite(p)
        hit = np.abs(y - p) <= q_by_h[h]
        if groups is None:
            rows.append({"horizon_min": h, "group": "all", "n": int(ok.sum()), "coverage": float(hit[ok].mean()),
                         "mean_width_mph": 2 * q_by_h[h]})
        else:
            g = groups[:, k] if groups.ndim == 3 else groups
            for gi, gname in enumerate(group_names):
                sel = ok & (g == gi)
                rows.append({"horizon_min": h, "group": gname, "n": int(sel.sum()),
                             "coverage": float(hit[sel].mean()) if sel.sum() else None,
                             "mean_width_mph": 2 * q_by_h[h]})
    return rows


def gate(width_by_h: dict, missing_frac: float, age_min: float | None, n_cal: dict, cfg: dict) -> tuple[bool, list[str]]:
    """Deterministic advisory-eligibility gate.  Thresholds come from config / validation data only."""
    reasons = []
    if age_min is None or age_min > cfg["max_data_age_minutes"]:
        reasons.append(f"STALE: data age {age_min} min > {cfg['max_data_age_minutes']}")
    if missing_frac > cfg["max_input_missing_fraction"]:
        reasons.append(f"MISSING_INPUT: {missing_frac:.2f} > {cfg['max_input_missing_fraction']}")
    wmax = cfg.get("max_interval_width_mph")
    if wmax is not None:
        for h, w in width_by_h.items():
            if w > wmax:
                reasons.append(f"WIDE_INTERVAL: h={h} width {w:.1f} > {wmax:.1f} mph")
    for h, n in n_cal.items():
        if n < cfg["min_calibration_samples"]:
            reasons.append(f"LOW_CALIBRATION_SUPPORT: h={h} n={n}")
    return (not reasons), reasons


def run(data, results: list[dict], selected_model: str = "proposed") -> dict:
    """Calibrate on the frozen selected model, report test coverage and the deferral trade-off."""
    ucfg = settings.load("uncertainty")
    alpha = ucfg["uncertainty"]["alpha"]
    out_dir = settings.ROOT / "artifacts" / "calibration"
    exp = settings.ROOT / "reports" / "experiments"
    res = next(r for r in results if r["info"]["model"] == selected_model)
    hm = data.horizon_minutes
    oc, ot = data.origins["calib"], data.origins["test"]
    cal = calibrate(data.Y[oc], res["preds"]["calib"], hm, alpha)
    cal.update(model=selected_model, model_run_id=res["info"]["run_id"],
               calibration_period=data.meta["split_times_utc"]["calib"])

    # Locally adaptive variant: residual scale by link (fitted on calibration only) -> per-link widths.
    per_link_q = {}
    for k, h in enumerate(hm):
        r = np.abs(data.Y[oc][:, k] - res["preds"]["calib"][:, k])
        per_link_q[h] = [conformal_quantile(r[:, n], alpha) if np.isfinite(r[:, n]).sum() >= 50 else None
                         for n in range(r.shape[1])]
    cal["q_by_horizon_link_mph"] = per_link_q

    Yt, Pt = data.Y[ot], res["preds"]["test"]
    rows = coverage(Yt, Pt, cal["q_by_horizon_mph"], hm)
    # congestion level groups: project-defined categories from speed / TRAIN reference (preregistered):
    ref = data.mu[None, None, :]
    ratio = Yt / ref
    lvl = np.where(ratio >= 0.8, 0, np.where(ratio >= 0.5, 1, 2))
    rows += coverage(Yt, Pt, cal["q_by_horizon_mph"], hm, lvl, ["free_ratio>=0.8", "moderate_0.5-0.8", "congested<0.5"])
    # scenario groups: rainy (operational weather proxy shows wet code) vs dry, rush hour vs not
    import pandas as pd
    lt = pd.to_datetime(data.times[ot], unit="s", utc=True).tz_convert("America/New_York")
    ts_local = np.asarray(lt.hour + lt.minute / 60.0)
    rush = ((ts_local >= 7) & (ts_local < 10)) | ((ts_local >= 16) & (ts_local < 19))
    rows += coverage(Yt, Pt, cal["q_by_horizon_mph"], hm, np.repeat(rush.astype(int)[:, None], Yt.shape[2], 1),
                     ["non_rush", "rush_hour_7-10_16-19"])
    wi = [i for i, n in enumerate(data.meta["feature_names"]) if n.endswith("wet_code")]
    if wi:
        wet = (data.X[ot, 0, wi[0]] > 0).astype(int)
        rows += coverage(Yt, Pt, cal["q_by_horizon_mph"], hm, np.repeat(wet[:, None], Yt.shape[2], 1),
                         ["weather_dry", "weather_wet_code"])

    # reliability-gate width threshold from CALIBRATION-partition per-link widths (never from test)
    widths_val = []
    for k, h in enumerate(hm):
        widths_val += [2 * q for q in per_link_q[h] if q is not None]
    gcfg = dict(ucfg["gate"])
    gcfg["max_interval_width_mph"] = float(np.quantile(widths_val, gcfg["width_quantile_on_val"])) if widths_val else None
    cal["gate_config"] = gcfg

    # deferral trade-off on TEST with the frozen gate (input missingness per origin/link)
    traffic_avail = data.M[..., data.meta["groups"].index("traffic")]
    L = data.L
    miss = np.stack([1 - traffic_avail[t - L + 1:t + 1].mean(0) for t in ot])  # [K, N]
    trade = []
    for thr in [0.0, 0.1, 0.2, 0.34, 0.5, 1.01]:
        for k, h in enumerate(hm):
            wl = np.array([2 * (q if q is not None else cal["q_by_horizon_mph"][h]) for q in per_link_q[h]])
            retained = (miss <= thr) & (wl[None, :] <= (gcfg["max_interval_width_mph"] or np.inf))
            y, p = Yt[:, k], Pt[:, k]
            ok = np.isfinite(y) & np.isfinite(p)
            sel = ok & retained
            trade.append({"missing_threshold": thr, "horizon_min": h, "n_valid": int(ok.sum()),
                          "retained": int(sel.sum()), "deferral_rate": float(1 - sel.sum() / max(ok.sum(), 1)),
                          "mae_retained": float(np.abs(y[sel] - p[sel]).mean()) if sel.any() else None,
                          "mae_all": float(np.abs(y[ok] - p[ok]).mean()),
                          "coverage_retained": float((np.abs(y[sel] - p[sel]) <= cal["q_by_horizon_mph"][h]).mean())
                          if sel.any() else None})
    write_json(out_dir / "calibrator.json", cal)
    for name, data_rows in (("coverage_by_horizon.csv", [r for r in rows if r["group"] == "all"]),
                            ("coverage_by_scenario.csv", [r for r in rows if r["group"] != "all"]),
                            ("deferral_tradeoff.csv", trade)):
        with open(out_dir / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data_rows[0].keys()))
            w.writeheader()
            w.writerows(data_rows)
    with open(out_dir / "interval_width_by_horizon.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["horizon_min", "global_width_mph", "median_link_width_mph", "n_calibration"])
        for h in hm:
            lw = [2 * q for q in per_link_q[h] if q is not None]
            w.writerow([h, 2 * cal["q_by_horizon_mph"][h], float(np.median(lw)) if lw else None, cal["n_calibration"][h]])
    period = f"{data.meta['split_times_utc']['test'][0]} .. {data.meta['split_times_utc']['test'][1]}"
    with open(exp / "uncertainty_metrics.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["run_id", "model", "evaluation_period_utc", "horizon_min", "group", "n",
                                           "nominal_coverage", "empirical_coverage", "mean_width_mph"])
        w.writeheader()
        for r in rows:
            w.writerow({"run_id": res["info"]["run_id"], "model": selected_model, "evaluation_period_utc": period,
                        "horizon_min": r["horizon_min"], "group": r["group"], "n": r["n"],
                        "nominal_coverage": 1 - alpha, "empirical_coverage": r["coverage"],
                        "mean_width_mph": r["mean_width_mph"]})
    return cal
