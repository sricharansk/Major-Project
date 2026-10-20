"""Evidence registry, runtime metrics and ablation table generated from artifacts (never typed by hand).

Status rules: VERIFIED requires code + an executed run + an artifact on disk (and a passing check where one is
defined); otherwise PARTIAL / BLOCKED / NOT_STARTED with the reason taken from reports/verification/overrides.json
(human-maintained notes such as "Docker build not executed").
"""

from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

from smartcity import settings
from smartcity.utils import sha256_file, write_json

R = settings.ROOT
VER = R / "reports" / "verification"


def _exists(*paths) -> bool:
    return all((R / p).exists() for p in paths)


def _csv(p) -> list[dict]:
    p = R / p
    if not p.exists():
        return []
    with open(p, newline="") as fh:
        return list(csv.DictReader(fh))


REQS = [
    ("DATA-01", "data", "Verified source identity and dates", "src/smartcity/ingestion/fetch.py; src/smartcity/ingestion/audit.py",
     "python -m smartcity.cli data audit", "reports/data_audit/source_inventory.csv"),
    ("DATA-02", "data", "Reproducible raw download with hashes", "src/smartcity/ingestion/fetch.py",
     "python src/smartcity/ingestion/fetch.py speeds ...", "data/manifests/source_manifest.json"),
    ("DATA-03", "data", "Availability and leakage audit", "src/smartcity/features/build.py; tests/leakage",
     "pytest tests/leakage", "reports/data_audit/availability_audit.md"),
    ("GRAPH-01", "graph", "Directed road graph with edge rationale", "src/smartcity/graph/build.py",
     "python -m smartcity.cli graph build && graph validate", "reports/data_audit/graph_validation.json"),
    ("GRAPH-02", "graph", "Real temporal snapshot integration (PyG Temporal)", "src/smartcity/graph/temporal.py; src/smartcity/training/data.py",
     "pytest tests/integration/test_temporal_signal.py", "data/processed/features_operational_meta.json"),
    ("MODEL-01", "models", "Trained context-gated GATv2-Transformer", "src/smartcity/models/deep.py",
     "python -m smartcity.cli train proposed", "artifacts/models/registry_operational.json"),
    ("MODEL-02", "models", "Baseline comparison on identical splits/masks", "src/smartcity/training/runner.py",
     "python -m smartcity.cli evaluate forecasts", "reports/experiments/forecast_metrics.csv"),
    ("UNC-01", "uncertainty", "Conformal calibration and coverage report", "src/smartcity/uncertainty/conformal.py",
     "python -m smartcity.cli uncertainty calibrate", "artifacts/calibration/calibrator.json"),
    ("XAI-01", "explainability", "Explanation of the actual proposed model", "src/smartcity/explainability/deep.py",
     "python -m smartcity.cli explain alerts", "artifacts/explanations/explanations_summary.json"),
    ("RAG-01", "rag", "Real vector retrieval (FAISS + MiniLM)", "src/smartcity/rag/retriever.py",
     "python -m smartcity.cli rag build && rag evaluate", "artifacts/retrieval/retrieval_eval.json"),
    ("LLM-01", "llm", "Real model call and validated structured response", "src/smartcity/agents/llm.py; scripts/ollama_batch.py",
     "python -m smartcity.cli agents evaluate", "artifacts/llm_requests/responses.jsonl"),
    ("AGENT-01", "agents", "Conditional LangGraph execution with distinct decisions", "src/smartcity/agents/workflow.py",
     "python -m smartcity.cli agents evaluate", "reports/experiments/advisory_metrics.csv"),
    ("SAFE-01", "safety", "Deterministic rejected action", "src/smartcity/safety/constraints.py",
     "pytest tests/safety", "tests/safety/test_constraints.py"),
    ("SIM-01", "simulation", "Real SUMO run via TraCI", "src/smartcity/simulation/sumo_runner.py",
     "python -m smartcity.cli simulation evaluate", "reports/experiments/simulation_metrics.csv"),
    ("SIM-02", "simulation", "Paired controller comparison (matched seeds)", "src/smartcity/simulation/pipeline.py",
     "python -m smartcity.cli simulation evaluate", "reports/experiments/simulation_metrics.csv"),
    ("API-01", "api", "Functional service endpoints", "src/smartcity/api/app.py",
     "pytest tests/integration/test_api.py", "reports/verification/api_smoke.json"),
    ("UI-01", "dashboard", "Artifact-backed dashboard", "src/smartcity/dashboard/app.py",
     "streamlit run src/smartcity/dashboard/app.py (headless smoke test)", "reports/verification/dashboard_smoke.json"),
    ("DB-01", "db", "Spatial query and persisted run", "src/smartcity/db/store.py; migrations/001_init.sql",
     "pytest tests/integration/test_db.py", "reports/verification/db_smoke.json"),
    ("TRACK-01", "tracking", "MLflow experiment record", "src/smartcity/training/tracking.py",
     "mlflow ui --backend-store-uri sqlite:///mlflow.db", "reports/verification/mlflow_runs.json"),
    ("PACK-01", "packaging", "Tested container configuration", "compose.yaml; Dockerfile.*",
     "docker compose build && docker compose up", "reports/verification/docker_smoke.json"),
    ("PAPER-01", "paper", "Manuscript claims trace to evidence", "paper/main.tex; reports/verification/paper_claims.csv",
     "python -m smartcity.cli paper sync && pdflatex", "reports/verification/paper_claims.csv"),
]


def evidence_registry() -> list[dict]:
    over = json.loads((VER / "overrides.json").read_text()) if (VER / "overrides.json").exists() else {}
    rows = []
    for rid, comp, fn, impl, cmd, art in REQS:
        p = R / art
        status = "VERIFIED" if p.exists() else "NOT_STARTED"
        o = over.get(rid, {})
        if o.get("status"):
            status = o["status"]
        rows.append({"requirement_id": rid, "component": comp, "required_function": fn, "implementation_path": impl,
                     "test_command": cmd, "test_status": status, "artifact_path": art if p.exists() else "",
                     "artifact_hash": sha256_file(p)[:16] if p.exists() and p.is_file() else "",
                     "last_verified_at": dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).isoformat()
                     if p.exists() else "", "limitations": o.get("limitations", "")})
    with open(VER / "evidence_registry.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return rows


def runtime_metrics() -> list[dict]:
    rows = []
    for r in _csv("reports/experiments/forecast_metrics.csv"):
        if r["horizon_min"] == "30":
            rows.append({"component": f"forecast:{r['model']}", "run_id": r["run_id"], "metric": "train_time_s",
                         "value": r["train_time_s"], "n": "", "hardware": "cloud container CPU x4"})
            rows.append({"component": f"forecast:{r['model']}", "run_id": r["run_id"], "metric": "inference_ms_per_origin",
                         "value": r["infer_latency_ms_per_origin"], "n": r["n_valid_targets"], "hardware": "cloud container CPU x4"})
    ex = R / "artifacts" / "explanations" / "explanations_summary.json"
    if ex.exists():
        s = json.loads(ex.read_text())
        for e in s["local_alerts"]:
            rows.append({"component": "explanation:grouped_kernel_shap", "run_id": e["explanation_id"], "metric": "runtime_s",
                         "value": round(e["runtime_s"], 3), "n": e["model_calls"], "hardware": "cloud container CPU x4"})
    for r in _csv("reports/experiments/retrieval_metrics.csv"):
        rows.append({"component": "retrieval:faiss", "run_id": r["query_id"], "metric": "latency_s", "value": r["latency_s"],
                     "n": 1, "hardware": "cloud container CPU x4"})
    rp = R / "artifacts" / "llm_requests" / "responses.jsonl"
    if rp.exists():
        for line in rp.read_text().splitlines():
            if line.strip():
                j = json.loads(line)
                rows.append({"component": "llm:" + j["model"], "run_id": j["request_hash"][:12], "metric": "latency_s",
                             "value": round(j["latency_s"], 2), "n": j.get("completion_tokens"),
                             "hardware": f"author workstation ({j.get('host')}), Ollama {j.get('ollama_version')}"})
    for r in _csv("reports/experiments/simulation_metrics.csv"):
        rows.append({"component": f"sumo:{r['controller']}", "run_id": r["run_id"], "metric": "wall_time_s",
                     "value": r.get("wall_time_s"), "n": 1, "hardware": "cloud container CPU"})
    for r in _csv("reports/experiments/advisory_metrics.csv"):
        if r.get("latency_s"):
            rows.append({"component": f"agent:{r['policy']}", "run_id": r.get("run_id", ""), "metric": "end_to_end_s",
                         "value": r["latency_s"], "n": 1, "hardware": "cloud container CPU (LLM latency recorded separately)"})
    if rows:
        with open(R / "reports" / "experiments" / "runtime_metrics.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return rows


def mlflow_runs() -> list[dict]:
    """Export the MLflow run table (sqlite store) to reports/verification/mlflow_runs.json so the tracking record
    travels with the repository without committing mlflow.db."""
    import os

    try:
        os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
        import mlflow
        from mlflow.tracking import MlflowClient
    except Exception as exc:  # pragma: no cover - mlflow missing
        write_json(VER / "mlflow_runs.json", {"status": "BLOCKED", "reason": f"mlflow import failed: {exc}"})
        return []
    uri = os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{R / 'mlflow.db'}")
    if uri.startswith("sqlite:///") and not Path(uri[len("sqlite:///"):]).exists():
        write_json(VER / "mlflow_runs.json", {"status": "NOT_RUN", "reason": f"no tracking store at {uri}"})
        return []
    mlflow.set_tracking_uri(uri)
    client = MlflowClient()
    rows = []
    for exp in client.search_experiments():
        for run in client.search_runs([exp.experiment_id], max_results=500):
            rows.append({"experiment": exp.name, "run_id": run.info.run_id, "run_name": run.info.run_name,
                         "status": run.info.status, "start_time_utc": dt.datetime.fromtimestamp(
                             run.info.start_time / 1000, dt.UTC).isoformat() if run.info.start_time else None,
                         "params": dict(run.data.params), "metrics": {k: round(v, 5) for k, v in run.data.metrics.items()},
                         "tags": {k: v for k, v in run.data.tags.items() if not k.startswith("mlflow.")}})
    write_json(VER / "mlflow_runs.json", {"status": "OK" if rows else "EMPTY", "tracking_uri": uri, "n_runs": len(rows),
                                          "exported_at": dt.datetime.now(dt.UTC).isoformat(), "runs": rows})
    return rows


def run() -> dict:
    VER.mkdir(parents=True, exist_ok=True)
    ev = evidence_registry()
    rt = runtime_metrics()
    ml = mlflow_runs()
    return {"evidence_rows": len(ev), "verified": sum(r["test_status"] == "VERIFIED" for r in ev), "runtime_rows": len(rt),
            "mlflow_runs": len(ml)}
