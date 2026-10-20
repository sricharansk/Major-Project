"""Run the full real-data pipeline stage by stage, logging exit status and wall time.

Usage (from the repository root, virtual environment active, Ollama serving qwen2.5:7b):
    python scripts/run_real_pipeline.py                 # all stages
    python scripts/run_real_pipeline.py --from "train proposed --track operational"
    python scripts/run_real_pipeline.py --skip simulation   # when SUMO is unavailable

Stops at the first failing stage. Appends one JSON line per stage to reports/verification/stage_log.jsonl and prints
the tail of the failing command's output so it can be pasted back for a fix. It never edits code or data itself.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "reports" / "verification" / "stage_log.jsonl"

STAGES = [
    "doctor",
    "data audit",
    "data preprocess",
    "graph build",
    "graph validate",
    "features build --track operational",
    "features build --track retrospective",
    "train baselines --track operational",
    "train proposed --track operational",
    ("train proposed --track operational --variants ablation_no_gate,ablation_no_weather,ablation_no_infrastructure,"
     "ablation_no_events,ablation_no_incidents"),
    "evaluate forecasts --track operational",
    "evaluate ablations --track operational",
    "uncertainty calibrate --track operational",
    "explain alerts --track operational",
    "train baselines --track retrospective",
    "train proposed --track retrospective --variants proposed",
    "evaluate forecasts --track retrospective",
    "rag fetch-docs",
    "rag build",
    "rag evaluate",
    "simulation prepare",
    "simulation evaluate",
    "agents evaluate",
    "report export",
    "paper sync",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default=None, help="first stage to run (exact stage string)")
    ap.add_argument("--skip", action="append", default=[], help="substring of stages to skip (repeatable)")
    a = ap.parse_args()
    stages = STAGES[STAGES.index(a.start):] if a.start else STAGES
    LOG.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    for stage in stages:
        if any(s in stage for s in a.skip):
            print(f"SKIP  {stage}")
            continue
        cmd = [sys.executable, "-m", "smartcity.cli", *stage.split()]
        print(f"RUN   {stage}", flush=True)
        t0 = time.time()
        r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
        rec = {"stage": stage, "returncode": r.returncode, "wall_s": round(time.time() - t0, 1),
               "finished_at": dt.datetime.now(dt.UTC).isoformat(), "stdout_tail": r.stdout[-3000:],
               "stderr_tail": r.stderr[-3000:]}
        with open(LOG, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(r.stdout[-1500:])
        if r.returncode != 0:
            print(f"FAIL  {stage} after {rec['wall_s']} s\n{r.stderr[-4000:]}")
            return r.returncode
        print(f"OK    {stage} in {rec['wall_s']} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
