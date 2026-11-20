"""Build the rebuilt IEEE conference paper (Word) on the conference's A4 template, with figures.

    python paper/word/make_figures.py          # draw the figures from the result files
    python paper/word/build_ieee_paper.py      # write paper/ieee_conference_paper.docx

Prose comes from paper/word/ieee_paper_text.py. Every table is computed here from the result files in
reports/experiments/, reports/data_audit/ and artifacts/calibration/, so no result is typed into a table by hand.
Figures are paper/word/figures/*.png. The inline-markup, table and author-block helpers are shared with
build_ieee_docx.py (the earlier edition of the paper).
"""
from __future__ import annotations

import argparse
import csv
import re
import struct
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import build_ieee_docx as B  # noqa: E402
import ieee_paper_text as T  # noqa: E402

B.C = T  # citation keys, authors and title come from the rebuilt text
EXP = REPO / "reports" / "experiments"
CAL = REPO / "artifacts" / "calibration"
FIGS = HERE / "figures"
COL = B.COL_PT
EMU_IN = 914400

FIG_NS = ('xmlns:a="http://purl.oclc.org/ooxml/drawingml/main"',
          'xmlns:pic="http://purl.oclc.org/ooxml/drawingml/picture"')

H = (15, 30, 60)


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def f2(x, p=2) -> str:
    return f"{float(x):,.{p}f}".replace("-", "−")


# ---------------------------------------------------------------------------------------------------------
# tables


def tbl(title: str, widths, header, body, aligns, refs, size=14, notes: str | None = None) -> str:
    x = B.caption(title, refs)
    t = B.table_xml(widths, header, body, refs, aligns, size=size)
    if notes:  # keep every row, and so the note, together with the table
        t = t.replace('<w:pStyle w:val="tablecopy"/><w:jc', '<w:pStyle w:val="tablecopy"/><w:keepNext/><w:jc')
    x += t
    if notes:
        x += B.note(notes, refs)
    else:
        x += B.para("tablecopy", "", '<w:spacing w:before="0pt" w:after="6pt"/>')
    return x


def table_related(refs) -> str:
    Y, N = "✓", "–"
    data = [("DCRNN [@li2018dcrnn]", "YYNNNNN"), ("STGCN [@yu2018stgcn]", "YYNNNNN"),
            ("Graph WaveNet [@wu2019graphwavenet]", "YYNNNNN"), ("ASTGCN [@guo2019astgcn]", "YYNNNNN"),
            ("GMAN [@zheng2020gman]", "YYNNNNN"), ("AGCRN [@bai2020agcrn]", "YYNNNNN"),
            ("EnbPI [@xu2021enbpi]", "NNYNNNN"), ("IntelliLight [@wei2018intellilight]", "NNNNNYN"),
            ("**This work**", "YYYYYYY")]
    body = [[name] + [Y if c == "Y" else N for c in flags] for name, flags in data]
    hdr = [["Study", "Graph", "Multi-\nstep", "Inter-\nvals", "XAI", "LLM/\nRAG", "Sim.", "Live"]]
    return tbl("Comparison With Related Studies", [68.3] + [25] * 7, hdr, body,
               ["start"] + ["center"] * 7, refs, size=13,
               notes="Multi-step: several forecast horizons. Intervals: calibrated prediction intervals. XAI: "
                     "explanations of predictions. Sim.: a controller or advisory checked in a traffic simulator. "
                     "Live: forecasts scored on data published after they were made.")


def table_sources(refs) -> str:
    inv = {r["source_id"]: r for r in rows(REPO / "reports" / "data_audit" / "source_inventory.csv")}

    def n(k):
        v = inv[k].get("raw_rows_downloaded") or ""
        return f"{int(float(v)):,}" if v else "–"

    body = [["NYC DOT link speeds [@nycdotspeeds]", "forecast target, 26 Manhattan links", n("speeds")],
            ["Open-Meteo weather [@openmeteo]", "archived forecasts (operational); reanalysis (retrospective)",
             "hourly"],
            ["NYC 311 requests", "infrastructure context, 24 h lag", n("sr311")],
            ["Motor vehicle collisions", "retrospective analysis only", n("collisions")],
            ["Permitted events", "retrospective analysis only", f"{int(float(inv['events']['raw_rows_downloaded']) + float(inv['events_hist']['raw_rows_downloaded'])):,}"],
            ["Traffic volume counts [@nycclasscounts]", "simulation demand only", n("volume")],
            ["OpenStreetMap", "simulation corridor geometry", "extract"]]
    return tbl("Public Data Sources", [78, 115.3, 50], [["Source", "Role in this study", "Rows used"]], body,
               ["start", "start", "end"], refs, size=13,
               notes="Rows used are the Manhattan or study-window subsets downloaded for this work; every download "
                     "is logged with a checksum.")


def table_setup(refs) -> str:
    body = [["History window *L*", "24 steps (2 h), 5-min steps"], ["Horizons", "3, 6, 12 steps (15/30/60 min)"],
            ["Hidden width *d*", "64"], ["Graph layers", "2 × GATv2, 4 heads, residual, layer norm"],
            ["Temporal layers", "2 × Transformer, 4 heads, FF 128"], ["Dropout", "0.1"],
            ["Loss", "masked Huber (δ = 1, standardised targets)"],
            ["Optimiser", "AdamW, lr 10^{−3}, weight decay 10^{−4}"], ["Batch size / clipping", "8 / 1.0"],
            ["Epochs", "≤ 30, early stop patience 5"], ["Windows per epoch", "4,096 sampled"],
            ["Parameters", "158,403 (GRU: 41,667)"], ["Conformal level", "90% (α = 0.1), per horizon"],
            ["Seeds", "42 (reference); 1, 2, 42 (robustness)"]]
    return tbl("Training and Evaluation Settings", [85, 158.3], [["Setting", "Value"]], body, ["start", "start"],
               refs, size=14)


MODEL = {"persistence": "Persistence", "historical_average": "Historical average", "xgboost": "XGBoost",
         "lightgbm": "LightGBM", "gru": "GRU", "temporal_transformer": "Temporal Transf.",
         "proposed": "**Proposed**"}


def table_forecast(refs) -> str:
    r = [x for x in rows(EXP / "forecast_metrics.csv") if x["split"] == "test" and x["track"] == "operational"]
    get = {(x["model"], int(x["horizon_min"])): x for x in r}
    best = {h: min(float(get[(m, h)]["mae_mph"]) for m in MODEL) for h in H}
    body = []
    for m, name in MODEL.items():
        cells = [name]
        for h in H:
            mae = float(get[(m, h)]["mae_mph"])
            s = f2(mae)
            cells += [f"**{s}**" if abs(mae - best[h]) < 1e-9 else s, f2(get[(m, h)]["rmse_mph"])]
        body.append(cells)
    n = [f"{int(get[('proposed', h)]['n_valid_targets']):,}" for h in H]
    hdr = [["Model", ("15 min", 2), ("30 min", 2), ("60 min", 2)], ["", "MAE", "RMSE", "MAE", "RMSE", "MAE", "RMSE"]]
    return tbl("Test Error by Model and Horizon (mph, REPLAY)", [65.3] + [29.7] * 6, hdr, body,
               ["start"] + ["end"] * 6, refs, size=14,
               notes=f"Held-out test period of 44 days; *n* = {n[0]}, {n[1]} and {n[2]} valid targets. Same mask "
                     "for all models; reference run with seed 42. Bold: lowest MAE.")


def table_seeds(refs) -> str:
    s = {x["model"]: x for x in rows(EXP / "multi_seed_summary.csv")}
    body = []
    for m, name in (("proposed", "Proposed"), ("gru", "GRU"), ("temporal_transformer", "Temporal Transf.")):
        body.append([name] + [f"{float(s[m][f'mae_{h}m_mean']):.3f} ± {float(s[m][f'mae_{h}m_sd']):.3f}" for h in H])
    for m, name in (("gru", "Δ GRU"), ("temporal_transformer", "Δ Temporal Transf.")):
        cells = [name]
        for h in H:
            d = float(s[m][f"diff_vs_proposed_{h}m"])
            lo, hi = [float(v) for v in s[m][f"diff_vs_proposed_{h}m_ci95"].strip("[]").split(",")]
            cells.append(f"{d:+.3f}\n[{lo:+.3f}, {hi:+.3f}]".replace("-", "−"))
        body.append(cells)
    return tbl("Test MAE Over Three Seeds (mph)", [64.3, 59.7, 59.7, 59.6], [["Model", "15 min", "30 min", "60 min"]],
               body, ["start", "center", "center", "center"], refs, size=14,
               notes="Mean ± standard deviation over seeds 1, 2 and 42. Δ rows: model minus proposed, with a 95% "
                     "paired day-block bootstrap interval; positive values favour the proposed model.")


def table_unc(refs) -> str:
    allc = {int(x["horizon_min"]): x for x in rows(EXP / "uncertainty_metrics.csv") if x["group"] == "all"}
    cong = {int(x["horizon_min"]): x for x in rows(CAL / "coverage_by_scenario.csv") if x["group"] == "congested<0.5"}
    dt = {int(x["horizon_min"]): x for x in rows(CAL / "deferral_tradeoff.csv")
          if abs(float(x["missing_threshold"]) - 0.34) < 1e-6}
    body = []
    for h in H:
        a = allc[h]
        body.append([f"{h} min", f2(float(a["mean_width_mph"]) / 2, 1), f2(a["empirical_coverage"], 3),
                     f2(cong[h]["coverage"], 3), f2(float(dt[h]["deferral_rate"]) * 100, 1),
                     f2(dt[h]["mae_retained"]), f2(dt[h]["coverage_retained"], 3)])
    hdr = [["Horizon", "Half-\nwidth", "Cover-\nage", "Cov.\ncongested", "Deferred\n(%)", "MAE\nretained",
            "Cov.\nretained"]]
    return tbl("Conformal Intervals and Reliability Gate (REPLAY)", [37.3] + [34.3] * 6, hdr, body,
               ["start"] + ["end"] * 6, refs, size=14,
               notes="Nominal coverage 0.90. Half-width in mph. Congested: speed below half of free flow. Retained: "
                     "forecasts that pass the reliability gate.")


def table_adv(refs) -> str:
    r = rows(EXP / "advisory_metrics.csv")
    pol = [("full_system", "Full system"), ("llm_without_retrieval", "Without retrieval"),
           ("rag_without_constraints", "Without constraints"),
           ("rag_constraints_without_simulation", "Without simulation gate")]
    body = []
    for key, name in pol:
        x = [v for v in r if v["policy"] == key]
        cnt = lambda pre: sum(1 for v in x if v["decision"].startswith(pre))  # noqa: E731
        inv = sum(1 for v in x if (v["n_invalid_citations"] or "0") not in ("", "0", "0.0"))
        body.append([name, str(len(x)), str(cnt("PENDING")), str(cnt("DEFER")), str(cnt("REJECT")), str(inv)])
    hdr = [["Policy", "Runs", "Pending\nreview", "Deferred", "Rejected", "Invalid\ncitations"]]
    return tbl("Advisory Outcomes by Policy (REPLAY)", [83.3, 28, 34, 32, 32, 34], hdr, body,
               ["start", "end", "end", "end", "end", "end"], refs, size=14,
               notes="Identical decisions in each of three passes. Pending review advisories are monitor-only; "
                     "no signal change was proposed.")


def table_sim(refs) -> str:
    r = [x for x in rows(EXP / "simulation_metrics.csv") if x["status"] == "OK"]
    scen = [("routine_peak", "Routine"), ("event_surge", "Event surge"), ("incident_reduced_capacity", "Incident")]

    def mean(s, c, col):
        v = [float(x[col]) for x in r if x["scenario"] == s and x["controller"] == c]
        return sum(v) / len(v)

    body = []
    for s, sname in scen:
        for c, cname in (("fixed_time", "Fixed time"), ("forecast_rule", "Forecast rule")):
            tl = mean(s, c, "corridor_mean_time_loss_s")
            body.append([sname if c == "fixed_time" else "", cname, f2(tl, 1),
                         f"{mean(s, c, 'completed_trips'):,.0f}", f"{mean(s, c, 'unfinished_trips'):,.0f}",
                         f"{mean(s, c, 'max_corridor_queue_veh'):,.0f}"])
    act = ", ".join(f"{sn.lower()} {mean(s, 'actuated', 'corridor_mean_time_loss_s'):.1f} s" for s, sn in scen)
    hdr = [["Scenario", "Controller", "Time loss\n(s/trip)", "Completed", "Unfinished", "Max\nqueue"]]
    return tbl("Controller Comparison on the Calibrated Corridor (SIMULATION)", [44, 52, 38, 38.3, 38, 33], hdr,
               body, ["start", "start", "end", "end", "end", "end"], refs, size=14,
               notes=f"Mean over five matched seeds; no teleports. Uncalibrated actuated reference: {act}.")


def table_live(refs) -> str:
    day = rows(EXP / "live_metrics_by_day.csv")
    pool = {int(x["horizon_minutes"]): x for x in rows(EXP / "live_metrics.csv")}
    dates = sorted({x["origin_date"] for x in day})
    body = []
    for k, d in enumerate(dates):
        x = {int(v["horizon_minutes"]): v for v in day if v["origin_date"] == d}
        body.append([f"A{k + 1}", x[15]["n_links"], f"{float(x[15]['mean_origin_lag_minutes']):.0f}",
                     x[15]["n_scored"]] + [f"{f2(x[h]['mae_mph'])} / {f2(x[h]['persistence_mae_mph'])}" for h in H])
    body.append(["Pooled", "–", f"{float(pool[15]['mean_origin_lag_minutes']):.0f}", pool[15]["n_scored"]]
                + [f"**{f2(pool[h]['mae_mph'])}** / **{f2(pool[h]['persistence_mae_mph'])}**" for h in H])
    hdr = [["After-\nnoon", "Links", "Age\n(min)", "*n*", "15 min", "30 min", "60 min"]]
    return tbl("Live Forecast Error, Model / Persistence (mph, LIVE)", [30, 25, 27, 22, 46.4, 46.4, 46.5], hdr, body,
               ["start", "end", "end", "end", "center", "center", "center"], refs, size=14,
               notes="Latest-available origin; age is the mean data age when the forecast was issued; *n* at 15 min "
                     "(the pooled 30 and 60 min rows have 91). Pooled coverage of the 90% intervals: "
                     f"{f2(pool[15]['coverage'], 3)}, {f2(pool[30]['coverage'], 3)} and "
                     f"{f2(pool[60]['coverage'], 3)}.")


TABLES = {"related": table_related, "sources": table_sources, "setup": table_setup, "forecast": table_forecast,
          "seeds": table_seeds, "unc": table_unc, "adv": table_adv, "sim": table_sim, "live": table_live}

# ---------------------------------------------------------------------------------------------------------
# figures


def png_size(p: Path) -> tuple[int, int]:
    with p.open("rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


class Figs:
    def __init__(self) -> None:
        self.media: list[tuple[str, Path]] = []

    def drawing(self, path: Path, width_in: float) -> str:
        w, h = png_size(path)
        cx = int(width_in * EMU_IN)
        cy = int(cx * h / w)
        k = len(self.media) + 1
        rid = f"rIdFig{k}"
        self.media.append((rid, path))
        return (f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
                f'<wp:docPr id="{1000 + k}" name="Figure {k}"/>'
                f'<a:graphic {FIG_NS[0]}><a:graphicData uri="http://purl.oclc.org/ooxml/drawingml/picture">'
                f'<pic:pic {FIG_NS[1]}><pic:nvPicPr><pic:cNvPr id="{1000 + k}" name="{escape(path.name)}"/>'
                '<pic:cNvPicPr/></pic:nvPicPr><pic:blipFill>'
                f'<a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
                '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
                '</wp:inline></w:drawing></w:r>')


def fig_refs(s: str, fignum: dict) -> str:
    return re.sub(r"\{F:(\w+)\}", lambda m: f"Fig. {fignum[m.group(1)]}", s)


# ---------------------------------------------------------------------------------------------------------


def build(out: Path) -> None:
    refs = B.Refs()
    h1 = 0
    fignum: dict[str, int] = {}
    for blk in T.BODY:
        if blk[0] == "h1":
            h1 += 1
            refs.sections[blk[2]] = h1
        elif blk[0] == "table":
            refs.tables[blk[1]] = len(refs.tables) + 1
        elif blk[0] == "fig":
            fignum[blk[1]] = len(fignum) + 1

    zin = zipfile.ZipFile(B.TEMPLATE)
    doc = zin.read("word/document.xml").decode("utf-8")
    head, body = doc.split("<w:body>", 1)
    sects = re.findall(r"<w:sectPr\b.*?</w:sectPr>", body, re.S)
    title_sect, authors_sect, body_sect, final_sect = sects[0], sects[1], sects[3], sects[4]
    authors_sect = authors_sect.replace('w:num="3"', f'w:num="{len(T.AUTHORS)}"')
    one_col_sect = re.sub(r'<w:cols [^>]*/>', '<w:cols w:space="18pt"/>', body_sect)
    figs = Figs()
    R = lambda s, base=None, **kw: B.runs(fig_refs(s, fignum), refs, base, **kw)  # noqa: E731

    x = B.para("papertitle", R(T.TITLE, extra='<w:kern w:val="48"/>'),
               '<w:spacing w:before="5pt" w:beforeAutospacing="1" w:after="5pt" w:afterAutospacing="1"/>')
    x += B.para("Author", "", '<w:spacing w:before="5pt" w:beforeAutospacing="1" w:after="5pt" '
                'w:afterAutospacing="1" w:line="6pt" w:lineRule="auto"/><w:rPr><w:sz w:val="16"/>'
                f'<w:szCs w:val="16"/></w:rPr>{title_sect}')
    x += B.author_block(refs, authors_sect)
    x += B.para("Abstract", R("*Abstract*—") + R(T.ABSTRACT))
    x += B.para("Keywords", R("Keywords—") + R(", ".join(T.KEYWORDS), {"b": False}))

    tiny = '<w:spacing w:before="0pt" w:after="0pt" w:line="2pt" w:lineRule="exact"/>'
    eq_no = 0
    for blk in T.BODY:
        kind = blk[0]
        if kind == "h1":
            x += B.para("Heading1", R(blk[1]))
        elif kind == "h2":
            x += B.para("Heading2", R(blk[1]))
        elif kind == "p":
            x += B.para("BodyText", R(blk[1]))
        elif kind == "pn":
            x += B.para("BodyText", R(blk[1]), '<w:ind w:start="0pt" w:firstLine="0pt"/>')
        elif kind == "eq":
            eq_no += 1
            tabs = ('<w:tabs><w:tab w:val="clear" w:pos="126pt"/><w:tab w:val="clear" w:pos="252pt"/>'
                    f'<w:tab w:val="center" w:pos="{COL / 2:.2f}pt"/><w:tab w:val="end" w:pos="{COL:.2f}pt"/>'
                    '</w:tabs><w:spacing w:before="4pt" w:after="4pt"/>')
            tnr = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'
            e = f'<w:r><w:rPr>{tnr}</w:rPr><w:tab/></w:r>'
            for text, f in B.segments(blk[1], refs):
                e += f'<w:r>{B.rpr(f, size=19, extra=tnr)}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
            e += f'<w:r><w:rPr>{tnr}</w:rPr><w:tab/><w:t>({eq_no})</w:t></w:r>'
            x += B.para("equation", e, tabs)
        elif kind == "table":
            x += TABLES[blk[1]](refs)
        elif kind == "fig":
            _, fid, fname, width, cap, full = blk
            pic = figs.drawing(FIGS / fname, width)
            box_pt = 504.6 if full else COL
            cell = (B.para(None, pic, '<w:keepNext/><w:spacing w:before="4pt" w:after="0pt"/><w:jc w:val="center"/>')
                    + B.para("figurecaption", R(cap), '<w:spacing w:before="4pt" w:after="2pt"/><w:jc w:val="center"/>'))
            # picture and caption share one unsplittable, borderless cell so they never part across columns or pages
            box = (f'<w:tbl><w:tblPr><w:tblW w:w="{box_pt:.2f}pt" w:type="dxa"/><w:jc w:val="center"/>'
                   '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:start w:w="0pt" w:type="dxa"/>'
                   '<w:end w:w="0pt" w:type="dxa"/></w:tblCellMar><w:tblLook w:firstRow="0" w:lastRow="0" '
                   'w:firstColumn="0" w:lastColumn="0" w:noHBand="1" w:noVBand="1"/></w:tblPr>'
                   f'<w:tblGrid><w:gridCol w:w="{round(box_pt * 20)}"/></w:tblGrid>'
                   '<w:tr><w:trPr><w:cantSplit/><w:jc w:val="center"/></w:trPr>'
                   f'<w:tc><w:tcPr><w:tcW w:w="{box_pt:.2f}pt" w:type="dxa"/></w:tcPr>{cell}</w:tc></w:tr></w:tbl>')
            if full:  # close the two-column section, place the figure across the page, reopen two columns
                x += B.para(None, "", tiny + body_sect)
                x += box
                x += B.para(None, "", tiny + one_col_sect)
            else:
                x += box + B.para(None, "", '<w:spacing w:before="0pt" w:after="4pt" w:line="4pt" w:lineRule="exact"/>')
        else:
            raise ValueError(kind)

    x += B.para("Heading5", R("References"))
    for n, key in enumerate(refs.cites):
        last = n == len(refs.cites) - 1
        x += B.para("references", R(T.REFERENCES[key]),
                    '<w:ind w:start="17.70pt" w:hanging="17.70pt"/>' + (body_sect if last else ""))
    x += "<w:p/>" + final_sect

    unused = sorted(set(T.REFERENCES) - set(refs.cites))
    if unused:
        raise SystemExit(f"references never cited: {unused}")

    new_doc = head + "<w:body>" + x + "</w:body></w:document>"
    rels = zin.read("word/_rels/document.xml.rels").decode("utf-8")
    rels = rels.replace("</Relationships>", "".join(
        f'<Relationship Id="{rid}" Type="http://purl.oclc.org/ooxml/officeDocument/relationships/image" '
        f'Target="media/{p.name}"/>' for rid, p in figs.media) + "</Relationships>")
    ctypes = zin.read("[Content_Types].xml").decode("utf-8")
    if 'Extension="png"' not in ctypes:
        ctypes = ctypes.replace('<Default Extension="xml"', '<Default Extension="png" ContentType="image/png"/>'
                                '<Default Extension="xml"')
    core = zin.read("docProps/core.xml").decode("utf-8")
    core = re.sub(r"<dc:title>.*?</dc:title>", f"<dc:title>{escape(T.TITLE)}</dc:title>", core)
    core = re.sub(r"<dc:creator>.*?</dc:creator>",
                  "<dc:creator>" + escape("; ".join(a["name"].rstrip("*") for a in T.AUTHORS)) + "</dc:creator>", core)
    core = re.sub(r"<cp:keywords>.*?</cp:keywords>|<cp:keywords/>",
                  "<cp:keywords>" + escape(", ".join(T.KEYWORDS)) + "</cp:keywords>", core)
    core = re.sub(r"<cp:lastModifiedBy>.*?</cp:lastModifiedBy>", "<cp:lastModifiedBy></cp:lastModifiedBy>", core)

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename.endswith("/"):
                continue
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = new_doc.encode("utf-8")
            elif item.filename == "word/_rels/document.xml.rels":
                data = rels.encode("utf-8")
            elif item.filename == "[Content_Types].xml":
                data = ctypes.encode("utf-8")
            elif item.filename == "docProps/core.xml":
                data = core.encode("utf-8")
            zout.writestr(item, data)
        for _, p in figs.media:
            zout.write(p, f"word/media/{p.name}")
    print(f"wrote {out} ({len(refs.cites)} references, {len(refs.tables)} tables, {len(fignum)} figures, "
          f"{eq_no} equations, abstract {len(T.ABSTRACT.split())} words)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=REPO / "paper" / "ieee_conference_paper.docx")
    build(ap.parse_args().out)


if __name__ == "__main__":
    main()
