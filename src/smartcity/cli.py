"""Command-line interface (reproducibility contract).  Exit code 0 only when the declared operation completed."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import typer

from smartcity import settings
from smartcity.utils import environment_info, read_json, write_json

app = typer.Typer(no_args_is_help=True, add_completion=False)
data_app, graph_app, features_app, train_app = typer.Typer(), typer.Typer(), typer.Typer(), typer.Typer()
unc_app, eval_app, explain_app, rag_app = typer.Typer(), typer.Typer(), typer.Typer(), typer.Typer()
sim_app, agents_app, report_app, paper_app, verify_app = typer.Typer(), typer.Typer(), typer.Typer(), typer.Typer(), typer.Typer()
for name, sub in [("data", data_app), ("graph", graph_app), ("features", features_app), ("train", train_app),
                  ("uncertainty", unc_app), ("evaluate", eval_app), ("explain", explain_app), ("rag", rag_app),
                  ("simulation", sim_app), ("agents", agents_app), ("report", report_app), ("paper", paper_app),
                  ("verify", verify_app)]:
    app.add_typer(sub, name=name)

ART = settings.ROOT / "artifacts" / "models"


def registry_path(track: str) -> Path:
    return ART / f"registry_{track}.json"


def register(results: list[dict], track: str):
    reg = read_json(registry_path(track)) if registry_path(track).exists() else {}
    for r in results:
        reg[r["info"]["model"]] = r["info"]
    write_json(registry_path(track), reg)


def load_results(track: str, models: list[str] | None = None) -> list[dict]:
    reg = read_json(registry_path(track))
    out = []
    for model, info in reg.items():
        if models and model not in models:
            continue
        d = Path(info["artifact_dir"])
        preds = {s: np.load(d / f"predictions_{s}.npz")["pred_mph"] for s in ("val", "calib", "test")}
        out.append({"info": info, "preds": preds})
    return out


@app.command()
def doctor():
    """Environment audit -> reports/verification/environment.json."""
    import platform
    import shutil

    info = environment_info()
    def cmd(c):
        try:
            return subprocess.run(c, capture_output=True, text=True, timeout=20).stdout.strip()[:300] or "no output"
        except Exception as exc:
            return f"UNAVAILABLE: {exc}"[:200]
    from smartcity.simulation.sumo_runner import sumo_version
    from smartcity.graph import temporal

    temporal._signal_class()
    info.update(os=platform.platform(), git=cmd(["git", "--version"]), docker=cmd(["docker", "--version"]),
                docker_compose=cmd(["docker", "compose", "version"]), nvidia_smi=cmd(["nvidia-smi", "-L"]),
                cpu_count=__import__("os").cpu_count(), sumo=sumo_version(), pgt_import_route=temporal.IMPORT_ROUTE,
                psql=cmd(["psql", "--version"]), disk=str(shutil.disk_usage(str(settings.ROOT))))
    try:
        info["ram_gb"] = round(__import__("os").sysconf("SC_PAGE_SIZE") * __import__("os").sysconf("SC_PHYS_PAGES") / 1e9, 1)
    except Exception:
        pass
    p = write_json(settings.ROOT / "reports" / "verification" / "environment.json", info)
    typer.echo(f"wrote {p}")


@data_app.command("audit")
def data_audit():
    from smartcity.ingestion import audit

    res = audit.run()
    typer.echo(f"source inventory rows: {len(res['inventory'])}; manifest {res['manifest_hash']}")


@data_app.command("download")
def data_download(start: str = "2026-01-01", end: str = "2026-10-20", borough: str = "Manhattan"):
    """Runs the stdlib downloader (needs network access to the sources)."""
    fetch = str(settings.ROOT / "src" / "smartcity" / "ingestion" / "fetch.py")
    for args in (["audit"], ["speed-links", "--since", start], ["speeds", "--start", start, "--end", end, "--borough", borough],
                 ["weather", "--start", start, "--end", end], ["collisions", "--start", start, "--end", end],
                 ["events", "--since", start], ["volume", "--start-year", "2024"], ["sr311", "--start", start, "--end", end]):
        r = subprocess.run([sys.executable, fetch, *args])
        if r.returncode != 0:
            raise typer.Exit(r.returncode)


@data_app.command("collect")
def data_collect(interval_s: int = 300, iterations: int = 1):
    """LIVE mode collector: polls the speed feed for the last 15 minutes and stores raw responses."""
    import datetime as dt
    import time as _t

    fetch = str(settings.ROOT / "src" / "smartcity" / "ingestion" / "fetch.py")
    for i in range(iterations):
        today = dt.datetime.now(dt.timezone.utc).date()
        r = subprocess.run([sys.executable, fetch, "speeds", "--start", str(today), "--end", str(today + dt.timedelta(days=1)),
                            "--days", "1"])
        typer.echo(f"LIVE collection iteration {i}: exit {r.returncode}")
        if i < iterations - 1:
            _t.sleep(interval_s)


@data_app.command("preprocess")
def data_preprocess():
    from smartcity.preprocessing import speeds

    s = speeds.run()
    typer.echo(json.dumps(s, indent=1, default=str))


@graph_app.command("build")
def graph_build():
    from smartcity.graph import build

    g = build.run()
    typer.echo(f"graph {g['graph_hash']}: {g['n_nodes']} nodes, {g['n_edges']} edges, {len(g['isolated_nodes'])} isolated")


@graph_app.command("validate")
def graph_validate():
    g = read_json(settings.path("processed") / "graph.json")
    ei = np.array(g["edge_index"])
    problems = []
    if ei.size and (ei[0] == ei[1]).any():
        problems.append("self loops present")
    if ei.size and len({(a, b) for a, b in ei.T.tolist()}) != ei.shape[1]:
        problems.append("duplicate edges")
    rev = {(b, a) for a, b in ei.T.tolist()} if ei.size else set()
    both = sum(1 for a, b in ei.T.tolist() if (a, b) in rev) if ei.size else 0
    rep = {"graph_hash": g["graph_hash"], "n_nodes": g["n_nodes"], "n_edges": g["n_edges"], "problems": problems,
           "bidirectional_pairs": both // 2, "isolated_nodes": len(g["isolated_nodes"])}
    write_json(settings.ROOT / "reports" / "data_audit" / "graph_validation.json", rep)
    typer.echo(json.dumps(rep))
    if problems:
        raise typer.Exit(1)


@features_app.command("build")
def features_build(track: str = "operational"):
    from smartcity.features import build

    m = build.build(track)
    typer.echo(f"{track}: {len(m['link_ids'])} links, features {len(m['feature_names'])}, groups {m['group_available_fraction']}")


@train_app.command("baselines")
def train_baselines(track: str = "operational"):
    from smartcity.training import runner
    from smartcity.training.data import load_data

    data = load_data(track)
    res = runner.run_simple_baselines(data) + runner.run_tree_baselines(data)
    register(res, track)
    typer.echo("trained: " + ", ".join(r["info"]["run_id"] for r in res))


@train_app.command("proposed")
def train_proposed(track: str = "operational", variants: str = "gru,temporal_transformer,proposed",
                   max_epochs: int = 0, windows_per_epoch: int = 0):
    from smartcity.training import runner
    from smartcity.training.data import load_data

    data = load_data(track)
    res = []
    for v in variants.split(","):
        res.append(runner.train_deep(v, data, max_epochs=max_epochs or None, windows_per_epoch=windows_per_epoch or None))
        register([res[-1]], track)
    typer.echo("trained: " + ", ".join(r["info"]["run_id"] for r in res))


@eval_app.command("forecasts")
def evaluate_forecasts(track: str = "operational", models: str = "persistence,historical_average,xgboost,lightgbm,gru,temporal_transformer,proposed",
                       file: str = "forecast_metrics.csv"):
    from smartcity.training import runner
    from smartcity.training.data import load_data

    data = load_data(track)
    results = load_results(track, models.split(","))
    rows = runner.evaluate_and_export(results, data, track, file)
    for r in rows:
        typer.echo(f"{r['model']:24s} h={r['horizon_min']:>3} n={r['n_valid_targets']} MAE={r['mae_mph']:.3f} RMSE={r['rmse_mph']:.3f}")


@eval_app.command("ablations")
def evaluate_ablations(track: str = "operational", reference: str = "proposed", n_boot: int = 1000):
    """Ablation table: test MAE (mean over horizons) of every trained ablation_* variant vs the reference model,
    with a day-block bootstrap 95% CI on the paired MAE difference. Variants that were not trained are listed as
    NOT_RUN so the paper table never silently omits them."""
    import csv as _csv

    from smartcity.training import metrics as M
    from smartcity.training.data import load_data
    from smartcity.training.runner import DEEP_VARIANTS

    data = load_data(track)
    o = data.origins["test"]
    Y = data.Y[o]
    day_index = np.asarray(data.times[o]).astype("datetime64[D]").astype("int64")
    loaded = {r["info"]["model"]: r for r in load_results(track, [reference] + [v for v in DEEP_VARIANTS if v.startswith("ablation_")])}
    if reference not in loaded:
        raise typer.BadParameter(f"reference model {reference!r} is not in the {track} registry")
    ref = loaded[reference]["preds"]["test"]
    mask = np.isfinite(Y) & np.isfinite(ref)
    for r in loaded.values():
        mask &= np.isfinite(r["preds"]["test"])
    rows = []
    for v in [reference] + [v for v in DEEP_VARIANTS if v.startswith("ablation_")]:
        if v not in loaded:
            rows.append({"variant": v, "track": track, "run_id": "", "mae_mean_mph": "", "delta_vs_proposed_mph": "",
                         "ci95_low": "", "ci95_high": "", "n_days": "", "status": "NOT_RUN"})
            continue
        P = loaded[v]["preds"]["test"]
        mh = M.by_horizon(Y, P, data.horizon_minutes, mask)
        mae = float(np.mean([x["mae"] for x in mh.values()]))
        if v == reference:
            d = {"mae_diff": 0.0, "ci95": [0.0, 0.0], "n_days": len(np.unique(day_index))}
        else:
            d = M.day_block_bootstrap_mae_diff(Y, P, ref, np.repeat(day_index[:, None, None], 1, axis=1)
                                               .repeat(Y.shape[1], 1).repeat(Y.shape[2], 2), n_boot=n_boot)
        rows.append({"variant": v, "track": track, "run_id": loaded[v]["info"]["run_id"], "mae_mean_mph": round(mae, 4),
                     "delta_vs_proposed_mph": round(d.get("mae_diff", 0.0), 4),
                     "ci95_low": round(d["ci95"][0], 4) if "ci95" in d else "",
                     "ci95_high": round(d["ci95"][1], 4) if "ci95" in d else "", "n_days": d.get("n_days", ""),
                     "status": "REFERENCE" if v == reference else "OK"})
    out = settings.ROOT / "reports" / "experiments" / "ablation_metrics.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        typer.echo(f"{r['variant']:28s} MAE={r['mae_mean_mph']} delta={r['delta_vs_proposed_mph']} [{r['ci95_low']}, {r['ci95_high']}] {r['status']}")


@unc_app.command("calibrate")
def uncertainty_calibrate(track: str = "operational", model: str = "proposed"):
    from smartcity.training.data import load_data
    from smartcity.uncertainty import conformal

    data = load_data(track)
    cal = conformal.run(data, load_results(track, [model]), model)
    info = read_json(registry_path(track))[model]
    write_json(ART / "selected.json", {"track": track, "proposed_run_id": info["run_id"],
                                        "proposed_artifact_dir": info["artifact_dir"], "selected_by": "declared model "
                                        "(proposed) frozen before calibration; selection not based on test results"})
    typer.echo(json.dumps({k: cal[k] for k in ("q_by_horizon_mph", "n_calibration")}))


def _load_frozen(track: str):
    import torch

    from smartcity.training.data import load_data
    from smartcity.training.runner import make_model

    data = load_data(track)
    info = read_json(registry_path(track))["proposed"]
    mcfg = {k: v for k, v in settings.load("model")["model"].items() if k not in ("name", "lookback_steps", "horizon_steps")}
    model = make_model("proposed", data, mcfg)
    model.load_state_dict(torch.load(Path(info["artifact_dir"]) / "model.pt"))
    model.eval()
    return data, model


@explain_app.command("alerts")
def explain_alerts(track: str = "operational", n_alerts: int = 12):
    import time as _t

    from smartcity.explainability import deep
    from smartcity.training.runner import predict_deep

    data, model = _load_frozen(track)
    reg = read_json(registry_path(track))
    results = load_results(track, ["proposed"])
    # tree baselines need their models for TreeExplainer
    for name in ("lightgbm",):
        if name in reg:
            import lightgbm as lgb

            d = Path(reg[name]["artifact_dir"])
            boosters = [lgb.Booster(model_file=str(d / f"model_h{h}.txt")) for h in data.horizon_minutes]
            results.append({"info": reg[name], "preds": {}, "models": boosters})
    cal = read_json(settings.ROOT / "artifacts" / "calibration" / "calibrator.json")
    t0 = _t.time()
    s = deep.run(model, data, results, predict_deep, cal, n_alerts=n_alerts)
    typer.echo(f"explanations: {len(s['local_alerts'])} alerts in {_t.time() - t0:.1f}s; global {s['global_grouped_mean_abs_shap_mph']}")


@rag_app.command("fetch-docs")
def rag_fetch_docs():
    """Download approved knowledge documents that are missing locally (SUMO docs, FHWA/MUTCD pages)."""
    from smartcity.knowledge import registry

    r = registry.fetch_missing()
    typer.echo(json.dumps(r, indent=1))
    if r["failed"]:
        raise typer.Exit(code=1)


@rag_app.command("build")
def rag_build():
    from smartcity.knowledge import registry
    from smartcity.rag import retriever

    rows = registry.populate()
    m = retriever.build_index()
    typer.echo(f"registry {len(rows)} docs; index {m['n_chunks']} chunks, corpus {m['corpus_hash']}, over-limit {m['chunks_over_model_limit']}")


@rag_app.command("evaluate")
def rag_evaluate():
    from smartcity.rag import retriever

    typer.echo(json.dumps(retriever.evaluate(), indent=1))


@sim_app.command("prepare")
def simulation_prepare():
    from smartcity.simulation import pipeline

    m = pipeline.prepare()
    typer.echo(json.dumps({k: m[k] for k in ("corridor", "tls_corridor", "corridor_phase", "mapping_summary", "demand")},
                          indent=1, default=str)[:4000])


@sim_app.command("evaluate")
def simulation_evaluate(seeds: str = ""):
    from smartcity.simulation import pipeline

    rows = pipeline.evaluate_controllers([int(s) for s in seeds.split(",")] if seeds else None)
    p = pipeline.export_sim_rows(rows)
    typer.echo(f"{len(rows)} simulation runs -> {p}")


def sim_context(track_data=None) -> dict:
    import csv as _csv

    from smartcity.simulation import pipeline

    prep = settings.ROOT / "simulation" / "scenarios" / "prepared.json"
    if not prep.exists():
        return {"mapping_valid_by_link": {}, "description": "SUMO scenario NOT_RUN", "network_id": "none"}
    meta = read_json(prep)
    mp = {}
    with open(settings.ROOT / "simulation" / "mappings" / "dot_to_sumo.csv") as fh:
        for r in _csv.DictReader(fh):
            mp[r["dot_link_id"]] = r["mapping_confidence"] == "high" and r["review_status"].startswith("auto_checked_reviewed")
    scen = next(s for s in pipeline.scenarios(meta) if s["name"] == "event_surge")
    seeds = settings.load("simulation")["simulation"]["seeds"][:3]
    allowed_tls = {t: {"green_phases": [p["index"] for p in v["phases"] if p["green"]],
                       "green_durations_s": {p["index"]: p["duration"] for p in v["phases"] if p["green"]},
                       "corridor_phase": meta["corridor_phase"].get(t)} for t, v in meta["tls_inventory"].items()}
    return {"mapping_valid_by_link": mp, "tls_inventory": meta["tls_inventory"], "allowed_tls": allowed_tls,
            "network_id": f"sumo:{meta['network']['static_sha256'][:12]}",
            "description": "SIMULATION testbed (OSM geometry, declared demand): " + scen["description"],
            "evaluate_candidate": lambda c: pipeline.paired_candidate_eval(meta, scen, c, seeds)}


@agents_app.command("evaluate")
def agents_evaluate(track: str = "operational", policies: str = ""):
    from smartcity.agents import evaluate
    from smartcity.explainability.deep import explain_alert
    from smartcity.rag.retriever import Retriever
    from smartcity.training.runner import predict_deep

    data, model = _load_frozen(track)
    cal = read_json(settings.ROOT / "artifacts" / "calibration" / "calibrator.json")
    preds = load_results(track, ["proposed"])[0]["preds"]["test"]
    rows = evaluate.run(data, model, predict_deep, cal, Retriever(), sim_context(), explain_alert, preds,
                        policies.split(",") if policies else None)
    for r in rows:
        typer.echo(f"{r['policy']:36s} {r['case']:28s} {r.get('decision')}")


@app.command("job-exec")
def job_exec(kind: str, params: str):
    """Executed by the worker in a subprocess.  Prints RESULT_JSON=... on success."""
    p = json.loads(params)
    if kind == "advisory":
        from langgraph.checkpoint.memory import InMemorySaver

        from smartcity.agents.llm import make_client
        from smartcity.agents.workflow import Toolkit, build_graph, run_case
        from smartcity.api import service
        from smartcity.explainability.deep import explain_alert
        from smartcity.rag.retriever import Retriever
        from smartcity.training.runner import predict_deep

        data, model, cal, sel = service.loaded()
        n = data.meta["link_ids"].index(p["link_id"])
        o = int(data.origins["test"][-1])
        if p.get("origin_utc"):
            import datetime as dt

            ts = int(dt.datetime.fromisoformat(p["origin_utc"].replace("Z", "+00:00")).timestamp())
            o = int(np.searchsorted(data.times, ts, side="right") - 1)
        tk = Toolkit(data, model, predict_deep, cal, Retriever(), make_client(), sim_context(), explain_alert)
        st = run_case(build_graph(tk, InMemorySaver()), {"name": "api_request", "origin": o, "link_index": n,
                                                         "case_id": f"api-{p['link_id']}-{o}", "auto_review": {"action": "pending"}})
        print("RESULT_JSON=" + json.dumps({"advisory_id": st["run_id"], "decision": st.get("decision")}))
    elif kind == "simulation":
        from smartcity.simulation import pipeline, sumo_runner

        meta = read_json(settings.ROOT / "simulation" / "scenarios" / "prepared.json")
        scen = next(s for s in pipeline.scenarios(meta) if s["name"] == p["scenario"])
        routes = pipeline.build_routes(meta, scen)
        net = settings.ROOT / meta["network"]["actuated" if p["controller"] == "actuated" else "static"]
        res = [sumo_runner.run_scenario(net, routes, scen, p["controller"], s) for s in p["seeds"]]
        print("RESULT_JSON=" + json.dumps([{"run_id": r["run_id"], "status": r["status"], "metrics": r["metrics"]} for r in res]))
    elif kind == "explanation":
        from smartcity.api import service
        from smartcity.explainability.deep import explain_alert

        data, model, cal, sel = service.loaded()
        n = data.meta["link_ids"].index(p["link_id"])
        o = int(data.origins["test"][-1])
        h = data.horizon_minutes.index(p.get("horizon_minutes", 30))
        e = explain_alert(model, data, o, n, h)
        write_json(settings.ROOT / "artifacts" / "explanations" / f"{e['explanation_id']}.json", e)
        print("RESULT_JSON=" + json.dumps({"explanation_id": e["explanation_id"]}))
    else:
        raise typer.Exit(2)


@report_app.command("export")
def report_export():
    from smartcity.reporting import export

    typer.echo(json.dumps(export.run(), indent=1, default=str)[:3000])


@paper_app.command("sync")
def paper_sync():
    from smartcity.reporting import paper

    typer.echo(paper.sync())


@verify_app.command("all")
def verify_all():
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=settings.ROOT)
    from smartcity.reporting import export

    export.run()
    raise typer.Exit(r.returncode)


@verify_app.command("smoke")
def verify_smoke(docker_build: bool = False):
    """API, database, dashboard and Docker smoke checks -> reports/verification/*_smoke.json."""
    from smartcity.reporting import smoke

    typer.echo(json.dumps(smoke.run_all(docker_build), indent=1))


if __name__ == "__main__":
    app()
