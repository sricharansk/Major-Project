"""Bounded background worker: claims QUEUED jobs from the persistent jobs table and runs each in a subprocess
(``python -m smartcity.cli job-exec``), capturing stdout, stderr, exit code, runtime and result."""

from __future__ import annotations

import json
import subprocess
import sys
import time

from smartcity.db import store


def run_once(timeout_s: int = 1800) -> bool:
    job = store.claim_job()
    if not job:
        return False
    t0 = time.time()
    cmd = [sys.executable, "-m", "smartcity.cli", "job-exec", job["kind"], json.dumps(job["params"])]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        result = None
        for line in reversed(p.stdout.splitlines()):
            if line.startswith("RESULT_JSON="):
                result = json.loads(line[len("RESULT_JSON="):])
                break
        status = "SUCCEEDED" if p.returncode == 0 else "FAILED"
        store.finish_job(job["job_id"], status, p.returncode, p.stdout, p.stderr,
                         {"runtime_s": round(time.time() - t0, 2), "result": result})
    except subprocess.TimeoutExpired as exc:
        store.finish_job(job["job_id"], "TIMEOUT", -1, str(exc.stdout or ""), str(exc.stderr or ""),
                         {"runtime_s": timeout_s})
    return True


def main():
    store.migrate()
    print("worker ready", flush=True)
    while True:
        if not run_once():
            time.sleep(2)


if __name__ == "__main__":
    main()
