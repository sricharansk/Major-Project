"""Build the IEEE conference paper as a Word document from the conference's A4 template.

    python paper/word/build_ieee_docx.py [--out paper/ieee_conference_paper.docx]

The template (paper/word/IEEE_conference-template-A4.docx, an OOXML "strict" document) supplies every style,
the page geometry, the section layout and the first-page footer; this script replaces the template's guidance
text with the paper. Text comes from paper/word/paper_content.py. Tables are read from the generated
paper/tables/*.tex (written by `python -m smartcity.cli paper sync` from reports/experiments/) and from
reports/data_audit/source_inventory.csv, so re-running paper sync and then this script keeps the Word tables in
step with the artifacts. No number is typed into a table by hand.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import paper_content as C  # noqa: E402

TEMPLATE = HERE / "IEEE_conference-template-A4.docx"
TABLES = REPO / "paper" / "tables"
SOURCES_CSV = REPO / "reports" / "data_audit" / "source_inventory.csv"

COL_PT = 243.3  # one text column of the A4 template: (595.3 - 2 * 45.35 - 18) / 2
MONO = "Courier New"
ZWSP = "\u200b"  # zero-width space: a line-break opportunity that prints nothing

# ---------------------------------------------------------------------------------------------------------
# inline markup -> runs


def roman(n: int) -> str:
    vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


class Refs:
    """Numbers citations, tables and sections in order of first appearance."""

    def __init__(self) -> None:
        self.cites: list[str] = []
        self.tables: dict[str, int] = {}
        self.sections: dict[str, int] = {}

    def cite(self, keys: list[str]) -> str:
        nums = []
        for k in keys:
            if k not in C.REFERENCES:
                raise KeyError(f"citation key {k!r} has no entry in paper_content.REFERENCES")
            if k not in self.cites:
                self.cites.append(k)
            nums.append(self.cites.index(k) + 1)
        nums = sorted(set(nums))
        parts, i = [], 0
        while i < len(nums):
            j = i
            while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
                j += 1
            if j - i >= 2:
                parts.append(f"[{nums[i]}]–[{nums[j]}]")
            else:
                parts.extend(f"[{n}]" for n in nums[i:j + 1])
            i = j + 1
        return ", ".join(parts)


def _find_close(s: str, i: int) -> int:
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return j
    raise ValueError(f"unbalanced braces in: {s}")


def segments(s: str, refs: Refs, fmt: dict | None = None) -> list[tuple[str, dict]]:
    """Split marked-up text into (text, format) segments."""
    fmt = dict(fmt or {})
    out: list[tuple[str, dict]] = []
    buf = ""

    def flush() -> None:
        nonlocal buf
        if buf:
            out.append((buf, dict(fmt)))
            buf = ""

    i = 0
    while i < len(s):
        if s.startswith("**", i):
            flush()
            fmt["b"] = not fmt.get("b")
            i += 2
        elif s[i] == "*":
            flush()
            fmt["i"] = not fmt.get("i")
            i += 1
        elif s[i] == "`":
            flush()
            fmt["mono"] = not fmt.get("mono")
            i += 1
        elif s.startswith("_{", i) or s.startswith("^{", i):
            flush()
            j = _find_close(s, i + 1)
            sub = dict(fmt, va="subscript" if s[i] == "_" else "superscript")
            out.extend(segments(s[i + 2:j], refs, sub))
            i = j + 1
        elif s.startswith("[@", i):
            flush()
            j = s.index("]", i)
            out.append((refs.cite([k.strip() for k in s[i + 2:j].split(",")]), dict(fmt, i=False)))
            i = j + 1
        elif s.startswith("{T:", i) or s.startswith("{S:", i):
            flush()
            j = s.index("}", i)
            key = s[i + 3:j]
            if s[i + 1] == "T":
                out.append((f"Table {roman(refs.tables[key])}", dict(fmt)))
            else:
                out.append((roman(refs.sections[key]), dict(fmt)))
            i = j + 1
        else:
            buf += s[i]
            i += 1
    flush()
    return out


def rpr(f: dict, size: int | None = None, extra: str = "") -> str:
    x = ""
    if f.get("mono"):
        x += f'<w:rFonts w:ascii="{MONO}" w:hAnsi="{MONO}" w:cs="{MONO}"/>'
    if f.get("b"):
        x += "<w:b/><w:bCs/>"
    if f.get("i"):
        x += "<w:i/><w:iCs/>"
    x += extra
    sz = size
    if f.get("mono") and sz is None:
        sz = 18  # 9 pt next to 10 pt Times
    if sz:
        x += f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
    if f.get("hl"):
        x += '<w:highlight w:val="yellow"/>'
    if f.get("va"):
        x += f'<w:vertAlign w:val="{f["va"]}"/>'
    return f"<w:rPr>{x}</w:rPr>" if x else ""


def runs(s: str, refs: Refs, base: dict | None = None, size: int | None = None, extra: str = "") -> str:
    xml = ""
    for text, f in segments(s, refs, base):
        if not f.get("mono"):
            text = text.replace("'", "’")
        else:  # let long paths wrap in a narrow column
            text = text.replace("/", "/" + ZWSP)
        text = text.replace("_", "_" + ZWSP)
        xml += f'<w:r>{rpr(f, size, extra)}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
    return xml


def para(style: str | None, body: str, ppr: str = "") -> str:
    st = f'<w:pStyle w:val="{style}"/>' if style else ""
    return f"<w:p><w:pPr>{st}{ppr}</w:pPr>{body}</w:p>"


# ---------------------------------------------------------------------------------------------------------
# tables


def tex_rows(name: str) -> tuple[str, list[list[str]]]:
    """Return (caption, data rows) of a generated paper/tables/<name>.tex tabular."""
    tex = (TABLES / f"{name}.tex").read_text(encoding="utf-8")
    cap = re.search(r"\\caption\{(.*?)\}\\label", tex, re.S).group(1)
    body = tex.split("\\midrule", 1)[1] if "\\midrule" in tex else tex.split("\\toprule", 1)[1]
    body = body.split("\\bottomrule", 1)[0]
    rows = []
    for line in body.split("\\\\"):
        line = line.replace("\\midrule", "").strip()
        if not line:
            continue
        rows.append([c.strip() for c in line.split("&")])
    return cap, rows


def detex(s: str) -> str:
    s = s.replace("\\_", "_").replace("\\%", "%").replace("\\,", " ").replace("--", "–")
    s = re.sub(r"\\emph\{([^}]*)\}", r"*\1*", s)
    s = re.sub(r"Table~\\ref\{[^}]*\}", "the audit table", s)
    s = s.replace("$\\Delta$", "Δ").replace("~", " ")
    return s


def num(s: str, places: int | None = None) -> str:
    try:
        v = float(s)
    except ValueError:
        return s
    if places is None:
        return f"{int(v):,}" if v == int(v) and "." not in s else s
    return f"{v:,.{places}f}".replace("-", "−")


def cell(text: str, width_pt: float, refs: Refs, head: bool = False, align: str = "center", size: int = 16,
         span: int = 1, keep: bool = True) -> str:
    style = "tablecolhead" if head else "tablecopy"
    jc = ("<w:keepNext/>" if keep else "") + f'<w:jc w:val="{align}"/>'
    span_xml = f'<w:gridSpan w:val="{span}"/>' if span > 1 else ""
    body = runs(text, refs, {"b": head}, size=size)
    return (f'<w:tc><w:tcPr><w:tcW w:w="{width_pt:.2f}pt" w:type="dxa"/>{span_xml}<w:vAlign w:val="center"/>'
            f'</w:tcPr><w:p><w:pPr><w:pStyle w:val="{style}"/>{jc}</w:pPr>{body}</w:p></w:tc>')


def table_xml(widths: list[float], header: list[list[tuple]], rows: list[list[str]], refs: Refs,
              aligns: list[str], size: int = 16) -> str:
    total = sum(widths)
    border = '<w:{0} w:val="single" w:sz="2" w:space="0" w:color="auto"/>'
    borders = "".join(border.format(b) for b in ("top", "start", "bottom", "end", "insideH", "insideV"))
    x = (f'<w:tbl><w:tblPr><w:tblW w:w="{total:.2f}pt" w:type="dxa"/><w:jc w:val="center"/>'
         f"<w:tblBorders>{borders}</w:tblBorders><w:tblLayout w:type=\"fixed\"/>"
         '<w:tblCellMar><w:start w:w="2pt" w:type="dxa"/><w:end w:w="2pt" w:type="dxa"/></w:tblCellMar>'
         '<w:tblLook w:firstRow="1" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="1" '
         'w:noVBand="1"/></w:tblPr><w:tblGrid>')
    x += "".join(f'<w:gridCol w:w="{round(w * 20)}"/>' for w in widths) + "</w:tblGrid>"
    for hrow in header:
        x += '<w:tr><w:trPr><w:cantSplit/><w:tblHeader/><w:jc w:val="center"/></w:trPr>'
        col = 0
        for item in hrow:
            text, span = (item, 1) if isinstance(item, str) else item
            x += cell(text, sum(widths[col:col + span]), refs, head=True, size=size, span=span)
            col += span
        x += "</w:tr>"
    for n, r in enumerate(rows):
        keep = len(rows) <= 12 and n < len(rows) - 1  # keep short tables in one piece
        x += '<w:tr><w:trPr><w:cantSplit/><w:jc w:val="center"/></w:trPr>'
        if len(r) == 1:  # a group label spanning the table
            x += cell(r[0], total, refs, align="start", size=size, span=len(widths), keep=True)
        else:
            for k, text in enumerate(r):
                x += cell(text, widths[k], refs, align=aligns[k], size=size, keep=keep)
        x += "</w:tr>"
    return x + "</w:tbl>"


def caption(title: str, refs: Refs) -> str:
    return para("tablehead", runs(title, refs), '<w:keepNext/>')


def note(text: str, refs: Refs) -> str:
    return para("tablecopy", runs("*Note:* " + text, refs, size=14),
                '<w:spacing w:before="3pt" w:after="8pt"/>')


ABL = {"proposed": "Proposed (reference)", "ablation_no_gate": "No availability gate",
       "ablation_no_weather": "No weather group", "ablation_no_infrastructure": "No 311 infrastructure group",
       "ablation_no_events": "No events group", "ablation_no_incidents": "No incidents group"}
MODEL = {"persistence": "Persistence", "historical_average": "Historical avg.", "xgboost": "XGBoost",
         "lightgbm": "LightGBM", "gru": "GRU", "temporal_transformer": "Temporal Transf.",
         "proposed": "Proposed"}
POLICY = {"full_system": "Full", "llm_without_retrieval": "No RAG",
          "rag_without_constraints": "No constr.",
          "rag_constraints_without_simulation": "No sim."}
CASE = {"routine_rush_hour": "Routine rush hour", "rain_period": "Rain period",
        "stale_data_stress": "Stale-data stress", "wide_interval_stress": "Wide interval",
        "insufficient_evidence": "Out-of-scope query", "mapped_corridor_alert": "Mapped alert",
        "mapped_corridor_rush_hour": "Mapped rush hour"}
SCEN = {"event_surge": "Event surge", "incident_reduced_capacity": "Incident", "routine_peak": "Routine peak"}
CTRL = {"actuated": "Actuated", "fixed_time": "Fixed-time", "forecast_rule": "Forecast rule"}


def build_table(tid: str, refs: Refs) -> str:
    if tid == "sources":
        rows = []
        for r in csv.DictReader(SOURCES_CSV.open(encoding="utf-8")):
            lo, hi = (r["observation_min"] or "")[:10], (r["observation_max"] or "")[:10]
            rows.append([r["source_id"], r["dataset_id"] or "–", f"{lo} to {hi}" if lo else "–",
                         num(r["record_count"]) if r["record_count"] else "–", r["limitations"]])
        x = caption("Verified Public Data Sources (Server-Side Audit)", refs)
        x += table_xml([31, 36, 46, 42, 88.3], [["Source", "Dataset", "Observed range", "Records", "Role / limitation"]],
                       rows, refs, ["start", "center", "center", "end", "start"], size=13)
        x += note("Observed ranges and record counts are server-side counts over each whole dataset "
                  "(`reports/data_audit/source_inventory.csv`); the speed feed’s 1930 minimum is an outlier "
                  "timestamp excluded by the 2026 study window.", refs)
        return x
    if tid == "forecast":
        cap, rows = tex_rows("forecast")
        period = re.search(r"Period (.*?) UTC", cap).group(1)
        data = [r for r in rows if not r[0].startswith("n")]
        ns = [re.search(r"\{(\d+)\}$", c).group(1) for c in rows[-1][1:]]
        body = [[MODEL.get(detex(r[0]), detex(r[0]))] + [num(v, 2) for v in r[1:]] for r in data]
        body.append(["*n*", num(ns[0]), "", num(ns[1]), "", num(ns[2]), ""])
        x = caption("Test-Partition Forecast Error (mph), Operational Track", refs)
        hdr = [["Model", ("15 min", 2), ("30 min", 2), ("60 min", 2)],
               ["", "MAE", "RMSE", "MAE", "RMSE", "MAE", "RMSE"]]
        x += table_xml([59.3] + [30.5] * 6, hdr, body, refs, ["start"] + ["end"] * 6, size=15)
        x += note(f"Test period {detex(period).replace('+00:00', '')} UTC; identical valid-target mask for all "
                  "models; single seed (42) for the learned models.", refs)
        return x
    if tid == "ablation":
        _, rows = tex_rows("ablation")
        body = []
        for r in rows:
            name = detex(r[0])
            status = detex(r[3])
            if status.startswith("NOT_APPLICABLE"):
                status = "NOT_APPLICABLE"
            body.append([ABL.get(name, name), r[1] if r[1] != "--" else "–",
                         num(r[2], 2) if r[2] != "--" else "–", status])
        x = caption("Ablations of the Proposed Model (Test MAE, mph, Mean Over Horizons)", refs)
        x += table_xml([90, 34, 34, 85.3], [["Variant", "MAE", "Δ", "Status"]], body, refs,
                       ["start", "end", "end", "start"], size=15)
        x += note("NOT_APPLICABLE: the operational track has no events or incidents group to remove.", refs)
        return x
    if tid == "seeds":
        tex = (TABLES / "multi_seed.tex").read_text(encoding="utf-8")
        x = caption("Multi-Seed Study of the Deep Forecasters (Test MAE, mph)", refs)
        if "NOT RUN" in tex.split("\\toprule", 1)[1]:
            x += table_xml([180], [["Status"]], [["NOT RUN"]], refs, ["center"], size=16)
            x += note("Seeds 42, 1 and 2 for the proposed model, the GRU and the temporal Transformer; mean ± sd over "
                      "seeds and a paired day-block bootstrap of the seed-averaged difference to the proposed model "
                      "will be reported here once the study has run.", refs)
            return x
        raise SystemExit("multi_seed.tex now holds results: extend build_table('seeds') to render them")
    if tid == "unc":
        _, rows = tex_rows("uncertainty")
        body = [[r[0], num(r[1]), r[2], r[3]] for r in rows]
        x = caption("Split-Conformal Intervals: Test Coverage (Nominal 90%) and Width", refs)
        x += table_xml([50, 60, 50, 60], [["Horizon", "*n*", "Coverage", "Width (mph)"]], body, refs,
                       ["start", "end", "end", "end"], size=16)
        return x
    if tid == "ret":
        _, rows = tex_rows("retrieval")
        flat = " ".join(" & ".join(r) for r in rows)
        pairs = re.findall(r"([A-Za-z@0-9\- ]+?) & ([0-9.]+)", flat)
        body = [[k.strip(), v] for k, v in pairs]
        x = caption("Retrieval Evaluation on the Labelled Query Set", refs)
        x += table_xml([120, 60], [["Measure", "Value"]], body, refs, ["start", "end"], size=16)
        x += note("Labels drafted by the project, not externally reviewed.", refs)
        return x
    if tid == "adv":
        _, rows = tex_rows("advisory")
        body = [[POLICY.get(detex(r[0]), detex(r[0])), CASE.get(detex(r[1]), detex(r[1])), detex(r[2]),
                 detex(r[3]).replace("--", "–"), r[4], r[5]] for r in rows]
        x = caption("Advisory Workflow Outcomes by Policy (REPLAY Cases)", refs)
        x += table_xml([34, 58, 88.3, 19, 22, 22],
                       [["Policy", "Case", "Decision", "LLM", "Cit.", "Viol."]], body, refs,
                       ["start", "start", "start", "center", "end", "end"], size=12)
        x += note("Policies: full system; LLM without retrieval (No RAG); RAG without the constraint layer (No "
                  "constr.); RAG with constraints but without the simulation gate (No sim.). Cit.: invalid "
                  "citations; Viol.: constraint violations; LLM “–”: the case ended before any LLM call. Mapped "
                  "cases are on the West Street link mapped to the SUMO corridor. Simulation-only effects; no "
                  "advisory reached the simulation gate.", refs)
        return x
    if tid == "sim":
        _, rows = tex_rows("simulation")
        body = [[SCEN.get(detex(r[0]), detex(r[0])), CTRL.get(detex(r[1]), detex(r[1])), num(r[4]), num(r[5]),
                 num(r[6]), r[7]] for r in rows]
        x = caption("SUPERSEDED Controller Comparison of 2026-10-20 (SIMULATION)", refs)
        x += table_xml([48, 48, 37, 37, 36, 37.3],
                       [["Scenario", "Controller", "Completed", "Unfinished", "Teleports", "Time loss (s)"]],
                       body, refs, ["start", "start", "end", "end", "end", "end"], size=13)
        x += note("Kept as recorded, not a corridor controller comparison: bare from/to flows let SUMO re-route at "
                  "insertion and about half of the mainline left West Street ({T:simaudit}). Mean over five matched "
                  "seeds; 6,675 (routine) or 8,350 vehicles loaded per run. Time loss is per *completed* trip, so a "
                  "lower value with fewer completed trips is survivorship, not improvement. Scenario-based testbed "
                  "with OSM geometry and declared demand, not a calibrated digital twin; full columns in "
                  "`reports/experiments/simulation_metrics.csv`.", refs)
        return x
    if tid == "simaudit":
        tex = (TABLES / "simulation_audit.tex").read_text(encoding="utf-8")
        inner = tex.split("\\midrule", 1)[1].split("\\bottomrule", 1)[0]
        body = []
        for line in inner.split("\\\\"):
            line = line.replace("\\midrule", "").strip()
            if not line or line.startswith("Side (veh"):
                continue
            g = re.search(r"\\multicolumn\{5\}\{l\}\{\\emph\{(.*?)\}\}", line)
            if g:
                body.append([detex(g.group(1)) + " (side demand, veh/h per approach)"])
                continue
            c = [x.strip() for x in line.split("&")]
            if c[0] in ("dynamic\\_insertion", "fixed\\_free\\_flow"):
                body.append(["Dyn. insertion" if c[0].startswith("dyn") else "Fixed free-flow"]
                            + [num(c[1]), num(c[2]), num(c[3]), c[4].replace("/", " / ")])
            else:
                body.append([c[0], num(c[1]), num(c[2]), num(c[3]), c[4]])
        top = [["Route choice", "Inserted", "Teleports", "Re-routed", "Main off West St"]]
        x = caption("SUMO Testbed Audit (SIMULATION)", refs)
        x += table_xml([62, 40, 40, 44, 57.3], top, body[:2], refs, ["start", "end", "end", "end", "end"], size=13)
        x += para("tablecopy", "", '<w:spacing w:after="2pt"/>')
        x += table_xml([62, 40, 40, 44, 57.3], [["Side demand", "Loaded", "Unfinished", "Teleports",
                                                 "Time loss (s)"]],
                       body[2:], refs, ["start", "end", "end", "end", "end"], size=13)
        x += note("Top: routine peak at the 2026-10-20 declared demand (1,200/150 veh/h per direction/side "
                  "approach), netconvert programs, seed 1. Below: preregistered side-demand selection on the routine "
                  "peak, fixed-time only, observed mainline demand (2014 count 1,389 veh/h per direction; 2025 "
                  "counts 2,510 NB / 2,444 SB veh/h), three development seeds, mean per run. A level is admissible "
                  "only with no teleport and at most 1% unfinished in every seed; no level is admissible under any "
                  "of the three protocols.", refs)
        return x
    raise KeyError(tid)


# ---------------------------------------------------------------------------------------------------------
# document assembly


def number_targets(refs: Refs) -> None:
    h1 = 0
    for blk in C.BODY:
        if blk[0] == "h1":
            h1 += 1
            refs.sections[blk[2]] = h1
        elif blk[0] == "table":
            refs.tables[blk[1]] = len(refs.tables) + 1


def author_block(refs: Refs, sect: str) -> str:
    """All authors in one paragraph, one per column, as in the template's author block."""
    size = 18
    body = ""
    for k, author in enumerate(C.AUTHORS):
        if k:
            body += '<w:r><w:br w:type="column"/></w:r>'
        body += runs(author["name"], refs, size=size)
        for style, text in author["lines"]:
            body += f'<w:r><w:rPr><w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr><w:br/></w:r>'
            body += runs(text, refs, {"i": style == "i"}, size=size)
    ppr = ('<w:spacing w:before="5pt" w:beforeAutospacing="1" w:after="14pt"/>'
           f'<w:rPr><w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>' + sect)
    return para("Author", body, ppr)


def build(out: Path) -> None:
    refs = Refs()
    number_targets(refs)
    zin = zipfile.ZipFile(TEMPLATE)
    doc = zin.read("word/document.xml").decode("utf-8")
    head, body = doc.split("<w:body>", 1)
    sects = re.findall(r"<w:sectPr\b.*?</w:sectPr>", body, re.S)
    title_sect, authors_sect, body_sect, final_sect = sects[0], sects[1], sects[3], sects[4]
    authors_sect = authors_sect.replace('w:num="3"', f'w:num="{len(C.AUTHORS)}"')

    x = para("papertitle", runs(C.TITLE, refs, extra='<w:kern w:val="48"/>'),
             '<w:spacing w:before="5pt" w:beforeAutospacing="1" w:after="5pt" w:afterAutospacing="1"/>')
    x += para("Author", "", '<w:spacing w:before="5pt" w:beforeAutospacing="1" w:after="5pt" '
              'w:afterAutospacing="1" w:line="6pt" w:lineRule="auto"/><w:rPr><w:sz w:val="16"/>'
              f'<w:szCs w:val="16"/></w:rPr>{title_sect}')
    x += author_block(refs, authors_sect)

    x += para("Abstract", runs("*Abstract*—", refs) + runs(C.ABSTRACT, refs))
    x += para("Keywords", runs("Keywords—", refs) + runs(", ".join(C.KEYWORDS), refs, {"b": False}))

    eq_no = 0
    for blk in C.BODY:
        kind = blk[0]
        if kind == "h1":
            x += para("Heading1", runs(blk[1], refs))
        elif kind == "h2":
            x += para("Heading2", runs(blk[1], refs))
        elif kind == "p":
            x += para("BodyText", runs(blk[1], refs))
        elif kind == "p_noindent":
            x += para("BodyText", runs(blk[1], refs), '<w:ind w:firstLine="0pt"/>')
        elif kind == "eq":
            eq_no += 1
            tabs = ('<w:tabs><w:tab w:val="clear" w:pos="126pt"/><w:tab w:val="clear" w:pos="252pt"/>'
                    f'<w:tab w:val="center" w:pos="{COL_PT / 2:.2f}pt"/><w:tab w:val="end" w:pos="{COL_PT:.2f}pt"/>'
                    '</w:tabs><w:spacing w:before="4pt" w:after="4pt"/>')
            tnr = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'
            body_eq = f'<w:r><w:rPr>{tnr}</w:rPr><w:tab/></w:r>'
            for text, f in segments(blk[1], refs):
                body_eq += (f'<w:r>{rpr(f, extra=tnr) if not f.get("mono") else rpr(f)}'
                            f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r>')
            body_eq += f'<w:r><w:rPr>{tnr}</w:rPr><w:tab/><w:t>({eq_no})</w:t></w:r>'
            x += para("equation", body_eq, tabs)
        elif kind == "table":
            x += build_table(blk[1], refs)
        else:
            raise ValueError(kind)

    x += para("Heading5", runs("References", refs))
    for n, key in enumerate(refs.cites):
        last = n == len(refs.cites) - 1
        x += para("references", runs(C.REFERENCES[key], refs),
                  '<w:ind w:start="17.70pt" w:hanging="17.70pt"/>' + (body_sect if last else ""))
    x += "<w:p/>" + final_sect

    unused = sorted(set(C.REFERENCES) - set(refs.cites))
    if unused:
        raise SystemExit(f"references never cited: {unused}")

    new_doc = head + "<w:body>" + x + "</w:body></w:document>"
    core = zin.read("docProps/core.xml").decode("utf-8")
    core = re.sub(r"<dc:title>.*?</dc:title>", f"<dc:title>{escape(C.TITLE)}</dc:title>", core)
    core = re.sub(r"<dc:creator>.*?</dc:creator>",
                  "<dc:creator>" + escape("; ".join(a["name"] for a in C.AUTHORS)) + "</dc:creator>", core)
    core = re.sub(r"<cp:keywords>.*?</cp:keywords>|<cp:keywords/>",
                  "<cp:keywords>" + escape(", ".join(C.KEYWORDS)) + "</cp:keywords>", core)
    core = re.sub(r"<cp:lastModifiedBy>.*?</cp:lastModifiedBy>", "<cp:lastModifiedBy></cp:lastModifiedBy>", core)

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = new_doc.encode("utf-8")
            elif item.filename == "docProps/core.xml":
                data = core.encode("utf-8")
            zout.writestr(item, data)
    words = len(C.ABSTRACT.split())
    print(f"wrote {out} ({len(refs.cites)} references, {len(refs.tables)} tables, {eq_no} equations, "
          f"abstract {words} words)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=REPO / "paper" / "ieee_conference_paper.docx")
    build(ap.parse_args().out)


if __name__ == "__main__":
    main()
