"""Configuration loading (YAML files under configs/ plus environment variables)."""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("SMARTCITY_ROOT", Path(__file__).resolve().parents[2]))
CONFIG_DIR = ROOT / "configs"


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    with open(CONFIG_DIR / f"{name}.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def config_hash(*names: str) -> str:
    blob = json.dumps({n: load(n) for n in names}, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def path(key: str) -> Path:
    p = ROOT / load("project")["paths"][key]
    p.mkdir(parents=True, exist_ok=True)
    return p


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def database_url() -> str:
    return env("DATABASE_URL", "postgresql+psycopg://smartcity:smartcity@localhost:5432/smartcity")
