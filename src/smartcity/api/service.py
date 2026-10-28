"""Artifact-backed service layer shared by the API, worker and dashboard.

Nothing here contains hard-coded results: every value comes from files under artifacts/ and reports/ or from
the database, and a missing artifact surfaces as NOT_TRAINED / NOT_RUN / SOURCE_UNAVAILABLE.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from smartcity import settings
from smartcity.utils import read_json

ROOT = settings.ROOT
SELECTED = ROOT / "artifacts" / "models" / "selected.json"


def read_csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def status_of(path: Path, missing: str = "NOT_RUN") -> str:
    return "AVAILABLE" if path.exists() else missing


def selected() -> dict | None:
    return read_json(SELECTED) if SELECTED.exists() else None


@lru_cache(maxsize=1)
def loaded():
    """Load the frozen proposed model, data and calibrator.  Raises FileNotFoundError when not trained."""
    import torch

    from smartcity.training.data import load_data
    from smartcity.training.runner import make_model

    sel = selected()
    if not sel:
        raise FileNotFoundError("NOT_TRAINED")
    data = load_data(sel["track"])
    mcfg = {k: v for k, v in settings.load("model")["model"].items() if k not in ("name", "lookback_steps", "horizon_steps")}
    model = make_model("proposed", data, mcfg)
    model.load_state_dict(torch.load(Path(sel["proposed_artifact_dir"]) / "model.pt"))
    model.eval()
    cal = read_json(ROOT / "artifacts" / "calibration" / "calibrator.json")
    return data, model, cal, sel


def source_status() -> list[dict]:
    rows = read_csv(ROOT / "reports" / "data_audit" / "source_inventory.csv")
    now = dt.datetime.now(dt.timezone.utc)
    for r in rows:
        try:
            last = dt.datetime.fromisoformat(r["observation_max"].replace("Z", "+00:00"))
            if last.tzinfo is None:
                last = last.replace(tzinfo=dt.timezone.utc)
            r["data_age_hours"] = round((now - last).total_seconds() / 3600, 1)
            r["freshness"] = "STALE" if r["data_age_hours"] > 24 else "FRESH"
        except Exception:
            r["data_age_hours"] = None
            r["freshness"] = r.get("availability_status") or "SOURCE_UNAVAILABLE"
    return rows


def road_links() -> list[dict]:
    p = settings.path("processed") / "graph.json"
    if not p.exists():
        return []
    g = read_json(p)
    return g["nodes"]


def forecast(link_id: str, origin_utc: str | None = None) -> dict:
    import uuid

    from smartcity.training.runner import predict_deep

    data, model, cal, sel = loaded()
    ids = data.meta["link_ids"]
    if link_id not in ids:
        raise KeyError(link_id)
    n = ids.index(link_id)
    test = data.origins["test"]
    if origin_utc:
        ts = int(dt.datetime.fromisoformat(origin_utc.replace("Z", "+00:00")).timestamp())
        o = int(np.searchsorted(data.times, ts, side="right") - 1)
    else:
        o = int(test[-1])
    o = max(o, data.L - 1)
    P = predict_deep(model, data, np.array([o]))[0]
    speed = data.speed[: o + 1, n]
    obs = np.where(np.isfinite(speed))[0]
    data_as_of = dt.datetime.fromtimestamp(int(data.times[obs[-1]]), dt.timezone.utc) if obs.size else None
    origin = dt.datetime.fromtimestamp(int(data.times[o]), dt.timezone.utc)
    hz = []
    for k, h in enumerate(data.horizon_minutes):
        ql = cal.get("q_by_horizon_link_mph", {}).get(str(h), [None] * len(ids))[n]
        q = ql if ql is not None else cal["q_by_horizon_mph"][str(h)]
        y = data.Y[o, k, n]
        hz.append({"horizon_minutes": h, "predicted_speed_mph": float(P[k, n]), "displayed_speed_mph": max(0.0, float(P[k, n])),
                   "lower_mph": float(P[k, n] - q), "upper_mph": float(P[k, n] + q), "interval_level": 1 - cal["alpha"],
                   "observed_speed_mph": None if not np.isfinite(y) else float(y)})
    return {"forecast_id": f"fc-{uuid.uuid4().hex[:10]}", "run_id": sel["proposed_run_id"], "mode": "REPLAY",
            "link_id": link_id, "origin_utc": origin, "data_as_of_utc": data_as_of,
            "generated_at_utc": dt.datetime.now(dt.timezone.utc), "model_version": sel["proposed_run_id"],
            "graph_hash": data.meta["graph_hash"], "feature_schema_hash": data.meta["feature_schema_hash"],
            "speed_unit": "mph", "horizons": hz,
            "warnings": ["REPLAY of historical data: not a live forecast"] +
                        (["origin outside the test partition"] if not (test[0] <= o <= test[-1]) else [])}


def history(link_id: str, origin_utc: str | None, steps: int = 72) -> dict:
    data, _, _, _ = loaded()
    n = data.meta["link_ids"].index(link_id)
    o = int(data.origins["test"][-1]) if not origin_utc else int(np.searchsorted(
        data.times, int(dt.datetime.fromisoformat(origin_utc.replace("Z", "+00:00")).timestamp()), side="right") - 1)
    lo = max(0, o - steps)
    return {"times_utc": data.times[lo:o + 13].tolist(), "speed_mph": [None if not np.isfinite(v) else float(v)
                                                                      for v in data.speed[lo:o + 13, n]],
            "origin_index_in_series": o - lo}


def experiments() -> dict:
    exp = ROOT / "reports" / "experiments"
    return {name: read_csv(exp / f"{name}.csv") for name in
            ["forecast_metrics", "ablation_metrics", "uncertainty_metrics", "retrieval_metrics", "advisory_metrics",
             "simulation_metrics", "runtime_metrics", "live_metrics"]}


def live_latest() -> dict | None:
    """Newest LIVE forecast batch written by ``smartcity.cli live forecast`` (None when LIVE was never run)."""
    files = sorted((ROOT / "artifacts" / "live" / "forecasts").glob("live-*.json"))
    return read_json(files[-1]) if files else None


def live_summary() -> dict | None:
    p = ROOT / "artifacts" / "live" / "live_summary.json"
    return read_json(p) if p.exists() else None


def evidence_status() -> list[dict]:
    return read_csv(ROOT / "reports" / "verification" / "evidence_registry.csv")


def agent_traces(limit: int = 50) -> list[dict]:
    d = ROOT / "artifacts" / "agent_traces"
    files = sorted(d.glob("adv-*.json"), reverse=True)[:limit]
    out = []
    for f in files:
        try:
            out.append(json.loads(f.read_text()))
        except Exception:
            continue
    return out
