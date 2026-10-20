"""Readers for the immutable raw responses written by ``smartcity.ingestion.fetch``."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import polars as pl

from smartcity import settings


def raw_dir(source: str) -> Path:
    return settings.path("raw") / source


def fetch_log(source: str) -> list[dict]:
    p = raw_dir(source) / "fetch_log.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_socrata(source: str, prefix: str | None = None) -> pl.DataFrame:
    """Concatenate all JSON pages of a source.  Columns are kept as strings (schema validated later)."""
    files = sorted(raw_dir(source).glob("*.json.gz"))
    if prefix:
        files = [f for f in files if f.name.startswith(prefix)]
    frames = []
    for f in files:
        with gzip.open(f, "rb") as fh:
            rows = json.loads(fh.read())
        if rows:
            df = pl.DataFrame(rows, infer_schema_length=None).with_columns(pl.all().cast(pl.Utf8))
            frames.append(df.with_columns(pl.lit(f.name).alias("_raw_file")))
    if not frames:
        return pl.DataFrame()
    return pl.concat(frames, how="diagonal_relaxed")


def read_json_gz(path: Path):
    with gzip.open(path, "rb") as fh:
        return json.loads(fh.read())
