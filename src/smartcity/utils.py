"""Small shared helpers: hashing, JSON IO, run IDs, timestamps."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import subprocess
import uuid
from pathlib import Path

import numpy as np


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def utcnow_iso() -> str:
    return utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id(prefix: str) -> str:
    return f"{prefix}-{utcnow().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


class _Enc(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, (dt.datetime, dt.date)):
            return o.isoformat()
        if isinstance(o, Path):
            return str(o)
        return super().default(o)


def write_json(p: Path, obj) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, cls=_Enc))
    return p


def read_json(p: Path):
    return json.loads(Path(p).read_text())


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def environment_info() -> dict:
    info = {"python": platform.python_version(), "platform": platform.platform(), "machine": platform.machine()}
    for mod in ["torch", "torch_geometric", "torch_geometric_temporal", "xgboost", "lightgbm", "shap", "faiss",
                "sentence_transformers", "langgraph", "mlflow", "pandas", "polars", "geopandas", "fastapi",
                "streamlit", "pydantic", "sumolib", "traci"]:
        try:
            m = __import__(mod)
            info[mod] = getattr(m, "__version__", "installed")
        except Exception as exc:  # record, never hide
            info[mod] = f"UNAVAILABLE: {type(exc).__name__}: {exc}"[:200]
    return info
