"""Draw the figures of the IEEE conference paper from the project's own result files.

    python paper/word/make_figures.py

Every plotted number is read from reports/experiments/, artifacts/calibration/ or artifacts/explanations/;
the block diagrams describe the code in src/smartcity/. Dashboard figures are crops of the stored dashboard
screenshots in presentation/assets/dashboard/. Output: paper/word/figures/*.png (300 dpi).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from PIL import Image  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
EXP = REPO / "reports" / "experiments"
CAL = REPO / "artifacts" / "calibration"
EXPL = REPO / "artifacts" / "explanations"
OUT = HERE / "figures"

COL_IN = 3.38   # one column of the A4 template
FULL_IN = 7.0   # both columns
DPI = 300

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Liberation Serif", "Times New Roman", "DejaVu Serif"],
    "font.size": 7.5, "axes.titlesize": 7.5, "axes.labelsize": 7.5, "xtick.labelsize": 6.8,
    "ytick.labelsize": 6.8, "legend.fontsize": 6.6, "axes.linewidth": 0.6, "xtick.major.width": 0.5,
    "ytick.major.width": 0.5, "lines.linewidth": 1.0, "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "savefig.dpi": DPI, "mathtext.fontset": "stix",
})

# a muted palette that stays distinct in greyscale print
INK = "#1f2933"
C_PROP = "#1d4e89"
C_GRU = "#c8553d"
C_TR = "#5b8e7d"
C_TREE = "#9a8c98"
C_BASE = "#b8b8b8"
C_PERS = "#8d99ae"
FILL = {"data": "#e8eef6", "proc": "#eef5ec", "model": "#dfe9f5", "unc": "#fdf1dc", "agent": "#f3e8f4",
        "safe": "#fbe4e1", "sim": "#e9e9e9", "out": "#ffffff"}

H = [15, 30, 60]


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=DPI, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------------------------------------
# diagram helpers


def box(ax, x, y, w, h, text, kind="proc", size=6.6, bold_first=True, lw=0.6, ec=INK, style="round,pad=0.02"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=style, fc=FILL[kind], ec=ec, lw=lw,
                                mutation_scale=1.0))
    lines = text.split("\n")
    if bold_first and len(lines) > 1:
        ax.text(x + w / 2, y + h / 2, lines[0] + "\n", ha="center", va="center", fontsize=size,
                fontweight="bold", color=INK, linespacing=1.15 * len(lines) / max(len(lines), 1))
        ax.text(x + w / 2, y + h / 2, "\n" + "\n".join(lines[1:]), ha="center", va="center", fontsize=size - 0.6,
                color=INK, linespacing=1.15)
    else:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size,
                fontweight="bold" if bold_first else "normal", color=INK, linespacing=1.15)


def label_box(ax, x, y, w, h, title, body, kind="proc", tsize=6.8, bsize=6.0):
    """A box with a bold title line and smaller body lines, laid out top-down."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02", fc=FILL[kind], ec=INK, lw=0.6,
                                mutation_scale=1.0))
    n = body.count("\n") + 1 if body else 0
    block = (1 + n) * 1.0
    top = y + h / 2 + block / 2 * 1.0
    ax.text(x + w / 2, y + h / 2 + (n * 0.5) * LINE, title, ha="center", va="center", fontsize=tsize,
            fontweight="bold", color=INK)
    if body:
        ax.text(x + w / 2, y + h / 2 - 0.5 * LINE, body, ha="center", va="center", fontsize=bsize, color=INK,
                linespacing=1.15)
    del top


LINE = 1.0  # set per figure (data units of one text line)


def arrow(ax, p, q, color=INK, lw=0.7, style="-|>", rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=6, color=color, lw=lw,
                                 connectionstyle=f"arc3,rad={rad}", linestyle=ls, shrinkA=0, shrinkB=0))


def tag(ax, x, y, text, fc, size=5.6):
    ax.text(x, y, text, ha="center", va="center", fontsize=size, color="white", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", fc=fc, ec="none"))


# ---------------------------------------------------------------------------------------------------------
# Fig. 1: system architecture (full width)


def fig_architecture() -> None:
    global LINE
    fig, ax = plt.subplots(figsize=(FULL_IN, 3.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 44)
    ax.axis("off")
    LINE = 1.75
    T, B = 6.3, 5.4

    ax.text(7.25, 42.6, "Public data sources", ha="center", va="center", fontsize=6.6, fontweight="bold",
            color=INK)
    srcs = [("Link speeds", "26 links, 5-min"), ("Weather", "forecast, reanalysis"),
            ("311 requests", "24 h lag"), ("Collisions, events", "retrospective only"),
            ("Counts, street map", "simulation only")]
    for k, (t, b) in enumerate(srcs):
        y = 34.4 - k * 7.6
        label_box(ax, 0.5, y, 13.5, 6.2, t, b, "data", tsize=6.0, bsize=5.2)
        ax.plot([14.1, 15.6], [y + 3.1, y + 3.1], color=INK, lw=0.7)
    ax.plot([15.6, 15.6], [37.5, 7.1], color=INK, lw=0.7)
    arrow(ax, (15.6, 35), (17.4, 35))

    xs, w = [17.5, 39.0, 60.5, 82.0], 17.8
    top = [("Ingestion and audit", "schema and range checks\nprovenance log\nzero-speed flags\ntime alignment",
            "proc"),
           ("Features and graph", "5-min grid, 2 h window\nsix feature groups\ndirected link graph\n"
            "purged time split", "proc"),
           ("Forecaster", "feature-group gate\n2 x GATv2 (space)\nTransformer (time)\n15/30/60-min heads",
            "model"),
           ("Uncertainty", "split-conformal 90%\nreliability gate on width,\nmissing share, data age,\n"
            "sample support", "unc")]
    for x, (t, b, k) in zip(xs, top):
        label_box(ax, x, 29.5, w, 11, t, b, k, tsize=T, bsize=B)
    for a, b in zip(xs[:-1], xs[1:]):
        arrow(ax, (a + w + 0.1, 35), (b - 0.1, 35))

    bot = [("Simulation gate", "calibrated SUMO testbed\nmatched seeds\ncandidate vs fixed time", "sim"),
           ("Safety constraints", "allowed actions only\ngreen limits, clearance\nmapped corridor only\n"
            "citations checked", "safe"),
           ("Advisory agent", "fixed state machine\none LLM node, JSON out\nmonitor-only default\n"
            "citations required", "agent"),
           ("Explanations", "exact grouped KernelSHAP\nneighbour removal\ntemporal window test", "unc")]
    for x, (t, b, k) in zip(xs, bot):
        label_box(ax, x, 13.0, w, 11, t, b, k, tsize=T, bsize=B)
    arrow(ax, (xs[3] + w / 2, 29.4), (xs[3] + w / 2, 24.1))
    for a, b in zip(xs[1:], xs[:-1]):
        arrow(ax, (a - 0.1, 18.5), (b + w + 0.1, 18.5))

    label_box(ax, xs[2], 1.0, w, 8.4, "Evidence retrieval", "15 public documents\n1,633 chunks, FAISS",
              "agent", tsize=T, bsize=B)
    arrow(ax, (xs[2] + w / 2, 9.5), (xs[2] + w / 2, 12.9))
    label_box(ax, xs[0], 1.0, w, 8.4, "Human review", "pending human review\nno signal is changed", "out",
              tsize=T, bsize=B)
    arrow(ax, (xs[0] + w / 2, 12.9), (xs[0] + w / 2, 9.5))
    label_box(ax, xs[1], 1.0, w, 8.4, "Dashboard and API", "12 pages, audit trail\nmode label on each view",
              "out", tsize=T, bsize=B)
    arrow(ax, (xs[0] + w + 0.1, 5.2), (xs[1] - 0.1, 5.2))
    ax.text(xs[3] + w / 2, 5.2, "early exits to the report:\nDEFER_DATA, DEFER_UNCERTAINTY,\nDEFER_EVIDENCE, "
            "REJECT_SCHEMA,\nREJECT_CONSTRAINT,\nREJECT_SIMULATION", ha="center", va="center", fontsize=4.9,
            color=INK, linespacing=1.15,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#888888", lw=0.5, ls="--"))

    tag(ax, 58, 42.6, "LIVE", "#2e7d32")
    tag(ax, 65, 42.6, "REPLAY", "#d17a00")
    tag(ax, 74.5, 42.6, "SIMULATION", "#555555")
    ax.text(81.5, 42.6, "mode label carried by every output", ha="left", va="center", fontsize=5.6, color=INK)
    save(fig, "fig01_architecture")


# ---------------------------------------------------------------------------------------------------------
# Fig. 2: forecaster


def fig_forecaster() -> None:
    global LINE
    fig, ax = plt.subplots(figsize=(COL_IN, 3.25))
    ax.set_xlim(0, 50)
    ax.set_ylim(0, 50)
    ax.axis("off")
    LINE = 1.75
    groups = ["own speed\n0-30 min", "own speed\n30-120 min", "neighbour\nspeeds", "calendar", "weather",
              "311 infra-\nstructure"]
    w = 7.6
    for k, g in enumerate(groups):
        x = 0.6 + k * 8.2
        box(ax, x, 44, w, 5.2, g, "data", size=5.6, bold_first=False)
        arrow(ax, (x + w / 2, 43.9), (x + w / 2, 41.1))
    box(ax, 0.6, 37.6, 48.8, 3.4, "per-group linear projection to d = 64 (missing groups flagged)", "proc",
        size=6.0, bold_first=False)
    arrow(ax, (25, 37.5), (25, 35.2))
    label_box(ax, 0.6, 29.0, 48.8, 6.1, "Availability-masked softmax gate",
              "weights over the groups that are present at this step", "unc", tsize=6.6, bsize=5.8)
    arrow(ax, (25, 28.9), (25, 26.7))
    label_box(ax, 0.6, 20.4, 48.8, 6.2, "Spatial block: 2 x GATv2",
              "4 heads, residual + layer norm, over the directed link graph", "model", tsize=6.6, bsize=5.8)
    arrow(ax, (25, 20.3), (25, 18.1))
    label_box(ax, 0.6, 11.8, 48.8, 6.2, "Temporal block: Transformer encoder",
              "2 layers, 4 heads, FF 128, dropout 0.1, L = 24 steps (2 h)", "model", tsize=6.6, bsize=5.8)
    for k, hzn in enumerate(H):
        x = 3.0 + k * 16.0
        arrow(ax, (x + 6.5, 11.7), (x + 6.5, 9.4))
        box(ax, x, 5.0, 13.0, 4.3, f"{hzn}-min head", "out", size=6.2)
        arrow(ax, (x + 6.5, 4.9), (x + 6.5, 3.4))
    ax.text(25, 1.6, "point forecast  ->  split-conformal 90% interval  ->  reliability gate",
            ha="center", va="center", fontsize=5.9, color=INK)
    save(fig, "fig02_forecaster")


# ---------------------------------------------------------------------------------------------------------
# Fig. 3: advisory workflow


def fig_workflow() -> None:
    global LINE
    fig, ax = plt.subplots(figsize=(COL_IN, 3.2))
    ax.set_xlim(0, 50)
    ax.set_ylim(1.5, 54.5)
    ax.axis("off")
    LINE = 1.6
    nodes = [("Data quality", "missing share, data age", "DEFER_DATA"),
             ("Forecast", "15 / 30 / 60 min", None),
             ("Uncertainty gate", "interval width, support", "DEFER_UNCERTAINTY"),
             ("Explanation", "grouped SHAP", None),
             ("Retrieval", "top-8 passages, min score", "DEFER_EVIDENCE"),
             ("Recommendation", "the only LLM call, JSON", "REJECT_SCHEMA"),
             ("Safety constraints", "deterministic rules", "REJECT_CONSTRAINT"),
             ("Simulation gate", "SUMO, matched seeds", "REJECT_SIMULATION"),
             ("Human review", "approve / reject", None)]
    y0 = 54.0
    y = y0
    hgt, gap = 4.4, 1.45
    for k, (t, b, exit_) in enumerate(nodes):
        kind = {"Recommendation": "agent", "Retrieval": "agent", "Safety constraints": "safe",
                "Simulation gate": "sim", "Human review": "out", "Uncertainty gate": "unc"}.get(t, "proc")
        label_box(ax, 2, y - hgt, 24, hgt, t, b, kind, tsize=6.4, bsize=5.5)
        if k < len(nodes) - 1:
            arrow(ax, (14, y - hgt - 0.05), (14, y - hgt - gap + 0.05))
        if exit_:
            arrow(ax, (26.1, y - hgt / 2), (31.4, y - hgt / 2), color="#a23b2a", ls="-")
            ax.text(31.8, y - hgt / 2, exit_, ha="left", va="center", fontsize=5.6, color="#a23b2a",
                    fontweight="bold")
        y -= hgt + gap
    ax.text(31.8, y0 - 8 * (hgt + gap) - hgt / 2, "PENDING_HUMAN_REVIEW\n(monitor-only advisory)",
            ha="left", va="center", fontsize=5.6, color="#2e7d32", fontweight="bold")
    arrow(ax, (26.1, y0 - 8 * (hgt + gap) - hgt / 2), (31.4, y0 - 8 * (hgt + gap) - hgt / 2),
          color="#2e7d32")
    save(fig, "fig03_workflow")


# ---------------------------------------------------------------------------------------------------------
# Fig. 4: code structure


def fig_modules() -> None:
    fig, ax = plt.subplots(figsize=(COL_IN, 2.45))
    ax.set_xlim(0, 51)
    ax.set_ylim(0, 41)
    ax.axis("off")
    layers = [
        ("Data", ["ingestion", "preprocessing", "db"], "data"),
        ("Learning", ["features", "graph", "models", "training"], "model"),
        ("Trust", ["uncertainty", "explainability", "evaluation"], "unc"),
        ("Decision", ["knowledge", "rag", "agents"], "agent"),
        ("Safety", ["safety", "simulation"], "safe"),
        ("Delivery", ["live", "api", "dashboard", "reporting"], "out"),
    ]
    y = 40.5
    for title, mods, kind in layers:
        ax.text(0.3, y - 2.5, title, ha="left", va="center", fontsize=6.3, fontweight="bold", color=INK)
        n = len(mods)
        w = (50.5 - 9.5 - 0.8 * (n - 1)) / n
        for k, m in enumerate(mods):
            x = 9.5 + k * (w + 0.8)
            ax.add_patch(FancyBboxPatch((x, y - 4.4), w, 3.8, boxstyle="round,pad=0.02", fc=FILL[kind], ec=INK,
                                        lw=0.5, mutation_scale=1.0))
            ax.text(x + w / 2, y - 2.5, m, ha="center", va="center", fontsize=5.4, family="monospace",
                    color=INK)
        y -= 6.0
    ax.text(25.5, 2.0, "shared by all layers: typed record contracts, settings, one command-line entry point",
            ha="center", va="center", fontsize=5.6, color=INK, style="italic")
    save(fig, "fig04_modules")


# ---------------------------------------------------------------------------------------------------------
# result figures


def fig_mae() -> None:
    df = pd.read_csv(EXP / "forecast_metrics.csv")
    df = df[(df.split == "test") & (df.track == "operational")]
    order = ["persistence", "historical_average", "xgboost", "lightgbm", "gru", "temporal_transformer", "proposed"]
    names = ["Persistence", "Hist. avg.", "XGBoost", "LightGBM", "GRU", "Temp. Transf.", "Proposed"]
    cols = [C_PERS, C_BASE, C_TREE, "#c9ada7", C_GRU, C_TR, C_PROP]
    fig, ax = plt.subplots(figsize=(COL_IN, 1.95))
    w = 0.115
    x = np.arange(len(H))
    for k, m in enumerate(order):
        vals = [df[(df.model == m) & (df.horizon_min == h)].mae_mph.iloc[0] for h in H]
        ax.bar(x + (k - 3) * w, vals, w, color=cols[k], label=names[k], ec="white", lw=0.3)
    ax.set_xticks(x, [f"{h} min" for h in H])
    ax.set_ylabel("Test MAE (mph)")
    ax.set_ylim(4, 8)
    ax.grid(axis="y", lw=0.3, color="#dddddd")
    ax.set_axisbelow(True)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.27), handlelength=1.0, columnspacing=0.8)
    save(fig, "fig06_mae")


def fig_seeds() -> None:
    df = pd.read_csv(EXP / "multi_seed_metrics.csv")
    models = [("proposed", "Proposed", C_PROP, "o"), ("gru", "GRU", C_GRU, "s"),
              ("temporal_transformer", "Temp. Transf.", C_TR, "^")]
    fig, axes = plt.subplots(1, 3, figsize=(COL_IN, 1.6))
    for ax, h in zip(axes, H):
        for k, (m, lab, c, mk) in enumerate(models):
            v = df[(df.model == m) & (df.horizon_min == h)].mae_mph.values
            ax.scatter(np.full(len(v), k) + np.array([-0.08, 0, 0.08])[:len(v)], v, s=9, color=c, marker=mk,
                       alpha=0.55, lw=0)
            ax.errorbar(k + 0.25, v.mean(), yerr=v.std(ddof=1), fmt=mk, color=c, ms=3.2, capsize=1.8, lw=0.8)
        ax.set_xticks(range(3), ["Prop.", "GRU", "Trf."], rotation=0)
        ax.set_title(f"{h} min", pad=2)
        ax.grid(axis="y", lw=0.3, color="#dddddd")
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", labelsize=5.8)
        ax.set_xlim(-0.5, 2.6)
    axes[0].set_ylabel("Test MAE (mph)")
    fig.tight_layout(w_pad=1.3)
    save(fig, "fig07_seeds")


def fig_ablation_window() -> None:
    ab = pd.read_csv(EXP / "ablation_metrics.csv")
    ab = ab[ab.status == "OK"]
    names = {"ablation_no_gate": "no gate", "ablation_no_weather": "no weather",
             "ablation_no_infrastructure": "no 311 group"}
    tw = pd.read_csv(EXPL / "temporal_window_sensitivity.csv").sort_values("minutes_kept")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(COL_IN, 1.55), gridspec_kw={"width_ratios": [1.05, 1]})
    y = np.arange(len(ab))
    d = ab.delta_vs_proposed_mph.values
    lo, hi = ab.ci95_low.values, ab.ci95_high.values
    cols = ["#a23b2a" if v > 0 else "#2e7d32" for v in d]
    a1.barh(y, d, color=cols, height=0.5)
    a1.errorbar(d, y, xerr=[d - lo, hi - d], fmt="none", ecolor=INK, capsize=1.8, lw=0.7)
    a1.axvline(0, color=INK, lw=0.5)
    a1.set_yticks(y, [names[v] for v in ab.variant])
    a1.set_xlabel("Δ MAE vs. full model (mph)")
    a1.set_title("(a) feature-group ablation", pad=2)
    a1.spines["left"].set_visible(False)
    a1.tick_params(axis="y", length=0)
    a2.plot(tw.minutes_kept, tw.mae_mph, "o-", color=C_PROP, ms=3)
    a2.set_xscale("log")
    a2.set_xticks(tw.minutes_kept.tolist(), [str(v) for v in tw.minutes_kept])
    a2.minorticks_off()
    a2.set_xlabel("own history kept (min)")
    a2.set_ylabel("MAE (mph)")
    a2.set_title("(b) temporal window", pad=2)
    a2.grid(lw=0.3, color="#dddddd")
    fig.tight_layout(w_pad=1.0)
    save(fig, "fig08_ablation_window")


def fig_uncertainty() -> None:
    dt = pd.read_csv(CAL / "deferral_tradeoff.csv")
    groups = [("free_ratio>=0.8", "free flow"), ("moderate_0.5-0.8", "moderate"), ("congested<0.5", "congested"),
              ("rush_hour_7-10_16-19", "rush hour"), ("non_rush", "off-peak"), ("weather_dry", "dry"),
              ("weather_wet_code", "wet")]
    unc = pd.read_csv(EXP / "uncertainty_metrics.csv")
    m = np.array([[unc[(unc.horizon_min == h) & (unc.group == g)].empirical_coverage.iloc[0] for h in H]
                  for g, _ in groups])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(COL_IN, 1.95), gridspec_kw={"width_ratios": [1.0, 1.05]})
    im = a1.imshow(m, cmap="RdYlGn", vmin=0.75, vmax=0.95, aspect="auto")
    a1.set_xticks(range(3), [f"{h} min" for h in H])
    a1.set_yticks(range(len(groups)), [g for _, g in groups])
    for i in range(m.shape[0]):
        for j in range(3):
            a1.text(j, i, f"{m[i, j]:.2f}", ha="center", va="center", fontsize=5.8,
                    color="white" if m[i, j] < 0.8 else INK)
    a1.set_title("(a) coverage by condition", pad=2)
    a1.tick_params(length=0)
    for sp in a1.spines.values():
        sp.set_visible(False)
    cb = fig.colorbar(im, ax=a1, fraction=0.06, pad=0.03)
    cb.ax.tick_params(labelsize=5.5, length=1.5)
    cb.outline.set_linewidth(0.4)
    for k, h in enumerate(H):
        d = dt[dt.horizon_min == h].sort_values("deferral_rate")
        a2.plot(d.deferral_rate * 100, d.mae_retained, "o-", ms=2.4, color=[C_PROP, C_TR, C_GRU][k],
                label=f"{h} min")
        a2.text(d.deferral_rate.iloc[0] * 100, d.mae_retained.iloc[0] + 0.1, f"{h} min", fontsize=5.6,
                color=[C_PROP, C_TR, C_GRU][k], ha="left", va="bottom")
    a2.set_ylim(3.3, 5.6)
    a2.set_xlabel("deferred forecasts (%)")
    a2.set_ylabel("MAE of retained (mph)")
    a2.set_title("(b) deferral trade-off", pad=2)
    a2.grid(lw=0.3, color="#dddddd")
    fig.tight_layout(w_pad=0.6)
    save(fig, "fig09_uncertainty")


def fig_shap() -> None:
    js = json.loads((EXPL / "explanations_summary.json").read_text(encoding="utf-8"))
    g = js["global_grouped_mean_abs_shap_mph"]
    names = {"traffic_target_last30min": "own speed, last 30 min", "traffic_target_30_120min":
             "own speed, 30-120 min", "calendar": "calendar", "traffic_graph_neighbours": "neighbour links",
             "weather": "weather", "infrastructure": "311 infrastructure"}
    items = sorted(g.items(), key=lambda kv: kv[1])
    tree = next(t for t in js["tree_baseline_shap"] if t["model"] == "lightgbm")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(COL_IN, 1.7), gridspec_kw={"width_ratios": [1.6, 0.8]})
    a1.barh(range(len(items)), [v for _, v in items], color=C_PROP, height=0.55)
    a1.set_yticks(range(len(items)), [names[k] for k, _ in items])
    a1.set_xlabel("mean |attribution| (mph)")
    a1.set_title("(a) proposed model (KernelSHAP)", pad=2, fontsize=6.8)
    a1.tick_params(axis="y", length=0, labelsize=6.2)
    a1.spines["left"].set_visible(False)
    for k, (_, v) in enumerate(items):
        a1.text(v + 0.12, k, f"{v:.2f}", va="center", fontsize=5.8)
    a1.set_xlim(0, 10)
    keys = ["traffic", "calendar", "weather", "link_identity", "infrastructure"]
    lab = ["traffic lags", "calendar", "weather", "link id.", "311"]
    cols = [C_PROP, C_TR, "#7aa6c2", C_TREE, C_GRU]
    bottom = np.zeros(3)
    for k, key in enumerate(keys):
        vals = []
        for h in H:
            gm = tree["by_horizon"][str(h)]["grouped_mean_abs_shap_z"]
            tot = sum(gm.values())
            vals.append(gm.get(key, 0) / tot * 100)
        a2.bar(range(3), vals, bottom=bottom, color=cols[k], label=lab[k], width=0.6)
        bottom += np.array(vals)
    a2.set_xticks(range(3), [str(h) for h in H])
    a2.set_xlabel("horizon (min)")
    a2.set_ylabel("share (%)")
    a2.set_title("(b) LightGBM", pad=2, fontsize=6.8)
    a2.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), handlelength=0.8)
    fig.tight_layout(w_pad=1.2)
    save(fig, "fig10_shap")


def fig_calibration() -> None:
    df = pd.read_csv(EXP / "simulation_split_calibration_v6_counts2025_cycle_splits_offsets.csv")
    df = df[df.status == "OK"]
    spd_col = next(c for c in df.columns if "speed" in c and "corridor" in c) if any(
        "speed" in c and "corridor" in c for c in df.columns) else None
    # the space-mean speed on the mapped edges is in the generated table; read it from there to stay in step
    tex = (REPO / "paper" / "tables" / "split_calibration_v6.tex").read_text(encoding="utf-8")
    rows = []
    for line in tex.split("\\midrule", 1)[1].split("\\bottomrule", 1)[0].split("\\\\"):
        c = [v.strip() for v in line.split("&")]
        if len(c) >= 7:
            rows.append((c[0], float(c[1]), c[2].replace("\\,", " "), float(c[3]), c[6]))
    del spd_col
    fig, ax = plt.subplots(figsize=(COL_IN, 1.75))
    ax.axhspan(10.95 - 1.5, 10.95 + 1.5, color="#e7f1e4", lw=0)
    ax.axhline(10.95, color="#2e7d32", lw=0.7, ls="--")
    ax.text(3.08, 11.45, "observed 10.95 mph\n(band ±1.5 mph)", fontsize=5.6, color="#2e7d32", va="bottom", ha="left")
    series = [("Webster", "none", "Webster cycles", "#888888", "o", "-"),
              ("90", "none", "90 s, no offsets", C_TR, "s", "-"),
              ("90", "25 mph", "90 s + 25 mph offsets", C_PROP, "s", "-"),
              ("120", "none", "120 s, no offsets", "#c9a227", "^", "--"),
              ("120", "25 mph", "120 s + 25 mph offsets", C_GRU, "^", "--")]
    for cyc, off, lab, c, mk, ls in series:
        pts = sorted((f, s, adm) for cc, f, o, s, adm in rows if cc == cyc and o == off)
        f = [p[0] for p in pts]
        s = [p[1] for p in pts]
        ax.plot(f, s, ls=ls, color=c, lw=0.9, label=lab)
        for fx, sx, adm in pts:
            ax.plot(fx, sx, mk, ms=3.2, color=c, mfc=c if adm == "yes" else "white", mew=0.8)
    ax.annotate("selected", xy=(1.5, 10.08), xytext=(1.75, 15.5), fontsize=6, color=C_PROP,
                arrowprops=dict(arrowstyle="-|>", color=C_PROP, lw=0.6, mutation_scale=6))
    ax.set_xlabel("corridor green factor")
    ax.set_ylabel("simulated speed (mph)")
    ax.set_xlim(0.9, 3.75)
    ax.set_xticks([1.0, 1.5, 2.0, 2.5, 3.0])
    ax.set_ylim(4, 23)
    ax.grid(lw=0.3, color="#dddddd")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=3, handlelength=1.4, columnspacing=0.8,
              fontsize=5.9)
    save(fig, "fig11_calibration")


def fig_controllers() -> None:
    df = pd.read_csv(EXP / "simulation_metrics.csv")
    df = df[df.status == "OK"]
    scen = [("routine_peak", "routine"), ("event_surge", "surge"), ("incident_reduced_capacity", "incident")]
    ctrls = [("fixed_time", "fixed time", C_PERS), ("forecast_rule", "forecast rule", C_PROP)]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(COL_IN, 1.65))
    x = np.arange(3)
    w = 0.36
    for k, (c, lab, col) in enumerate(ctrls):
        tl, ct = [], []
        tl_lo, tl_hi = [], []
        for s, _ in scen:
            d = df[(df.scenario == s) & (df.controller == c)]
            tl.append(d.corridor_mean_time_loss_s.mean())
            tl_lo.append(d.corridor_mean_time_loss_s.min())
            tl_hi.append(d.corridor_mean_time_loss_s.max())
            ct.append(d.completed_trips.mean())
        tl, tl_lo, tl_hi = map(np.array, (tl, tl_lo, tl_hi))
        a1.bar(x + (k - 0.5) * w, tl, w, color=col, label=lab)
        a1.errorbar(x + (k - 0.5) * w, tl, yerr=[tl - tl_lo, tl_hi - tl], fmt="none", ecolor=INK, capsize=1.5,
                    lw=0.6)
        a2.bar(x + (k - 0.5) * w, ct, w, color=col, label=lab)
    a1.set_ylabel("time loss per trip (s)")
    a1.set_title("(a) delay (seed range)", pad=2)
    a1.set_ylim(0, 560)
    a2.set_ylabel("completed trips per run")
    a2.set_title("(b) throughput", pad=2)
    a2.set_ylim(4500, 6200)
    for a in (a1, a2):
        a.set_xticks(x, [s for _, s in scen], fontsize=6.0)
        a.grid(axis="y", lw=0.3, color="#dddddd")
        a.set_axisbelow(True)
    h_, l_ = a1.get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.07), handlelength=1.0)
    fig.tight_layout(w_pad=0.8)
    save(fig, "fig12_controllers")


def fig_live() -> None:
    day = pd.read_csv(EXP / "live_metrics_by_day.csv")
    pool = pd.read_csv(EXP / "live_metrics.csv")
    dates = sorted(day.origin_date.unique())
    labels = [f"A{k + 1}" for k in range(len(dates))] + ["pooled"]
    fig, axes = plt.subplots(1, 3, figsize=(COL_IN, 1.65), sharey=True)
    w = 0.38
    for ax, h in zip(axes, H):
        m, p = [], []
        for d in dates:
            r = day[(day.origin_date == d) & (day.horizon_minutes == h)].iloc[0]
            m.append(r.mae_mph)
            p.append(r.persistence_mae_mph)
        r = pool[pool.horizon_minutes == h].iloc[0]
        m.append(r.mae_mph)
        p.append(r.persistence_mae_mph)
        x = np.arange(len(labels))
        ax.bar(x - w / 2, m, w, color=C_PROP, label="proposed")
        ax.bar(x + w / 2, p, w, color=C_PERS, label="persistence")
        ax.axvline(len(dates) - 0.5, color="#999999", lw=0.5, ls=":")
        ax.set_xticks(x, labels, fontsize=6.0)
        ax.set_title(f"{h} min", pad=2)
        ax.grid(axis="y", lw=0.3, color="#dddddd")
        ax.set_axisbelow(True)
    axes[0].set_ylabel("LIVE MAE (mph)")
    h_, l_ = axes[0].get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.08), handlelength=1.0)
    axes[0].set_ylim(0, 8.2)
    fig.tight_layout(w_pad=0.4)
    save(fig, "fig13_live")


# ---------------------------------------------------------------------------------------------------------
# screenshots


SHOTS2 = REPO / "presentation" / "assets" / "dashboard_2026-11-20"  # 2x captures of the final dashboard


def crop(name: str, box_px: tuple[int, int, int, int], folder: Path = SHOTS2) -> Image.Image:
    return Image.open(folder / name).convert("RGB").crop(box_px)


def shot(im: Image.Image, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(OUT / f"{name}.png", dpi=(DPI, DPI))


def stack(parts: list[Image.Image], gap: int = 24) -> Image.Image:
    w = max(p.width for p in parts)
    out = Image.new("RGB", (w, sum(p.height for p in parts) + gap * (len(parts) - 1)), "white")
    y = 0
    for p in parts:
        out.paste(p, (0, y))
        y += p.height + gap
    return out


def fig_study_area() -> None:
    shot(crop("traffic_map_laptop.png", (300, 312, 2322, 1312)), "fig05_study_area")


def fig_dashboard() -> None:  # crops avoid file paths, commands and run identifiers shown on some pages
    shot(crop("forecast_laptop.png", (20, 60, 2340, 1750)), "fig14_dash_forecast")
    shot(crop("retrieval.png", (30, 230, 2330, 1300)), "fig16_dash_retrieval")
    shot(crop("agent.png", (470, 230, 2330, 1010)), "fig17_dash_agent")
    shot(stack([crop("live.png", (20, 420, 2340, 840)), crop("live_table.png", (30, 900, 2350, 1990))]),
         "fig18_dash_live")


# ---------------------------------------------------------------------------------------------------------
# further chart types


def fig_data() -> None:
    pre = json.loads((REPO / "reports" / "data_audit" / "speeds_preprocessing.json").read_text(encoding="utf-8"))
    miss = pd.read_csv(REPO / "reports" / "data_audit" / "missingness.csv")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(COL_IN, 1.6), gridspec_kw={"width_ratios": [0.9, 1.2]})
    vals = [pre["valid_rows"], pre["speed_zero_or_negative"], pre["speed_above_max"]]
    labs = ["valid", "zero speed\n(no measurement)", "above limit"]
    wedges, _ = a1.pie(vals, colors=[C_PROP, "#d9d9d9", C_GRU], startangle=90, counterclock=False,
                       wedgeprops=dict(width=0.38, edgecolor="white", linewidth=0.8))
    a1.text(0, 0, f"{pre['raw_rows'] / 1e6:.2f} M\nrecords", ha="center", va="center", fontsize=6.2)
    a1.legend(wedges[:2], [f"{labs[i]}: {vals[i] / pre['raw_rows'] * 100:.1f}%" for i in range(2)],
              loc="upper center", bbox_to_anchor=(0.5, 0.02), fontsize=5.6, handlelength=0.8)
    a1.set_title("(a) raw speed records", pad=2)
    mon = pd.to_datetime(miss.month_utc)
    a2.fill_between(range(len(miss)), miss.observed_fraction_all_links, color=C_PROP, alpha=0.18, lw=0)
    a2.plot(range(len(miss)), miss.observed_fraction_all_links, "o-", color=C_PROP, ms=2.6)
    a2.set_xticks(range(len(miss)), [m.strftime("%b") for m in mon], fontsize=5.8)
    a2.set_ylim(0, 1)
    a2.set_ylabel("observed fraction")
    a2.set_title("(b) grid coverage by month, 2026", pad=2)
    a2.grid(lw=0.3, color="#dddddd")
    fig.tight_layout(w_pad=0.8)
    save(fig, "fig19_data")


def fig_link_heatmap() -> None:
    d = pd.read_csv(REPO / "reports" / "data_audit" / "link_split_coverage.csv")
    d = d[d.in_grid == True].copy()  # noqa: E712
    def short(n: str) -> str:
        words = [w if any(ch.isdigit() for ch in w) or len(w) <= 3 and w.isalpha() and w in ("FDR", "BQE", "GWB",
                 "CBE", "QMT", "BBT", "TBB", "NJ", "NY", "BKN", "MAN", "E", "W", "N", "S") else w.capitalize()
                 for w in n.replace(" - ", " – ").split()]
        out = ""
        for w in words:
            if len(out) + len(w) + 1 > 36:
                return out + " …"
            out = (out + " " + w).strip()
        return out
    d["name"] = d.link_name.map(short)
    d = d.sort_values("all", ascending=False)
    cols = ["train", "val", "calib", "test"]
    m = d[cols].to_numpy(float)
    fig, ax = plt.subplots(figsize=(COL_IN, 3.0))
    im = ax.imshow(m, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(4), ["train", "validation", "calibration", "test"], fontsize=6)
    ax.set_yticks(range(len(d)), [n + ("" if f else "  (not modelled)") for n, f in zip(d.name, d.in_features)],
                  fontsize=5.2)
    for i in range(m.shape[0]):
        for j in range(4):
            ax.text(j, i, f"{m[i, j]:.2f}", ha="center", va="center", fontsize=4.9,
                    color="white" if m[i, j] > 0.55 else INK)
    ax.tick_params(length=0)
    ax.xaxis.tick_top()
    for sp in ax.spines.values():
        sp.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.ax.tick_params(labelsize=5.5, length=1.5)
    cb.set_label("observed fraction", fontsize=6)
    cb.outline.set_linewidth(0.4)
    save(fig, "fig20_link_heatmap")


def fig_radar() -> None:
    df = pd.read_csv(EXP / "forecast_metrics.csv")
    df = df[(df.split == "test") & (df.track == "operational")]
    models = [("xgboost", "XGBoost", C_TREE), ("gru", "GRU", C_GRU), ("temporal_transformer", "Temp. Transf.", C_TR),
              ("proposed", "Proposed", C_PROP)]
    axes_ = [(m, h) for m in ("mae_mph", "rmse_mph") for h in H]
    lab = [f"{'MAE' if m == 'mae_mph' else 'RMSE'} {h}" for m, h in axes_]
    pers = {(m, h): df[(df.model == "persistence") & (df.horizon_min == h)][m].iloc[0] for m, h in axes_}
    ang = np.linspace(0, 2 * np.pi, len(axes_), endpoint=False).tolist()
    fig = plt.figure(figsize=(COL_IN, 2.1))
    ax = fig.add_subplot(111, polar=True)
    for key, name, c in models:
        v = [100 * (1 - df[(df.model == key) & (df.horizon_min == h)][m].iloc[0] / pers[(m, h)]) for m, h in axes_]
        ax.plot(ang + ang[:1], v + v[:1], color=c, lw=1.0 if key == "proposed" else 0.8, label=name)
        if key == "proposed":
            ax.fill(ang + ang[:1], v + v[:1], color=c, alpha=0.12)
    ax.set_xticks(ang, lab, fontsize=6)
    ax.set_ylim(0, 25)
    ax.set_rlabel_position(200)
    ax.set_yticks([5, 10, 15, 20], ["5%", "10%", "15%", "20%"], fontsize=5.2)
    ax.grid(lw=0.3, color="#bbbbbb")
    ax.spines["polar"].set_linewidth(0.4)
    ax.legend(loc="upper left", bbox_to_anchor=(1.05, 1.0), fontsize=6, handlelength=1.2)
    save(fig, "fig21_radar")


def fig_sim_seeds() -> None:
    df = pd.read_csv(EXP / "simulation_metrics.csv")
    df = df[df.status == "OK"]
    fig, axes = plt.subplots(1, 2, figsize=(COL_IN, 1.55), sharey=True)
    for ax, (s, t) in zip(axes, (("event_surge", "(a) event surge"), ("incident_reduced_capacity", "(b) incident"))):
        f = df[(df.scenario == s) & (df.controller == "fixed_time")].set_index("seed").corridor_mean_time_loss_s
        r = df[(df.scenario == s) & (df.controller == "forecast_rule")].set_index("seed").corridor_mean_time_loss_s
        seeds = sorted(f.index)
        for k, sd in enumerate(seeds):
            ax.plot([r[sd], f[sd]], [k, k], color="#bbbbbb", lw=1.6, zorder=1)
            ax.scatter(f[sd], k, color=C_PERS, s=14, zorder=2, label="fixed time" if k == 0 else None)
            ax.scatter(r[sd], k, color=C_PROP, s=14, zorder=3, label="forecast rule" if k == 0 else None)
            ax.text(f[sd] + 3, k, f"−{f[sd] - r[sd]:.0f} s", va="center", fontsize=5.4, color=INK)
        ax.set_yticks(range(len(seeds)), [f"seed {sd}" for sd in seeds], fontsize=5.8)
        ax.set_title(t, pad=2)
        ax.set_xlabel("time loss per trip (s)")
        ax.grid(axis="x", lw=0.3, color="#dddddd")
        ax.margins(x=0.18)
    h_, l_ = axes[0].get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.09), handlelength=1.0)
    fig.tight_layout(w_pad=0.5)
    save(fig, "fig22_sim_seeds")


def fig_live_scatter() -> None:
    s = pd.read_csv(REPO / "artifacts" / "live" / "scored.csv")
    s = s[s.status == "SCORED"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(COL_IN, 2.0), gridspec_kw={"width_ratios": [1, 1.15]})
    for h, c, mk in zip(H, (C_PROP, C_TR, C_GRU), ("o", "s", "^")):
        d = s[s.horizon_minutes == h]
        a1.scatter(d.observed_speed_mph, d.predicted_speed_mph, s=5, color=c, marker=mk, alpha=0.6, lw=0,
                   label=f"{h} min")
    lim = [0, max(s.observed_speed_mph.max(), s.predicted_speed_mph.max()) + 2]
    a1.plot(lim, lim, color=INK, lw=0.5, ls="--")
    a1.set_xlim(lim)
    a1.set_ylim(lim)
    a1.set_xlabel("observed (mph)")
    a1.set_ylabel("predicted (mph)")
    a1.set_title("(a) predicted vs observed", pad=2)
    h1, l1 = a1.get_legend_handles_labels()
    a1.set_aspect("equal")
    data, pos, cols = [], [], []
    for k, h in enumerate(H):
        d = s[s.horizon_minutes == h]
        data += [d.abs_error_mph.dropna(), d.persistence_abs_error_mph.dropna()]
        pos += [k * 3 + 0.6, k * 3 + 1.4]
        cols += [C_PROP, C_PERS]
    bp = a2.boxplot(data, positions=pos, widths=0.65, patch_artist=True, showfliers=True,
                    flierprops=dict(marker=".", markersize=2, markeredgecolor="#777777"),
                    medianprops=dict(color="white", lw=0.9), whiskerprops=dict(lw=0.6), capprops=dict(lw=0.6),
                    boxprops=dict(lw=0.5))
    for patch, c in zip(bp["boxes"], cols):
        patch.set_facecolor(c)
    a2.set_xticks([1, 4, 7], [f"{h} min" for h in H])
    a2.set_ylabel("absolute error (mph)")
    a2.set_title("(b) error distribution", pad=2)
    a2.grid(axis="y", lw=0.3, color="#dddddd")
    from matplotlib.patches import Patch
    fig.legend(h1 + [Patch(color=C_PROP), Patch(color=C_PERS)], l1 + ["proposed", "persistence"],
               loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=5, fontsize=5.6, handlelength=0.9,
               handletextpad=0.3, columnspacing=0.8, markerscale=1.5)
    fig.tight_layout(w_pad=0.6, rect=(0, 0, 1, 0.9))
    save(fig, "fig23_live_scatter")


def fig_advisory_retrieval() -> None:
    adv = pd.read_csv(EXP / "advisory_metrics.csv")
    pol = [("full_system", "full system"), ("llm_without_retrieval", "no retrieval"),
           ("rag_without_constraints", "no constraints"), ("rag_constraints_without_simulation", "no sim. gate")]
    cats = [("PENDING", "pending review", "#2e7d32"), ("DEFER", "deferred", "#d9a441"), ("REJECT", "rejected", C_GRU)]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(COL_IN, 1.7), gridspec_kw={"width_ratios": [1.25, 1]})
    left = np.zeros(len(pol))
    for pre, lab, c in cats:
        v = np.array([sum(adv[adv.policy == k].decision.str.startswith(pre)) for k, _ in pol])
        a1.barh(range(len(pol)), v, left=left, color=c, label=lab, height=0.55)
        for i, (x0, w) in enumerate(zip(left, v)):
            if w:
                a1.text(x0 + w / 2, i, str(w), ha="center", va="center", fontsize=5.6, color="white")
        left += v
    a1.set_yticks(range(len(pol)), [n for _, n in pol], fontsize=6)
    a1.invert_yaxis()
    a1.set_xlabel("advisory runs")
    a1.set_title("(a) decisions by policy", pad=2)
    h_, l_ = a1.get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper center", bbox_to_anchor=(0.5, 1.08), ncol=3, fontsize=5.8, handlelength=0.8,
               columnspacing=0.8)
    a1.tick_params(axis="y", length=0)
    r = pd.read_csv(EXP / "retrieval_metrics.csv")
    for k, (st, lab, c) in enumerate((("SUPPORTED", "answerable", C_PROP),
                                      ("INSUFFICIENT_EVIDENCE", "out of scope", C_GRU))):
        d = r[r.expected_status == st]
        jitter = np.linspace(-0.18, 0.18, len(d))
        a2.scatter(np.full(len(d), k) + jitter, d.top1_score, s=8, color=c, lw=0, alpha=0.85)
    a2.axhline(0.35, color=INK, lw=0.6, ls="--")
    a2.text(-0.45, 0.36, "threshold 0.35", fontsize=5.4, ha="left", va="bottom")
    a2.set_xticks([0, 1], ["answerable", "out of\nscope"], fontsize=6)
    a2.set_xlim(-0.5, 1.5)
    a2.set_ylabel("top-1 similarity")
    a2.set_title("(b) retrieval scores", pad=2)
    a2.grid(axis="y", lw=0.3, color="#dddddd")
    fig.tight_layout(w_pad=0.6)
    save(fig, "fig24_advisory_retrieval")


def fig_runtime() -> None:
    rt = pd.read_csv(EXP / "runtime_metrics.csv")
    rt = rt[rt.metric == "inference_ms_per_origin"].drop_duplicates("component")  # first row: reference run
    order = [("forecast:persistence", "Persistence"), ("forecast:historical_average", "Hist. avg."),
             ("forecast:xgboost", "XGBoost"), ("forecast:lightgbm", "LightGBM"), ("forecast:gru", "GRU"),
             ("forecast:temporal_transformer", "Temp. Transf."), ("forecast:proposed", "Proposed")]
    v = [float(rt[rt.component == k].value.iloc[0]) for k, _ in order]
    fig, ax = plt.subplots(figsize=(COL_IN, 1.45))
    cols = [C_PERS, C_BASE, C_TREE, "#c9ada7", C_GRU, C_TR, C_PROP]
    ax.barh(range(len(order)), v, color=cols, height=0.6)
    ax.set_xscale("log")
    ax.set_yticks(range(len(order)), [n for _, n in order], fontsize=6)
    for i, x in enumerate(v):
        ax.text(x * 1.15, i, f"{x:.3g} ms", va="center", fontsize=5.6)
    ax.set_xlim(3e-4, 60)
    ax.set_xlabel("CPU inference time per forecast origin, all links (ms, log scale)")
    ax.grid(axis="x", lw=0.3, color="#dddddd", which="major")
    ax.tick_params(axis="y", length=0)
    save(fig, "fig25_runtime")


def main() -> None:
    for f in (fig_architecture, fig_forecaster, fig_workflow, fig_modules, fig_study_area, fig_mae, fig_seeds,
              fig_ablation_window, fig_uncertainty, fig_shap, fig_calibration, fig_controllers, fig_live,
              fig_dashboard, fig_data, fig_link_heatmap, fig_radar, fig_sim_seeds, fig_live_scatter,
              fig_advisory_retrieval, fig_runtime):
        f()
        print("drew", f.__name__)


if __name__ == "__main__":
    main()
