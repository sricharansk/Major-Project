"""FastAPI endpoint tests (TestClient)."""

from fastapi.testclient import TestClient

from smartcity.api.app import app

client = TestClient(app)


def test_live():
    assert client.get("/health/live").json() == {"status": "live"}


def test_envelope_fields_and_states():
    r = client.get("/road-links").json()
    for k in ("run_id", "mode", "data_as_of", "generated_at", "source_status", "model_version", "artifact_status", "warnings"):
        assert k in r


def test_mutations_require_token(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "secret-test")
    assert client.post("/advisories", json={"link_id": "x"}).status_code == 401
    assert client.post("/advisories/abc/review", json={"reviewer": "a", "decision": "HUMAN_REJECTED"},
                       headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_review_cannot_approve_deployment(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "secret-test")
    r = client.post("/advisories/abc/review", json={"reviewer": "a", "decision": "APPROVED_FOR_DEPLOYMENT"},
                    headers={"Authorization": "Bearer secret-test"})
    assert r.status_code == 422


def test_live_endpoints_report_not_run_without_artifacts(monkeypatch):
    from smartcity.api import service

    monkeypatch.setattr(service, "live_latest", lambda: None)
    monkeypatch.setattr(service, "live_summary", lambda: None)
    r = client.get("/forecasts/live/latest").json()
    assert r["artifact_status"] == "NOT_RUN" and r["data"] is None
    r = client.get("/forecasts/live/metrics").json()
    assert r["artifact_status"] == "NOT_RUN"


def test_live_endpoints_serve_stored_batches(monkeypatch):
    from smartcity.api import service

    rec = {"mode": "LIVE", "forecast_batch_id": "live-1", "origin_utc": "2026-10-28T14:05:00+00:00", "warnings": ["w"],
           "links": []}
    summ = {"mode": "LIVE", "status": "OK", "n_scored": 3, "metrics_by_horizon": [{"horizon_minutes": 15, "n_scored": 3}],
            "note": "n"}
    monkeypatch.setattr(service, "live_latest", lambda: rec)
    monkeypatch.setattr(service, "live_summary", lambda: summ)
    r = client.get("/forecasts/live/latest").json()
    assert r["data"]["mode"] == "LIVE" and r["run_id"] == "live-1" and r["data_as_of"] == rec["origin_utc"]
    r = client.get("/forecasts/live/metrics").json()
    assert r["artifact_status"] == "AVAILABLE" and r["data"]["metrics_by_horizon"][0]["n_scored"] == 3
    assert "metrics_by_horizon" not in r["data"]["summary"]
