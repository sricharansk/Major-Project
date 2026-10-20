"""Populate knowledge/source_registry.csv from downloaded documents (fetch logs) and project-authored files."""

from __future__ import annotations

import json
import shutil

from smartcity import settings
from smartcity.knowledge.corpus import file_sha, read_registry, write_registry

APPROVED = settings.ROOT / "knowledge" / "approved"

# Known metadata for documents fetched by the downloader (title/publisher/authority are curated here).
KNOWN = {
    "sumo_Simulation_Traffic_Lights.md": ("SUMO documentation: Traffic Lights", "software_documentation"),
    "sumo_TraCI_Change_Traffic_Lights_State.md": ("SUMO documentation: TraCI Change Traffic Lights State", "software_documentation"),
    "sumo_TraCI_Traffic_Lights_Value_Retrieval.md": ("SUMO documentation: TraCI Traffic Lights Value Retrieval", "software_documentation"),
    "sumo_Simulation_Output_Lane-_or_Edge-based_Traffic_Measures.md": ("SUMO documentation: Lane- or Edge-based Traffic Measures", "software_documentation"),
    "sumo_Simulation_Output_TripInfo.md": ("SUMO documentation: TripInfo output", "software_documentation"),
    "sumo_Tools_Trip.md": ("SUMO documentation: Trip tools (randomTrips)", "software_documentation"),
    "sumo_Simulation_Why_Vehicles_are_teleporting.md": ("SUMO documentation: Why vehicles are teleporting", "software_documentation"),
    "sumo_Demand_Routes_from_Observation_Points.md": ("SUMO documentation: Routes from Observation Points", "software_documentation"),
    "sumo_Simulation_Output_Summary.md": ("SUMO documentation: Summary output", "software_documentation"),
    "mutcd2009_part4d.htm": ("MUTCD 2009 Edition, Chapter 4D: Traffic Control Signal Features", "official_guidance"),
    "mutcd2009_part4e.htm": ("MUTCD 2009 Edition, Chapter 4E: Pedestrian Control Features", "official_guidance"),
    "fhwa_signal_timing_manual_2008.pdf": ("FHWA Traffic Signal Timing Manual (FHWA-HOP-08-024)", "official_guidance"),
    "fhwa_stm_ch5.htm": ("FHWA Traffic Signal Timing Manual, Chapter 5: Basic Signal Timing Procedure", "official_guidance"),
    "fhwa_stm_ch6.htm": ("FHWA Traffic Signal Timing Manual, Chapter 6: Coordination", "official_guidance"),
}

LICENSES = {
    "software_documentation": "Eclipse Public License 2.0 (SUMO repository docs)",
    "official_guidance": "U.S. federal government work (public domain, 17 U.S.C. 105)",
}


def populate() -> list[dict]:
    rows = {r["document_id"]: r for r in read_registry()}
    log = settings.path("raw") / "knowledge" / "fetch_log.jsonl"
    entries = [json.loads(line) for line in log.read_text().splitlines() if line.strip()] if log.exists() else []
    for e in entries:
        name = e["file"]
        if name not in KNOWN:
            continue
        src = settings.path("raw") / "knowledge" / name
        if not src.exists() or e.get("http_status") != 200:
            continue
        dst = APPROVED / name
        shutil.copyfile(src, dst)
        title, auth = KNOWN[name]
        url = e["url"]
        publisher = "Eclipse SUMO project" if name.startswith("sumo_") else "U.S. DOT Federal Highway Administration"
        rows[name.rsplit(".", 1)[0]] = {
            "document_id": name.rsplit(".", 1)[0], "title": title, "publisher": publisher, "source_url": url,
            "jurisdiction": "software (n/a)" if auth == "software_documentation" else "United States (federal guidance)",
            "document_type": "documentation" if auth == "software_documentation" else "guidance",
            "published_date": "v1_28_0 tag" if name.startswith("sumo_") else ("2009 edition" if "mutcd" in name else "2008"),
            "retrieved_at": e["retrieved_at_utc"], "license": LICENSES[auth], "sha256": file_sha(dst),
            "version": "1.28.0" if name.startswith("sumo_") else "as retrieved", "authority_level": auth,
            "local_path": str(dst.relative_to(settings.ROOT)), "approved": "yes",
        }
    pol = APPROVED / "project_signal_policy.md"
    rows["project_signal_policy"] = {
        "document_id": "project_signal_policy", "title": "Project-defined experimental signal-advisory policy (v1)",
        "publisher": "This project (MTech research prototype)", "source_url": "knowledge/approved/project_signal_policy.md",
        "jurisdiction": "project-internal (not a regulation)", "document_type": "experimental policy",
        "published_date": "2026-10-20", "retrieved_at": "2026-10-20", "license": "project (MIT)",
        "sha256": file_sha(pol), "version": "v1", "authority_level": "project_defined_experimental_policy",
        "local_path": str(pol.relative_to(settings.ROOT)), "approved": "yes"}
    for p in sorted(APPROVED.glob("simulation_evidence_*.md")):
        did = p.stem
        rows[did] = {"document_id": did, "title": f"Prior simulation evidence: {did}", "publisher": "This project",
                     "source_url": str(p.relative_to(settings.ROOT)), "jurisdiction": "SUMO testbed (simulation only)",
                     "document_type": "simulation result summary", "published_date": "generated",
                     "retrieved_at": "generated", "license": "project (MIT)", "sha256": file_sha(p), "version": "v1",
                     "authority_level": "prior_simulation_evidence", "local_path": str(p.relative_to(settings.ROOT)),
                     "approved": "yes"}
    out = sorted(rows.values(), key=lambda r: r["document_id"])
    write_registry(out)
    return out
