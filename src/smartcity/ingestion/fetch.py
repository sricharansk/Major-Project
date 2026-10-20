"""Bounded, resumable, provenance-preserving downloader for the project's public sources.

This module deliberately uses only the Python standard library so the exact same code can
run on any machine that has network access to the sources (the project's cloud container
was network-restricted, so raw downloads were executed on the author's workstation).

Every HTTP response is stored verbatim (gzip-compressed) under ``data/raw/<source>/`` and
recorded in ``data/raw/<source>/fetch_log.jsonl`` with request URL, parameters, retrieval
time (UTC), HTTP status, row count and SHA-256 of the uncompressed body.  Re-running a
command skips partitions whose raw file already exists (checkpoint/resume).

Usage (run from the repository root)::

    python src/smartcity/ingestion/fetch.py audit
    python src/smartcity/ingestion/fetch.py speeds --start 2025-10-01 --end 2026-10-19 --borough Manhattan
    python src/smartcity/ingestion/fetch.py speed-links
    python src/smartcity/ingestion/fetch.py weather --start 2025-10-01 --end 2026-10-19
    python src/smartcity/ingestion/fetch.py collisions --start 2025-10-01 --end 2026-10-19
    python src/smartcity/ingestion/fetch.py volume --start-year 2024
    python src/smartcity/ingestion/fetch.py events
    python src/smartcity/ingestion/fetch.py sr311 --start 2025-10-01 --end 2026-10-19
    python src/smartcity/ingestion/fetch.py osm --bbox 40.700,-74.020,40.880,-73.900 --name manhattan_major
    python src/smartcity/ingestion/fetch.py hf-model
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "smartcity-traffic-research/0.1 (MTech academic project; contact via GitHub sricharansk)"
SOCRATA = "https://data.cityofnewyork.us"
RAW = Path(os.environ.get("SMARTCITY_RAW_DIR", "data/raw"))
PAGE = 50000

# Candidate NYC Open Data datasets (identities are verified by the `audit` command).
DATASETS = {
    "speeds": "i4gi-tjb9",  # DOT Traffic Speeds NBE
    "volume": "7ym2-wayt",  # Automated Traffic Volume Counts
    "events": "tvpp-9vvx",  # NYC Permitted Event Information (current)
    "events_hist": "bkfu-528j",  # NYC Permitted Event Information - Historical (candidate)
    "collisions": "h9gi-nx95",  # Motor Vehicle Collisions - Crashes
    "sr311": "erm2-nwe9",  # 311 Service Requests from 2010 to Present (candidate)
}

# 311 complaint types plausibly related to road capacity / signal operation.
SR311_TYPES = [
    "Traffic Signal Condition",
    "Street Condition",
    "Street Light Condition",
    "Blocked Driveway",
    "Illegal Parking",
    "Highway Condition",
    "Bridge Condition",
]


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get(url: str, params: dict | None = None, *, timeout: int = 180, retries: int = 6) -> tuple[int, bytes, str]:
    """GET with exponential backoff.  Returns (status, body, final_url).

    Dropped connections mid-body surface as http.client.IncompleteRead (an HTTPException, not a URLError), so the
    whole HTTPException family and socket-level OSError are retried as network errors.

    A non-retryable HTTP error is raised; an empty JSON list is a *valid* empty result and
    is returned like any other body, so callers can distinguish it from failures.
    """
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    token = os.environ.get("SOCRATA_APP_TOKEN")
    if token and SOCRATA in url:
        headers["X-App-Token"] = token
    delay = 2.0
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read(), url
        except urllib.error.HTTPError as exc:  # 4xx/5xx
            body = exc.read()
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                print(f"  HTTP {exc.code}; retry in {delay:.0f}s", file=sys.stderr)
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"HTTP {exc.code} for {url}: {body[:500]!r}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, OSError) as exc:
            if attempt < retries - 1:
                print(f"  network error {exc}; retry in {delay:.0f}s", file=sys.stderr)
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError("unreachable")


def store(source: str, name: str, url: str, params: dict | None, status: int, body: bytes, rows: int | None) -> Path:
    out_dir = RAW / source
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.json.gz"
    with gzip.open(path, "wb") as fh:
        fh.write(body)
    record = {
        "source": source,
        "file": path.name,
        "url": url,
        "params": params,
        "retrieved_at_utc": utcnow(),
        "http_status": status,
        "rows": rows,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    with open(out_dir / "fetch_log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return path


def socrata_paged(source: str, dataset: str, name: str, params: dict) -> int:
    """Download one partition with stable ordering and offset paging.  Resumable per page."""
    total = 0
    offset = 0
    page_no = 0
    while True:
        part = f"{name}_p{page_no:03d}"
        path = RAW / source / f"{part}.json.gz"
        if path.exists():
            with gzip.open(path, "rb") as fh:
                n = len(json.loads(fh.read()))
        else:
            p = dict(params, **{"$limit": PAGE, "$offset": offset})
            status, body, url = http_get(f"{SOCRATA}/resource/{dataset}.json", p)
            data = json.loads(body)
            if not isinstance(data, list):
                raise RuntimeError(f"unexpected response for {part}: {str(data)[:300]}")
            n = len(data)
            store(source, part, url, p, status, body, n)
        total += n
        if n < PAGE:
            return total
        offset += PAGE
        page_no += 1


def date_partitions(start: str, end: str, days: int):
    s = dt.date.fromisoformat(start)
    e = dt.date.fromisoformat(end)
    today = dt.datetime.now(dt.timezone.utc).date()
    if e > today:  # never request future observations
        print(f"end {e} is after today {today}; clamping", file=sys.stderr)
        e = today
    while s < e:
        n = min(s + dt.timedelta(days=days), e)
        yield s, n
        s = n


# --------------------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------------------

def cmd_audit(args) -> None:
    """Metadata + server-side coverage aggregates for every candidate dataset."""
    out = RAW / "_audit"
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"generated_at_utc": utcnow(), "datasets": {}}
    time_cols = {
        "speeds": "data_as_of",
        "volume": None,  # split yr/m/d columns; audited by yr
        "events": "start_date_time",
        "events_hist": "start_date_time",
        "collisions": "crash_date",
        "sr311": "created_date",
    }
    for key, ds in DATASETS.items():
        entry: dict = {"dataset_id": ds}
        try:
            status, body, url = http_get(f"{SOCRATA}/api/views/{ds}.json")
            store("_audit", f"meta_{ds}", url, None, status, body, None)
            meta = json.loads(body)
            entry.update(
                name=meta.get("name"),
                attribution=meta.get("attribution"),
                license=(meta.get("license") or {}).get("name"),
                license_url=(meta.get("license") or {}).get("termsLink"),
                rows_updated_at=meta.get("rowsUpdatedAt"),
                view_last_modified=meta.get("viewLastModified"),
                columns=[c.get("fieldName") for c in meta.get("columns", [])],
            )
            tcol = time_cols[key]
            if tcol and tcol in entry["columns"]:
                p = {"$select": f"min({tcol}) AS first_obs, max({tcol}) AS last_obs, count(*) AS n"}
                status, body, url = http_get(f"{SOCRATA}/resource/{ds}.json", p, timeout=300)
                store("_audit", f"coverage_{ds}", url, p, status, body, None)
                entry["coverage"] = json.loads(body)
                p = {"$select": f"date_extract_y({tcol}) AS yr, count(*) AS n", "$group": "yr", "$order": "yr"}
                try:
                    status, body, url = http_get(f"{SOCRATA}/resource/{ds}.json", p, timeout=600)
                    store("_audit", f"by_year_{ds}", url, p, status, body, None)
                    entry["by_year"] = json.loads(body)
                except Exception as exc:  # report, never assume
                    entry["by_year_error"] = str(exc)
            if key == "volume" and "yr" in entry["columns"]:
                p = {"$select": "yr, count(*) AS n", "$group": "yr", "$order": "yr"}
                status, body, url = http_get(f"{SOCRATA}/resource/{ds}.json", p, timeout=600)
                store("_audit", f"by_year_{ds}", url, p, status, body, None)
                entry["by_year"] = json.loads(body)
            if key == "speeds":
                p = {"$select": "borough, count(*) AS n", "$where": "data_as_of >= '2025-01-01'", "$group": "borough"}
                status, body, url = http_get(f"{SOCRATA}/resource/{ds}.json", p, timeout=600)
                store("_audit", f"by_borough_{ds}", url, p, status, body, None)
                entry["by_borough_since_2025"] = json.loads(body)
        except Exception as exc:
            entry["error"] = str(exc)
        report["datasets"][key] = entry
        print(key, ds, entry.get("name"), entry.get("coverage"), entry.get("error", ""))
    (out / "audit_summary.json").write_text(json.dumps(report, indent=2))


def cmd_speed_links(args) -> None:
    """One row per link with geometry (link_points / polyline) from the most recent records."""
    ds = DATASETS["speeds"]
    p = {
        "$select": "link_id, max(link_name) AS link_name, max(borough) AS borough, max(owner) AS owner, "
        "max(transcom_id) AS transcom_id, max(link_points) AS link_points, "
        "max(encoded_poly_line) AS encoded_poly_line, count(*) AS n, min(data_as_of) AS first_obs, "
        "max(data_as_of) AS last_obs",
        "$where": f"data_as_of >= '{args.since}'",
        "$group": "link_id",
        "$order": "link_id",
        "$limit": 5000,
    }
    status, body, url = http_get(f"{SOCRATA}/resource/{ds}.json", p, timeout=600)
    rows = json.loads(body)
    store("speeds_links", f"links_since_{args.since}", url, p, status, body, len(rows))
    print(f"{len(rows)} links")


def cmd_speeds(args) -> None:
    ds = DATASETS["speeds"]
    cols = "id, speed, travel_time, status, data_as_of, link_id, borough, link_name, owner"
    total = 0
    for s, e in date_partitions(args.start, args.end, args.days):
        where = f"data_as_of >= '{s}T00:00:00' AND data_as_of < '{e}T00:00:00'"
        if args.borough:
            where += f" AND borough = '{args.borough}'"
        name = f"speeds_{(args.borough or 'all').lower()}_{s}_{e}"
        n = socrata_paged("speeds", ds, name, {"$select": cols, "$where": where, "$order": "data_as_of, id"})
        total += n
        print(f"{name}: {n} rows (cum {total})", flush=True)


def cmd_collisions(args) -> None:
    ds = DATASETS["collisions"]
    for s, e in date_partitions(args.start, args.end, 31):
        where = f"crash_date >= '{s}T00:00:00' AND crash_date < '{e}T00:00:00'"
        if args.borough:
            where += f" AND borough = '{args.borough.upper()}'"
        name = f"collisions_{(args.borough or 'all').lower()}_{s}_{e}"
        n = socrata_paged("collisions", ds, name, {"$where": where, "$order": "collision_id"})
        print(f"{name}: {n}", flush=True)


def cmd_volume(args) -> None:
    ds = DATASETS["volume"]
    this_year = dt.date.today().year
    for yr in range(args.start_year, this_year + 1):
        where = f"yr = '{yr}'"
        if args.boro:
            where += f" AND boro = '{args.boro}'"
        name = f"volume_{(args.boro or 'all').lower()}_{yr}"
        n = socrata_paged("volume", ds, name, {"$where": where, "$order": ":id"})
        print(f"{name}: {n}", flush=True)


def cmd_events(args) -> None:
    for key in ("events", "events_hist"):
        ds = DATASETS[key]
        where = f"event_borough = '{args.borough}'" if args.borough else None
        params = {"$order": ":id"}
        if where:
            params["$where"] = where
        if key == "events_hist" and args.since:
            params["$where"] = (where + " AND " if where else "") + f"start_date_time >= '{args.since}'"
        try:
            n = socrata_paged(key, ds, f"{key}_{(args.borough or 'all').lower()}", params)
            print(f"{key}: {n}")
        except Exception as exc:
            print(f"{key}: FAILED {exc}")
            with open(RAW / "_audit" / "failures.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"source": key, "error": str(exc), "at": utcnow()}) + "\n")


def cmd_sr311(args) -> None:
    ds = DATASETS["sr311"]
    types = ", ".join(f"'{t}'" for t in SR311_TYPES)
    cols = ("unique_key, created_date, closed_date, agency, complaint_type, descriptor, status, "
            "borough, latitude, longitude, incident_address, resolution_action_updated_date")
    for s, e in date_partitions(args.start, args.end, 31):
        where = (f"created_date >= '{s}T00:00:00' AND created_date < '{e}T00:00:00' "
                 f"AND complaint_type in ({types})")
        if args.borough:
            where += f" AND borough = '{args.borough.upper()}'"
        name = f"sr311_{(args.borough or 'all').lower()}_{s}_{e}"
        n = socrata_paged("sr311", ds, name, {"$select": cols, "$where": where, "$order": "unique_key"})
        print(f"{name}: {n}", flush=True)


def cmd_weather(args) -> None:
    """Open-Meteo reanalysis archive (retrospective) and historical-forecast (operational proxy)."""
    hourly = "temperature_2m,precipitation,rain,snowfall,weather_code,wind_speed_10m,visibility,cloud_cover"
    end = min(dt.date.fromisoformat(args.end), dt.datetime.now(dt.timezone.utc).date())
    base = {
        "latitude": args.lat,
        "longitude": args.lon,
        "start_date": args.start,
        "end_date": str(end),
        "hourly": hourly,
        "timezone": "UTC",
    }
    for name, url in (
        ("archive", "https://archive-api.open-meteo.com/v1/archive"),
        ("historical_forecast", "https://historical-forecast-api.open-meteo.com/v1/forecast"),
    ):
        status, body, full = http_get(url, base, timeout=300)
        store("weather", f"{name}_{args.start}_{end}", full, base, status, body, None)
        print(name, status, len(body))


def cmd_osm(args) -> None:
    s, w, n, e = (float(x) for x in args.bbox.split(","))
    if args.kind == "major":
        filt = '["highway"~"^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary)$"]'
    else:
        filt = '["highway"~"^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|residential|unclassified|living_street)$"]'
    query = f"""[out:xml][timeout:300];
(
  way{filt}({s},{w},{n},{e});
  node["highway"="traffic_signals"]({s},{w},{n},{e});
);
(._;>;);
out meta;"""
    for endpoint in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
        try:
            status, body, url = http_get(endpoint, {"data": query}, timeout=400, retries=3)
            out_dir = RAW / "osm"
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{args.name}.osm"
            path.write_bytes(body)
            rec = {"source": "osm", "file": path.name, "url": endpoint, "query": query, "bbox": args.bbox,
                   "retrieved_at_utc": utcnow(), "http_status": status, "bytes": len(body),
                   "sha256": hashlib.sha256(body).hexdigest(), "license": "ODbL 1.0 (c) OpenStreetMap contributors"}
            with open(out_dir / "fetch_log.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(f"osm {args.name}: {len(body)} bytes from {endpoint}")
            return
        except Exception as exc:
            print(f"overpass {endpoint} failed: {exc}", file=sys.stderr)
    raise SystemExit("all Overpass endpoints failed")


def cmd_hf_model(args) -> None:
    repo = args.repo
    api = f"https://huggingface.co/api/models/{repo}"
    status, body, _ = http_get(api)
    info = json.loads(body)
    sha = info.get("sha")
    files = [s["rfilename"] for s in info.get("siblings", [])]
    wanted = [f for f in files if f in {
        "config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "vocab.txt",
        "special_tokens_map.json", "modules.json", "sentence_bert_config.json",
        "config_sentence_transformers.json", "1_Pooling/config.json", "README.md"}]
    out = RAW.parent / "models" / repo.replace("/", "__")
    manifest = {"repo": repo, "revision": sha, "retrieved_at_utc": utcnow(), "files": {}}
    for f in wanted:
        status, data, _ = http_get(f"https://huggingface.co/{repo}/resolve/{sha}/{f}", timeout=600)
        p = out / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        manifest["files"][f] = hashlib.sha256(data).hexdigest()
        print(f, len(data))
    (out / "download_manifest.json").write_text(json.dumps(manifest, indent=2))


def cmd_url(args) -> None:
    """Fetch an approved knowledge document (official guidance) verbatim with provenance."""
    status, body, url = http_get(args.url, timeout=600)
    out_dir = RAW / "knowledge"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / args.name
    path.write_bytes(body)
    rec = {"source": "knowledge", "file": args.name, "url": url, "retrieved_at_utc": utcnow(),
           "http_status": status, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    with open(out_dir / "fetch_log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(args.name, len(body))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("audit").set_defaults(fn=cmd_audit)
    p = sub.add_parser("speed-links"); p.add_argument("--since", default="2025-01-01"); p.set_defaults(fn=cmd_speed_links)
    p = sub.add_parser("speeds"); p.add_argument("--start", required=True); p.add_argument("--end", required=True)
    p.add_argument("--borough", default="Manhattan"); p.add_argument("--days", type=int, default=7); p.set_defaults(fn=cmd_speeds)
    p = sub.add_parser("collisions"); p.add_argument("--start", required=True); p.add_argument("--end", required=True)
    p.add_argument("--borough", default="Manhattan"); p.set_defaults(fn=cmd_collisions)
    p = sub.add_parser("volume"); p.add_argument("--start-year", type=int, default=2024); p.add_argument("--boro", default="Manhattan")
    p.set_defaults(fn=cmd_volume)
    p = sub.add_parser("events"); p.add_argument("--borough", default="Manhattan"); p.add_argument("--since", default="2025-01-01")
    p.set_defaults(fn=cmd_events)
    p = sub.add_parser("sr311"); p.add_argument("--start", required=True); p.add_argument("--end", required=True)
    p.add_argument("--borough", default="Manhattan"); p.set_defaults(fn=cmd_sr311)
    p = sub.add_parser("weather"); p.add_argument("--start", required=True); p.add_argument("--end", required=True)
    p.add_argument("--lat", type=float, default=40.7549); p.add_argument("--lon", type=float, default=-73.9840)
    p.set_defaults(fn=cmd_weather)
    p = sub.add_parser("osm"); p.add_argument("--bbox", required=True, help="south,west,north,east")
    p.add_argument("--name", required=True); p.add_argument("--kind", choices=["major", "all"], default="major")
    p.set_defaults(fn=cmd_osm)
    p = sub.add_parser("hf-model"); p.add_argument("--repo", default="sentence-transformers/all-MiniLM-L6-v2")
    p.set_defaults(fn=cmd_hf_model)
    p = sub.add_parser("url"); p.add_argument("--url", required=True); p.add_argument("--name", required=True)
    p.set_defaults(fn=cmd_url)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
