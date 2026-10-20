"""MLflow tracking helpers.  Default store: local SQLite ``mlflow.db`` (override with MLFLOW_TRACKING_URI)."""

from __future__ import annotations

import os
import platform

from smartcity import settings
from smartcity.utils import git_commit, read_json


def _mlflow():
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    import mlflow

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{settings.ROOT / 'mlflow.db'}"))
    return mlflow


def _manifest_hash() -> str:
    p = settings.ROOT / "data" / "manifests" / "source_manifest.json"
    return read_json(p).get("manifest_hash", "") if p.exists() else ""


def log_forecast_run(info: dict, data, metrics_by_h: dict, track: str, status: str = "FINISHED"):
    try:
        mlflow = _mlflow()
        mlflow.set_experiment("forecasting")
        with mlflow.start_run(run_name=info["run_id"]):
            mlflow.set_tags({"smartcity_run_id": info["run_id"], "model_name": info["model"], "track": track,
                             "git_commit": git_commit(), "status": status, "mode": "REPLAY"})
            mlflow.log_params({
                "config_hash": settings.config_hash("data", "model", "training"),
                "source_manifest_hash": _manifest_hash(), "graph_hash": data.meta["graph_hash"],
                "feature_schema_hash": data.meta["feature_schema_hash"],
                "split_manifest_hash": data.meta["sha256"][:16],
                "random_seed": settings.load("training")["training"]["seed"],
                "hardware": f"{platform.machine()} cpu x{os.cpu_count()}",
                "n_links": data.X.shape[1], "n_features": data.X.shape[2],
            })
            for k in ("best_epoch", "epochs_run", "n_params", "train_rows"):
                if info.get(k) is not None:
                    mlflow.log_param(k, info[k])
            mlflow.log_metric("training_duration_s", float(info.get("train_time_s") or 0))
            if info.get("infer_latency_ms_per_origin") is not None:
                mlflow.log_metric("inference_latency_ms", float(info["infer_latency_ms_per_origin"]))
            for h, v in metrics_by_h.items():
                for m in ("mae", "rmse", "smape", "r2"):
                    if v.get(m) is not None:
                        mlflow.log_metric(f"test_{m}_h{h}", v[m])
                mlflow.log_metric(f"test_n_h{h}", v["n"])
            d = info["artifact_dir"]
            for f in ("config.yaml", "feature_schema.json", "split_manifest.json", "environment.json",
                      "run_info.json", "training_history.csv"):
                p = os.path.join(d, f)
                if os.path.exists(p):
                    mlflow.log_artifact(p)
    except Exception as exc:  # tracking failure must be visible but must not erase the experiment
        print(f"MLFLOW LOGGING FAILED for {info.get('run_id')}: {exc}")


def log_generic(experiment: str, run_name: str, params: dict, metrics: dict, tags: dict | None = None,
                artifacts: list[str] | None = None):
    try:
        mlflow = _mlflow()
        mlflow.set_experiment(experiment)
        with mlflow.start_run(run_name=run_name):
            mlflow.set_tags({"git_commit": git_commit(), **(tags or {})})
            mlflow.log_params({k: (str(v)[:490]) for k, v in params.items()})
            for k, v in metrics.items():
                if v is not None:
                    mlflow.log_metric(k, float(v))
            for a in artifacts or []:
                if os.path.exists(a):
                    mlflow.log_artifact(a)
    except Exception as exc:
        print(f"MLFLOW LOGGING FAILED for {run_name}: {exc}")
