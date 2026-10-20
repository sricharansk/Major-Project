"""Directed road-link graph from NYC DOT link geometries.

Node  = monitored directed DOT road link (its geometry runs in the travel direction).
Edge  = A -> B when B plausibly receives traffic leaving A, by one of two rules:
        1. endpoint continuity: B's first point lies within ``endpoint_join_m`` of A's last point, the heading change
           between A's last bearing and B's first bearing is <= ``max_heading_change_deg``, and B is not simply the
           opposite carriageway of A (reverse geometry);
        2. corridor continuity: A and B are on the same signed corridor (same name stem and direction token, e.g.
           "FDR N"), B's start lies downstream of A's end (ahead along A's end bearing) within ``corridor_join_m``
           with a compatible heading, and B is the nearest such link.  DOT links do not tile a highway, so consecutive
           monitored segments can be separated by unmonitored stretches; this rule connects them explicitly;
        3. named-endpoint continuity: DOT link names are "<road> <dir> <from> - <to>"; when the <to> label of A and the
           <from> label of B share a distinctive token (a street number, "Catherine Slip", "ganservoort", "GWB"), the
           two links are not opposite directions, B's start lies ahead of A's start and within ``named_join_m`` of
           A's end, and the headings are compatible, A -> B is accepted.  This rule exists because the published
           ``link_points`` polylines do not reliably reach the named end of a link (on the 2026 Manhattan set, "FDR S
           63rd - 25th St" is 1.5 km of geometry for a 3 km segment and ends 1.5 km short of "FDR S 25th St -
           Catherine Slip"), so geometry-only rules miss joins that the names state explicitly.
Geometries that merely cross (mid-segment intersections, bridges over roads) are never connected because
only endpoint-to-startpoint relations are considered.  Every candidate edge (accepted or rejected) is written
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


_DIR = {"N": "N", "S": "S", "E": "E", "W": "W", "NB": "N", "SB": "S", "EB": "E", "WB": "W"}


def corridor_key(name: str | None) -> tuple[str, str] | None:
    """('fdr', 'N') from 'FDR N 25th - 42nd'; None when the name carries no direction token.

    The stem is everything before the first direction token; names without one (bridges named by endpoints,
    free text) get no corridor and can only be joined by endpoint continuity."""
    if not name:
        return None
    toks = re.split(r"\s+", name.strip())
    for i, t in enumerate(toks[1:], start=1):
        d = _DIR.get(t.upper().strip(".,"))
        if d:
            stem = " ".join(toks[:i]).lower()
            return (stem, d) if stem else None
    return None


_GENERIC = {"st", "street", "ave", "avenue", "av", "rd", "road", "dr", "drive", "hwy", "highway", "pkwy", "expwy",
            "at", "@", "and", "the", "of", "side", "plaza", "toll", "portal", "manhattan", "outbound", "inbound",
            "lower", "upper", "level", "ny", "nj", "tube", "north", "south", "east", "west", "n", "s", "e", "w",
            "nb", "sb", "eb", "wb"}
_ORD = re.compile(r"^[nsew]?(\d+)(st|nd|rd|th)?$")


def _label_tokens(label: str) -> set[str]:
    """Distinctive tokens of an endpoint label: ordinals become bare numbers ('63rd' -> '63', 'E116TH' -> '116'),
    generic road words and direction tokens are dropped."""
    out = set()
    for t in re.split(r"[\s,./()]+", label.lower()):
        t = t.strip("-:;'\"")
        if not t or t in _GENERIC:
            continue
        m = _ORD.match(t)
        out.add(m.group(1) if m else t)
    return out


def endpoint_labels(name: str | None) -> tuple[set[str], set[str]]:
    """(from_tokens, to_tokens) parsed from a DOT link name of the form '<road> <dir> <from> - <to>'.

    The last two ' - ' separated parts are the endpoints ('FDR N - TBB E 116TH STREET - MANHATTAN TRUSS' -> '116TH
    STREET', 'MANHATTAN TRUSS').  A corridor prefix on the from part ('FDR N Catherine Slip') is removed; the road
    stem itself is kept as a token when it is not generic ('BBT E Manhattan Portal' -> {'bbt'}).  Names without a
    ' - ' separator give two empty sets and can never be joined by this rule."""
    if not name or " - " not in name:
        return set(), set()
    parts = [x.strip() for x in re.split(r"\s+-\s+", name.strip()) if x.strip()]
    if len(parts) < 2:
        return set(), set()
    frm, to = parts[-2], parts[-1]
    key = corridor_key(name)
    if key and len(parts) == 2:
        stem_dir = re.compile(r"^" + re.escape(key[0]) + r"\s+\S+\s*", re.I)
        frm_stripped = stem_dir.sub("", frm, count=1)
        frm_tokens = _label_tokens(frm_stripped) if frm_stripped.strip() else set()
        frm_tokens |= {t for t in _label_tokens(key[0]) if t not in frm_tokens} if not frm_tokens else set()
    else:
        frm_tokens = _label_tokens(frm)
    return frm_tokens, _label_tokens(to)


def _opposite(a_key, b_key) -> bool:
    """True when both links carry direction tokens that are opposite (N/S or E/W): never joined by name."""
    if not a_key or not b_key:
        return False
    return {a_key[1], b_key[1]} in ({"N", "S"}, {"E", "W"})


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
    for n in nodes:
        n["corridor"] = corridor_key(n["link_name"])
        n["from_tokens"], n["to_tokens"] = endpoint_labels(n["link_name"])
    corridor_join = float(cfg.get("corridor_join_m", 0) or 0)
    named_join = float(cfg.get("named_join_m", 0) or 0)
    corridor_turn = float(cfg.get("corridor_max_heading_change_deg", cfg["max_heading_change_deg"]))
    # rule 2 candidates: nearest downstream same-corridor successor per link
    successor: dict[int, tuple[int, float, float]] = {}
    if corridor_join > 0:
        for i, a in enumerate(nodes):
            if not a["corridor"]:
                continue
            best = None
            for j, b in enumerate(nodes):
                if i == j or b["corridor"] != a["corridor"]:
                    continue
                d = haversine_m(*a["end"], *b["start"])
                if d > corridor_join:
                    continue
                ahead = angle_diff(bearing_deg(*a["end"], *b["start"]), a["end_bearing"]) if d > 1 else 0.0
                turn = angle_diff(a["end_bearing"], b["start_bearing"])
                if ahead <= 90 and turn <= corridor_turn and (best is None or d < best[1]):
                    best = (j, d, turn)
            if best:
                successor[i] = best
    # rule 3 candidates: named-endpoint continuity (to-label of A shares a distinctive token with from-label of B)
    named: dict[tuple[int, int], str] = {}
    if named_join > 0:
        for i, a in enumerate(nodes):
            if not a["to_tokens"]:
                continue
            for j, b in enumerate(nodes):
                if i == j or not b["from_tokens"]:
                    continue
                shared = a["to_tokens"] & b["from_tokens"]
                if not shared or _opposite(a["corridor"], b["corridor"]):
                    continue
                d = haversine_m(*a["end"], *b["start"])
                if d > named_join:
                    continue
                d0 = haversine_m(*a["start"], *b["start"])
                ahead = angle_diff(bearing_deg(*a["start"], *b["start"]), a["start_bearing"]) if d0 > 1 else 0.0
                turn = angle_diff(a["end_bearing"], b["start_bearing"])
                if ahead <= 90 and turn <= corridor_turn:
                    named[(i, j)] = ",".join(sorted(shared))
    edges, audit = [], []
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            if i == j:
                continue
            d = haversine_m(*a["end"], *b["start"])
            if d > max(cfg["endpoint_join_m"] * 3, corridor_join) and (i, j) not in named:
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
            rationale = "end(src)->start(dst) continuity with compatible heading" if accepted else "; ".join(reasons)
            if not accepted and successor.get(i, (None,))[0] == j:
                accepted = True
                rationale = (f"corridor continuity: same signed corridor {a['corridor'][0]!r} {a['corridor'][1]}, "
                             f"nearest downstream segment {d:.0f}m ahead (endpoint rule failed: {'; '.join(reasons)})")
            elif not accepted and (i, j) in named:
                accepted = True
                rationale = (f"named-endpoint continuity: shared endpoint token(s) {named[(i, j)]!r}, start of dst "
                             f"{d:.0f}m from end of src (endpoint rule failed: {'; '.join(reasons)})")
            audit.append({"src": a["link_id"], "dst": b["link_id"], "src_name": a["link_name"],
                          "dst_name": b["link_name"], "endpoint_gap_m": round(d, 1), "heading_change_deg": round(turn, 1),
                          "src_corridor": " ".join(a["corridor"]) if a["corridor"] else "",
                          "dst_corridor": " ".join(b["corridor"]) if b["corridor"] else "",
                          "src_to_label": " ".join(sorted(a["to_tokens"])), "dst_from_label": " ".join(sorted(b["from_tokens"])),
                          "accepted": accepted, "rationale": rationale})
            if accepted:
                edges.append((i, j))
    edge_index = np.array(edges, dtype=np.int64).T if edges else np.zeros((2, 0), dtype=np.int64)
    in_deg = np.bincount(edge_index[1], minlength=len(nodes)) if edges else np.zeros(len(nodes), int)
    out_deg = np.bincount(edge_index[0], minlength=len(nodes)) if edges else np.zeros(len(nodes), int)
    graph = {
        "link_ids": [n["link_id"] for n in nodes],
        "nodes": [{k: (" ".join(v) if k == "corridor" and v else sorted(v) if isinstance(v, set) else v)
                   for k, v in n.items() if k != "points"} for n in nodes],
        "n_edges_endpoint_rule": sum(1 for r in audit if r["accepted"] and r["rationale"].startswith("end(src)")),
        "n_edges_corridor_rule": sum(1 for r in audit if r["accepted"] and r["rationale"].startswith("corridor")),
        "n_edges_named_rule": sum(1 for r in audit if r["accepted"] and r["rationale"].startswith("named")),
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
    # one row per node: the link set behind the graph, with the parsed name parts and the resulting degrees
    g = res["graph"]
    src, dst = g["edge_index"]
    with open(audit_path.with_name(f"{borough.lower()}_links.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["link_id", "link_name", "owner", "length_m", "corridor", "from_label",
                                           "to_label", "out_degree", "in_degree"])
        w.writeheader()
        for k, n in enumerate(g["nodes"]):
            w.writerow({"link_id": n["link_id"], "link_name": n["link_name"], "owner": n["owner"],
                        "length_m": round(n["length_m"], 1), "corridor": n["corridor"] or "",
                        "from_label": " ".join(n["from_tokens"]), "to_label": " ".join(n["to_tokens"]),
                        "out_degree": src.count(k), "in_degree": dst.count(k)})
    return res["graph"]
