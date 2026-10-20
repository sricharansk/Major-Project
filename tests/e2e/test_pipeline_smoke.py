"""End-to-end SOFTWARE smoke test on a small synthetic fixture written to a temporary project root.

The fixture is deterministic test data, NOT project observations; nothing it produces is reported as a result.
"""

import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]


def _fixture(root: Path):
    shutil.copytree(REPO / "configs", root / "configs")
    raw = root / "data" / "raw"
    (raw / "speeds").mkdir(parents=True)
    (raw / "speeds_links").mkdir(parents=True)
    # three links in a chain heading north along a line of longitude
    links = []
    for k in range(3):
        lat0 = 40.70 + 0.01 * k
        pts = " ".join(f"{lat0 + 0.002 * i:.5f},{-74.0:.5f}" for i in range(6))
        links.append({"link_id": str(100 + k), "link_name": f"TEST LINK {k}", "borough": "Manhattan", "owner": "test",
                      "link_points": pts, "encoded_poly_line": ""})
    with gzip.open(raw / "speeds_links" / "links_since_x.json.gz", "wt") as fh:
        json.dump(links, fh)
    rng = np.random.default_rng(0)
    rows = []
    start = np.datetime64("2026-03-02T00:00")
    for i in range(12 * 24 * 6):  # 6 days of 5-minute data
        t = start + np.timedelta64(5 * i, "m") + np.timedelta64(int(rng.integers(0, 240)), "s")
        hod = (i % 288) / 12
        for k in range(3):
            if rng.random() < 0.05:
                continue
            sp = 30 - 10 * np.exp(-((hod - 8) ** 2) / 2) + rng.normal(0, 1)
            rows.append({"id": str(k), "speed": f"{sp:.2f}", "travel_time": "60", "status": "0",
                         "data_as_of": str(t).replace(" ", "T") + ".000", "link_id": str(100 + k),
                         "borough": "Manhattan", "link_name": f"TEST LINK {k}", "owner": "test"})
    with gzip.open(raw / "speeds" / "speeds_fixture_p000.json.gz", "wt") as fh:
        json.dump(rows, fh)


def test_pipeline_runs_end_to_end(tmp_path):
    _fixture(tmp_path)
    env = dict(os.environ, SMARTCITY_ROOT=str(tmp_path), MLFLOW_TRACKING_URI=f"sqlite:///{tmp_path / 'mlflow.db'}")
    def cli(*args):
        r = subprocess.run([sys.executable, "-m", "smartcity.cli", *args], env=env, capture_output=True, text=True,
                           cwd=tmp_path)
        assert r.returncode == 0, f"{args}: {r.stdout[-2000:]}\n{r.stderr[-4000:]}"
        return r.stdout
    cli("data", "preprocess")
    out = cli("graph", "build")
    assert "3 nodes" in out and "2 edges" in out
    cli("graph", "validate")
    cli("features", "build", "--track", "operational")
    cli("train", "baselines")
    cli("train", "proposed", "--max-epochs", "1", "--windows-per-epoch", "64")
    cli("train", "proposed", "--variants", "ablation_no_gate", "--max-epochs", "1", "--windows-per-epoch", "64")
    cli("evaluate", "forecasts")
    out = cli("evaluate", "ablations", "--n-boot", "50")
    assert "ablation_no_gate" in out and "ablation_no_weather" in out
    assert (tmp_path / "reports" / "experiments" / "ablation_metrics.csv").exists()
    cli("uncertainty", "calibrate")
    assert (tmp_path / "artifacts" / "calibration" / "calibrator.json").exists()
    assert (tmp_path / "reports" / "experiments" / "forecast_metrics.csv").exists()
    cli("report", "export")
    assert (tmp_path / "reports" / "verification" / "mlflow_runs.json").exists()
