"""PostGIS integration: migrations, idempotent upsert, spatial query, persistent job queue."""

import pytest

from smartcity.db import store


@pytest.fixture(scope="module")
def db():
    if not store.ready().get("ok") and not store.migrate():
        pytest.skip("database unavailable")
    store.migrate()
    assert store.ready()["ok"]
    return store


def test_spatial_query_and_upsert(db):
    graph = {"graph_hash": "test", "nodes": [{"link_id": "TEST-1", "link_name": "fixture", "borough": "Manhattan",
                                               "owner": "test", "length_m": 100.0}]}
    geoms = {"TEST-1": [(40.7000, -74.0000), (40.7010, -74.0000)]}
    assert db.load_road_links(graph, geoms) == 1
    assert db.load_road_links(graph, geoms) == 1  # idempotent
    near = db.links_near(40.7005, -74.0001, 50)
    assert any(r["link_id"] == "TEST-1" for r in near)
    assert not any(r["link_id"] == "TEST-1" for r in db.links_near(40.80, -73.90, 50))


def test_job_queue_roundtrip(db):
    import uuid

    jid = f"test-{uuid.uuid4().hex[:8]}"
    db.enqueue(jid, "noop", {"x": 1})
    j = None
    for _ in range(100):  # claim until our job (other queued jobs may exist)
        j = db.claim_job()
        if j is None or j["job_id"] == jid:
            break
        db.finish_job(j["job_id"], "FAILED", 1, "", "claimed by test", None)
    assert j and j["job_id"] == jid
    db.finish_job(jid, "SUCCEEDED", 0, "out", "", {"ok": True})
    assert db.get_job(jid)["status"] == "SUCCEEDED"


def teardown_module(module):
    from sqlalchemy import text

    with store.engine().begin() as con:  # remove fixture rows so they never mix with project data
        con.execute(text("DELETE FROM road_links WHERE link_id = 'TEST-1'"))
        con.execute(text("DELETE FROM jobs WHERE job_id LIKE 'test-%'"))
