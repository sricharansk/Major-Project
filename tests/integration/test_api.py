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
