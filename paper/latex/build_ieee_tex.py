"""Generate the LaTeX source of the IEEE conference paper from the shared text and result files.

    python paper/latex/build_ieee_tex.py      # writes paper/main.tex
    cd paper && pdflatex main && pdflatex main

The prose, figure list, captions and references come from paper/word/ieee_paper_text.py, the tables are computed
by paper/word/build_ieee_paper.py from the result files, and the figures are paper/word/figures/*.png, so the
LaTeX paper and the Word paper always say the same thing. The LaTeX version uses the IEEEtran conference class
(A4), with proper math for the equations and booktabs tables.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER = HERE.parent
WORD = PAPER / "word"
sys.path.insert(0, str(WORD))
import build_ieee_paper as W  # noqa: E402
import ieee_paper_text as T  # noqa: E402

# --------------------------------------------------------------------------------------------------------------
# inline markup -> LaTeX

SYMBOLS = {
    "†": r"\dag{}", "∈": r"$\in$", "Σ": r"$\sum$", "⊤": r"$\top$", "−": r"$-$", "≤": r"$\le$", "≥": r"$\ge$", "×": r"$\times$",
    "δ": r"$\delta$", "α": r"$\alpha$", "θ": r"$\theta$", "φ": r"$\varphi$", "Δ": r"$\Delta$", "ℒ": r"$\mathcal{L}$",
    "ŷ": r"$\hat{y}$", "⌈": r"$\lceil$", "⌉": r"$\rceil$", "∖": r"$\setminus$", "∪": r"$\cup$", "⊆": r"$\subseteq$",
    "±": r"$\pm$", "✓": r"\checkmark", "–": "--", "—": "---", "“": "``", "”": "''", "‘": "`", "’": "'",
    "…": r"\ldots{}", "≈": r"$\approx$", "∗": r"\textsuperscript{$\ast$}", "→": r"$\rightarrow$",
    "²": r"\textsuperscript{2}", "°": r"$^{\circ}$", "·": r"$\cdot$", "\u00a0": "~",
}
ESCAPES = {"&": r"\&", "%": r"\%", "#": r"\#", "$": r"\$", "~": r"\textasciitilde{}", "<": r"\textless{}",
           ">": r"\textgreater{}", "\\": r"\textbackslash{}"}


class Refs:
    def __init__(self) -> None:
        self.cites: list[str] = []
        self.tables: dict[str, int] = {}
        self.sections: dict[str, int] = {}

    def cite(self, keys: list[str]) -> str:
        for k in keys:
            if k not in T.REFERENCES:
                raise KeyError(f"citation key {k!r} has no entry in ieee_paper_text.REFERENCES")
            if k not in self.cites:
                self.cites.append(k)
        return r"\cite{" + ",".join(keys) + "}"


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


def plain(s: str) -> str:
    out = []
    for ch in s:
        if ch in SYMBOLS:
            out.append(SYMBOLS[ch])
        elif ch in ESCAPES:
            out.append(ESCAPES[ch])
        elif ord(ch) > 127 and not (ord(ch) < 0x180 and ch.isalpha()):
            raise ValueError(f"unmapped character {ch!r} (U+{ord(ch):04X}) in: {s[:60]}")
        else:
            out.append(ch)
    text = "".join(out)
    # a URL in a reference becomes \url{...}
    text = re.sub(r"(https?://[^\s]+?)(?=[.,;]?(\s|$))", lambda m: r"\url{" + m.group(1).replace(r"\_", "_") + "}",
                  text)
    return text


def tex(s: str, refs: Refs) -> str:
    """Convert the paper's inline markup (see ieee_paper_text.py) to LaTeX."""
    out = ""
    buf = ""
    bold = italic = mono = False
    i = 0

    def flush() -> None:
        nonlocal buf, out
        if buf:
            out += plain(buf)
            buf = ""

    while i < len(s):
        if s.startswith("**", i):
            flush()
            out += r"\textbf{" if not bold else "}"
            bold = not bold
            i += 2
        elif s[i] == "*":
            flush()
            out += r"\emph{" if not italic else "}"
            italic = not italic
            i += 1
        elif s[i] == "`":
            flush()
            out += r"\texttt{" if not mono else "}"
            mono = not mono
            i += 1
        elif s.startswith("_{", i) or s.startswith("^{", i):
            flush()
            j = _find_close(s, i + 1)
            inner = tex(s[i + 2:j], refs)
            out += (r"\textsubscript{" if s[i] == "_" else r"\textsuperscript{") + inner + "}"
            i = j + 1
        elif s.startswith("[@", i):
            flush()
            j = s.index("]", i)
            out += refs.cite([k.strip() for k in s[i + 2:j].split(",")])
            i = j + 1
        elif s.startswith("{T:", i) or s.startswith("{S:", i) or s.startswith("{F:", i):
            flush()
            j = s.index("}", i)
            kind, key = s[i + 1], s[i + 3:j]
            if kind == "T":
                out += r"Table~\ref{tab:" + key + "}"
            elif kind == "F":
                out += r"Fig.~\ref{fig:" + key + "}"
            else:
                out += r"\ref{sec:" + key + "}"
            i = j + 1
        else:
            buf += s[i]
            i += 1
    flush()
    if bold or italic or mono:
        raise ValueError(f"unclosed markup in: {s[:80]}")
    return out


# --------------------------------------------------------------------------------------------------------------
# equations: the Word text carries them as pseudo-math; the LaTeX paper sets them properly

EQUATIONS = {
    "*ŷ*_{t+h,v} = *f*_{θ}": r"\hat{y}_{t+h,v} = f_{\theta}\big(X_{t-L+1:t}, G\big), \qquad h \in \{3, 6, 12\}",
    "*α*_{t,v,g} = softmax": (r"\begin{aligned} \alpha_{t,v,g} &= \operatorname{softmax}_{g:\, m_{t,v,g}=1}"
                              r"\big(w^{\top}\tanh(U h_{t,v,g})\big), \\ z_{t,v} &= \sum_{g} \alpha_{t,v,g}\, h_{t,v,g} \end{aligned}"),
    "ℒ(*θ*) = (1/|*O*|)": (r"\mathcal{L}(\theta) = \frac{1}{|O|} \sum_{(t,v,h)\in O} "
                            r"\operatorname{Huber}_{\delta}\big(y_{t+h,v} - \hat{y}_{t+h,v}\big)"),
    "*q*_{h} = the ⌈": (r"q_{h} = \text{the } \lceil (n+1)(1-\alpha) \rceil\text{-th smallest of } "
                        r"|y_{i} - \hat{y}_{i}|, \qquad \alpha = 0.1"),
    "*φ*_{i} = Σ_{S⊆P∖{i}}": (r"\varphi_{i} = \sum_{S \subseteq P \setminus \{i\}} "
                              r"\frac{|S|!\,(|P|-|S|-1)!}{|P|!}\,\big(v(S \cup \{i\}) - v(S)\big)"),
    "MAE = (1/*N*) Σ_{i}": (r"\mathrm{MAE} = \frac{1}{N}\sum_{i} |y_{i} - \hat{y}_{i}|, \quad "
                            r"\mathrm{RMSE} = \Big(\frac{1}{N}\sum_{i} (y_{i} - \hat{y}_{i})^{2}\Big)^{1/2}"),
}


def equation(raw: str) -> str:
    for prefix, body in EQUATIONS.items():
        if raw.startswith(prefix):
            return body
    raise SystemExit(f"no LaTeX form for the equation starting {raw[:40]!r}; add it to EQUATIONS")


# --------------------------------------------------------------------------------------------------------------
# tables: reuse the data logic of the Word builder, render with booktabs

ALIGN = {"start": r">{\raggedright\arraybackslash}p", "center": r">{\centering\arraybackslash}p",
         "end": r">{\raggedleft\arraybackslash}p"}


def latex_table(title: str, widths, header, body, aligns, refs: Refs, size=14, notes: str | None = None) -> str:
    tid = latex_table.current_id
    total = float(sum(widths))
    cols = []
    for w, a in zip(widths, aligns):
        frac = w / total
        cols.append(ALIGN[a] + r"{\dimexpr " + f"{frac:.4f}" + r"\columnwidth-2\tabcolsep\relax}")
    dense = len(widths) >= 6 or any("\n" in c for row in body for c in row)
    lines = [r"\begin{table}[!t]", r"\caption{" + tex(title, refs) + "}", r"\label{tab:" + tid + "}",
             r"\centering" + (r"\scriptsize" if dense else r"\footnotesize"), r"\setlength{\tabcolsep}{3pt}",
             r"\renewcommand{\arraystretch}{1.08}",
             r"\begin{tabular}{" + "".join(cols) + "}", r"\toprule"]
    for hrow in header:
        cells, cmid, col = [], [], 1
        for h in hrow:
            if isinstance(h, tuple):
                text, span = h
                cells.append(r"\multicolumn{" + str(span) + "}{c}{" + tex(text, refs) + "}")
                cmid.append(f"\\cmidrule(lr){{{col}-{col + span - 1}}}")
                col += span
            else:
                cells.append(r"\textbf{" + tex(h, refs).replace("\n", r"\newline ") + "}" if h else "")
                col += 1
        lines.append(" & ".join(cells) + r" \\")
        if cmid:
            lines.append(" ".join(cmid))
    lines.append(r"\midrule")
    for row in body:
        lines.append(" & ".join(tex(c, refs).replace("\n", r"\newline ") for c in row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    if notes:
        lines += [r"\par\vspace{2pt}", r"\begin{minipage}{\columnwidth}\scriptsize " + tex(notes, refs)
                  + r"\end{minipage}"]
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n\n"


latex_table.current_id = ""
W.tbl = latex_table  # the Word builder's table functions now emit LaTeX


def table(tid: str, refs: Refs) -> str:
    latex_table.current_id = tid
    return W.TABLES[tid](refs)


# --------------------------------------------------------------------------------------------------------------


def author_block() -> str:
    blocks = []
    for a in T.AUTHORS:
        name = tex(a["name"], Refs())
        lines = []
        for style, text in a["lines"]:
            t = tex(text, Refs())
            lines.append(r"\textit{" + t + "}" if style == "i" else t)
        blocks.append(r"\IEEEauthorblockN{" + name + "}\n\\IEEEauthorblockA{" + " \\\\\n".join(lines) + "}")
    return "\n\\and\n".join(blocks)


PREAMBLE = r"""\documentclass[conference,a4paper]{IEEEtran}
% Generated by paper/latex/build_ieee_tex.py from paper/word/ieee_paper_text.py and the result files.
% Do not edit by hand: change the text module or the table/figure builders and regenerate.
\IEEEoverridecommandlockouts
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb,booktabs,array,graphicx,url}
\usepackage[hidelinks]{hyperref}
\graphicspath{{word/figures/}}
\renewcommand{\topfraction}{0.95}
\renewcommand{\bottomfraction}{0.6}
\renewcommand{\textfraction}{0.05}
\renewcommand{\floatpagefraction}{0.85}
\renewcommand{\dbltopfraction}{0.9}
\renewcommand{\dblfloatpagefraction}{0.8}
\setcounter{topnumber}{4}
\setcounter{totalnumber}{6}
\urlstyle{same}
\renewcommand{\IEEEkeywordsname}{Keywords}
\begin{document}
"""


# LaTeX-only width of a full-width figure as a fraction of \textwidth, overriding the width in the text
# module. The map is set narrower than in the Word layout so that the section heading after it fits on the
# same page instead of leaving a column gap.
FULL_WIDTH_FRACTION = {"area": 0.85}
TEXT_WIDTH_IN = 7.16  # IEEEtran conference, A4


def first_cite(seq, kind, fid):
    tag = "{" + kind + ":" + fid + "}"
    for i, b in enumerate(seq):
        if b[0] in ("p", "pn") and tag in b[1]:
            return (i, b[1].index(tag))
    raise SystemExit(f"{kind} never cited in the text: {fid}")


def hoist_full_figures(body):
    """Anchor each full-width figure right after the heading of the subsection that first cites it.

    In two-column LaTeX a figure* can only appear at the top of a page after its anchor, so an anchor
    placed after the citing paragraph (right for Word) pushes the figure a page further than needed,
    in the worst case among the references.
    """
    rest = [b for b in body if not (b[0] == "fig" and b[5])]
    for fig in [b for b in body if b[0] == "fig" and b[5]]:
        cite = first_cite(rest, "F", fig[1])
        pos = max(i for i, b in enumerate(rest[:cite[0]]) if b[0] in ("h1", "h2")) + 1
        while pos < len(rest) and rest[pos][0] == "fig" and rest[pos][5]:
            pos += 1
        rest.insert(pos, fig)
    return rest


def figure_numbers(body):
    """Figure numbers in order of first citation, independent of where the floats are anchored."""
    figs = [b[1] for b in body if b[0] == "fig"]
    order = sorted(figs, key=lambda fid: first_cite(body, "F", fid))
    return {fid: n for n, fid in enumerate(order, 1)}


def build(out: Path) -> None:
    refs = Refs()
    doc = [PREAMBLE]
    doc.append(r"\title{" + tex(T.TITLE, refs) + "}\n")
    doc.append(r"\author{" + author_block() + "}\n\\maketitle\n")
    doc.append(r"\begin{abstract}" + "\n" + tex(T.ABSTRACT, refs) + "\n" + r"\end{abstract}" + "\n")
    doc.append(r"\begin{IEEEkeywords}" + "\n" + tex(", ".join(T.KEYWORDS), refs) + "\n" + r"\end{IEEEkeywords}"
               + "\n\n")
    n_fig = n_tab = n_eq = 0
    body = hoist_full_figures(T.BODY)
    numbers = figure_numbers(body)
    for blk in body:
        kind = blk[0]
        if kind == "h1":
            doc.append(r"\section{" + tex(blk[1], refs) + "}\\label{sec:" + blk[2] + "}\n")
        elif kind == "h2":
            doc.append(r"\subsection{" + tex(blk[1], refs) + "}\n")
        elif kind == "p":
            doc.append(tex(blk[1], refs) + "\n\n")
        elif kind == "pn":
            doc.append(r"\noindent " + tex(blk[1], refs) + "\n\n")
        elif kind == "eq":
            n_eq += 1
            doc.append(r"\begin{equation}" + "\n" + equation(blk[1]) + "\n" + r"\end{equation}" + "\n")
        elif kind == "table":
            n_tab += 1
            doc.append(table(blk[1], refs))
        elif kind == "fig":
            _, fid, fname, width_in, cap, full = blk
            n_fig += 1
            if not (WORD / "figures" / fname).exists():
                raise SystemExit(f"figure file missing: {fname}")
            env = "figure*" if full else "figure"
            width = r"\columnwidth"
            if full:
                frac = FULL_WIDTH_FRACTION.get(fid, min(1.0, width_in / TEXT_WIDTH_IN))
                width = r"\textwidth" if frac >= 0.999 else f"{frac:.3f}\\textwidth"
            doc.append("\n".join([r"\setcounter{figure}{" + str(numbers[fid] - 1) + "}",
                                  r"\begin{" + env + "}[!t]", r"\centering",
                                  r"\includegraphics[width=" + width + "]{" + fname + "}",
                                  r"\caption{" + tex(cap, refs) + "}", r"\label{fig:" + fid + "}",
                                  r"\end{" + env + "}"]) + "\n\n")
        else:
            raise ValueError(kind)
    unused = sorted(set(T.REFERENCES) - set(refs.cites))
    if unused:
        raise SystemExit(f"references never cited: {unused}")
    doc.append(r"\begin{thebibliography}{" + str(len(refs.cites)) + "}\n")
    for key in refs.cites:
        doc.append(r"\bibitem{" + key + "} " + tex(T.REFERENCES[key], refs) + "\n")
    doc.append(r"\end{thebibliography}" + "\n" + r"\end{document}" + "\n")
    out.write_text("".join(doc), encoding="utf-8")
    print(f"wrote {out} ({len(refs.cites)} references, {n_tab} tables, {n_fig} figures, {n_eq} equations)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=PAPER / "main.tex")
    build(ap.parse_args().out)


if __name__ == "__main__":
    main()
