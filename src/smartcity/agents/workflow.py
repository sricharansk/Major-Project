"""LangGraph advisory workflow with deterministic gates and a human-review interrupt.

quality -> forecast -> uncertainty -(eligible)-> explanation -> retrieval -(supported)-> recommendation
        -> safety -(valid)-> simulation -> decision -> human_review -> report
Every non-eligible branch goes straight to ``report`` with a distinct decision status and reasons.
Only the recommendation node calls the LLM; validation, safety, simulation and decision are deterministic.
"""

from __future__ import annotations

import datetime as dt
import time
import traceback
import uuid
from typing import Any, TypedDict

import numpy as np
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from smartcity import settings
from smartcity.contracts import Decision
from smartcity.utils import utcnow_iso, write_json

TRACE_DIR = settings.ROOT / "artifacts" / "agent_traces"


class AdvisoryState(TypedDict, total=False):
    run_id: str
    thread_id: str
    mode: str
    case: dict
    forecast_origin: str
    source_manifest_ids: list
    data_quality: dict
    forecast: dict
    forecast_artifact_id: str
    calibration_artifact_id: str
    uncertainty: dict
    explanation: dict
    explanation_artifact_id: str
    retrieval: dict
    retrieved_evidence_ids: list
    llm: dict
    candidate_actions: list
    constraint_results: list
    simulation_results: list
    decision: str
    decision_reasons: list
    human_review: dict
    errors: list
    timings: dict
    started_at: str
    finished_at: str


def _timed(name):
    def deco(fn):
        def wrapper(state):
            t0 = time.time()
            try:
                out = fn(state)
            except Exception as exc:  # tool failure -> ERROR_TOOL with cause, never silent approval
                out = {"decision": Decision.ERROR_TOOL.value,
                       "decision_reasons": [f"{name}: {type(exc).__name__}: {exc}"],
                       "errors": (state.get("errors") or []) + [traceback.format_exc()[-2000:]]}
            timings = dict(state.get("timings") or {})
            timings[name] = round(time.time() - t0, 3)
            out["timings"] = timings
            return out
        wrapper.__name__ = name
        return wrapper
    return deco


class Toolkit:
    """Holds frozen artifacts and tools used by nodes."""

    def __init__(self, data, model, predict_fn, calibrator, retriever, llm_client, sim_ctx, explain_fn,
                 use_retrieval=True, use_constraints=True, use_uncertainty_gate=True, use_simulation=True):
        self.data, self.model, self.predict_fn = data, model, predict_fn
        self.cal, self.retriever, self.llm, self.sim_ctx = calibrator, retriever, llm_client, sim_ctx
        self.explain_fn = explain_fn
        self.use_retrieval, self.use_constraints = use_retrieval, use_constraints
        self.use_uncertainty_gate, self.use_simulation = use_uncertainty_gate, use_simulation
        self.gate_cfg = calibrator["gate_config"]


def build_graph(tk: Toolkit, checkpointer=None):
    from smartcity.agents.llm import propose
    from smartcity.safety.constraints import check_response
    from smartcity.uncertainty.conformal import gate

    data = tk.data
    hm = data.horizon_minutes

    @_timed("quality")
    def quality(s: AdvisoryState):
        o, n = s["case"]["origin"], s["case"]["link_index"]
        stale_steps = s["case"].get("simulate_stale_steps", 0)  # stress test: pretend the feed froze
        speed = data.speed[: o + 1, n]
        obs_idx = np.where(np.isfinite(speed))[0]
        obs_idx = obs_idx[obs_idx <= o - stale_steps] if stale_steps else obs_idx
        age_min = None if obs_idx.size == 0 else float((o - obs_idx[-1]) * data.meta["frequency_minutes"])
        L = data.L
        tr = data.M[o - L + 1:o + 1, n, data.meta["groups"].index("traffic")].copy()
        if stale_steps:
            tr[-min(stale_steps, L):] = False
        miss = float(1 - tr.mean())
        dq = {"data_age_minutes": age_min, "input_missing_fraction": miss,
              "source_timestamp_utc": None if obs_idx.size == 0 else
              dt.datetime.fromtimestamp(int(data.times[obs_idx[-1]]), dt.timezone.utc).isoformat(),
              "stale_stress_steps": stale_steps}
        reasons = []
        if age_min is None or age_min > tk.gate_cfg["max_data_age_minutes"]:
            reasons.append(f"STALE: data age {age_min} min > {tk.gate_cfg['max_data_age_minutes']}")
        if miss > tk.gate_cfg["max_input_missing_fraction"]:
            reasons.append(f"MISSING_INPUT: {miss:.2f} > {tk.gate_cfg['max_input_missing_fraction']}")
        out = {"data_quality": dq, "forecast_origin": dt.datetime.fromtimestamp(int(data.times[o]), dt.timezone.utc).isoformat()}
        if reasons:
            out.update(decision=Decision.DEFER_DATA.value, decision_reasons=reasons)
        return out

    @_timed("forecast")
    def forecast(s: AdvisoryState):
        o, n = s["case"]["origin"], s["case"]["link_index"]
        P = tk.predict_fn(tk.model, data, np.array([o]))[0]  # [H, N] mph
        hz = []
        for k, h in enumerate(hm):
            qn = tk.cal["q_by_horizon_link_mph"][str(h) if str(h) in tk.cal["q_by_horizon_link_mph"] else h][n] \
                if "q_by_horizon_link_mph" in tk.cal else None
            q = qn if qn is not None else tk.cal["q_by_horizon_mph"][str(h) if str(h) in tk.cal["q_by_horizon_mph"] else h]
            y = data.Y[o, k, n]
            hz.append({"horizon_minutes": h, "predicted_speed_mph": float(P[k, n]),
                       "displayed_speed_mph": max(0.0, float(P[k, n])), "lower_mph": float(P[k, n] - q),
                       "upper_mph": float(P[k, n] + q), "interval_level": 1 - tk.cal["alpha"],
                       "observed_speed_mph": None if not np.isfinite(y) else float(y)})
        ref = float(data.mu[n])
        return {"forecast": {"link_id": data.meta["link_ids"][n], "link_index": n, "horizons": hz,
                             "train_reference_speed_mph": ref,
                             "congestion_ratio_30min": hz[min(1, len(hz) - 1)]["predicted_speed_mph"] / ref,
                             "model_run_id": s["case"]["model_run_id"], "speed_unit": "mph"},
                "forecast_artifact_id": s["case"]["model_run_id"],
                "calibration_artifact_id": "artifacts/calibration/calibrator.json"}

    @_timed("uncertainty")
    def uncertainty(s: AdvisoryState):
        widths = {h["horizon_minutes"]: h["upper_mph"] - h["lower_mph"] for h in s["forecast"]["horizons"]}
        n_cal = {int(k): v for k, v in tk.cal["n_calibration"].items()}
        cfg = dict(tk.gate_cfg)
        if s["case"].get("force_interval_width_mph"):
            widths = {h: s["case"]["force_interval_width_mph"] for h in widths}  # stress test input
        ok, reasons = gate(widths, s["data_quality"]["input_missing_fraction"],
                           s["data_quality"]["data_age_minutes"], n_cal, cfg)
        out = {"uncertainty": {"eligible": ok, "reasons": reasons, "interval_widths": widths,
                               "gate_config": cfg}}
        if not ok and tk.use_uncertainty_gate:
            out.update(decision=Decision.DEFER_UNCERTAINTY.value, decision_reasons=reasons)
        return out

    @_timed("explanation")
    def explanation(s: AdvisoryState):
        o, n = s["case"]["origin"], s["case"]["link_index"]
        e = tk.explain_fn(tk.model, data, o, n, min(1, len(hm) - 1))
        return {"explanation": e, "explanation_artifact_id": e["explanation_id"]}

    @_timed("retrieval")
    def retrieval(s: AdvisoryState):
        f = s["forecast"]
        mapped = tk.sim_ctx.get("mapping_valid_by_link", {}).get(f["link_id"], False)
        q = s["case"].get("query") or (
            f"Forecast speed drop to {f['congestion_ratio_30min']:.0%} of typical on an urban "
            f"{'signalized arterial' if mapped else 'monitored road link'} within 30 minutes. "
            "Which bounded signal timing adjustment such as extending green time is permitted while preserving "
            "minimum green, yellow change and red clearance intervals and pedestrian clearance?")
        if not tk.use_retrieval:
            return {"retrieval": {"query": q, "status": "DISABLED", "evidence": []}, "retrieved_evidence_ids": []}
        status, ev = tk.retriever.evidence(q)
        out = {"retrieval": {"query": q, "status": status, "evidence": [e.model_dump() for e in ev]},
               "retrieved_evidence_ids": [e.chunk_id for e in ev]}
        if status != "SUPPORTED":
            out.update(decision=Decision.DEFER_EVIDENCE.value,
                       decision_reasons=["INSUFFICIENT_EVIDENCE: no passage above min_score for query"])
        return out

    @_timed("recommendation")
    def recommendation(s: AdvisoryState):
        from smartcity.contracts import RetrievedEvidence

        f = s["forecast"]
        mapped = tk.sim_ctx.get("mapping_valid_by_link", {}).get(f["link_id"], False)
        allowed = {"action_types": ["bounded_green_extension", "monitor_only"] if mapped else ["monitor_only"],
                   "traffic_lights": tk.sim_ctx.get("allowed_tls", {}) if mapped else {},
                   "green_extension_seconds": settings.load("agents")["actions"]["green_extension_s"],
                   "note": None if mapped else "No reviewed DOT->SUMO mapping for this link: monitor_only only."}
        ev = [RetrievedEvidence(**e) for e in s["retrieval"]["evidence"]]
        ctx = {"forecast_run_id": s["case"]["case_id"], "network_id": tk.sim_ctx.get("network_id", "none"),
               "mode": s.get("mode"),
               "forecast_summary": {"link_id": f["link_id"], "horizons": [{k: h[k] for k in
                                    ("horizon_minutes", "predicted_speed_mph", "lower_mph", "upper_mph")} for h in f["horizons"]],
                                    "train_reference_speed_mph": round(f["train_reference_speed_mph"], 1)},
               "uncertainty_summary": s["uncertainty"]["reasons"] or "gate passed",
               "quality_summary": s["data_quality"],
               "explanation_summary": {k: round(v, 2) for k, v in
                                       (s.get("explanation") or {}).get("group_contributions", {}).items()},
               "simulation_context": tk.sim_ctx.get("description")}
        res = propose(tk.llm, ctx, ev, allowed, with_evidence=tk.use_retrieval)
        llm_rec = {"status": res["status"], "attempts": res["attempts"], "provider": tk.llm.provider,
                   "model": tk.llm.model, "prompt_version": settings.load("agents")["llm"]["prompt_version"]}
        out = {"llm": llm_rec}
        if res["status"] == "AWAITING_LLM":
            out.update(decision="AWAITING_LLM", decision_reasons=["request queued for remote Ollama executor"])
        elif res["status"] == "ERROR_TOOL":
            out.update(decision=Decision.ERROR_TOOL.value, decision_reasons=[res["attempts"][-1]["error"]])
        elif res["status"] != "OK":
            out.update(decision=Decision.REJECT_SCHEMA.value, decision_reasons=["LLM output failed schema validation"])
        else:
            out["candidate_actions"] = [c.model_dump() for c in res["response"].candidates]
            llm_rec["response"] = res["response"].model_dump()
        return out

    @_timed("safety")
    def safety(s: AdvisoryState):
        from smartcity.contracts import AdvisoryResponse

        resp = AdvisoryResponse(**s["llm"]["response"])
        f = s["forecast"]
        ctx = {"network": tk.sim_ctx.get("tls_inventory", {}), "forecast_run_id": s["case"]["case_id"],
               "network_id": tk.sim_ctx.get("network_id", "none"),
               "mapping_valid": tk.sim_ctx.get("mapping_valid_by_link", {}).get(f["link_id"], False),
               "known_evidence_ids": s.get("retrieved_evidence_ids", []),
               "data_fresh": s["data_quality"]["data_age_minutes"] is not None
               and s["data_quality"]["data_age_minutes"] <= tk.gate_cfg["max_data_age_minutes"],
               "forecast_reliable": s["uncertainty"]["eligible"],
               "retrieval_supported": s["retrieval"]["status"] == "SUPPORTED",
               "pedestrian_modelled": False, "side_road_measured": True}
        results, errs = check_response(resp, ctx)
        rr = [r.model_dump() for r in results]
        passed = [r for r in results if r.passed]
        out = {"constraint_results": rr}
        if errs:
            out.update(decision=Decision.REJECT_CONSTRAINT.value, decision_reasons=errs)
        elif not passed and tk.use_constraints:
            out.update(decision=Decision.REJECT_CONSTRAINT.value,
                       decision_reasons=[x for r in results for x in r.reasons])
        return out

    @_timed("simulation")
    def simulation(s: AdvisoryState):
        cands = {c["candidate_id"]: c for c in s["candidate_actions"]}
        passed = [r["candidate_id"] for r in s["constraint_results"] if r["passed"]] if tk.use_constraints \
            else list(cands)
        sig = [cands[c] for c in passed if cands[c]["action_type"] == "bounded_green_extension"]
        if not sig:
            return {"simulation_results": []}  # monitor_only: nothing to simulate
        if not tk.use_simulation:
            return {"simulation_results": [{"candidate_id": c["candidate_id"], "skipped": "simulation gate disabled"}
                                           for c in sig]}
        results = []
        for c in sig[:2]:
            results.append(tk.sim_ctx["evaluate_candidate"](c))
        return {"simulation_results": results}

    @_timed("decision")
    def decision(s: AdvisoryState):
        sims = s.get("simulation_results") or []
        if not sims:
            if all(c["action_type"] == "monitor_only" for c in s.get("candidate_actions", [])):
                return {"decision": Decision.PENDING_HUMAN_REVIEW.value,
                        "decision_reasons": ["monitor_only advisory (no signal change proposed)"]}
            return {"decision": Decision.REJECT_SIMULATION.value, "decision_reasons": ["no simulated candidate"]}
        acc = settings.load("simulation")["simulation"]["acceptance"]
        best, reasons = None, []
        for r in sims:
            if r.get("skipped"):
                best = best or r
                reasons.append(f"{r['candidate_id']}: simulation gate disabled (ablation)")
                continue
            if r.get("status") != "OK":
                reasons.append(f"{r['candidate_id']}: simulation {r.get('status')} {r.get('error')}")
                continue
            ok = (r["delay_improvement_pct"] is not None and r["delay_improvement_pct"] >= acc["min_delay_improvement_pct"]
                  and (r["side_road_delay_change_pct"] is None or r["side_road_delay_change_pct"] <= acc["max_side_road_delay_increase_pct"])
                  and r["teleports_candidate"] <= acc["max_teleports"])
            reasons.append(f"{r['candidate_id']}: delay change {r['delay_improvement_pct']}% improvement, side-road "
                           f"{r['side_road_delay_change_pct']}%, teleports {r['teleports_candidate']} -> "
                           f"{'PASS' if ok else 'FAIL'}")
            if ok and (best is None or r["delay_improvement_pct"] > best.get("delay_improvement_pct", -1e9)):
                best = r
        if best is None:
            return {"decision": Decision.REJECT_SIMULATION.value, "decision_reasons": reasons}
        return {"decision": Decision.PENDING_HUMAN_REVIEW.value,
                "decision_reasons": reasons + [f"selected {best['candidate_id']} (SIMULATION_PASSED)"],
                "simulation_passed": True}

    def human_review(s: AdvisoryState):
        if s["case"].get("auto_review") is None:
            review = interrupt({"advisory_id": s["run_id"], "decision": s["decision"],
                                "question": "Approve for simulation, reject, or request revision?"})
        else:
            review = s["case"]["auto_review"]
        dec = {"approve": Decision.HUMAN_APPROVED_FOR_SIMULATION.value,
               "reject": Decision.HUMAN_REJECTED.value}.get(review.get("action"), s["decision"])
        return {"human_review": review, "decision": dec}

    def report(s: AdvisoryState):
        st = dict(s)
        st["finished_at"] = utcnow_iso()
        write_json(TRACE_DIR / f"{s['run_id']}.json", st)
        return {"finished_at": st["finished_at"]}

    def route(next_ok: str):
        def r(s: AdvisoryState):
            return "report" if s.get("decision") else next_ok
        return r

    g = StateGraph(AdvisoryState)
    for name, fn in [("quality", quality), ("forecast", forecast), ("uncertainty", uncertainty),
                     ("explanation", explanation), ("retrieval", retrieval), ("recommendation", recommendation),
                     ("safety", safety), ("simulation", simulation), ("decision", decision),
                     ("human_review", human_review), ("report", report)]:
        g.add_node(name, fn)
    g.add_edge(START, "quality")
    g.add_conditional_edges("quality", route("forecast"), ["forecast", "report"])
    g.add_conditional_edges("forecast", route("uncertainty"), ["uncertainty", "report"])
    g.add_conditional_edges("uncertainty", route("explanation"), ["explanation", "report"])
    g.add_conditional_edges("explanation", route("retrieval"), ["retrieval", "report"])
    g.add_conditional_edges("retrieval", route("recommendation"), ["recommendation", "report"])
    g.add_conditional_edges("recommendation", route("safety"), ["safety", "report"])
    g.add_conditional_edges("safety", route("simulation"), ["simulation", "report"])
    g.add_conditional_edges("simulation", route("decision"), ["decision", "report"])
    g.add_conditional_edges("decision", lambda s: "human_review" if s.get("decision") == Decision.PENDING_HUMAN_REVIEW.value
                            else "report", ["human_review", "report"])
    g.add_edge("human_review", "report")
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer)


def new_state(case: dict, mode: str = "REPLAY") -> AdvisoryState:
    rid = f"adv-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    return {"run_id": rid, "thread_id": rid, "mode": mode, "case": case, "errors": [], "timings": {},
            "started_at": utcnow_iso()}


def run_case(app, case: dict, mode: str = "REPLAY") -> dict[str, Any]:
    st = new_state(case, mode)
    cfg = {"configurable": {"thread_id": st["thread_id"]}}
    out = app.invoke(st, cfg)
    return out
