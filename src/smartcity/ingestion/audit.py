"""Data-audit report generation from the raw audit responses, fetch logs and downloaded partitions.

Outputs (reports/data_audit/): source_inventory.csv, coverage_by_year.csv, link_coverage.csv, missingness.csv,
schema_validation.json, availability_audit.md; and data/manifests/source_manifest.json.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib

import numpy as np

from smartcity import settings
from smartcity.preprocessing.raw import fetch_log, raw_dir
from smartcity.utils import read_json, sha256_json, write_json

OUT = settings.ROOT / "reports" / "data_audit"
TERMS = "https://www.nyc.gov/home/terms-of-use.page (NYC Open Data terms of use)"

EXPECTED_COLUMNS = {
    "speeds": {"id", "speed", "travel_time", "status", "data_as_of", "link_id", "link_points", "borough", "link_name"},
    "volume": {"requestid", "boro", "yr", "m", "d", "hh", "mm", "vol", "segmentid", "street", "direction"},
    "events": {"event_id", "event_name", "start_date_time", "end_date_time", "event_type", "event_borough"},
    "events_hist": {"event_id", "event_name", "start_date_time", "end_date_time", "event_type", "event_borough"},
    "collisions": {"crash_date", "crash_time", "borough", "latitude", "longitude", "collision_id"},
    "sr311": {"unique_key", "created_date", "complaint_type", "borough", "latitude", "longitude"},
}

ROLE_LIMITS = {
    "speeds": ("Link speed targets (mph)", "Historical retention verified by server-side counts; includes outlier timestamps "
               "(e.g. 1930, 1978) excluded by the study window; links are DOT-selected corridors, many highways."),
    "volume": ("Sampled volume counts", "Sparse sampled ATR counts; not continuous observed volume; used for SUMO demand only."),
    "events": ("Current/scheduled permitted events", "Current feed only; does not reconstruct what was announced in the past."),
    "events_hist": ("Historical permitted events", "Free-text locations (no coordinates); permit announcement time unknown -> "
                    "retrospective track only."),
    "collisions": ("Retrospective incident context", "Publication lag of months (latest record far behind today); not a "
                   "live incident feed; retrospective track only."),
    "sr311": ("Infrastructure-related service requests", "Creation time is not publication time; used with a declared 24 h lag."),
}


def _audit_summary() -> dict:
    p = raw_dir("_audit") / "audit_summary.json"
    return read_json(p) if p.exists() else {"datasets": {}}


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    summ = _audit_summary()
    inventory, cov_rows, schema = [], [], {}
    for key, d in summ.get("datasets", {}).items():
        logs = fetch_log(key if key != "speeds" else "speeds")
        raw_files = [lg["file"] for lg in logs]
        raw_sha = sha256_json(sorted(lg["sha256"] for lg in logs))[:16] if logs else ""
        cols = set(d.get("columns") or [])
        exp = EXPECTED_COLUMNS.get(key, set())
        schema[key] = {"dataset_id": d.get("dataset_id"), "missing_expected_columns": sorted(exp - cols),
                       "n_columns": len(cols), "schema_hash": hashlib.sha256(",".join(sorted(cols)).encode()).hexdigest()[:16],
                       "valid": not (exp - cols) and not d.get("error")}
        cov = (d.get("coverage") or [{}])[0]
        years = [int(float(r["yr"])) for r in d.get("by_year", []) if r.get("yr") not in (None, "")]
        for r in d.get("by_year", []):
            if r.get("yr") in (None, ""):
                continue
            cov_rows.append({"source_id": key, "dataset_id": d.get("dataset_id"), "year": int(float(r["yr"])),
                             "record_count": int(float(r["n"]))})
        rows_downloaded = sum((lg.get("rows") or 0) for lg in logs)
        inventory.append({
            "source_id": key, "official_title": d.get("name"), "publisher": d.get("attribution") or "City of New York",
            "dataset_id": d.get("dataset_id"), "endpoint": f"https://data.cityofnewyork.us/resource/{d.get('dataset_id')}.json",
            "retrieved_at_utc": summ.get("generated_at_utc"),
            "source_updated_at": dt.datetime.fromtimestamp(d["rows_updated_at"], dt.timezone.utc).isoformat()
            if d.get("rows_updated_at") else None,
            "observation_min": cov.get("first_obs"), "observation_max": cov.get("last_obs"),
            "record_count": cov.get("n"), "years_present": ";".join(str(y) for y in sorted(years)),
            "units": "speed mph, travel_time seconds" if key == "speeds" else "",
            "license_or_terms_url": d.get("license_url") or TERMS, "schema_hash": schema[key]["schema_hash"],
            "raw_files": len(raw_files), "raw_rows_downloaded": rows_downloaded, "raw_sha256": raw_sha,
            "availability_status": "ERROR" if d.get("error") else ("DOWNLOADED" if logs else "AUDITED_NOT_DOWNLOADED"),
            "limitations": ROLE_LIMITS.get(key, ("", ""))[1]})
    # weather (Open-Meteo) and OSM
    for src, title, terms in (("weather", "Open-Meteo archive (ERA5-based reanalysis) + historical forecast API",
                               "https://open-meteo.com/en/terms (CC BY 4.0)"),
                              ("osm", "OpenStreetMap extracts via Overpass API", "https://www.openstreetmap.org/copyright (ODbL 1.0)")):
        logs = fetch_log(src)
        inventory.append({"source_id": src, "official_title": title, "publisher": "Open-Meteo" if src == "weather" else "OpenStreetMap contributors",
                          "dataset_id": "", "endpoint": ";".join(sorted({lg["url"].split("?")[0] for lg in logs})),
                          "retrieved_at_utc": logs[-1]["retrieved_at_utc"] if logs else None, "source_updated_at": None,
                          "observation_min": None, "observation_max": None, "record_count": None, "years_present": "",
                          "units": "precip mm, temp C, wind km/h" if src == "weather" else "WGS84",
                          "license_or_terms_url": terms, "schema_hash": "", "raw_files": len(logs),
                          "raw_rows_downloaded": None, "raw_sha256": sha256_json(sorted(lg["sha256"] for lg in logs))[:16] if logs else "",
                          "availability_status": "DOWNLOADED" if logs else "NOT_DOWNLOADED",
                          "limitations": "Reanalysis is not street-level measurement; archived forecasts lack issue times."
                          if src == "weather" else "Current topology applied to the 2026 study period."})
    pre = OUT / "speeds_preprocessing.json"
    if pre.exists():
        p = read_json(pre)
        for r in inventory:
            if r["source_id"] == "speeds":
                r["study_window_min_utc"], r["study_window_max_utc"] = p.get("ts_min_utc"), p.get("ts_max_utc")
    keys = list(dict.fromkeys(k for r in inventory for k in r))
    with open(OUT / "source_inventory.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(inventory)
    with open(OUT / "coverage_by_year.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["source_id", "dataset_id", "year", "record_count"])
        w.writeheader()
        w.writerows(cov_rows)
    write_json(OUT / "schema_validation.json", schema)
    link_cov = _link_coverage()
    manifest = {"generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "sources": {}}
    for src_dir in sorted(settings.path("raw").iterdir()):
        if src_dir.is_dir():
            logs = fetch_log(src_dir.name)
            manifest["sources"][src_dir.name] = {"n_fetches": len(logs),
                                                 "files": {lg["file"]: lg["sha256"] for lg in logs}}
    manifest["manifest_hash"] = sha256_json(manifest["sources"])[:16]
    write_json(settings.ROOT / "data" / "manifests" / "source_manifest.json", manifest)
    return {"inventory": inventory, "link_coverage": link_cov, "manifest_hash": manifest["manifest_hash"]}


def _link_coverage() -> list[dict]:
    gp = settings.path("processed") / "speed_grid.npz"
    if not gp.exists():
        return []
    g = np.load(gp)
    sp = g["speed"]
    obs = np.isfinite(sp)
    rows = []
    for j, lid in enumerate(g["link_ids"].tolist()):
        o = obs[:, j]
        runs, cur = [], 0
        for v in ~o:
            cur = cur + 1 if v else 0
            runs.append(cur)
        rows.append({"link_id": lid, "observed_fraction": round(float(o.mean()), 4),
                     "longest_gap_steps": int(max(runs) if runs else 0),
                     "mean_speed_mph": round(float(np.nanmean(sp[:, j])), 2) if o.any() else None,
                     "n_obs_bins": int(o.sum())})
    with open(OUT / "link_coverage.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # missingness per month
    times = g["times_utc"]
    months = np.array([dt.datetime.fromtimestamp(int(t), dt.timezone.utc).strftime("%Y-%m") for t in times])
    mrows = []
    for m in sorted(set(months)):
        sel = months == m
        mrows.append({"month_utc": m, "grid_steps": int(sel.sum()), "observed_fraction_all_links": round(float(obs[sel].mean()), 4)})
    with open(OUT / "missingness.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(mrows[0].keys()))
        w.writeheader()
        w.writerows(mrows)
    return rows
