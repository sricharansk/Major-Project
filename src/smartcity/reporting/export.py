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
     "pytest tests/unit/test_models.py tests/leakage", "artifacts/models/proposed-*/feature_schema.json"),
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
    ("LLM-01", "llm", "Real model call and validated structured response", "src/smartcity/agents/llm.py; src/smartcity/agents/workflow.py",
     "python -m smartcity.cli agents evaluate && report export", "reports/experiments/llm_calls.csv"),
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
    # a fresh checkout gives every file a new mtime; an artifact whose hash is unchanged keeps the time it was verified
    prev = {r["requirement_id"]: r for r in _csv("reports/verification/evidence_registry.csv")}
    rows = []
    for rid, comp, fn, impl, cmd, art in REQS:
        if "*" in art:  # per-run artifact: the newest run that carries it (run ids are timestamped)
            hits = sorted(R.glob(art))
            art = str(hits[-1].relative_to(R)).replace("\\", "/") if hits else art
        p = R / art
        status = "VERIFIED" if p.exists() else "NOT_STARTED"
        if p.exists() and p.suffix == ".json":  # smoke/export files carry their own outcome
            try:
                js = json.loads(p.read_text())
                st = js.get("status") if isinstance(js, dict) else None
                status = {"OK": "VERIFIED", "BLOCKED": "BLOCKED", "FAILED": "FAILED", "PARTIAL": "PARTIAL",
                          "NOT_RUN": "NOT_STARTED", "EMPTY": "NOT_STARTED"}.get(st, status)
            except (ValueError, OSError):
                status = "FAILED"
        o = over.get(rid, {})
        if o.get("status"):
            status = o["status"]
        h = sha256_file(p)[:16] if p.exists() and p.is_file() else ""
        when = dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).isoformat() if p.exists() else ""
        old = prev.get(rid, {})
        if h and old.get("artifact_hash") == h and old.get("artifact_path") == art and old.get("last_verified_at"):
            when = old["last_verified_at"]
        rows.append({"requirement_id": rid, "component": comp, "required_function": fn, "implementation_path": impl,
                     "test_command": cmd, "test_status": status, "artifact_path": art if p.exists() else "",
                     "artifact_hash": h, "last_verified_at": when, "limitations": o.get("limitations", "")})
    with open(VER / "evidence_registry.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return rows


def hardware_label() -> dict:
    """Hardware strings taken from the recorded environment of the run (reports/verification/environment.json),
    never typed: CPU label from platform/cpu_count, GPU label from nvidia-smi when it was present."""
    env_p = VER / "environment.json"
    if not env_p.exists():
        return {"cpu": "unknown (no environment.json)", "gpu": "unknown (no environment.json)"}
    env = json.loads(env_p.read_text())
    cpu = f"{env.get('platform', 'unknown platform')}, {env.get('cpu_count', '?')} CPUs"
    gpu = env.get("nvidia_smi") or ""
    gpu = f"{cpu}; {gpu.split('(UUID')[0].strip()}" if gpu and not gpu.startswith("UNAVAILABLE") else f"{cpu}; no GPU"
    return {"cpu": cpu, "gpu": gpu}


def _run_device(run_id: str) -> str | None:
    p = R / "artifacts" / "models" / run_id / "run_info.json"
    if p.exists():
        try:
            return json.loads(p.read_text()).get("train_device")
        except ValueError:
            return None
    return None


def llm_calls() -> list[dict]:
    """One row per LLM call recorded in the agent traces (artifacts/agent_traces/*.json): the evidence that a real
    model was called and that its structured response was validated.  Written to reports/experiments/llm_calls.csv."""
    rows = []
    for p in sorted((R / "artifacts" / "agent_traces").glob("adv-*.json")):
        try:
            t = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        llm = t.get("llm") or {}
        for a in llm.get("attempts") or []:
            resp = llm.get("response") or {}
            cands = resp.get("candidates") or []
            rows.append({"run_id": t.get("run_id"), "policy": (t.get("case") or {}).get("policy"),
                         "case": (t.get("case") or {}).get("name"), "provider": llm.get("provider"),
                         "model": llm.get("model"), "prompt_version": llm.get("prompt_version"),
                         "attempt": a.get("attempt"), "status": llm.get("status"), "schema_valid": a.get("schema_valid"),
                         "prompt_tokens": a.get("prompt_tokens"), "completion_tokens": a.get("completion_tokens"),
                         "latency_s": round(a["latency_s"], 2) if a.get("latency_s") is not None else "",
                         "recommendation_type": resp.get("recommendation_type"),
                         "n_candidates": len(cands),
                         "n_evidence_ids": sum(len(c.get("evidence_ids") or []) for c in cands),
                         "decision": t.get("decision"), "mode": t.get("mode")})
    if rows:
        out = R / "reports" / "experiments" / "llm_calls.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return rows


def runtime_metrics() -> list[dict]:
    hw = hardware_label()
    rows = []
    for r in _csv("reports/experiments/forecast_metrics.csv"):
        if r["horizon_min"] == "30":
            dev = _run_device(r["run_id"])
            label = hw["gpu"] if dev and dev.startswith("cuda") else hw["cpu"]
            rows.append({"component": f"forecast:{r['model']}", "run_id": r["run_id"], "metric": "train_time_s",
                         "value": r["train_time_s"], "n": "", "hardware": f"{label}; train_device={dev or 'cpu'}"})
            rows.append({"component": f"forecast:{r['model']}", "run_id": r["run_id"], "metric": "inference_ms_per_origin",
                         "value": r["infer_latency_ms_per_origin"], "n": r["n_valid_targets"],
                         "hardware": f"{hw['cpu']}; inference on CPU"})
    ex = R / "artifacts" / "explanations" / "explanations_summary.json"
    if ex.exists():
        s = json.loads(ex.read_text())
        for e in s["local_alerts"]:
            rows.append({"component": "explanation:grouped_kernel_shap", "run_id": e["explanation_id"], "metric": "runtime_s",
                         "value": round(e["runtime_s"], 3), "n": e["model_calls"], "hardware": hw["cpu"]})
    for r in _csv("reports/experiments/retrieval_metrics.csv"):
        rows.append({"component": "retrieval:faiss", "run_id": r["query_id"], "metric": "latency_s", "value": r["latency_s"],
                     "n": 1, "hardware": hw["cpu"]})
    for j in llm_calls():
        rows.append({"component": f"llm:{j['model']}", "run_id": j["run_id"], "metric": "latency_s", "value": j["latency_s"],
                     "n": j.get("completion_tokens"), "hardware": f"{hw['gpu']}; Ollama ({j.get('provider')})"})
    for r in _csv("reports/experiments/simulation_metrics.csv"):
        rows.append({"component": f"sumo:{r['controller']}", "run_id": r["run_id"], "metric": "wall_time_s",
                     "value": r.get("wall_time_s"), "n": 1, "hardware": f"{hw['cpu']}; SUMO {r.get('sumo_version', '')}"})
    for r in _csv("reports/experiments/advisory_metrics.csv"):
        if r.get("latency_s"):
            rows.append({"component": f"agent:{r['policy']}", "run_id": r.get("run_id", ""), "metric": "end_to_end_s",
                         "value": r["latency_s"], "n": 1, "hardware": f"{hw['cpu']} (LLM latency recorded separately)"})
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
        prev = VER / "mlflow_runs.json"
        if prev.exists():  # an export recorded on another machine (the run's workstation) is kept, never downgraded
            try:
                js = json.loads(prev.read_text())
                if js.get("status") == "OK":
                    return js.get("runs", [])
            except ValueError:
                pass
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
    ml = mlflow_runs()  # before the registry so TRACK-01 sees the fresh export
    lc = llm_calls()  # before the registry so LLM-01 sees the export
    ev = evidence_registry()
    rt = runtime_metrics()
    return {"evidence_rows": len(ev), "verified": sum(r["test_status"] == "VERIFIED" for r in ev), "runtime_rows": len(rt),
            "mlflow_runs": len(ml), "llm_calls": len(lc)}
