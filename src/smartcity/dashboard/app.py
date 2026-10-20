"""Streamlit operator dashboard.  Every number shown is read from generated artifacts / the database.
Missing results are shown as NOT_TRAINED / NOT_RUN / SOURCE_UNAVAILABLE, never replaced by samples.

Run:  streamlit run src/smartcity/dashboard/app.py
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from smartcity import settings
from smartcity.api import service

ROOT = settings.ROOT
st.set_page_config(page_title="Smart-city traffic advisory (research prototype)", layout="wide")

PAGES = ["Overview & status", "Data audit & provenance", "Traffic map", "Multi-horizon forecast",
         "Uncertainty & reliability", "Explainability", "Evidence retrieval", "Agent trace & advisory",
         "SUMO comparisons", "Experiment results", "Limitations & model card"]
page = st.sidebar.radio("Page", PAGES)
st.sidebar.caption("Research prototype. No connection to real traffic signals. "
                   "Mode labels: LIVE / REPLAY / SIMULATION.")


def mode_badge(mode: str):
    color = {"LIVE": "green", "REPLAY": "orange", "SIMULATION": "violet"}.get(mode, "gray")
    st.markdown(f"**Mode:** :{color}[{mode}]")


def csv_or_state(path: Path, state="NOT_RUN"):
    if path.exists():
        df = pd.read_csv(path)
        if len(df):
            return df
    st.warning(f"{state}: `{path.relative_to(ROOT)}` not found")
    return None


def json_or_state(path: Path, state="NOT_RUN"):
    if path.exists():
        return json.loads(path.read_text())
    st.warning(f"{state}: `{path.relative_to(ROOT)}` not found")
    return None


if page == "Overview & status":
    st.title("Multi-horizon traffic forecasting & explainable agentic signal advisory")
    st.caption(settings.load("project")["project"]["title"])
    sel = service.selected()
    c1, c2, c3 = st.columns(3)
    c1.metric("Proposed model", sel["proposed_run_id"] if sel else "NOT_TRAINED")
    c2.metric("Track", sel["track"] if sel else "-")
    c3.metric("Study area", settings.load("project")["project"]["study_area"])
    st.subheader("Component status (evidence registry)")
    df = csv_or_state(ROOT / "reports" / "verification" / "evidence_registry.csv")
    if df is not None:
        st.dataframe(df[["requirement_id", "component", "test_status", "artifact_path", "limitations"]],
                     use_container_width=True, hide_index=True)
    fs = ROOT / "reports" / "verification" / "final_status.md"
    if fs.exists():
        with st.expander("final_status.md"):
            st.markdown(fs.read_text())

elif page == "Data audit & provenance":
    st.title("Data audit & provenance")
    mode_badge("REPLAY")
    rows = service.source_status()
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.warning("SOURCE_UNAVAILABLE: reports/data_audit/source_inventory.csv not generated")
    df = csv_or_state(ROOT / "reports" / "data_audit" / "coverage_by_year.csv")
    if df is not None:
        st.subheader("Coverage by year (server-side counts)")
        st.dataframe(df, use_container_width=True, hide_index=True)
    md = ROOT / "reports" / "data_audit" / "availability_audit.md"
    if md.exists():
        st.markdown(md.read_text())

elif page == "Traffic map":
    st.title("Monitored road links")
    mode_badge("REPLAY")
    gp = settings.path("processed") / "link_geometries.json"
    g = json_or_state(gp)
    if g:
        import pydeck as pdk

        paths = [{"link_id": k, "path": [[lon, lat] for lat, lon in v]} for k, v in g.items()]
        st.pydeck_chart(pdk.Deck(layers=[pdk.Layer("PathLayer", paths, get_path="path", get_width=5,
                                                   width_min_pixels=2, get_color=[200, 30, 0], pickable=True)],
                                 initial_view_state=pdk.ViewState(latitude=40.76, longitude=-73.97, zoom=11),
                                 tooltip={"text": "{link_id}"}))
        st.caption("Geometry: NYC DOT link_points (directed). Edges of the forecasting graph: reports/data_audit/graph_edges.csv")

elif page == "Multi-horizon forecast":
    st.title("Multi-horizon forecast")
    mode_badge("REPLAY")
    try:
        data, model, cal, sel = service.loaded()
    except FileNotFoundError:
        st.error("NOT_TRAINED")
        st.stop()
    link = st.selectbox("Road link", data.meta["link_ids"])
    test = data.origins["test"]
    t_lo = dt.datetime.fromtimestamp(int(data.times[test[0]]), dt.timezone.utc)
    t_hi = dt.datetime.fromtimestamp(int(data.times[test[-1]]), dt.timezone.utc)
    st.caption(f"Replay origins limited to the held-out test partition: {t_lo} .. {t_hi} (UTC)")
    pick = st.slider("Forecast origin (test partition index)", 0, len(test) - 1, len(test) - 1)
    origin = dt.datetime.fromtimestamp(int(data.times[test[pick]]), dt.timezone.utc).isoformat()
    fr = service.forecast(link, origin)
    h = service.history(link, origin)
    c = st.columns(5)
    c[0].metric("Forecast origin (UTC)", str(fr["origin_utc"])[:16])
    c[1].metric("Source timestamp (UTC)", str(fr["data_as_of_utc"])[:16] if fr["data_as_of_utc"] else "none")
    age = (fr["origin_utc"] - fr["data_as_of_utc"]).total_seconds() / 60 if fr["data_as_of_utc"] else None
    c[2].metric("Data age at origin", f"{age:.0f} min" if age is not None else "n/a")
    c[3].metric("Model version", fr["model_version"][:22])
    c[4].metric("Interval level", f"{fr['horizons'][0]['interval_level']:.0%}")
    times = [dt.datetime.fromtimestamp(t, dt.timezone.utc) for t in h["times_utc"]]
    oi = h["origin_index_in_series"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times[: oi + 1], y=h["speed_mph"][: oi + 1], name="observed (input history)", mode="lines"))
    fig.add_trace(go.Scatter(x=times[oi + 1:], y=h["speed_mph"][oi + 1:], name="observed (after origin; hidden from model)",
                             mode="lines", line=dict(dash="dot")))
    ft = [fr["origin_utc"] + dt.timedelta(minutes=x["horizon_minutes"]) for x in fr["horizons"]]
    fig.add_trace(go.Scatter(x=ft, y=[x["predicted_speed_mph"] for x in fr["horizons"]], name="predicted",
                             mode="markers+lines",
                             error_y=dict(type="data", symmetric=False,
                                          array=[x["upper_mph"] - x["predicted_speed_mph"] for x in fr["horizons"]],
                                          arrayminus=[x["predicted_speed_mph"] - x["lower_mph"] for x in fr["horizons"]])))
    fig.update_layout(yaxis_title="speed (mph)", xaxis_title="time (UTC)", height=420)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(pd.DataFrame(fr["horizons"]), hide_index=True, use_container_width=True)
    for w in fr["warnings"]:
        st.info(w)

elif page == "Uncertainty & reliability":
    st.title("Uncertainty & reliability")
    mode_badge("REPLAY")
    cal = json_or_state(ROOT / "artifacts" / "calibration" / "calibrator.json")
    if cal:
        st.json({k: cal[k] for k in ("method", "alpha", "nominal_coverage", "q_by_horizon_mph", "n_calibration",
                                     "calibration_period", "model_run_id", "gate_config") if k in cal})
    for f in ("coverage_by_horizon.csv", "coverage_by_scenario.csv", "deferral_tradeoff.csv",
              "interval_width_by_horizon.csv"):
        df = csv_or_state(ROOT / "artifacts" / "calibration" / f)
        if df is not None:
            st.subheader(f)
            st.dataframe(df, hide_index=True, use_container_width=True)
    st.caption("Empirical coverage only; split-conformal guarantees assume exchangeability, which traffic series may violate.")

elif page == "Explainability":
    st.title("Explanations of the proposed model")
    s = json_or_state(ROOT / "artifacts" / "explanations" / "explanations_summary.json")
    if s:
        st.caption(s["explained_model"] + " — grouped KernelSHAP; sensitivities, not causal effects.")
        g = s["global_grouped_mean_abs_shap_mph"]
        st.plotly_chart(go.Figure(go.Bar(x=list(g.values()), y=list(g.keys()), orientation="h")).update_layout(
            xaxis_title="mean |SHAP| (mph)", height=350), use_container_width=True)
        idx = st.selectbox("Local alert", range(len(s["local_alerts"])),
                           format_func=lambda i: f"{s['local_alerts'][i]['link_id']} h={s['local_alerts'][i]['horizon_minutes']}")
        e = s["local_alerts"][idx]
        st.json(e)
        st.subheader("Neighbour-removal sensitivity")
        st.dataframe(pd.DataFrame(s["neighbour_removal"]), hide_index=True)
        st.subheader("Temporal-window sensitivity")
        st.dataframe(pd.DataFrame(s["temporal_window"]), hide_index=True)
        st.subheader("Tree baseline SHAP (explains the BASELINE only)")
        for t in s["tree_baseline_shap"]:
            st.write(t["model"], t["run_id"])
            st.json(t["by_horizon"])

elif page == "Evidence retrieval":
    st.title("Evidence retrieval (FAISS + all-MiniLM-L6-v2)")
    q = st.text_input("Query", "extend green time while preserving yellow change and red clearance intervals")
    if st.button("Search"):
        try:
            from smartcity.rag.retriever import Retriever

            r = Retriever()
            status, ev = r.evidence(q)
            st.markdown(f"**Status:** {status}")
            for e in r.search(q):
                st.markdown(f"`{e.chunk_id}` — {e.title} — *{e.authority.value}* — score {e.score:.3f}")
                st.text(e.text[:800])
        except FileNotFoundError:
            st.error("NOT_RUN: knowledge index missing")
    df = csv_or_state(ROOT / "knowledge" / "source_registry.csv")
    if df is not None:
        st.subheader("Approved knowledge registry")
        st.dataframe(df.drop(columns=["sha256"]), hide_index=True, use_container_width=True)

elif page == "Agent trace & advisory":
    st.title("Agent traces & advisories")
    traces = service.agent_traces()
    if not traces:
        st.warning("NOT_RUN: no agent traces")
    else:
        df = pd.DataFrame([{"run_id": t["run_id"], "case": t.get("case", {}).get("name"), "decision": t.get("decision"),
                            "reasons": "; ".join(t.get("decision_reasons", []))[:200]} for t in traces])
        st.dataframe(df, hide_index=True, use_container_width=True)
        pick = st.selectbox("Trace", [t["run_id"] for t in traces])
        t = next(x for x in traces if x["run_id"] == pick)
        mode_badge(t.get("mode", "REPLAY"))
        st.markdown(f"### Decision: `{t.get('decision')}`")
        for k in ("data_quality", "forecast", "uncertainty", "retrieval", "llm", "constraint_results",
                  "simulation_results", "human_review", "timings"):
            if t.get(k) is not None:
                with st.expander(k):
                    st.json(t[k])
        st.subheader("Record human review")
        st.caption("Writes to POST /advisories/{id}/review (requires API token). Approval is for SIMULATION only.")

elif page == "SUMO comparisons":
    st.title("SUMO comparisons")
    mode_badge("SIMULATION")
    df = csv_or_state(ROOT / "reports" / "experiments" / "simulation_metrics.csv")
    if df is not None:
        st.caption("Scenario-based microscopic simulation testbed using real-world road geometry (OSM) and declared "
                   "demand assumptions. Not a calibrated digital twin; not real-world gains.")
        st.dataframe(df, hide_index=True, use_container_width=True)
        metric = st.selectbox("Metric", [c for c in df.columns if c.startswith(("mean_", "side_", "corridor_", "teleports",
                                                                                  "unfinished", "arrived"))])
        agg = df.groupby(["scenario", "controller"])[metric].mean().reset_index()
        st.plotly_chart(go.Figure([go.Bar(name=s, x=g["controller"], y=g[metric]) for s, g in agg.groupby("scenario")]),
                        use_container_width=True)
    sc = ROOT / "simulation" / "scenarios" / "scenarios.json"
    if sc.exists():
        st.json(json.loads(sc.read_text()))

elif page == "Experiment results":
    st.title("Experiment results")
    for name, rows in service.experiments().items():
        st.subheader(name)
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.warning("NOT_RUN")

elif page == "Limitations & model card":
    st.title("Limitations & model card")
    for p in (ROOT / "reports" / "limitations.md", ROOT / "docs" / "model_card.md"):
        if p.exists():
            st.markdown(p.read_text())
        else:
            st.warning(f"NOT_RUN: {p.name}")
