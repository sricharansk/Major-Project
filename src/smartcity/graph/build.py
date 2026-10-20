"""Directed road-link graph from NYC DOT link geometries.

Node  = monitored directed DOT road link (its geometry runs in the travel direction).
Edge  = A -> B when B plausibly receives traffic leaving A:
        * B's first point lies within ``endpoint_join_m`` of A's last point (topological continuity), and
        * the heading change between A's last bearing and B's first bearing is <= ``max_heading_change_deg``, and
        * B is not simply the opposite carriageway of A (reverse geometry).
Geometries that merely cross (mid-segment intersections, bridges over roads) are never connected because
only endpoint-to-startpoint proximity is considered.  Every candidate edge (accepted or rejected) is written
with its rationale to ``reports/data_audit/graph_edges.csv``.
"""

from __future__ import annotations

import csv
import math
import re

import numpy as np

from smartcity import settings
from smartcity.utils import sha256_json, write_json

EARTH_R = 6371000.0


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def bearing_deg(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


_PAIR = re.compile(r"(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)")


def parse_link_points(s: str | None) -> list[tuple[float, float]]:
    """DOT ``link_points`` is a space-separated 'lat,lon' list; truncated/garbled pairs are dropped."""
    if not s:
        return []
    pts = []
    for la, lo in _PAIR.findall(s):
        lat, lon = float(la), float(lo)
        if 40.4 < lat < 41.0 and -74.3 < lon < -73.6:  # NYC envelope sanity check
            pts.append((lat, lon))
    return pts


def decode_polyline(s: str | None) -> list[tuple[float, float]]:
    """Google encoded polyline (precision 1e-5)."""
    if not s:
        return []
    s = s.replace("\\\\", "\\")
    coords, idx, lat, lon = [], 0, 0, 0
    try:
        while idx < len(s):
            for which in (0, 1):
                shift = result = 0
                while True:
                    b = ord(s[idx]) - 63
                    idx += 1
                    result |= (b & 0x1F) << shift
                    shift += 5
                    if b < 0x20:
                        break
                d = ~(result >> 1) if result & 1 else result >> 1
                if which == 0:
                    lat += d
                else:
                    lon += d
            coords.append((lat / 1e5, lon / 1e5))
    except IndexError:
        pass
    return [(a, b) for a, b in coords if 40.4 < a < 41.0 and -74.3 < b < -73.6]


def link_geometry(row: dict) -> list[tuple[float, float]]:
    pts = parse_link_points(row.get("link_points"))
    if len(pts) < 2:
        pts = decode_polyline(row.get("encoded_poly_line"))
    return pts


def _end_bearing(pts, start: bool) -> float:
    # use a point ~ several vertices in to avoid noise from duplicated vertices
    if start:
        a = pts[0]
        b = next((p for p in pts[1:] if haversine_m(*a, *p) > 20), pts[-1])
        return bearing_deg(*a, *b)
    a = pts[-1]
    b = next((p for p in reversed(pts[:-1]) if haversine_m(*p, *a) > 20), pts[0])
    return bearing_deg(*b, *a)


def build_graph(links: list[dict], cfg: dict) -> dict:
    nodes, rejected_geom = [], []
    for row in links:
        pts = link_geometry(row)
        if len(pts) < 2:
            rejected_geom.append(row["link_id"])
            continue
        length = sum(haversine_m(*pts[i], *pts[i + 1]) for i in range(len(pts) - 1))
        nodes.append({
            "link_id": str(row["link_id"]), "link_name": row.get("link_name"), "borough": row.get("borough"),
            "owner": row.get("owner"), "points": pts, "length_m": length,
            "start": pts[0], "end": pts[-1],
            "start_bearing": _end_bearing(pts, True), "end_bearing": _end_bearing(pts, False),
        })
    nodes.sort(key=lambda n: n["link_id"])
    edges, audit = [], []
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            if i == j:
                continue
            d = haversine_m(*a["end"], *b["start"])
            if d > cfg["endpoint_join_m"] * 3:
                continue  # not a candidate at all
            turn = angle_diff(a["end_bearing"], b["start_bearing"])
            reverse = (haversine_m(*a["start"], *b["end"]) < cfg["endpoint_join_m"]
                       and angle_diff(a["end_bearing"], (b["start_bearing"] + 180) % 360) < 30)
            reasons = []
            if d > cfg["endpoint_join_m"]:
                reasons.append(f"endpoint gap {d:.0f}m > {cfg['endpoint_join_m']}m")
            if turn > cfg["max_heading_change_deg"]:
                reasons.append(f"heading change {turn:.0f} deg > {cfg['max_heading_change_deg']}")
            if reverse and cfg.get("reject_if_reverse_direction", True):
                reasons.append("opposite carriageway (reverse geometry)")
            accepted = not reasons
            audit.append({"src": a["link_id"], "dst": b["link_id"], "src_name": a["link_name"],
                          "dst_name": b["link_name"], "endpoint_gap_m": round(d, 1), "heading_change_deg": round(turn, 1),
                          "accepted": accepted,
                          "rationale": "end(src)->start(dst) continuity with compatible heading" if accepted
                          else "; ".join(reasons)})
            if accepted:
                edges.append((i, j))
    edge_index = np.array(edges, dtype=np.int64).T if edges else np.zeros((2, 0), dtype=np.int64)
    in_deg = np.bincount(edge_index[1], minlength=len(nodes)) if edges else np.zeros(len(nodes), int)
    out_deg = np.bincount(edge_index[0], minlength=len(nodes)) if edges else np.zeros(len(nodes), int)
    graph = {
        "link_ids": [n["link_id"] for n in nodes],
        "nodes": [{k: v for k, v in n.items() if k != "points"} for n in nodes],
        "edge_index": edge_index.tolist(),
        "n_nodes": len(nodes), "n_edges": int(edge_index.shape[1]),
        "isolated_nodes": [nodes[k]["link_id"] for k in range(len(nodes)) if in_deg[k] == 0 and out_deg[k] == 0],
        "rejected_no_geometry": rejected_geom,
        "config": cfg,
    }
    graph["graph_hash"] = sha256_json({"link_ids": graph["link_ids"], "edge_index": graph["edge_index"],
                                       "config": cfg})[:16]
    return {"graph": graph, "audit": audit, "geometries": {n["link_id"]: n["points"] for n in nodes}}


def run(link_ids_keep: list[str] | None = None) -> dict:
    from smartcity.preprocessing.raw import raw_dir, read_json_gz

    files = sorted(raw_dir("speeds_links").glob("*.json.gz"))
    if not files:
        raise SystemExit("NOT_RUN: no link geometry file (run fetch.py speed-links)")
    links = read_json_gz(files[-1])
    borough = settings.load("data")["study"]["borough"]
    links = [r for r in links if (r.get("borough") or "").lower() == borough.lower()]
    if link_ids_keep is not None:
        keep = set(map(str, link_ids_keep))
        links = [r for r in links if str(r["link_id"]) in keep]
    res = build_graph(links, settings.load("graph")["graph"])
    out = settings.path("processed")
    write_json(out / "graph.json", res["graph"])
    write_json(out / "link_geometries.json", res["geometries"])
    audit_path = settings.ROOT / "reports" / "data_audit" / "graph_edges.csv"
    with open(audit_path, "w", newline="", encoding="utf-8") as fh:
        if res["audit"]:
            w = csv.DictWriter(fh, fieldnames=list(res["audit"][0].keys()))
            w.writeheader()
            w.writerows(res["audit"])
    return res["graph"]
