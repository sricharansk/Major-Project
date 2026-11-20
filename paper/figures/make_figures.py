"""Draw the paper figures from the stored result artifacts.

Every chart reads the committed CSV/JSON files under reports/ and artifacts/; nothing is typed in by hand
except the two diagrams (system pipeline and forecaster block diagram), whose boxes describe the code in
src/smartcity. Outputs: paper/figures/<name>.pdf and <name>.png (300 dpi). Run from the repository root:

    python paper/figures/make_figures.py
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "paper" / "figures"
EXP = ROOT / "reports" / "experiments"
ART = ROOT / "artifacts"

COL = 3.45  # IEEE single column width in inches
DBL = 7.16  # IEEE double column width in inches

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
    "font.size": 8,
    "axes.titlesize": 8,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "lines.linewidth": 1.0,
    "pdf.fonttype": 42,
    "savefig.dpi": 300,
})

# A restrained palette that stays distinguishable in greyscale print.
C = {
    "proposed": "#1f4e79",
    "gru": "#c55a11",
    "transformer": "#548235",
    "tree": "#7f7f7f",
    "naive": "#bfbfbf",
    "persistence": "#9e9e9e",
    "ok": "#2e7d32",
    "warn": "#c62828",
    "box": "#f2f2f2",
    "box_dark": "#dbe5f1",
    "edge": "#404040",
}
MODEL_LABEL = {
    "persistence": "Persistence",
    "historical_average": "Historical average",
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "gru": "GRU",
    "temporal_transformer": "Temporal Transformer",
    "proposed": "Proposed",
}
MODEL_COLOR = {
    "persistence": C["naive"], "historical_average": C["naive"], "xgboost": C["tree"], "lightgbm": C["tree"],
    "gru": C["gru"], "temporal_transformer": C["transformer"], "proposed": C["proposed"],
}
HORIZONS = (15, 30, 60)


def rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print("wrote", name)


# ----------------------------------------------------------------------------------------------------------
# Diagrams
# ----------------------------------------------------------------------------------------------------------
def _box(ax, x, y, w, h, text, fc=None, fs=7, bold=False, ls="-", lw=0.7):
    patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.012", linewidth=lw,
                           edgecolor=C["edge"], facecolor=fc or C["box"], linestyle=ls)
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", linespacing=1.15)
    return patch


def _arrow(ax, p, q, style="-|>", lw=0.7, ls="-", color=None):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=7, linewidth=lw, linestyle=ls,
                                 color=color or C["edge"], shrinkA=0, shrinkB=0))


def fig_system_architecture():
    fig = plt.figure(figsize=(DBL, 3.55))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Column 1: public data sources
    ax.text(0.085, 0.965, "Public data", ha="center", va="center", fontsize=7.5, fontweight="bold")
    srcs = [
        ("NYC DOT real-time\nlink speeds (5-min bins)", C["box_dark"]),
        ("Open-Meteo weather\n(hourly)", None),
        ("NYC 311 service\nrequests", None),
        ("Calendar: hour, weekday,\nholidays", None),
        ("OpenStreetMap corridor,\nNYC DOT traffic counts", None),
    ]
    ys = [0.80, 0.645, 0.49, 0.335, 0.18]
    for (t, fc), y in zip(srcs, ys):
        _box(ax, 0.01, y - 0.055, 0.15, 0.11, t, fc=fc, fs=6.3)

    # Column 2: preprocessing and graph
    _box(ax, 0.21, 0.56, 0.15, 0.30,
         "Ingestion and audit\n\nUTC alignment, cleaning,\nright-labelled 5-min grid,\navailability masks,\nchronological split\n(train / val / test)", fs=6.3)
    _box(ax, 0.21, 0.19, 0.15, 0.27,
         "Directed road-link\ngraph\n\nlink geometry +\nname-based continuity;\nPyG Temporal signal", fs=6.3)
    for y, ty in zip(ys[:4], (0.83, 0.75, 0.67, 0.60)):
        _arrow(ax, (0.16, y), (0.21, ty))
    _arrow(ax, (0.16, ys[4]), (0.21, 0.26))
    _arrow(ax, (0.16, ys[0] - 0.02), (0.21, 0.40))

    # Column 3: forecaster and calibration
    _box(ax, 0.41, 0.50, 0.17, 0.36,
         "Forecaster\n\nContext-gated\nspatiotemporal graph\nTransformer\n(availability gate,\nGATv2 x2, temporal\nencoder x2)\n15 / 30 / 60 min", fc=C["box_dark"], fs=6.3, bold=False)
    _box(ax, 0.41, 0.30, 0.17, 0.15, "Split conformal\nintervals (90 %)\n+ deferral gate", fs=6.3)
    _box(ax, 0.41, 0.10, 0.17, 0.15, "Grouped KernelSHAP\nexplanations", fs=6.3)
    _arrow(ax, (0.36, 0.71), (0.41, 0.71))
    _arrow(ax, (0.36, 0.33), (0.41, 0.60))
    _arrow(ax, (0.495, 0.50), (0.495, 0.45))
    _arrow(ax, (0.495, 0.30), (0.495, 0.25))

    # Column 4: agentic advisory
    _box(ax, 0.63, 0.56, 0.17, 0.30,
         "Agentic advisory\n(LangGraph)\n\nForecast + interval\n→ candidate signal\nactions → local LLM\ndraft with citations", fc=C["box_dark"], fs=6.3)
    _box(ax, 0.63, 0.30, 0.17, 0.19,
         "Retrieval (RAG)\nallowlisted corpus:\nFHWA signal timing,\nproject policy, SUMO\ndocs; FAISS index", fs=6.3)
    _box(ax, 0.63, 0.08, 0.17, 0.16,
         "Deterministic safety\nconstraints and\nschema validation", fs=6.3)
    _arrow(ax, (0.58, 0.68), (0.63, 0.68))
    _arrow(ax, (0.58, 0.375), (0.63, 0.40))
    _arrow(ax, (0.715, 0.49), (0.715, 0.56))
    _arrow(ax, (0.715, 0.30), (0.715, 0.24))

    # Column 5: evaluation and delivery
    _box(ax, 0.85, 0.62, 0.14, 0.24,
         "SUMO testbed\n(calibrated West\nStreet corridor,\nmatched seeds)\nSIMULATION", fs=6.3)
    _box(ax, 0.85, 0.36, 0.14, 0.20, "Human review\nqueue\n(no command is\never sent)", fs=6.3)
    _box(ax, 0.85, 0.08, 0.14, 0.22, "FastAPI service,\nStreamlit\ndashboard,\nverification\nrecords", fs=6.3)
    _arrow(ax, (0.80, 0.74), (0.85, 0.74))
    _arrow(ax, (0.80, 0.46), (0.85, 0.46))
    _arrow(ax, (0.80, 0.16), (0.85, 0.16))
    _arrow(ax, (0.92, 0.62), (0.92, 0.56))

    # Live path annotation
    ax.text(0.5, 0.025,
            "Modes: REPLAY of stored forecasts on the chronological test period; LIVE forecasts from the public feed "
            "at its own latency; SIMULATION on the calibrated SUMO testbed.",
            ha="center", va="center", fontsize=6.3, style="italic")
    save(fig, "fig_system_architecture")


def fig_model_architecture():
    fig = plt.figure(figsize=(COL, 3.9))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    groups = ["Target speed\n(last 30 min)", "Target speed\n(30-120 min)", "Graph\nneighbours", "Calendar", "Weather",
              "Infrastructure\n(311)"]
    n = len(groups)
    w = 0.145
    gap = (1 - 0.02 - n * w) / (n - 1)
    xs = [0.01 + i * (w + gap) for i in range(n)]
    for x, g in zip(xs, groups):
        _box(ax, x, 0.86, w, 0.10, g, fs=5.6)
        _box(ax, x, 0.755, w, 0.07, "Linear + tanh", fs=5.6)
        _arrow(ax, (x + w / 2, 0.86), (x + w / 2, 0.825))
        _arrow(ax, (x + w / 2, 0.755), (x + w / 2, 0.70))
    ax.text(0.5, 0.995, "Input window: 24 steps x 16 links x feature groups (with availability masks)",
            ha="center", va="top", fontsize=6.2, style="italic")

    _box(ax, 0.03, 0.60, 0.94, 0.10,
         "Availability-aware gate (64-d): softmax weights over the observed groups,\nlearned placeholder vector when a group is missing",
         fc=C["box_dark"], fs=6.0)
    _arrow(ax, (0.5, 0.60), (0.5, 0.545))
    _box(ax, 0.17, 0.445, 0.66, 0.10,
         "Spatial block x2: GATv2 attention over directed link graph\n(4 heads, residual, LayerNorm)", fs=6.0)
    _arrow(ax, (0.5, 0.445), (0.5, 0.39))
    _box(ax, 0.17, 0.29, 0.66, 0.10,
         "Temporal block x2: Transformer encoder over 24 steps\n(4 heads, learned positions, FFN 128)", fs=6.0)
    _arrow(ax, (0.5, 0.29), (0.5, 0.235))
    _box(ax, 0.30, 0.15, 0.40, 0.085, "Linear head on last step → 3 horizons", fs=6.0)
    ax.plot([0.5, 0.5], [0.15, 0.12], color=C["edge"], lw=0.7)
    ax.plot([0.15, 0.85], [0.12, 0.12], color=C["edge"], lw=0.7)
    for x, t in ((0.04, "15 min"), (0.39, "30 min"), (0.74, "60 min")):
        _box(ax, x, 0.015, 0.22, 0.075, f"{t} speed\n+ conformal band", fs=5.8, fc=C["box_dark"])
        _arrow(ax, (x + 0.11, 0.12), (x + 0.11, 0.09))
    ax.text(0.985, 0.30, "158 k\nparameters", ha="right", va="center", fontsize=5.6, style="italic")
    save(fig, "fig_model_architecture")


def fig_code_structure():
    tree = [
        ("smartcity/", "Python package (CLI entry point: smartcity.cli)"),
        ("  ingestion/", "NYC DOT speeds, weather, 311, counts; fetch logs and audit"),
        ("  preprocessing/", "cleaning, 5-min grid, availability masks, chronological split"),
        ("  graph/", "directed link graph and PyG Temporal signal"),
        ("  features/", "feature groups and group masks"),
        ("  models/", "context-gated graph Transformer, GRU, Transformer, tree baselines"),
        ("  training/", "deadline-aware training loop, seeds, MLflow logging"),
        ("  uncertainty/", "split conformal calibration and deferral gate"),
        ("  explainability/", "grouped KernelSHAP on the trained model"),
        ("  knowledge/, rag/", "allowlisted corpus, FAISS index, retrieval evaluation"),
        ("  agents/", "LangGraph advisory workflow and local LLM client"),
        ("  safety/", "deterministic constraints and schema validation"),
        ("  simulation/", "SUMO testbed, calibration protocol, controller comparison"),
        ("  live/", "latest-available live mode with publication-time guard"),
        ("  api/, dashboard/", "FastAPI service and Streamlit dashboard"),
        ("  reporting/", "paper tables, verification records"),
        ("tests/", "unit, leakage, safety, integration and end-to-end tests (119)"),
    ]
    fig = plt.figure(figsize=(COL, 2.75))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    y = 0.97
    step = 0.057
    for name, desc in tree:
        ax.text(0.02, y, name, family="monospace", fontsize=6.3, va="top",
                fontweight="bold" if not name.startswith(" ") else "normal")
        ax.text(0.36, y, desc, fontsize=6.3, va="top")
        y -= step
    save(fig, "fig_code_structure")


# ----------------------------------------------------------------------------------------------------------
# Forecasting results
# ----------------------------------------------------------------------------------------------------------
def fig_forecast_mae():
    data = defaultdict(dict)
    for r in rows(EXP / "forecast_metrics.csv"):
        if r["track"] == "operational" and r["split"] == "test":
            data[r["model"]][int(r["horizon_min"])] = float(r["mae_mph"])
    order = [m for m in MODEL_LABEL if m in data]
    fig, ax = plt.subplots(figsize=(COL, 2.3))
    width = 0.8 / len(order)
    for i, m in enumerate(order):
        xs = [h + (i - (len(order) - 1) / 2) * width for h in range(3)]
        vals = [data[m][h] for h in HORIZONS]
        bars = ax.bar(xs, vals, width=width * 0.95, color=MODEL_COLOR[m], label=MODEL_LABEL[m],
                      edgecolor="white", linewidth=0.3)
        if m == "proposed":
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, v + 0.08, f"{v:.2f}", ha="center", va="bottom", fontsize=5.5)
    ax.set_xticks(range(3))
    ax.set_xticklabels([f"{h} min" for h in HORIZONS])
    ax.set_ylabel("Test MAE (mph)")
    ax.set_ylim(0, 8.6)
    ax.legend(ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.22), handlelength=1.0,
              columnspacing=0.7, handletextpad=0.4)
    save(fig, "fig_forecast_mae")


def fig_multi_seed():
    data = {r["model"]: r for r in rows(EXP / "multi_seed_summary.csv")}
    order = ["proposed", "gru", "temporal_transformer"]
    fig, ax = plt.subplots(figsize=(COL, 2.1))
    for i, m in enumerate(order):
        r = data[m]
        means = [float(r[f"mae_{h}m_mean"]) for h in HORIZONS]
        sds = [float(r[f"mae_{h}m_sd"]) for h in HORIZONS]
        xs = [h + (i - 1) * 0.18 for h in range(3)]
        ax.errorbar(xs, means, yerr=sds, fmt="o", ms=3.5, capsize=2, lw=0.8, color=MODEL_COLOR[m],
                    label=MODEL_LABEL[m])
    ax.set_xticks(range(3))
    ax.set_xticklabels([f"{h} min" for h in HORIZONS])
    ax.set_ylabel("Test MAE (mph), 3 seeds")
    ax.legend(frameon=False, loc="upper left")
    ax.set_ylim(4.5, 6.4)
    save(fig, "fig_multi_seed")


def fig_conformal_coverage():
    groups = [("all", "All"), ("free_ratio>=0.8", "Free flow"), ("moderate_0.5-0.8", "Moderate"),
              ("congested<0.5", "Congested")]
    cov = {(r["group"], int(r["horizon_min"])): float(r["empirical_coverage"])
           for r in rows(EXP / "uncertainty_metrics.csv")}
    fig, ax = plt.subplots(figsize=(COL, 2.1))
    width = 0.2
    shades = ["#1f4e79", "#2e75b6", "#9dc3e6", "#c55a11"]
    for i, (g, label) in enumerate(groups):
        xs = [h + (i - 1.5) * width for h in range(3)]
        ax.bar(xs, [cov[(g, h)] for h in HORIZONS], width=width * 0.95, color=shades[i], label=label,
               edgecolor="white", linewidth=0.3)
    ax.axhline(0.9, color="black", lw=0.7, ls="--")
    ax.text(2.42, 0.905, "nominal 0.90", fontsize=6, ha="right", va="bottom")
    ax.set_xticks(range(3))
    ax.set_xticklabels([f"{h} min" for h in HORIZONS])
    ax.set_ylabel("Empirical coverage")
    ax.set_ylim(0.6, 1.0)
    ax.legend(ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.14), handlelength=1.0,
              columnspacing=0.8)
    save(fig, "fig_conformal_coverage")


def fig_ablation():
    labels = {"ablation_no_gate": "Without availability gate", "ablation_no_weather": "Without weather features",
              "ablation_no_infrastructure": "Without 311 features"}
    items = [r for r in rows(EXP / "ablation_metrics.csv") if r["variant"] in labels and r["status"] == "OK"]
    fig, ax = plt.subplots(figsize=(COL, 1.6))
    ys = range(len(items))
    for y, r in zip(ys, items):
        d = float(r["delta_vs_proposed_mph"])
        lo, hi = float(r["ci95_low"]), float(r["ci95_high"])
        ax.errorbar([d], [y], xerr=[[d - lo], [hi - d]], fmt="o", ms=3.5, capsize=2.5, lw=0.9,
                    color=C["warn"] if d > 0 else C["ok"])
    ax.axvline(0, color="black", lw=0.6)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([labels[r["variant"]] for r in items])
    ax.set_xlabel("Change in test MAE vs. proposed (mph), 95 % bootstrap interval over test days")
    ax.invert_yaxis()
    save(fig, "fig_ablation")


def fig_shap_groups():
    s = json.load(open(ART / "explanations" / "explanations_summary.json"))
    g = s["global_grouped_mean_abs_shap_mph"]
    label = {"traffic_target_last30min": "Target speed, last 30 min",
             "traffic_target_30_120min": "Target speed, 30-120 min",
             "traffic_graph_neighbours": "Graph neighbours", "calendar": "Calendar", "weather": "Weather",
             "infrastructure": "Infrastructure (311)"}
    items = sorted(g.items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(COL, 1.7))
    ax.barh([label[k] for k, _ in items], [v for _, v in items], color=C["proposed"], height=0.6)
    for i, (_, v) in enumerate(items):
        ax.text(v + 0.1, i, f"{v:.2f}", va="center", fontsize=6)
    ax.set_xlabel("Mean |SHAP| (mph) over 12 explained test points")
    ax.set_xlim(0, 9.6)
    save(fig, "fig_shap_groups")


def fig_temporal_window():
    s = json.load(open(ART / "explanations" / "explanations_summary.json"))
    tw = sorted(s["temporal_window"], key=lambda d: d["minutes_kept"])
    fig, ax = plt.subplots(figsize=(COL, 1.7))
    ax.plot([d["minutes_kept"] for d in tw], [d["mae_mph"] for d in tw], "o-", color=C["proposed"], ms=3.5)
    for d in tw:
        ax.text(d["minutes_kept"], d["mae_mph"] + 0.08, f"{d['mae_mph']:.2f}", ha="center", fontsize=6)
    ax.set_xlabel("Minutes of input history kept")
    ax.set_ylabel("Test MAE (mph)")
    ax.set_xticks([5, 15, 30, 60, 120])
    ax.set_ylim(5.0, 7.6)
    save(fig, "fig_temporal_window")


def fig_deferral():
    data = defaultdict(list)
    for r in rows(ART / "calibration" / "deferral_tradeoff.csv"):
        data[int(r["horizon_min"])].append((float(r["deferral_rate"]), float(r["mae_retained"]),
                                            float(r["missing_threshold"])))
    fig, ax = plt.subplots(figsize=(COL, 1.9))
    shades = {15: "#9dc3e6", 30: "#2e75b6", 60: "#1f4e79"}
    for h in HORIZONS:
        pts = sorted(data[h])
        ax.plot([p[0] * 100 for p in pts], [p[1] for p in pts], "o-", ms=2.5, color=shades[h], label=f"{h} min")
        chosen = [p for p in pts if abs(p[2] - 0.34) < 1e-6]
        if chosen:
            ax.plot(chosen[0][0] * 100, chosen[0][1], "s", ms=5, mfc="none", mec="black", mew=0.8)
    ax.set_xlabel("Deferred origins (%)")
    ax.set_ylabel("MAE on retained origins (mph)")
    ax.legend(frameon=False, title="Horizon", title_fontsize=7)
    ax.text(0.98, 0.97, "square: chosen threshold (0.34)", transform=ax.transAxes, ha="right", va="top", fontsize=6)
    save(fig, "fig_deferral")


# ----------------------------------------------------------------------------------------------------------
# Live runs
# ----------------------------------------------------------------------------------------------------------
def fig_live_by_day():
    byday = defaultdict(dict)
    for r in rows(EXP / "live_metrics_by_day.csv"):
        byday[r["origin_date"]][int(r["horizon_minutes"])] = (float(r["mae_mph"]), float(r["persistence_mae_mph"]),
                                                                int(r["n_scored"]))
    pooled = {int(r["horizon_minutes"]): (float(r["mae_mph"]), float(r["persistence_mae_mph"]), int(r["n_scored"]))
              for r in rows(EXP / "live_metrics.csv") if r["mode"] == "LIVE"}
    days = sorted(byday)
    labels = {"2026-10-30": "Fri 30 Oct", "2026-11-16": "Mon 16 Nov", "2026-11-18": "Wed 18 Nov"}
    panels = [(labels.get(d, d), byday[d]) for d in days] + [("Pooled", pooled)]
    fig, axes = plt.subplots(1, len(panels), figsize=(DBL, 1.9), sharey=True)
    for ax, (title, d) in zip(axes, panels):
        xs = range(3)
        ax.bar([x - 0.19 for x in xs], [d[h][0] for h in HORIZONS], width=0.36, color=C["proposed"], label="Model")
        ax.bar([x + 0.19 for x in xs], [d[h][1] for h in HORIZONS], width=0.36, color=C["persistence"],
               label="Persistence")
        n = d[15][2]
        ax.set_title(f"{title} (n = {n} per horizon)", fontsize=7)
        ax.set_xticks(list(xs))
        ax.set_xticklabels([f"{h}" for h in HORIZONS])
        ax.set_xlabel("Horizon (min)")
    axes[0].set_ylabel("MAE (mph)")
    axes[0].set_ylim(0, 8.3)
    axes[0].legend(frameon=False, loc="upper left")
    save(fig, "fig_live_by_day")


# ----------------------------------------------------------------------------------------------------------
# SUMO
# ----------------------------------------------------------------------------------------------------------
def fig_sumo_calibration():
    d = json.load(open(ROOT / "simulation" / "scenarios" / "split_calibration_v6_counts2025_cycle_splits_offsets.json"))
    target = d["rule"]["target_speed_mph"]
    tol = d["rule"].get("tolerance_mph", 1.5)
    series = defaultdict(list)
    for c in d["per_factor"]:
        cyc = c["common_cycle_s"]
        key = ("Webster per signal" if cyc is None else f"{int(cyc)} s common cycle") + \
              (", 25 mph offsets" if c["progression_speed_mph"] else "")
        series[key].append((c["green_factor"], c["speed_mean_mph"]))
    fig, ax = plt.subplots(figsize=(COL, 2.2))
    ax.axhspan(target - tol, target + tol, color="#e2efda", zorder=0)
    ax.axhline(target, color=C["ok"], lw=0.8, ls="--")
    ax.text(3.0, target + 0.15, f"observed {target} mph ± {tol}", fontsize=6, ha="right", va="bottom")
    styles = {"Webster per signal": ("o", "#7f7f7f", "-"), "Webster per signal, 25 mph offsets": ("o", "#7f7f7f", "--"),
              "90 s common cycle": ("s", C["proposed"], "-"), "90 s common cycle, 25 mph offsets": ("s", C["proposed"], "--"),
              "120 s common cycle": ("^", C["gru"], "-"), "120 s common cycle, 25 mph offsets": ("^", C["gru"], "--")}
    for key, pts in series.items():
        pts.sort()
        m, col, ls = styles.get(key, ("o", "black", "-"))
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker=m, ls=ls, color=col, ms=3.5, label=key)
    sel = d["selected_cell"]
    ax.plot(sel["green_factor"], d["selected_speed_mph"], "*", ms=10, color="black", zorder=5)
    ax.set_xlabel("Corridor green factor")
    ax.set_ylabel("Simulated speed on\nthe DOT link (mph)")
    ax.legend(frameon=False, fontsize=5.6, loc="upper left", ncol=2, handlelength=1.8, columnspacing=0.8)
    ax.set_ylim(4, 33)
    save(fig, "fig_sumo_calibration")


def fig_sumo_comparison():
    agg = defaultdict(list)
    for r in rows(EXP / "simulation_metrics.csv"):
        if r["network_hash"] in ("36fb9c1fb895b7e7", "98e143b6f4e1296a") and r["status"] == "OK":
            agg[(r["scenario"], r["controller"])].append((float(r["mean_time_loss_s"]), int(r["completed_trips"])))
    scen = [("routine_peak", "Routine peak"), ("event_surge", "Event surge"),
            ("incident_reduced_capacity", "Incident")]
    ctrl = [("fixed_time", "Fixed time", C["persistence"], ""), ("forecast_rule", "Forecast-triggered rule", C["proposed"], ""),
            ("actuated", "Actuated (reference, uncalibrated)", "white", "//")]
    fig, axes = plt.subplots(1, 2, figsize=(DBL, 2.0))
    width = 0.26
    for ax, (idx, ylabel) in zip(axes, ((0, "Mean time loss per vehicle (s)"), (1, "Completed trips"))):
        for j, (c, label, col, hatch) in enumerate(ctrl):
            xs = [i + (j - 1) * width for i in range(3)]
            vals = [sum(v[idx] for v in agg[(s, c)]) / len(agg[(s, c)]) for s, _ in scen]
            ax.bar(xs, vals, width=width * 0.95, color=col, edgecolor=C["edge"], linewidth=0.5, hatch=hatch, label=label)
        ax.set_xticks(range(3))
        ax.set_xticklabels([s for _, s in scen])
        ax.set_ylabel(ylabel)
    # annotate change of the rule against fixed time
    ax = axes[0]
    for i, (s, _) in enumerate(scen):
        f = sum(v[0] for v in agg[(s, "fixed_time")]) / 5
        r = sum(v[0] for v in agg[(s, "forecast_rule")]) / 5
        a = sum(v[0] for v in agg[(s, "actuated")]) / 5
        ax.text(i, max(f, r, a) + 15, f"rule vs fixed: {(r - f) / f * 100:+.1f} %", ha="center", fontsize=6)
    axes[0].set_ylim(0, 640)
    axes[1].set_ylim(4000, 6200)
    axes[0].legend(frameon=False, fontsize=6, loc="upper left")
    save(fig, "fig_sumo_comparison")


# ----------------------------------------------------------------------------------------------------------
# Advisory and retrieval
# ----------------------------------------------------------------------------------------------------------
def fig_advisory_decisions():
    pol = [("llm_without_retrieval", "LLM only"), ("rag_without_constraints", "RAG, no\nconstraints"),
           ("rag_constraints_without_simulation", "RAG +\nconstraints"), ("full_system", "Full system\n(+ simulation)")]
    dec = [("PENDING_HUMAN_REVIEW", "Pending human review", C["ok"]), ("DEFER_UNCERTAINTY", "Deferred: uncertainty", "#9dc3e6"),
           ("DEFER_DATA", "Deferred: data", "#2e75b6"), ("DEFER_EVIDENCE", "Deferred: evidence", "#1f4e79"),
           ("REJECT_CONSTRAINT", "Rejected by constraint", C["warn"])]
    cnt = defaultdict(int)
    for r in rows(EXP / "advisory_metrics.csv"):
        cnt[(r["policy"], r["decision"])] += 1
    fig, ax = plt.subplots(figsize=(COL, 2.0))
    bottoms = [0] * len(pol)
    for code, label, col in dec:
        vals = [cnt[(p, code)] for p, _ in pol]
        ax.bar(range(len(pol)), vals, bottom=bottoms, color=col, label=label, edgecolor="white", linewidth=0.3)
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_xticks(range(len(pol)))
    ax.set_xticklabels([l for _, l in pol], fontsize=6.3)
    ax.set_ylabel("Replayed cases")
    ax.set_yticks(range(0, 8))
    ax.legend(frameon=False, fontsize=5.8, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    save(fig, "fig_advisory_decisions")


def fig_retrieval_queries():
    rs = rows(EXP / "retrieval_metrics.csv")
    fig, ax = plt.subplots(figsize=(COL, 1.8))
    xs, rec, rr = [], [], []
    for r in rs:
        if r["recall@8"] == "":
            continue
        xs.append(r["query_id"])
        rec.append(float(r["recall@8"]))
        rr.append(float(r["reciprocal_rank"]))
    pos = range(len(xs))
    ax.bar([p - 0.2 for p in pos], rec, width=0.4, color=C["proposed"], label="Recall@8")
    ax.bar([p + 0.2 for p in pos], rr, width=0.4, color="#9dc3e6", label="Reciprocal rank")
    ax.set_xticks(list(pos))
    ax.set_xticklabels(xs, rotation=90, fontsize=5.5)
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.18), fontsize=6)
    ax.set_ylabel("Score")
    save(fig, "fig_retrieval_queries")


def main():
    fig_system_architecture()
    fig_model_architecture()
    fig_code_structure()
    fig_forecast_mae()
    fig_multi_seed()
    fig_conformal_coverage()
    fig_ablation()
    fig_shap_groups()
    fig_temporal_window()
    fig_deferral()
    fig_live_by_day()
    fig_sumo_calibration()
    fig_sumo_comparison()
    fig_advisory_decisions()
    fig_retrieval_queries()


if __name__ == "__main__":
    main()
