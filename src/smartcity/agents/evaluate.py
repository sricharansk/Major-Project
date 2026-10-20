"""Advisory-workflow evaluation: required scenario cases and the grounding / constraint / simulation ablations.

Cases (all REPLAY on held-out test origins unless labelled SIMULATION):
  routine_rush_hour      : weekday rush-hour origin, typical conditions
  rain_period            : test origin during a wet weather code (if one exists in the test partition)
  event_context          : origin with active permitted events (retrospective track info, reported only)
  stale_data_stress      : same as routine but the feed is treated as frozen for 30 min (stress test)
  wide_interval_stress   : forces an interval width above the calibrated gate (stress test)
  insufficient_evidence  : retrieval query outside the corpus scope -> DEFER_EVIDENCE expected
  mapped_corridor_alert  : largest predicted drop on a link with a reviewed DOT->SUMO mapping (if any)
Policies: full system; LLM without retrieval; RAG without constraint layer; RAG+constraints without simulation.
"""

from __future__ import annotations

import csv
import json
import time

import numpy as np
import pandas as pd

from smartcity import settings
from smartcity.agents.llm import make_client
from smartcity.agents.workflow import Toolkit, build_graph, run_case
from smartcity.utils import write_json


def pick_cases(data, preds_test: np.ndarray, mapped_links: list[str]) -> list[dict]:
    test = data.origins["test"]
    ts = pd.to_datetime(data.times[test], unit="s", utc=True).tz_convert("America/New_York")
    hours, dow = np.asarray(ts.hour), np.asarray(ts.dayofweek)
    ids = data.meta["link_ids"]
    traffic_g = data.meta["groups"].index("traffic")
    ok_obs = data.M[test, :, traffic_g]
    cases = []

    def first(mask, n=None):
        idx = np.where(mask)[0]
        if not idx.size:
            return None
        k = int(idx[len(idx) // 2])
        if n is None:  # choose the link with the largest predicted 30-min drop at that origin
            drop = (data.mu - preds_test[k, min(1, preds_test.shape[1] - 1)]) / data.mu
            drop = np.where(ok_obs[k], drop, -np.inf)
            n = int(np.argmax(drop))
        return int(test[k]), n

    rush = (dow < 5) & (((hours >= 7) & (hours < 10)) | ((hours >= 16) & (hours < 19)))
    c = first(rush)
    if c:
        cases.append({"name": "routine_rush_hour", "origin": c[0], "link_index": c[1]})
    wet_idx = [i for i, nm in enumerate(data.meta["feature_names"]) if nm.endswith("wet_code")]
    if wet_idx:
        wet = data.X[test, 0, wet_idx[0]] > 0
        c = first(wet)
        cases.append({"name": "rain_period", "origin": c[0], "link_index": c[1]} if c else
                     {"name": "rain_period", "skip": "NOT_APPLICABLE: no wet weather code in test partition"})
    if c := first(rush):
        cases.append({"name": "stale_data_stress", "origin": c[0], "link_index": c[1], "simulate_stale_steps": 6})
        cases.append({"name": "wide_interval_stress", "origin": c[0], "link_index": c[1],
                      "force_interval_width_mph": 99.0})
        cases.append({"name": "insufficient_evidence", "origin": c[0], "link_index": c[1],
                      "query": "What is the recommended dosage schedule for pediatric antibiotics?"})
    mapped_idx = [ids.index(m) for m in mapped_links if m in ids]
    if mapped_idx:
        best = None
        for n in mapped_idx:
            drop = (data.mu[n] - preds_test[:, 1, n]) / data.mu[n]
            drop = np.where(ok_obs[:, n], drop, -np.inf)
            k = int(np.argmax(drop))
            if best is None or drop[k] > best[0]:
                best = (drop[k], int(test[k]), n)
        cases.append({"name": "mapped_corridor_alert", "origin": best[1], "link_index": best[2]})
        # second mapped case at an ordinary (non-extreme) rush-hour time
        k2 = np.where(rush & ok_obs[:, best[2]])[0]
        if k2.size:
            cases.append({"name": "mapped_corridor_rush_hour", "origin": int(test[k2[len(k2) // 3]]), "link_index": best[2]})
    for c in cases:
        c["case_id"] = f"case-{c['name']}-{c.get('origin')}-{c.get('link_index')}"
    return cases


POLICIES = {
    "full_system": dict(use_retrieval=True, use_constraints=True, use_uncertainty_gate=True, use_simulation=True),
    "llm_without_retrieval": dict(use_retrieval=False, use_constraints=True, use_uncertainty_gate=True, use_simulation=True),
    "rag_without_constraints": dict(use_retrieval=True, use_constraints=False, use_uncertainty_gate=True, use_simulation=True),
    "rag_constraints_without_simulation": dict(use_retrieval=True, use_constraints=True, use_uncertainty_gate=True,
                                               use_simulation=False),
}


def unsupported_claims(state: dict) -> dict:
    """Citation validity: evidence ids that were not in the retrieved set are fabricated/unsupported."""
    resp = (state.get("llm") or {}).get("response")
    if not resp:
        return {"n_candidates": 0, "n_cited": 0, "n_invalid_citations": 0}
    known = set(state.get("retrieved_evidence_ids") or [])
    cited = [e for c in resp["candidates"] for e in c["evidence_ids"]]
    bad = [e for e in cited if e not in known]
    return {"n_candidates": len(resp["candidates"]), "n_cited": len(cited), "n_invalid_citations": len(bad)}


def run(data, model, predict_fn, cal, retriever, sim_ctx, explain_fn, preds_test, policies=None) -> list[dict]:
    from langgraph.checkpoint.memory import InMemorySaver

    client = make_client()
    mapped = [k for k, v in sim_ctx.get("mapping_valid_by_link", {}).items() if v]
    cases = pick_cases(data, preds_test, mapped)
    write_json(settings.ROOT / "artifacts" / "agent_traces" / "cases.json", cases)
    rows = []
    for pname in policies or POLICIES:
        tk = Toolkit(data, model, predict_fn, cal, retriever, client, sim_ctx, explain_fn, **POLICIES[pname])
        app = build_graph(tk, checkpointer=InMemorySaver())
        for case in cases:
            if case.get("skip"):
                rows.append({"policy": pname, "case": case["name"], "decision": case["skip"]})
                continue
            if pname != "full_system" and case["name"] in ("stale_data_stress", "wide_interval_stress", "insufficient_evidence"):
                continue  # gate stress cases are evaluated on the full system only
            c = dict(case, auto_review={"action": "pending"}, policy=pname)
            t0 = time.time()
            st = run_case(app, c)
            uc = unsupported_claims(st)
            cr = st.get("constraint_results") or []
            rows.append({"policy": pname, "case": case["name"], "case_id": case["case_id"], "run_id": st["run_id"],
                         "link_id": data.meta["link_ids"][case["link_index"]],
                         "origin_utc": st.get("forecast_origin"), "decision": st.get("decision"),
                         "reasons": " | ".join(st.get("decision_reasons") or [])[:600],
                         "llm_status": (st.get("llm") or {}).get("status"),
                         "schema_valid": None if not st.get("llm") else (st["llm"]["status"] == "OK"),
                         "llm_attempts": len((st.get("llm") or {}).get("attempts", [])),
                         "n_candidates": uc["n_candidates"], "n_invalid_citations": uc["n_invalid_citations"],
                         "n_cited": uc["n_cited"],
                         "constraint_violations": sum(1 for r in cr if not r["passed"]),
                         "candidates_checked": len(cr),
                         "sim_delay_improvement_pct": ";".join(str(r.get("delay_improvement_pct")) for r in st.get("simulation_results") or []),
                         "latency_s": round(time.time() - t0, 2),
                         "timings": json.dumps(st.get("timings")), "mode": st.get("mode")})
    out = settings.ROOT / "reports" / "experiments" / "advisory_metrics.csv"
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    return rows
