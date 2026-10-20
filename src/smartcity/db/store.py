"""PostgreSQL/PostGIS persistence: migrations, idempotent upserts, spatial queries, job table.

All SQL uses bound parameters (never string-concatenated untrusted input).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from smartcity import settings

_ENGINE: Engine | None = None


def engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(settings.database_url(), pool_pre_ping=True)
    return _ENGINE


def migrate() -> list[str]:
    applied = []
    with engine().begin() as con:
        for f in sorted((settings.ROOT / "migrations").glob("*.sql")):
            con.exec_driver_sql(f.read_text())
            applied.append(f.name)
    return applied


def ready() -> dict:
    try:
        with engine().connect() as con:
            v = con.execute(text("SELECT postgis_version()")).scalar()
            m = con.execute(text("SELECT array_agg(version) FROM schema_migrations")).scalar()
        return {"ok": True, "postgis": v, "migrations": m}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


def load_road_links(graph: dict, geoms: dict):
    rows = []
    for n in graph["nodes"]:
        pts = geoms[n["link_id"]]
        wkt = "LINESTRING(" + ", ".join(f"{lon} {lat}" for lat, lon in pts) + ")"
        rows.append({"id": n["link_id"], "name": n.get("link_name"), "b": n.get("borough"), "o": n.get("owner"),
                     "len": n["length_m"], "wkt": wkt, "gh": graph["graph_hash"]})
    with engine().begin() as con:
        con.execute(text("""INSERT INTO road_links (link_id, link_name, borough, owner, length_m, geom, graph_hash)
                            VALUES (:id, :name, :b, :o, :len, ST_GeomFromText(:wkt, 4326), :gh)
                            ON CONFLICT (link_id) DO UPDATE SET link_name=EXCLUDED.link_name, geom=EXCLUDED.geom,
                            length_m=EXCLUDED.length_m, graph_hash=EXCLUDED.graph_hash"""), rows)
    return len(rows)


def load_observations(clean_parquet: Path, link_ids: set[str], batch: int = 50_000) -> int:
    df = pl.read_parquet(clean_parquet).filter(pl.col("link_id").is_in(list(link_ids)))
    n = 0
    sql = text("""INSERT INTO traffic_observations (link_id, source_timestamp_local, event_time, speed_mph,
                  travel_time_s, status, valid, raw_file) VALUES (:link_id, :data_as_of, :ts_utc, :speed_mph,
                  :travel_time_s, :status, :valid, :_raw_file) ON CONFLICT (link_id, event_time) DO NOTHING""")
    cols = ["link_id", "data_as_of", "ts_utc", "speed_mph", "travel_time_s", "status", "valid", "_raw_file"]
    with engine().begin() as con:
        for i in range(0, df.height, batch):
            part = df.slice(i, batch).select(cols).to_dicts()
            con.execute(sql, part)
            n += len(part)
    return n


def load_fetch_logs() -> int:
    raw = settings.path("raw")
    n = 0
    with engine().begin() as con:
        for log in raw.glob("*/fetch_log.jsonl"):
            for line in log.read_text().splitlines():
                if not line.strip():
                    continue
                e = json.loads(line)
                con.execute(text("""INSERT INTO source_fetches (source_id, raw_file, url, params, retrieved_at,
                                    http_status, rows, sha256) VALUES (:s, :f, :u, CAST(:p AS JSONB), :t, :h, :r, :sha)
                                    ON CONFLICT DO NOTHING"""),
                            {"s": e.get("source"), "f": e.get("file"), "u": e.get("url"),
                             "p": json.dumps(e.get("params")), "t": e.get("retrieved_at_utc"),
                             "h": e.get("http_status"), "r": e.get("rows"), "sha": e.get("sha256")})
                n += 1
    return n


def links_near(lat: float, lon: float, radius_m: float) -> list[dict]:
    with engine().connect() as con:
        rs = con.execute(text("""SELECT link_id, link_name, ST_Distance(geom::geography,
                                 ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m
                                 FROM road_links WHERE ST_DWithin(geom::geography,
                                 ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :r) ORDER BY dist_m"""),
                         {"lat": lat, "lon": lon, "r": radius_m})
        return [dict(r._mapping) for r in rs]


def link_observations(link_id: str, start=None, end=None, limit: int = 2000) -> list[dict]:
    q = "SELECT event_time, speed_mph, travel_time_s, valid FROM traffic_observations WHERE link_id = :l"
    p: dict = {"l": link_id, "lim": limit}
    if start:
        q += " AND event_time >= :s"
        p["s"] = start
    if end:
        q += " AND event_time < :e"
        p["e"] = end
    q += " ORDER BY event_time DESC LIMIT :lim"
    with engine().connect() as con:
        return [dict(r._mapping) for r in con.execute(text(q), p)]


def save_forecast(fr: dict):
    with engine().begin() as con:
        con.execute(text("""INSERT INTO forecast_runs (forecast_id, run_id, mode, model_version, graph_hash,
                            feature_schema_hash, origin_utc, data_as_of, payload) VALUES (:forecast_id, :run_id, :mode,
                            :model_version, :graph_hash, :feature_schema_hash, :origin_utc, :data_as_of_utc,
                            CAST(:payload AS JSONB)) ON CONFLICT DO NOTHING"""),
                    {**{k: fr.get(k) for k in ("forecast_id", "run_id", "mode", "model_version", "graph_hash",
                                                "feature_schema_hash", "origin_utc", "data_as_of_utc")},
                     "payload": json.dumps(fr, default=str)})
        for h in fr["horizons"]:
            con.execute(text("""INSERT INTO forecast_values VALUES (:f, :l, :h, :p, :lo, :hi, :ob)
                                ON CONFLICT DO NOTHING"""),
                        {"f": fr["forecast_id"], "l": fr["link_id"], "h": h["horizon_minutes"],
                         "p": h["predicted_speed_mph"], "lo": h.get("lower_mph"), "hi": h.get("upper_mph"),
                         "ob": h.get("observed_speed_mph")})


def save_agent_run(state: dict):
    with engine().begin() as con:
        con.execute(text("""INSERT INTO agent_runs (run_id, thread_id, mode, decision, decision_reasons, state,
                            started_at, finished_at) VALUES (:r, :t, :m, :d, CAST(:dr AS JSONB), CAST(:s AS JSONB),
                            :a, :b) ON CONFLICT (run_id) DO UPDATE SET decision=EXCLUDED.decision,
                            decision_reasons=EXCLUDED.decision_reasons, state=EXCLUDED.state, finished_at=EXCLUDED.finished_at"""),
                    {"r": state["run_id"], "t": state.get("thread_id"), "m": state.get("mode"),
                     "d": state.get("decision"), "dr": json.dumps(state.get("decision_reasons", [])),
                     "s": json.dumps(state, default=str), "a": state.get("started_at"), "b": state.get("finished_at")})
        for c in state.get("constraint_results", []):
            con.execute(text("""INSERT INTO constraint_checks VALUES (:c, :r, CAST(:k AS JSONB), :p, CAST(:rs AS JSONB))
                                ON CONFLICT DO NOTHING"""),
                        {"c": c["candidate_id"], "r": state["run_id"], "k": json.dumps(c["checks"]), "p": c["passed"],
                         "rs": json.dumps(c["reasons"])})


def save_review(advisory_id: str, reviewer: str, decision: str, comment: str) -> int:
    with engine().begin() as con:
        return con.execute(text("""INSERT INTO human_reviews (advisory_id, reviewer, decision, comment)
                                   VALUES (:a, :r, :d, :c) RETURNING review_id"""),
                           {"a": advisory_id, "r": reviewer, "d": decision, "c": comment}).scalar()


def save_sim_run(r: dict):
    with engine().begin() as con:
        con.execute(text("""INSERT INTO simulation_runs (sim_run_id, scenario, controller, seed, status, sumo_version,
                            network_hash, demand_hash, metrics) VALUES (:run_id, :scenario, :controller, :seed, :status,
                            :sumo_version, :network_hash, :demand_hash, CAST(:m AS JSONB)) ON CONFLICT DO NOTHING"""),
                    {**{k: r.get(k) for k in ("run_id", "scenario", "controller", "seed", "status", "sumo_version",
                                              "network_hash", "demand_hash")}, "m": json.dumps(r.get("metrics"))})


# ---- persistent job queue (survives API restarts) ------------------------------------------------

def enqueue(job_id: str, kind: str, params: dict):
    with engine().begin() as con:
        con.execute(text("INSERT INTO jobs (job_id, kind, params) VALUES (:j, :k, CAST(:p AS JSONB))"),
                    {"j": job_id, "k": kind, "p": json.dumps(params)})


def claim_job() -> dict | None:
    with engine().begin() as con:
        r = con.execute(text("""UPDATE jobs SET status='RUNNING', started_at=now() WHERE job_id = (
                                SELECT job_id FROM jobs WHERE status='QUEUED' ORDER BY created_at
                                FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING job_id, kind, params""")).first()
        return dict(r._mapping) if r else None


def finish_job(job_id: str, status: str, exit_code: int, stdout: str, stderr: str, result: dict | None):
    with engine().begin() as con:
        con.execute(text("""UPDATE jobs SET status=:s, finished_at=now(), exit_code=:e, stdout=:o, stderr=:er,
                            result=CAST(:r AS JSONB) WHERE job_id=:j"""),
                    {"s": status, "e": exit_code, "o": stdout[-20000:], "er": stderr[-20000:],
                     "r": json.dumps(result, default=str), "j": job_id})


def get_job(job_id: str) -> dict | None:
    with engine().connect() as con:
        r = con.execute(text("SELECT * FROM jobs WHERE job_id=:j"), {"j": job_id}).first()
        return dict(r._mapping) if r else None


def to_float(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)
