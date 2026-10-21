"""Fill the VIT final-review template (assets/final_review_template_24_slides.pptx) with the project's verified content."""
import copy
import sys
from pathlib import Path

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

SRC, OUT, LOGO = sys.argv[1], sys.argv[2], sys.argv[3]
DASH = Path(__file__).resolve().parent / "assets" / "dashboard"
ARIAL, TNR = "Arial", "Times New Roman"
NAVY = RGBColor(0x1F, 0x49, 0x7D)      # theme dk2
BLUE = RGBColor(0x54, 0x8D, 0xD4)      # template title band (dk2 at 60 %)
TINT = RGBColor(0xE4, 0xEC, 0xF7)
INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x55, 0x5F, 0x6B)
OK = RGBColor(0x2E, 0x7D, 0x4F)
WARN = RGBColor(0xB2, 0x6B, 0x00)
STOP = RGBColor(0xB0, 0x2A, 0x22)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SUBNAVY = RGBColor(0x24, 0x40, 0x61)   # template subtitle colour (accent1 at 50 %)

prs = Presentation(SRC)
S = prs.slides


def drop(shape):
    shape._element.getparent().remove(shape._element)


def set_title(slide, text):
    tf = slide.shapes.title.text_frame
    p = tf.paragraphs[0]
    p.runs[0].text = text
    for r in p.runs[1:]:
        r._r.getparent().remove(r._r)
    for extra in tf.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)


def style(run, font, size, color=INK, bold=False, italic=False):
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:cs", "a:ea"):
        el = rPr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rPr, qn(tag))
        el.set("typeface", font)


def no_bullet(p):
    pPr = p._p.get_or_add_pPr()
    for tag in ("a:buNone", "a:buChar", "a:buAutoNum"):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    pPr.set("marL", "0")
    pPr.set("indent", "0")
    etree.SubElement(pPr, qn("a:buNone"))


def bullet(p, char="•", level_indent=0.3):
    pPr = p._p.get_or_add_pPr()
    for tag in ("a:buNone", "a:buChar", "a:buAutoNum", "a:buFont"):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    pPr.set("marL", str(int(Inches(level_indent))))
    pPr.set("indent", str(int(-Inches(0.25))))
    bf = etree.SubElement(pPr, qn("a:buFont"))
    bf.set("typeface", "Arial")
    bc = etree.SubElement(pPr, qn("a:buChar"))
    bc.set("char", char)


def fill(tf, paras, font, size, color=INK, align=PP_ALIGN.LEFT, after=4, bullets=False, line=None):
    """paras: list of items; an item is a string or a list of (text, bold[, color]) runs."""
    tf.clear()
    tf.word_wrap = True
    for i, item in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        runs = [(item, False)] if isinstance(item, str) else item
        for spec in runs:
            r = p.add_run()
            r.text = spec[0]
            style(r, font, spec[3] if len(spec) > 3 else size, spec[2] if len(spec) > 2 else color, bold=spec[1])
        p.alignment = align
        p.space_after = Pt(after)
        if line:
            p.line_spacing = line
        (bullet(p) if bullets else no_bullet(p))
    return tf


def box(slide, x, y, w, h, paras, font, size, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, bg=None,
        shape=MSO_SHAPE.RECTANGLE, margin=0.08, after=3, bullets=False, name=None, line=None):
    if bg is None:
        sh = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    else:
        sh = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
        sh.fill.solid()
        sh.fill.fore_color.rgb = bg
        sh.line.fill.background()
        sh.shadow.inherit = False
        if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
            sh.adjustments[0] = 0.08
    if name:
        sh.name = name
    tf = sh.text_frame
    for side in ("left", "right", "top", "bottom"):
        setattr(tf, f"margin_{side}", Inches(margin))
    tf.vertical_anchor = anchor
    tf.auto_size = None
    fill(tf, paras, font, size, color, align, after, bullets, line)
    return sh


def arrow(slide, x1, y1, x2, y2, color=NAVY, kind=MSO_CONNECTOR.STRAIGHT):
    c = slide.shapes.add_connector(kind, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(1.75)
    ln = c.line._get_or_add_ln()
    tail = etree.SubElement(ln, qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("len", "med")
    return c


def body_ph(slide):
    return next((sh for sh in slide.placeholders if sh.placeholder_format.idx == 1), None)


def refs(slide, lines, y, size=11, font=ARIAL):
    box(slide, 0.55, y, 12.9, 7.38 - y, [[(t, False, MUTED)] for t in lines], font, size, after=1, margin=0.02)


REF = {
    1: "[1] Y. Li, R. Yu, C. Shahabi, and Y. Liu, “Diffusion convolutional recurrent neural network: Data-driven traffic forecasting,” in Proc. ICLR, 2018.",
    2: "[2] B. Yu, H. Yin, and Z. Zhu, “Spatio-temporal graph convolutional networks: A deep learning framework for traffic forecasting,” in Proc. IJCAI, 2018, pp. 3634–3640.",
    3: "[3] Z. Wu, S. Pan, G. Long, J. Jiang, and C. Zhang, “Graph WaveNet for deep spatial-temporal graph modeling,” in Proc. IJCAI, 2019, pp. 1907–1913.",
    4: "[4] P. Lewis et al., “Retrieval-augmented generation for knowledge-intensive NLP tasks,” in Proc. NeurIPS, 2020.",
    5: "[5] P. A. Lopez et al., “Microscopic traffic simulation using SUMO,” in Proc. IEEE ITSC, 2018, pp. 2575–2582.",
    6: "[6] S. Brody, U. Alon, and E. Yahav, “How attentive are graph attention networks?,” in Proc. ICLR, 2022.",
    7: "[7] A. N. Angelopoulos and S. Bates, “A gentle introduction to conformal prediction and distribution-free uncertainty quantification,” arXiv:2107.07511, 2021.",
    8: "[8] C. Xu and Y. Xie, “Conformal prediction interval for dynamic time-series,” in Proc. ICML, PMLR vol. 139, 2021, pp. 11559–11569.",
    9: "[9] S. M. Lundberg and S.-I. Lee, “A unified approach to interpreting model predictions,” in Proc. NeurIPS, 2017.",
    10: "[10] B. Rozemberczki et al., “PyTorch Geometric Temporal: Spatiotemporal signal processing with neural machine learning models,” in Proc. ACM CIKM, 2021, pp. 4564–4573.",
    11: "[11] NYC Department of Transportation, “DOT Traffic Speeds NBE,” NYC Open Data, dataset i4gi-tjb9, accessed Oct. 2026.",
    12: "[12] NYC Department of Transportation, “Automated Traffic Volume Counts,” NYC Open Data, dataset 7ym2-wayt, accessed Oct. 2026.",
}

# ---------------------------------------------------------------- 1. title slide (matches the Review-II layout)
s = S[0]
t = s.shapes.title
r = t.text_frame.paragraphs[0].runs[0]
r.text = "Predictive Analytics for Smart City Infrastructure"
style(r, ARIAL, 40, INK, bold=False)
t.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
t.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
pic = next(sh for sh in s.shapes if sh.shape_type == 13)
drop(pic)
w_in = 5.4
iw, ih = Image.open(LOGO).size
s.shapes.add_picture(LOGO, Inches((14 - w_in) / 2), Inches(1.95), Inches(w_in), Inches(w_in * ih / iw)).name = "VIT Chennai 15 years logo"
sub = body_ph(s)
sub.left, sub.top, sub.width, sub.height = Inches(0.4), Inches(3.5), Inches(13.2), Inches(4.35)
bp = sub.text_frame._txBody.find(qn("a:bodyPr"))
for el in list(bp):
    bp.remove(el)
etree.SubElement(bp, qn("a:noAutofit"))
lines = ["M.Tech Project Work Final Review", "Presented by",
         "S K Sricharan (25MML1010)",
         "M.Tech Computer Science and Engineering",
         "(Artificial Intelligence and Machine Learning – In collaboration with LTI Mindtree)",
         "Under the Guidance of", "Dr R. Srinivasa Perumal", "Associate Professor",
         "School of Computer Science and Engineering", "Vellore Institute of Technology, Chennai."]
fill(sub.text_frame, [[(ln, ln.startswith("S K Sricharan"), SUBNAVY)] for ln in lines], TNR, 20, SUBNAVY,
     PP_ALIGN.CENTER, after=0, line=1.0)
for i in (2, 5):  # the blank lines of the Review-II slide, as paragraph spacing
    sub.text_frame.paragraphs[i].space_before = Pt(14)

# ---------------------------------------------------------------- 2. contents (template list, instructions removed)
s = S[1]
tb = next(sh for sh in s.shapes if sh.name == "Content Placeholder 2")
paras = tb.text_frame.paragraphs
for p in paras:
    txt = "".join(r.text for r in p.runs)
    for key in ("INTRODUCTION", "LITERATURE SURVEY"):
        if txt.startswith(key) and p.runs:
            p.runs[0].text = key
            for rr in p.runs[1:]:
                rr._r.getparent().remove(rr._r)
last = [p for p in paras if "".join(r.text for r in p.runs).startswith("TIMELINE")][0]
last.runs[0].text = "RESULTS & OUTCOMES"
for rr in last.runs[1:]:
    rr._r.getparent().remove(rr._r)
new = copy.deepcopy(last._p)
last._p.addnext(new)
for tnode in new.iter(qn("a:t")):
    tnode.text = ""
new.findall(qn("a:r"))[0].find(qn("a:t")).text = "REFERENCES"

# ---------------------------------------------------------------- 3. abstract (Times New Roman 24, <= 200 words)
abstract = ("Traffic control rooms can see congestion as it happens, but rarely receive forecasts that are explained, "
            "honest about their uncertainty and tested before an action is suggested. This project builds a decision-support "
            "prototype on public New York City data. A context-gated GATv2–Transformer forecasts link speeds 15, 30 and 60 "
            "minutes ahead on a graph of 16 Manhattan DOT speed links (January–October 2026), fusing weather, 311 and calendar "
            "context through an availability-aware gate. Split-conformal intervals quantify uncertainty, grouped SHAP explains "
            "the trained model, and a LangGraph workflow uses a local LLM (qwen2.5 7B) with FAISS retrieval to draft signal "
            "advisories that deterministic safety rules and a SUMO simulation must pass before human review. On a 45-day test "
            "period the model reaches 4.77, 5.33 and 6.15 mph MAE, 7–16 % below persistence; intervals reach 90 % coverage "
            "overall, and retrieval removed every fabricated citation. An audit of the simulation testbed showed it cannot yet "
            "support a controller comparison, which is therefore reported as not run.")
ph = body_ph(S[2])
ph.left, ph.top, ph.width, ph.height = Inches(0.45), Inches(1.95), Inches(13.1), Inches(5.35)
fill(ph.text_frame, [abstract], TNR, 24, INK, PP_ALIGN.JUSTIFY, after=0, line=1.05)

# ---------------------------------------------------------------- 4. introduction (Arial 24, <= 150 words, references below)
ph = body_ph(S[3])
ph.left, ph.top, ph.width, ph.height = Inches(0.55), Inches(1.95), Inches(12.9), Inches(4.2)
fill(ph.text_frame, [
    "Urban congestion depends on demand, neighbouring roads, weather, events and incidents, yet control rooms mostly see only current conditions.",
    "Graph neural networks forecast traffic on road networks [1]–[3], but give point forecasts without uncertainty or explanation.",
    "An LLM can phrase advice convincingly without evidence; retrieval grounding [4] and simulation testing [5] are needed before any signal action.",
    "Objective: join forecasts, uncertainty, explanations, cited evidence and simulation checks in one auditable, human-in-the-loop advisory pipeline on real NYC data.",
], ARIAL, 24, INK, after=10, bullets=True)
refs(S[3], [REF[i] for i in (1, 2, 3, 4, 5)], 6.3, size=11)


# ---------------------------------------------------------------- 5-6. literature survey tables
def lit(slide, rows, ref_ids, title=None):
    if title:
        set_title(slide, title)
    gf = next(sh for sh in slide.shapes if sh.has_table)
    gf.top = Inches(1.82)
    tbl = gf.table
    heights = [0.42] + [1.06] * 4
    for i, h in enumerate(heights):
        tbl.rows[i].height = Inches(h)
    for ri, row in enumerate(rows, start=1):
        for ci, val in enumerate([str(ri if title is None else ri + 4)] + list(row)):
            cell = tbl.cell(ri, ci)
            tf = cell.text_frame
            fill(tf, [val], ARIAL, 12, INK, PP_ALIGN.CENTER if ci == 0 else PP_ALIGN.LEFT, after=0)
            cell.margin_left = cell.margin_right = Inches(0.06)
            cell.margin_top = cell.margin_bottom = Inches(0.04)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    for ci in range(5):  # header text a touch larger and dark for projection
        for p in tbl.cell(0, ci).text_frame.paragraphs:
            for rr in p.runs:
                style(rr, ARIAL, 13, NAVY, bold=True)
    refs(slide, [REF[i] for i in ref_ids], 6.62, size=10.5)


lit(S[4], [
    ("[1] Li et al., Diffusion Convolutional Recurrent Neural Network (ICLR 2018)",
     "Diffusion convolution on a directed road graph inside a GRU encoder–decoder (seq2seq)",
     "Modelling traffic as diffusion on the directed graph improved multi-step speed forecasts over non-graph baselines",
     "Fixed, predefined graph; point forecasts only; no exogenous context or uncertainty"),
    ("[2] Yu et al., Spatio-Temporal Graph Convolutional Networks (IJCAI 2018)",
     "Graph convolution combined with gated temporal convolution; fully convolutional, no recurrence",
     "Accurate short-term forecasts with faster training and fewer parameters than recurrent models",
     "Static graph; point forecasts; no weather or event context"),
    ("[3] Wu et al., Graph WaveNet (IJCAI 2019)",
     "Self-adaptive adjacency matrix learned from data plus dilated causal convolutions",
     "Captures hidden spatial dependencies even when the given graph is incomplete; long receptive field",
     "Learned graph is hard to interpret; no uncertainty estimates"),
    ("[6] Brody et al., How Attentive are Graph Attention Networks? (ICLR 2022)",
     "GATv2: reorders the attention computation so that attention becomes dynamic",
     "Shows that GAT attention is static; GATv2 is strictly more expressive and performs better on benchmarks",
     "General-purpose graph layer; no temporal modelling"),
], (1, 2, 3, 6))
lit(S[5], [
    ("[7] Angelopoulos & Bates, A Gentle Introduction to Conformal Prediction (2021)",
     "Split conformal prediction wrapped around any trained model",
     "Distribution-free, finite-sample marginal coverage guarantee",
     "Assumes exchangeable data; guarantees marginal, not conditional, coverage"),
    ("[8] Xu & Xie, Conformal Prediction Interval for Dynamic Time-Series (ICML 2021)",
     "EnbPI: bootstrap ensemble with conformal-style intervals for time series",
     "Approximately valid intervals without exchangeability, under stated assumptions on the errors",
     "Requires an ensemble of models; validity is approximate"),
    ("[9] Lundberg & Lee, A Unified Approach to Interpreting Model Predictions (NeurIPS 2017)",
     "SHAP: Shapley-value feature attribution (KernelSHAP and model-specific variants)",
     "Unifies additive attribution methods with consistency guarantees",
     "Cost grows with the number of features; attributions describe the model, not causes"),
    ("[4] Lewis et al., Retrieval-Augmented Generation (NeurIPS 2020)",
     "Dense passage retriever combined with a seq2seq generator",
     "More specific and factual generation on knowledge-intensive tasks than a parametric-only model",
     "Bounded by corpus and retriever quality; can still produce unsupported text"),
], (4, 7, 8, 9), title="3.LITERATURE SURVEY (CONTD.)")

# ---------------------------------------------------------------- 7. research gaps (3 x 2 cards)
gaps = [
    ("G1  Forecast stops at the number", "Graph forecasting studies [1]–[3] report accuracy but do not connect the forecast to a checked, testable action."),
    ("G2  Uncertainty does not decide", "Point forecasts dominate; interval width and data quality rarely decide whether an advisory is issued."),
    ("G3  Surrogate explanations", "Explanations are often computed on simpler surrogate models instead of the deployed forecaster."),
    ("G4  Ungrounded LLM advice", "LLM recommendations are rarely tied to cited, allow-listed evidence or bounded by deterministic safety rules."),
    ("G5  Missing context is hidden", "Dead sensors and unavailable feeds are usually imputed silently instead of being modelled with availability masks."),
    ("G6  Untested testbeds", "Simulation studies seldom audit route choice, demand and signal timing before comparing controllers."),
]
for k, (head, txt) in enumerate(gaps):
    cx, cy = 0.5 + (k % 3) * 4.4, 2.0 + (k // 3) * 2.65
    box(S[6], cx, cy, 4.1, 2.4, [[(head, True, NAVY, 19)], [(txt, False, INK, 16)]], ARIAL, 16, bg=TINT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, margin=0.18, after=8, name=f"Gap {k + 1}")

# ---------------------------------------------------------------- 8. objectives (badge + text rows, two columns)
objs = [
    ("O1", "Forecast link speeds 15, 30 and 60 min ahead with a context-gated GATv2–Transformer and compare it with six baselines on identical data", "G1, G5"),
    ("O2", "Quantify uncertainty with per-horizon split-conformal intervals and defer advisories when reliability is low", "G2"),
    ("O3", "Explain the trained model itself with grouped SHAP and sensitivity tests", "G3"),
    ("O4", "Draft advisories with a local LLM that must cite retrieved evidence and pass deterministic safety checks", "G4"),
    ("O5", "Test admissible advisories in a SUMO simulation, after verifying the testbed itself", "G6"),
    ("O6", "Make every result reproducible and traceable: tests, MLflow, Docker, evidence registry and a paper generated from artifacts", "all"),
]
for k, (tag, txt, g) in enumerate(objs):
    cx, cy = 0.5 + (k % 2) * 6.6, 2.0 + (k // 2) * 1.75
    badge = S[7].shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx), Inches(cy + 0.15), Inches(0.9), Inches(0.9))
    badge.fill.solid()
    badge.fill.fore_color.rgb = NAVY
    badge.line.fill.background()
    badge.shadow.inherit = False
    badge.name = f"Objective badge {tag}"
    fill(badge.text_frame, [[(tag, True, WHITE)]], ARIAL, 20, WHITE, PP_ALIGN.CENTER, after=0)
    badge.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    box(S[7], cx + 1.05, cy, 5.25, 1.55, [[(txt, False, INK, 17)], [(f"Addresses: {g}", False, MUTED, 13)]], ARIAL, 17,
        margin=0.04, after=4, name=f"Objective {tag}")

# ---------------------------------------------------------------- 9. research work done (Arial 24 + four measured callouts)
ph = body_ph(S[8])
ph.left, ph.top, ph.width, ph.height = Inches(0.7), Inches(1.95), Inches(12.6), Inches(3.3)
tf = ph.text_frame
fill(tf, ["The research work is organised in four parts:", "MODULE IDENTIFICATION", "SYSTEM ARCHITECTURE",
          "DEVELOPMENT & INTEGRATION", "PROTOTYPE / RESEARCH FRAMEWORK"], ARIAL, 24, INK, after=4)
for i, p in enumerate(tf.paragraphs):
    if i == 0:
        bullet(p)
    else:
        bullet(p, char="❖", level_indent=1.05)
        p._p.get_or_add_pPr().set("indent", str(int(-Inches(0.42))))
        for rr in p.runs:
            style(rr, ARIAL, 22, NAVY, bold=True)
stats = [("1,968,303", "raw speed records processed"), ("16", "Manhattan links modelled"),
         ("7", "forecasting models compared"), ("66", "automated tests passing")]
for k, (v, lab) in enumerate(stats):
    box(S[8], 0.5 + k * 3.3, 5.45, 3.0, 1.75, [[(v, True, NAVY, 34)], [(lab, False, INK, 15)]], ARIAL, 15,
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, bg=TINT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, after=2,
        name=f"Stat {k + 1}")

# ---------------------------------------------------------------- 10. module identification (4 x 3 cards)
drop(body_ph(S[9]))
mods = [
    ("M1  Data ingestion", "NYC Open Data, Open-Meteo, OSM; resumable downloads with SHA-256 provenance"),
    ("M2  Preprocessing & features", "5-minute grid, causal lags, availability masks, leakage-tested splits"),
    ("M3  Road graph", "Directed DOT-link graph (26 nodes, 16 edges) as a PyG Temporal signal [10]"),
    ("M4  Forecasting", "Context-gated GATv2–Transformer plus six baselines at 15/30/60 min"),
    ("M5  Uncertainty", "Per-horizon split-conformal intervals and a reliability gate"),
    ("M6  Explainability", "Grouped KernelSHAP on the trained model; neighbour and window sensitivity"),
    ("M7  Knowledge & RAG", "15 approved documents, MiniLM embeddings, FAISS index"),
    ("M8  LLM agent", "LangGraph workflow; local qwen2.5 7B via Ollama; schema-validated JSON"),
    ("M9  Safety constraints", "13 deterministic checks; protected TraCI signal controller"),
    ("M10  Simulation", "SUMO 1.28 West Street corridor; matched seeds; testbed audit"),
    ("M11  Services", "FastAPI, PostgreSQL/PostGIS job queue, worker, Streamlit dashboard"),
    ("M12  Tracking & reporting", "MLflow, evidence registry, claims ledger, paper tables from artifacts"),
]
for k, (head, txt) in enumerate(mods):
    cx, cy = 0.5 + (k % 4) * 3.3, 1.95 + (k // 4) * 1.8
    box(S[9], cx, cy, 3.05, 1.6, [[(head, True, NAVY, 17)], [(txt, False, INK, 14)]], ARIAL, 14, bg=TINT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, margin=0.13, after=4, name=f"Module {k + 1}")

# ---------------------------------------------------------------- 11. system architecture (Times New Roman)
s = S[10]
drop(body_ph(s))
row1 = ["Public data sources\n(NYC DOT, ATR, 311, events, Open-Meteo, OSM)", "Ingestion &\nprovenance", "Preprocessing &\ncausal features",
        "Directed road graph\n(PyG Temporal)", "Forecasting\n(GATv2–Transformer)"]
row2 = ["Conformal intervals\n& reliability gate", "SHAP explanation\n& FAISS retrieval", "LLM recommendation\n(qwen2.5 7B)",
        "Deterministic safety\nconstraints", "SUMO / TraCI\nsimulation gate", "Human review\n(simulation only)"]
w1, g1 = 2.36, 0.3
for k, txt in enumerate(row1):
    x = 0.5 + k * (w1 + g1)
    box(s, x, 1.95, w1, 1.15, [[(ln, i == 0, WHITE if k < 5 else INK, 15 if i == 0 else 12)] for i, ln in enumerate(txt.split("\n"))],
        TNR, 15, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, bg=NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE, after=0,
        name=f"Arch stage {k + 1}")
    if k:
        arrow(s, x - g1 + 0.02, 2.525, x - 0.02, 2.525)
w2, g2 = 1.93, 0.284
for k, txt in enumerate(row2):
    x = 0.5 + k * (w2 + g2)
    box(s, x, 3.75, w2, 1.15, [[(ln, i == 0, NAVY, 14 if i == 0 else 12)] for i, ln in enumerate(txt.split("\n"))],
        TNR, 14, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, bg=TINT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, after=0,
        name=f"Advisory stage {k + 1}")
    if k:
        arrow(s, x - g2 + 0.02, 4.325, x - 0.02, 4.325)
xa, xb, ym = 0.5 + 4 * (w1 + g1) + w1 / 2, 0.5 + w2 / 2, 3.42
for (ax, ay, bx, by) in ((xa, 3.11, xa, ym), (xa, ym, xb, ym)):
    seg = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(ax), Inches(ay), Inches(bx), Inches(by))
    seg.line.color.rgb = NAVY
    seg.line.width = Pt(1.75)
arrow(s, xb, ym, xb, 3.73)
box(s, 0.5, 5.2, 6.35, 2.1, [[("Data flow", True, NAVY, 16)],
    [("Raw API responses stored verbatim with hashes → 5-minute grid per link → windows of 24 steps × nodes × features → "
      "forecasts with 90 % intervals → advisory state in LangGraph → decision and audit trail persisted in PostgreSQL/PostGIS; "
      "every run logged in MLflow.", False, INK, 14)]], TNR, 14, bg=TINT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, margin=0.15, after=4,
    name="Data flow")
box(s, 7.15, 5.2, 6.35, 2.1, [[("Technology stack", True, NAVY, 16)],
    [("Python 3.12 · Pandas/Polars · PyTorch + PyTorch Geometric + PyG Temporal · XGBoost/LightGBM · SHAP · "
      "sentence-transformers + FAISS · Ollama (qwen2.5:7b) · LangGraph · SUMO 1.28 / TraCI · FastAPI · Streamlit · "
      "PostgreSQL/PostGIS · MLflow · Docker Compose · Pytest", False, INK, 14)]], TNR, 14, bg=TINT,
    shape=MSO_SHAPE.ROUNDED_RECTANGLE, margin=0.15, after=4, name="Technology stack")

# ---------------------------------------------------------------- 12. development & integration (Times New Roman)
s = S[11]
drop(body_ph(s))
cols = [
    ("Implementation of modules", [
        "One Python package with a staged command-line interface, YAML configuration and Pydantic contracts",
        "Every stage writes artifacts with run IDs and SHA-256 hashes",
        "The same code path runs the smoke tests and the full experiment"]),
    ("Integration strategy", [
        "Shared contracts frozen first: forecast, uncertainty, evidence, candidate action, decision",
        "A stage runner executes the real-data pipeline in fixed order with a stage log",
        "Only the recommendation node calls the LLM; every gate is deterministic code",
        "66 automated tests: unit, leakage, safety, integration, end-to-end"]),
]
for k, (head, items) in enumerate(cols):
    box(s, 0.5 + k * 4.0, 1.95, 3.75, 5.35, [[(head, True, NAVY, 18)]] + [[(it, False, INK, 15)] for it in items], TNR, 15,
        bg=TINT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, margin=0.16, after=8, name=head)
issues = [
    ("7 of 26 links report zero speed all year", "treated as missing; 16 links kept by a train-coverage rule"),
    ("DOT link geometries stop short of link ends", "three documented graph-edge rules"),
    ("GRU crash with cuDNN on Windows/CUDA", "cuDNN disabled for GRU runs only"),
    ("Bootstrap resampled 5-minute steps, not days", "unit fixed and ablations re-run"),
    ("A missing field silently blocked every LLM call", "fixed and agent evaluation re-run"),
    ("SUMO re-routed half the corridor traffic", "fixed routes and a testbed audit"),
]
box(s, 8.5, 1.95, 5.0, 0.45, [[("Challenges faced → solutions", True, NAVY, 18)]], TNR, 18, margin=0.02, after=0)
for k, (prob, fix) in enumerate(issues):
    box(s, 8.5, 2.45 + k * 0.81, 5.0, 0.74, [[(prob, True, INK, 14)], [("→ " + fix, False, OK, 14)]], TNR, 14, margin=0.04,
        after=1, name=f"Challenge {k + 1}")

# ---------------------------------------------------------------- 13. prototype (Arial)
s = S[12]
ph = body_ph(s)
ph.left, ph.top, ph.width, ph.height = Inches(0.45), Inches(1.95), Inches(6.9), Inches(5.35)
fill(ph.text_frame, [
    [("Command-line pipeline: ", True), ("one command per stage, from data audit to paper tables", False)],
    [("FastAPI service: ", True), ("18 endpoints for forecasts, explanations, retrieval, advisories, simulations and review; long jobs run in a PostgreSQL-backed worker", False)],
    [("Streamlit dashboard: ", True), ("11 pages, from data audit and traffic map to forecasts, explanations, agent traces, SUMO results and the model card", False)],
    [("Every view labels its mode: ", True), ("LIVE, REPLAY or SIMULATION", False)],
    [("Docker Compose: ", True), ("PostGIS, API, worker and dashboard images, built and smoke-tested", False)],
    [("Human review ", True), ("approves or rejects for simulation only; nothing is sent to real signals", False)],
], ARIAL, 17, INK, after=9, bullets=True)
steps = [("Data quality check", "DEFER_DATA"), ("Forecast", ""), ("Uncertainty gate", "DEFER_UNCERTAINTY"),
         ("SHAP + evidence retrieval", "DEFER_EVIDENCE"), ("LLM candidate", "REJECT_SCHEMA"),
         ("Safety constraints", "REJECT_CONSTRAINT"), ("SUMO simulation gate", "REJECT_SIMULATION"),
         ("Human review", "PENDING_HUMAN_REVIEW")]
box(s, 7.75, 1.9, 5.8, 0.35, [[("Advisory workflow (LangGraph)", True, NAVY, 15)]], ARIAL, 15, margin=0.02, after=0)
for k, (name, exitst) in enumerate(steps):
    y = 2.3 + k * 0.62
    box(s, 7.75, y, 3.05, 0.48, [[(f"{k + 1}  {name}", True, WHITE, 13)]], ARIAL, 13, anchor=MSO_ANCHOR.MIDDLE, bg=NAVY,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, margin=0.1, after=0, name=f"Workflow step {k + 1}")
    if k < len(steps) - 1:
        arrow(s, 9.275, y + 0.49, 9.275, y + 0.61)
    if exitst:
        arrow(s, 10.82, y + 0.24, 11.15, y + 0.24, color=MUTED)
        box(s, 11.18, y + 0.04, 2.4, 0.4, [[(exitst, True, OK if exitst.startswith("PENDING") else (WARN if exitst.startswith("DEFER") else STOP), 11)]],
            ARIAL, 11, anchor=MSO_ANCHOR.MIDDLE, margin=0.02, after=0)

# ---------------------------------------------------------------- 14. conclusions (Times New Roman)
s = S[13]
drop(body_ph(s))
box(s, 0.5, 1.9, 6.5, 0.4, [[("Performance metrics (test period 6 Sep – 20 Oct 2026)", True, NAVY, 16)]], TNR, 16, margin=0.02, after=0)
data = [("Metric", "15 min", "30 min", "60 min"),
        ("Proposed model MAE (mph)", "4.77", "5.33", "6.15"),
        ("Proposed, mean of 3 seeds (mph)", "4.69", "5.34", "6.15"),
        ("Persistence MAE (mph)", "5.14", "6.06", "7.29"),
        ("90 % interval coverage", "0.909", "0.907", "0.903"),
        ("Coverage under congestion", "0.798", "0.794", "0.757"),
        ("MAE kept after gate (≈26 % deferred)", "3.72", "4.38", "5.25")]
gt = s.shapes.add_table(len(data), 4, Inches(0.5), Inches(2.35), Inches(6.5), Inches(3.3))
gt.name = "Performance metrics"
tbl = gt.table
for ci, wv in enumerate((3.5, 1.0, 1.0, 1.0)):
    tbl.columns[ci].width = Inches(wv)
for ri, row in enumerate(data):
    for ci, val in enumerate(row):
        cell = tbl.cell(ri, ci)
        fill(cell.text_frame, [[(val, ri == 0 or (ri == 1 and ci > 0), WHITE if ri == 0 else INK, 15)]], TNR, 15,
             align=PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.RIGHT, after=0)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY if ri == 0 else (TINT if ri % 2 else WHITE)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
box(s, 0.5, 5.85, 6.5, 1.45, [[("Validation of approach", True, NAVY, 16)],
    [("Chronological splits with purge gaps and leakage tests; identical targets and masks for every model; day-block "
      "bootstrap for ablations; a preregistered simulation baseline test; failed runs kept and reported.", False, INK, 14)]],
    TNR, 14, margin=0.02, after=3)
box(s, 7.4, 1.9, 6.1, 5.4, [[("Observations", True, NAVY, 18)],
    [("The proposed model beats persistence by 7–16 % and both tree models. Over three seeds it is 0.03–0.08 mph below the "
      "temporal Transformer at every horizon and the GRU at 30/60 min; the GRU is better at 15 min. Small, not decisive.",
      False, INK, 15)],
    [("The availability-aware gate helps (MAE +0.067 mph when removed); operational weather features hurt (−0.046 mph), "
      "a negative result.", False, INK, 15)],
    [("Intervals meet 90 % overall but under-cover congestion, the regime that matters for advisories.", False, INK, 15)],
    [("Retrieval removed fabricated citations (3 of 3 without it, 0 of 9 with it); the constraint layer, not the LLM, "
      "decides admissibility.", False, INK, 15)],
    [("The simulation testbed fails its own baseline test, so the controller comparison is not run.", False, INK, 15)]],
    TNR, 15, bg=TINT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, margin=0.18, after=9, name="Observations")
for p in list(s.shapes)[-1].text_frame.paragraphs[1:]:
    bullet(p)

# ---------------------------------------------------------------- 15. outcome: forecasting (native chart, Times New Roman)
s = S[14]
drop(body_ph(s))
cd = CategoryChartData()
cd.categories = ["Persistence", "Historical avg", "XGBoost", "LightGBM", "GRU", "Temporal Transformer", "Proposed"]
cd.add_series("15 min", (5.1386, 7.6321, 4.8229, 4.8725, 4.7145, 4.7334, 4.7726))
cd.add_series("30 min", (6.0556, 7.6329, 5.5792, 5.5993, 5.3731, 5.3375, 5.3308))
cd.add_series("60 min", (7.2875, 7.6369, 6.3079, 6.3150, 6.1742, 6.1835, 6.1546))
gfc = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.4), Inches(1.85), Inches(8.6), Inches(5.45), cd)
gfc.name = "MAE by model"
ch = gfc.chart
ch.has_title = True
ch.chart_title.text_frame.text = "Test MAE (mph) by model and horizon — lower is better"
for p in ch.chart_title.text_frame.paragraphs:
    for rr in p.runs:
        rr.font.name, rr.font.size, rr.font.bold, rr.font.color.rgb = TNR, Pt(15), True, NAVY
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.BOTTOM
ch.legend.include_in_layout = False
ch.legend.font.name, ch.legend.font.size = TNR, Pt(13)
for ser, col in zip(ch.series, (RGBColor(0x9C, 0xBC, 0xE6), BLUE, NAVY)):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = col
plot = ch.plots[0]
plot.gap_width = 60
plot.overlap = -5
plot.has_data_labels = True
dl = plot.data_labels
dl.number_format, dl.number_format_is_linked = "0.00", False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
dl.font.name, dl.font.size, dl.font.color.rgb = TNR, Pt(9), INK
va = ch.value_axis
va.minimum_scale, va.maximum_scale = 0, 8.5
va.has_major_gridlines = True
va.major_gridlines.format.line.color.rgb = RGBColor(0xDD, 0xE3, 0xEA)
va.tick_labels.font.name, va.tick_labels.font.size = TNR, Pt(12)
va.format.line.fill.background()
ca = ch.category_axis
ca.tick_labels.font.name, ca.tick_labels.font.size = TNR, Pt(12)
box(s, 9.3, 1.95, 4.2, 5.35, [[("Key results", True, NAVY, 18)],
    [("Every learned model beats persistence and the historical average.", False, INK, 15)],
    [("Proposed model: 4.77 / 5.33 / 6.15 mph; lowest at 30 and 60 min, GRU lowest at 15 min.", False, INK, 15)],
    [("R² rises from 0.55 / 0.46 / 0.30 (persistence) to 0.69 / 0.63 / 0.56.", False, INK, 15)],
    [("144,205–144,217 test targets per horizon, identical for every model.", False, INK, 15)],
    [("Data: NYC DOT speeds [11], 1 Jan – 20 Oct 2026.", False, MUTED, 13)]],
    TNR, 15, bg=TINT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, margin=0.18, after=9, name="Forecast results")
for p in list(s.shapes)[-1].text_frame.paragraphs[1:5]:
    bullet(p)

# ---------------------------------------------------------------- 16. outcome: advisory and simulation (Times New Roman)
s = S[15]
set_title(s, "8. OUTCOME (CONTD.)")
drop(body_ph(s))
cd = CategoryChartData()
cd.categories = ["PENDING_HUMAN_REVIEW", "REJECT_CONSTRAINT", "DEFER_UNCERTAINTY", "DEFER_DATA", "DEFER_EVIDENCE"]
cd.add_series("Runs", (7, 5, 5, 1, 1))
gfc = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.4), Inches(1.85), Inches(6.4), Inches(4.0), cd)
gfc.name = "Advisory outcomes"
ch = gfc.chart
ch.has_title = True
ch.chart_title.text_frame.text = "Advisory decisions in 19 workflow runs (REPLAY cases)"
for p in ch.chart_title.text_frame.paragraphs:
    for rr in p.runs:
        rr.font.name, rr.font.size, rr.font.bold, rr.font.color.rgb = TNR, Pt(15), True, NAVY
ch.has_legend = False
ch.plots[0].gap_width = 55
ch.series[0].format.fill.solid()
ch.series[0].format.fill.fore_color.rgb = NAVY
ch.plots[0].has_data_labels = True
ch.plots[0].data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
ch.plots[0].data_labels.font.name, ch.plots[0].data_labels.font.size = TNR, Pt(12)
ch.category_axis.reverse_order = True
ch.category_axis.tick_labels.font.name, ch.category_axis.tick_labels.font.size = TNR, Pt(11)
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
ch.value_axis.minimum_scale, ch.value_axis.maximum_scale = 0, 8
box(s, 0.5, 6.0, 6.3, 1.3, [[("12 of 12 LLM responses were schema-valid. Without retrieval the model cited non-existent "
                              "evidence in 3 of 3 cases (all rejected); with retrieval in 0 of 9.", False, INK, 14)]],
    TNR, 14, margin=0.04, after=0)
box(s, 7.2, 1.9, 6.3, 0.4, [[("SUMO testbed outcome (simulation only)", True, NAVY, 16)]], TNR, 16, margin=0.02, after=0)
sim = [("Protocol", "Unfinished*", "Result"),
       ("First comparison, 20 Oct (45 runs)", "—", "Withdrawn"),
       ("2014 count, generated signal timing", "17.7 %", "Fails test"),
       ("2014 count, Webster re-timed signals", "4.3 %", "Fails test"),
       ("2025 counts, Webster, no turn-lane limits", "10.1 %", "Fails test")]
gt = s.shapes.add_table(len(sim), 3, Inches(7.2), Inches(2.35), Inches(6.3), Inches(2.45))
gt.name = "Simulation protocols"
tbl = gt.table
for ci, wv in enumerate((3.6, 1.3, 1.4)):
    tbl.columns[ci].width = Inches(wv)
for ri, row in enumerate(sim):
    for ci, val in enumerate(row):
        cell = tbl.cell(ri, ci)
        colr = WHITE if ri == 0 else (STOP if ci == 2 else INK)
        fill(cell.text_frame, [[(val, ri == 0 or ci == 2, colr, 14)]], TNR, 14,
             align=PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER, after=0)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY if ri == 0 else (TINT if ri % 2 else WHITE)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
box(s, 7.2, 4.9, 6.3, 2.45, [
    [("* Vehicles not finishing with no side-street traffic; the preregistered test allows at most 1 % and no stuck vehicles.", False, MUTED, 12)],
    [("The first comparison let SUMO re-route 1,120 of 2,189 main-road vehicles off West Street, so it did not test the corridor.", False, INK, 13)],
    [("With real 2025 counts (2,510 NB / 2,444 SB veh/h) the modelled link runs at 5.8\u00a0mph; the real street runs at 10.95\u00a0mph in the PM peak.", False, INK, 13)],
    [("The test was not relaxed: the comparison is reported as not run, and 10.95\u00a0mph is now the calibration target.", True, INK, 13)]],
    TNR, 13, margin=0.04, after=5)

# ---------------------------------------------------------------- 17-20. outcome: the working dashboard (screenshots)
MODE_COLOUR = {"REPLAY": RGBColor(0xC2, 0x5E, 0x00), "SIMULATION": RGBColor(0x6A, 0x3F, 0xA0), "LIVE": OK}


def shot(slide, x, y, w, name, page, mode):
    """One dashboard screenshot with its page name and the mode label the page itself shows."""
    path = DASH / f"{name}.png"
    iw, ih = Image.open(path).size
    h = w * ih / iw
    label = [(page, True, NAVY, 14)]
    label += [("   Mode shown: ", False, MUTED, 12), (mode, True, MODE_COLOUR[mode], 12)] if mode else \
             [("   (status page, no mode label)", False, MUTED, 12)]
    box(slide, x, y, w, 0.36, [label], ARIAL, 14, margin=0.02, after=0, anchor=MSO_ANCHOR.BOTTOM)
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y + 0.42), Inches(w), Inches(h))
    pic.line.color.rgb = RGBColor(0xC9, 0xD3, 0xE0)
    pic.line.width = Pt(1)
    pic.name = f"Dashboard: {page}"
    return y + 0.42 + h


DASH_NOTE = ("Screenshots of the project's Streamlit dashboard (src/smartcity/dashboard/app.py) captured on 21 Oct 2026; every "
             "number on them is read from committed result files. Live NYC feeds were not reachable from the capture "
             "machine, so no LIVE view is shown.")
pairs = [
    (("overview", "Overview & status", None), ("data_audit", "Data audit & provenance", "REPLAY")),
    (("experiments", "Experiment results", "REPLAY"), ("uncertainty", "Uncertainty & reliability", "REPLAY")),
    (("explainability", "Explainability (proposed model)", "REPLAY"), ("agent", "Agent trace & advisory", "REPLAY")),
]
for k, (left, right) in enumerate(pairs):
    s = S[16 + k]
    set_title(s, f"8. OUTCOME: WORKING DASHBOARD ({k + 1}/4)")
    drop(body_ph(s))
    bottom = max(shot(s, 0.55, 1.75, 6.25, *left), shot(s, 7.2, 1.75, 6.25, *right))
    box(s, 0.55, bottom + 0.08, 12.9, 0.5, [[(DASH_NOTE, False, MUTED, 11)]], ARIAL, 11, margin=0.02, after=0)
s = S[19]
set_title(s, "8. OUTCOME: WORKING DASHBOARD (4/4)")
drop(body_ph(s))
bottom = shot(s, 0.55, 1.75, 6.25, "sumo", "SUMO comparisons", "SIMULATION")
box(s, 0.55, bottom + 0.08, 12.9, 0.5, [[(DASH_NOTE, False, MUTED, 11)]], ARIAL, 11, margin=0.02, after=0)
box(s, 7.2, 2.17, 6.25, 4.78, [
    [("What the dashboard shows, and what it does not", True, NAVY, 17)],
    [("The SUMO page states the first 45-run comparison is SUPERSEDED and the controller comparison NOT RUN, so it "
      "shows no simulated gain.", False, INK, 14)],
    [("Agent traces end in PENDING_HUMAN_REVIEW, DEFER or REJECT; approval is for simulation only and nothing is "
      "sent to real signals.", False, INK, 14)],
    [("Not captured yet: the Multi-horizon forecast and Traffic map pages need the trained model file and processed "
      "data held on the training laptop; they will be captured there for the final version.", False, INK, 14)],
    [("The Experiment results page shows the seed-42 runs; the three-seed results are on slide 21.", False, INK, 14)]],
    ARIAL, 14, bg=TINT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, margin=0.18, after=8, name="Dashboard notes")
for p in list(s.shapes)[-1].text_frame.paragraphs[1:]:
    bullet(p)

# ---------------------------------------------------------------- 21. results and outcomes (replaces the Gantt chart)
s = S[20]
set_title(s, "9. RESULTS & OUTCOMES")
drop(next(sh for sh in s.shapes if sh.name == "TextBox 2"))
box(s, 0.55, 1.75, 12.9, 0.4, [[("Held-out test period 6 Sep – 20 Oct 2026, 16 Manhattan links; advisory and retrieval results "
                                 "from the REPLAY workflow runs", False, MUTED, 14)]], ARIAL, 14, margin=0.02, after=0)
box(s, 0.55, 2.2, 6.6, 0.4, [[("Test MAE (mph): mean ± s.d. over seeds 42, 1 and 2", True, NAVY, 16)]], ARIAL, 16,
    margin=0.02, after=0)
ms = [("Model", "15 min", "30 min", "60 min"),
      ("Proposed GATv2–Transformer", "4.69 ± 0.06", "5.34 ± 0.03", "6.15 ± 0.02"),
      ("GRU", "4.67 ± 0.06", "5.37 ± 0.02", "6.18 ± 0.01"),
      ("Temporal Transformer", "4.72 ± 0.03", "5.38 ± 0.03", "6.23 ± 0.08"),
      ("Proposed, seed 42 only", "4.77", "5.33", "6.15"),
      ("Persistence", "5.14", "6.06", "7.29")]
gt = s.shapes.add_table(len(ms), 4, Inches(0.55), Inches(2.65), Inches(6.6), Inches(2.7))
gt.name = "Three-seed results"
tbl = gt.table
for ci, wv in enumerate((2.85, 1.25, 1.25, 1.25)):
    tbl.columns[ci].width = Inches(wv)
for ri, row in enumerate(ms):
    for ci, val in enumerate(row):
        cell = tbl.cell(ri, ci)
        fill(cell.text_frame, [[(val, ri == 0 or ri == 1, WHITE if ri == 0 else (MUTED if ri >= 4 else INK), 14)]], ARIAL, 14,
             align=PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER, after=0)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY if ri == 0 else (TINT if ri % 2 else WHITE)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
box(s, 0.55, 5.45, 6.6, 1.9, [
    [("Paired day-block bootstrap (44 test days): the proposed model is lower than the temporal Transformer at every horizon "
      "(0.035 / 0.037 / 0.080 mph) and than the GRU at 30 and 60 min (0.032 / 0.031); the GRU is lower at 15 min (0.021). "
      "All intervals exclude zero, but with three seeds the advantage is small, not decisive.", False, INK, 13)],
    [("Source: reports/experiments/multi_seed_summary.csv (nine GPU runs, 21 Oct 2026).", False, MUTED, 11)]],
    ARIAL, 13, margin=0.02, after=4)
stats = [("7–16 %", "lower MAE than persistence (seed 42 run)"),
         ("0.91 / 0.91 / 0.90", "coverage of the 90 % conformal intervals; 0.76–0.80 under congestion"),
         ("15–22 %", "lower MAE on forecasts the reliability gate keeps (≈26 % deferred)"),
         ("24 / 24", "local-LLM responses schema-valid over two workflow passes (qwen2.5 7B)"),
         ("3 of 3 → 0 of 9", "advisories citing non-existent evidence, without vs with retrieval"),
         ("19", "workflow runs per pass: 7 pending human review, 5 rejected by safety checks, 7 deferred")]
for k, (v, lab) in enumerate(stats):
    cx, cy = 7.5 + (k % 2) * 3.0, 2.2 + (k // 2) * 1.62
    box(s, cx, cy, 2.85, 1.47, [[(v, True, NAVY, 20)], [(lab, False, INK, 12)]], ARIAL, 12, align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE, bg=TINT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, margin=0.1, after=3, name=f"Result {k + 1}")
box(s, 0.55, 7.05, 12.9, 0.5, [
    [("Also measured: ", True, NAVY, 12),
     ("removing the availability-aware gate raises MAE by 0.067 mph (95 % CI 0.048–0.086); removing operational weather features "
      "lowers it by 0.046 mph (a negative result). No simulated controller gain is claimed: the SUMO testbed fails its own "
      "baseline test (5.8 vs 10.95 mph).", False, INK, 12)]],
    ARIAL, 12, margin=0.02, after=0)

# ---------------------------------------------------------------- 22. results and outcomes: status, deliverables, next steps
s = S[21]
set_title(s, "9. RESULTS & OUTCOMES (CONTD.)")
drop(next(sh for sh in s.shapes if sh.name == "TextBox 2"))
cols = [
    ("Implemented and verified", OK, [
        "Real-data pipeline on NYC DOT speeds, 1 Jan – 20 Oct 2026, with provenance hashes",
        "Seven forecasting models on identical targets; three-seed study of the deep models; ablations",
        "Conformal intervals, reliability gate and grouped SHAP on the trained model",
        "FAISS retrieval over 15 approved documents; local LLM with schema validation",
        "LangGraph workflow with 13 deterministic safety checks",
        "FastAPI, PostGIS jobs, Streamlit, MLflow, Docker Compose"]),
    ("Partial or not run", WARN, [
        "SUMO controller comparison NOT RUN; the first 45-run comparison is superseded",
        "No real advisory has reached the simulation gate (the LLM chose monitor-only in both passes)",
        "Only three seeds; the proposed model is not bit-reproducible on GPU at a fixed seed",
        "Road graph is sparse: 26 nodes, 16 edges",
        "Intervals under-cover congested periods"]),
    ("Outcomes and next steps", NAVY, [
        "IEEE conference paper (LaTeX and Word), every claim traced in the claims ledger",
        "GitHub repository with tests, runbooks and result files",
        "Next: calibrate West St signal timing to 10.95 mph or obtain NYC DOT timing plans, then run the comparison",
        "Next: more seeds without the compute budget",
        "Next: paper submission"]),
]
for k, (head, colr, items) in enumerate(cols):
    cx = 0.55 + k * 4.37
    box(s, cx, 1.85, 4.1, 0.5, [[(head, True, WHITE, 17)]], ARIAL, 17, anchor=MSO_ANCHOR.MIDDLE, bg=colr,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, margin=0.15, after=0, name=f"{head} header")
    box(s, cx, 2.45, 4.1, 4.9, [[(t, False, INK, 14)] for t in items], ARIAL, 14, bg=TINT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, margin=0.15, after=7, bullets=True, name=head)

# ---------------------------------------------------------------- 18. references (IEEE)
s = S[22]
set_title(s, "REFERENCES")
box(s, 0.6, 1.95, 12.8, 5.35, [[(REF[i], False, INK, 14)] for i in range(1, 13)], TNR, 14, margin=0.04, after=5)

for i, slide in enumerate(S, start=1):
    for fld in slide._element.iter(qn("a:fld")):
        if fld.get("type") == "slidenum":
            fld.find(qn("a:t")).text = str(i)

prs.save(OUT)
print("saved", OUT)
