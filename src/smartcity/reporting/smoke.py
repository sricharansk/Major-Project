"""Service smoke checks that write machine-readable evidence to reports/verification/*_smoke.json.

Each check records what was actually executed and its outcome (OK / FAILED / BLOCKED with the reason); nothing is
inferred from configuration alone.  `python -m smartcity.cli verify smoke [--docker-build]`.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

from smartcity import settings
from smartcity.utils import write_json

VER = settings.ROOT / "reports" / "verification"


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def api_smoke() -> dict:
    from fastapi.testclient import TestClient

    from smartcity.api.app import app

    client = TestClient(app)
    checks = []
    for path in ("/health/live", "/health/ready", "/sources/status", "/road-links", "/experiments", "/evidence/status"):
        t0 = time.time()
        r = client.get(path)
        checks.append({"endpoint": path, "status_code": r.status_code, "latency_ms": round((time.time() - t0) * 1000, 1)})
    os.environ["API_AUTH_TOKEN"] = "smoke-token"
    checks.append({"endpoint": "POST /advisories (no token)", "status_code": client.post("/advisories", json={"link_id": "x"}).status_code,
                   "expected": 401})
    checks.append({"endpoint": "POST /advisories/{id}/review APPROVED_FOR_DEPLOYMENT", "expected": 422,
                   "status_code": client.post("/advisories/abc/review", json={"reviewer": "a", "decision": "APPROVED_FOR_DEPLOYMENT"},
                                              headers={"Authorization": "Bearer smoke-token"}).status_code})
    os.environ.pop("API_AUTH_TOKEN", None)
    ok = all(c["status_code"] == c.get("expected", 200) for c in checks if c["endpoint"] != "/health/ready")
    ready = next(c for c in checks if c["endpoint"] == "/health/ready")
    out = {"status": "OK" if ok else "FAILED", "checked_at": _now(), "checks": checks,
           "readiness": "ready" if ready["status_code"] == 200 else "not ready (503: a dependency is unavailable, reported as such)"}
    write_json(VER / "api_smoke.json", out)
    return out


def db_smoke() -> dict:
    from smartcity.db import store

    out: dict = {"checked_at": _now()}
    try:
        if not store.ready().get("ok") and not store.migrate():
            out.update(status="BLOCKED", reason=f"database unavailable: {store.ready()}")
            write_json(VER / "db_smoke.json", out)
            return out
        store.migrate()
        out["ready"] = store.ready()
        graph = {"graph_hash": "smoke", "nodes": [{"link_id": "SMOKE-1", "link_name": "smoke", "borough": "Manhattan",
                                                    "owner": "smoke", "length_m": 100.0}]}
        geoms = {"SMOKE-1": [(40.7000, -74.0000), (40.7010, -74.0000)]}
        out["upsert_rows"] = store.load_road_links(graph, geoms)
        near = store.links_near(40.7005, -74.0001, 50)
        out["spatial_query_hit"] = any(r["link_id"] == "SMOKE-1" for r in near)
        jid = f"smoke-{int(time.time())}"
        store.enqueue(jid, "noop", {"x": 1})
        store.finish_job(jid, "SUCCEEDED", 0, "out", "", {"ok": True})
        out["job_roundtrip"] = store.get_job(jid)["status"] == "SUCCEEDED"
        from sqlalchemy import text

        with store.engine().begin() as con:
            con.execute(text("DELETE FROM road_links WHERE link_id = 'SMOKE-1'"))
            con.execute(text("DELETE FROM jobs WHERE job_id = :j"), {"j": jid})
        out["status"] = "OK" if out["spatial_query_hit"] and out["job_roundtrip"] else "FAILED"
    except Exception as exc:  # noqa: BLE001 - the whole point is to record whatever failed
        out.update(status="FAILED", error=f"{type(exc).__name__}: {exc}"[:500])
    write_json(VER / "db_smoke.json", out)
    return out


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def dashboard_smoke(timeout_s: int = 90) -> dict:
    port = _free_port()
    cmd = [sys.executable, "-m", "streamlit", "run", str(settings.ROOT / "src" / "smartcity" / "dashboard" / "app.py"),
           "--server.headless", "true", "--server.port", str(port), "--browser.gatherUsageStats", "false"]
    out: dict = {"checked_at": _now(), "command": " ".join(cmd[1:]), "port": port}
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=settings.ROOT)
    t0 = time.time()
    code = None
    try:
        while time.time() - t0 < timeout_s:
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=3) as r:
                    code = r.status
                    body = r.read().decode()[:50]
                if code == 200:
                    out.update(health_status=code, health_body=body, startup_s=round(time.time() - t0, 1))
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
                        out["index_status"] = r.status
                    break
            except Exception:  # noqa: BLE001 - not up yet
                time.sleep(1)
    finally:
        proc.terminate()
        try:
            log = proc.communicate(timeout=10)[0]
        except subprocess.TimeoutExpired:
            proc.kill()
            log = proc.communicate()[0]
    out["log_tail"] = (log or "")[-1500:]
    out["status"] = "OK" if out.get("health_status") == 200 and out.get("index_status") == 200 else "FAILED"
    write_json(VER / "dashboard_smoke.json", out)
    return out


def docker_smoke(build: bool = False, timeout_s: int = 900) -> dict:
    out: dict = {"checked_at": _now()}
    env = dict(os.environ)
    env.setdefault("POSTGRES_PASSWORD", "smoke-only")
    env.setdefault("POSTGRES_USER", "smartcity")
    env.setdefault("DATABASE_URL", "postgresql+psycopg://smartcity:smoke-only@postgres:5432/smartcity")

    def run(cmd, t):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=t, cwd=settings.ROOT, env=env, check=False)
            return {"cmd": " ".join(cmd), "returncode": r.returncode, "tail": (r.stdout + r.stderr)[-1500:]}
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return {"cmd": " ".join(cmd), "returncode": None, "tail": f"{type(exc).__name__}: {exc}"[:300]}

    if not shutil.which("docker"):
        out.update(status="BLOCKED", reason="docker CLI not installed")
        write_json(VER / "docker_smoke.json", out)
        return out
    out["docker_version"] = run(["docker", "--version"], 20)
    out["daemon"] = run(["docker", "info", "--format", "{{.ServerVersion}}"], 30)
    out["compose_config"] = run(["docker", "compose", "config", "-q"], 60)
    if out["daemon"]["returncode"] != 0:
        out.update(status="BLOCKED", reason="Docker daemon not reachable")
    elif out["compose_config"]["returncode"] != 0:
        out.update(status="FAILED", reason="compose config invalid")
    elif build:
        out["compose_build"] = run(["docker", "compose", "build"], timeout_s)
        if out["compose_build"]["returncode"] == 0:
            out["images"] = run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}} {{.Size}}", "--filter", "reference=smartcity*"], 30)
            out["status"] = "OK"
        else:
            tail = out["compose_build"]["tail"].lower()
            limited = "toomanyrequests" in tail or "too many requests" in tail or "rate limit" in tail or " 429 " in tail
            out.update(status="BLOCKED" if limited else "FAILED",
                       reason="registry rate limit (HTTP 429) while pulling the base image" if limited else "build failed (see tail)")
    else:
        out.update(status="PARTIAL", reason="config validated; build not requested (--docker-build)")
    write_json(VER / "docker_smoke.json", out)
    return out


def run_all(docker_build: bool = False) -> dict:
    VER.mkdir(parents=True, exist_ok=True)
    return {"api": api_smoke()["status"], "db": db_smoke()["status"], "dashboard": dashboard_smoke()["status"],
            "docker": docker_smoke(docker_build)["status"]}
