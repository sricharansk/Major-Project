"""FastAPI application.  Long-running work (advisories, simulations) goes to the persistent job table and is
executed by ``python -m smartcity.api.worker``; HTTP handlers never run SUMO or training synchronously."""

from __future__ import annotations

import datetime as dt
import os
import shutil
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from smartcity import settings
from smartcity.api import service
from smartcity.db import store

app = FastAPI(title="Smart-city traffic advisory API (research prototype)", version="0.1.0")


def require_token(authorization: str | None = Header(default=None)):
    token = os.environ.get("API_AUTH_TOKEN")
    if not token:
        raise HTTPException(503, "API_AUTH_TOKEN not configured: mutation endpoints disabled")
    if authorization != f"Bearer {token}":
        raise HTTPException(401, "invalid token")


def envelope(payload, run_id=None, warnings=None, artifact_status="AVAILABLE", data_as_of=None):
    sel = service.selected() or {}
    return {"run_id": run_id, "mode": os.environ.get("APP_MODE", "replay").upper(), "data_as_of": data_as_of,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source_status": "see /sources/status", "model_version": sel.get("proposed_run_id", "NOT_TRAINED"),
            "artifact_status": artifact_status, "warnings": warnings or [], "data": payload}


@app.get("/health/live")
def live():
    return {"status": "live"}


@app.get("/health/ready")
def ready():
    checks = {"database": store.ready()}
    checks["model"] = {"ok": service.selected() is not None}
    checks["knowledge_index"] = {"ok": (settings.ROOT / "knowledge" / "indexes" / "knowledge.faiss").exists()}
    from smartcity.simulation.sumo_runner import binary

    checks["sumo"] = {"ok": shutil.which(binary()) is not None or os.path.exists(binary())}
    try:
        from smartcity.agents.llm import OllamaClient

        info = OllamaClient().info()
        checks["llm"] = {"ok": info["available"], **info}
    except Exception as exc:
        checks["llm"] = {"ok": False, "error": str(exc)[:200]}
    ok = all(c.get("ok") for c in checks.values())
    if not ok:
        raise HTTPException(503, detail=checks)
    return checks


@app.get("/sources/status")
def sources():
    return envelope(service.source_status())


@app.get("/road-links")
def road_links():
    links = service.road_links()
    return envelope(links, artifact_status="AVAILABLE" if links else "NOT_RUN")


@app.get("/road-links/{link_id}")
def road_link(link_id: str):
    for n in service.road_links():
        if n["link_id"] == link_id:
            return envelope(n)
    raise HTTPException(404, "unknown link")


@app.get("/road-links/{link_id}/observations")
def observations(link_id: str, start: str | None = None, end: str | None = None, limit: int = 500):
    try:
        rows = store.link_observations(link_id, start, end, min(limit, 5000))
    except Exception as exc:
        raise HTTPException(503, f"database unavailable: {exc}") from exc
    return envelope(rows, warnings=["observed values (REPLAY of historical public data)"])


class ForecastIn(BaseModel):
    link_id: str
    origin_utc: str | None = None


@app.post("/forecasts")
def create_forecast(body: ForecastIn):
    try:
        fr = service.forecast(body.link_id, body.origin_utc)
    except FileNotFoundError:
        raise HTTPException(409, "NOT_TRAINED")
    except KeyError:
        raise HTTPException(404, "unknown link")
    try:
        store.save_forecast(fr)
    except Exception as exc:
        fr["warnings"].append(f"not persisted: {exc}"[:200])
    return envelope(fr, run_id=fr["run_id"], data_as_of=str(fr["data_as_of_utc"]), warnings=fr["warnings"])


@app.get("/forecasts/{forecast_id}")
def get_forecast(forecast_id: str):
    from sqlalchemy import text

    with store.engine().connect() as con:
        r = con.execute(text("SELECT payload FROM forecast_runs WHERE forecast_id=:f"), {"f": forecast_id}).first()
    if not r:
        raise HTTPException(404, "unknown forecast")
    return envelope(r[0])


class ExplainIn(BaseModel):
    link_id: str
    origin_utc: str | None = None
    horizon_minutes: int = 30


@app.post("/explanations")
def create_explanation(body: ExplainIn, _=Depends(require_token)):
    job_id = f"job-{uuid.uuid4().hex[:10]}"
    store.enqueue(job_id, "explanation", body.model_dump())
    return envelope({"job_id": job_id, "status": "QUEUED"})


@app.get("/explanations/{explanation_id}")
def get_explanation(explanation_id: str):
    s = settings.ROOT / "artifacts" / "explanations" / "explanations_summary.json"
    if not s.exists():
        raise HTTPException(404, "NOT_RUN")
    import json

    summ = json.loads(s.read_text())
    for e in summ.get("local_alerts", []):
        if e["explanation_id"] == explanation_id:
            return envelope(e)
    raise HTTPException(404, "unknown explanation")


class SearchIn(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    k: int = 8


@app.post("/retrieval/search")
def search(body: SearchIn):
    from smartcity.rag.retriever import Retriever

    try:
        r = Retriever()
    except FileNotFoundError:
        raise HTTPException(409, "knowledge index NOT_RUN")
    status, ev = r.evidence(body.query)
    return envelope({"status": status, "evidence": [e.model_dump() for e in ev],
                     "all_hits": [e.model_dump() for e in r.search(body.query, k=body.k)]},
                    warnings=["retrieved text is untrusted reference material"])


class AdvisoryIn(BaseModel):
    link_id: str
    origin_utc: str | None = None


@app.post("/advisories")
def create_advisory(body: AdvisoryIn, _=Depends(require_token)):
    job_id = f"job-{uuid.uuid4().hex[:10]}"
    store.enqueue(job_id, "advisory", body.model_dump())
    return envelope({"job_id": job_id, "status": "QUEUED"})


@app.get("/advisories/{advisory_id}")
def get_advisory(advisory_id: str):
    p = settings.ROOT / "artifacts" / "agent_traces" / f"{advisory_id}.json"
    if not p.exists():
        raise HTTPException(404, "unknown advisory")
    import json

    return envelope(json.loads(p.read_text()), run_id=advisory_id)


class SimIn(BaseModel):
    scenario: str
    controller: str
    seeds: list[int] = [1]


@app.post("/simulations")
def create_sim(body: SimIn, _=Depends(require_token)):
    job_id = f"job-{uuid.uuid4().hex[:10]}"
    store.enqueue(job_id, "simulation", body.model_dump())
    return envelope({"job_id": job_id, "status": "QUEUED"})


@app.get("/jobs/{job_id}")
def job(job_id: str):
    j = store.get_job(job_id)
    if not j:
        raise HTTPException(404, "unknown job")
    return envelope(j)


class ReviewIn(BaseModel):
    reviewer: str = Field(min_length=1, max_length=100)
    decision: str = Field(pattern="^(HUMAN_APPROVED_FOR_SIMULATION|HUMAN_REJECTED|REQUEST_REVISION)$")
    comment: str = ""


@app.post("/advisories/{advisory_id}/review")
def review(advisory_id: str, body: ReviewIn, _=Depends(require_token)):
    p = settings.ROOT / "artifacts" / "agent_traces" / f"{advisory_id}.json"
    if not p.exists():
        raise HTTPException(404, "unknown advisory")
    rid = store.save_review(advisory_id, body.reviewer, body.decision, body.comment)
    return envelope({"review_id": rid, "advisory_id": advisory_id, "decision": body.decision,
                     "note": "Approval is for SIMULATION only; this prototype never approves real deployment."})


@app.get("/experiments")
def experiments():
    return envelope(service.experiments())


@app.get("/evidence/status")
def evidence():
    return envelope(service.evidence_status())
