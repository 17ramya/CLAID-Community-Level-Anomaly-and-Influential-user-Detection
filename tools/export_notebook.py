#!/usr/bin/env python
"""Export the CLAID Jupyter notebook as runnable Python under ``exploratory/``.

Usage
-----
    python tools/export_notebook.py
    python tools/export_notebook.py --notebook <file.ipynb> --outdir exploratory

Outputs (in ``exploratory/``)
-----------------------------
``claid_workflow.py``           the notebook as one executable workflow, with the
                               documented runtime fixes applied (FILE_FIXES).
``claid_workflow_verbatim.py``  the notebook verbatim; only ``%magics``, ``!shell``
                               escapes and bare ``pip install`` lines become
                               comments so the file stays valid Python.
``parts/part_N_<topic>.py``     one file per markdown section of the notebook,
                               named after the algorithm the section covers.
``figures/``                    figures written by ``claid_show()`` at runtime.
``README.md``                   generated: cell map, the fixes that fired, file
                               list and ``py_compile`` results.
"""
from __future__ import annotations

import argparse
import json
import os
import py_compile
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_NB = os.path.join(
    ROOT, "CLAID_Community_Level_Anomaly_and_Influential_user_Detection.ipynb"
)
DEFAULT_OUT = os.path.join(ROOT, "exploratory")

#: Part files are named after the algorithm they cover rather than after the
#: notebook's own wording, so the file list reads like the study's outline.
SECTION_SLUG_OVERRIDES = {
    "intro": "imports_and_graph_basics",
    "edge_betweenness_girvan_newman": "edge_betweenness",
    "fast_community_unfolding_louvian": "louvain_communities",
    "final": "combined_analysis",
    "calculate_centrality_measures": "centrality_measures",
}

# --------------------------------------------------------------------------- #
# Line-level rewrites that make the notebook valid, non-interactive Python.
# (id, description, compiled regex, replacement)
# --------------------------------------------------------------------------- #
LINE_FIXES = [
    (
        "magic-matplotlib",
        "%matplotlib inline -> 'Agg' backend is chosen by the preamble",
        re.compile(r"^[ \t]*%matplotlib\s+inline[ \t]*$", re.M),
        "# %matplotlib inline  -> handled by the 'Agg' backend in the preamble",
    ),
    (
        "magic-generic",
        "other %magics -> comments",
        re.compile(r"^([ \t]*)%(\w+)(.*)$", re.M),
        r"\1# %\2\3",
    ),
    (
        "shell-pip",
        "!pip install X -> comment + install hint",
        re.compile(r"^([ \t]*)!\s*pip\s+install\s+(.+)$", re.M),
        r"\1# pip install \2   (run once: python -m pip install \2)",
    ),
    (
        "shell-generic",
        "other !shell commands -> comments",
        re.compile(r"^([ \t]*)!\s*(.+)$", re.M),
        r"\1# \2",
    ),
    (
        "bare-pip",
        "bare 'pip install X' (a SyntaxError in Python) -> comment",
        re.compile(r"^([ \t]*)pip\s+install\s+(.+)$", re.M),
        r"\1# pip install \2   (run once: python -m pip install \2)",
    ),
]

# --------------------------------------------------------------------------- #
# Fixes applied only to the executable conversion; all are reported in
# conversion_report.txt so they can be audited against the original notebook.
# (id, description, compiled regex, replacement)
# --------------------------------------------------------------------------- #
FILE_FIXES = [
    (
        "colour-lookup-guard",
        "colors[counter] counted nodes, not colours -> modulo guard",
        re.compile(r"colors\[counter\]"),
        "colors[counter % len(colors)]",
    ),
    (
        "module-shadowing",
        "loop variable 'community' shadowed the networkx community module",
        re.compile(r"for community, mod_value in zip\("),
        "for comm_set, mod_value in zip(",
    ),
    (
        "module-shadowing-2",
        "the same loop assigned max_community = community (shadowed)",
        re.compile(r"max_community = community\b"),
        "max_community = comm_set",
    ),
    (
        "colab-path",
        "hard-coded Colab path /content/Dataset.csv -> repo dataset",
        re.compile(r"dataset_path\s*=\s*[\"']/content/Dataset\.csv[\"']"),
        "dataset_path = str(DATASET_PATH)",
    ),
    (
        "scraper-guard",
        "example.com word-graph demo is off by default (needs internet)",
        re.compile(r'if __name__ == "__main__":'),
        'if __name__ == "__main__" and RUN_SCRAPER:',
    ),
    (
        "show-hook",
        "plt.show() -> claid_show() so figures land in exploratory/figures",
        re.compile(r"\bplt\.show\(\)"),
        "claid_show()",
    ),
    (
        "igraph-optional",
        "import igraph made optional (cell 0 only used it to install itself)",
        re.compile(r"^import igraph as ig[ \t]*$", re.M),
        "try:\n"
        "    import igraph as ig  # noqa: F401  (optional: python -m pip install igraph)\n"
        "except ImportError:  # pragma: no cover - optional dependency\n"
        "    ig = None",
    ),
]

RUNNABLE_PREAMBLE = '''"""The CLAID study pipeline, exported from the original Jupyter notebook.

Generated by tools/export_notebook.py - run it from the repository root:

    python exploratory/claid_workflow.py

The runtime fixes it applies are documented in exploratory/README.md. Figures
are written to exploratory/figures/ instead of opening a window.
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")  # headless: every plt.show() is captured by claid_show()
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUT_DIR = os.path.join(HERE, "figures")
DATASET_PATH = os.path.join(ROOT, "data", "Dataset.csv")  # extracted from the dataset zip
RUN_SCRAPER = False  # the example.com word-graph demo needs internet access

os.makedirs(OUTPUT_DIR, exist_ok=True)
_FIG_N = [0]


def claid_show():
    """Save the current figure (the notebook called plt.show() here)."""
    _FIG_N[0] += 1
    fig = plt.gcf()
    if fig.get_axes():
        path = os.path.join(OUTPUT_DIR, "fig_%02d.png" % _FIG_N[0])
        fig.savefig(path, dpi=110, bbox_inches="tight")
        print("  [saved] %s" % os.path.relpath(path, ROOT))
    plt.close("all")


sys.path.insert(0, os.path.join(ROOT, "src"))

import community as community_louvain  # noqa: E402,F401  (python-louvain)
import networkx as nx  # noqa: E402,F401
import pandas as pd  # noqa: E402,F401
from networkx.algorithms import community  # noqa: E402,F401

assert os.path.exists(DATASET_PATH), "dataset not found: %s" % DATASET_PATH
'''

RAW_PREAMBLE = '''"""The CLAID notebook, transcribed verbatim as a Python script.

IPython magics (``%...``), shell escapes (``!...``) and bare ``pip install`` lines
are comments so the file parses as Python - nothing else was changed.  Some cells
need optional packages (igraph) or Colab paths, so this file records the original
study code; run claid_workflow.py to actually execute it.
"""
'''

SECTION_PREAMBLE = (
    '# Part %d: %s\n'
    '# One section of the CLAID study pipeline - claid_workflow.py runs them all.\n'
)


def cell_source(cell):
    src = cell.get("source", "")
    return src if isinstance(src, str) else "".join(src)


def apply_fixes(text, fixes, fired):
    for fid, desc, pattern, repl in fixes:
        text, n = pattern.subn(repl, text)
        if n:
            fired.append((fid, desc, n))
    return text


def slugify(title):
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", title.strip().lower()).strip("_")
    return slug[:48] or "section"


def split_sections(cells):
    """Group cell indices by markdown headings (a section starts at a '# ' cell)."""
    sections = []
    current = (-1, "intro", [])
    for idx, cell in enumerate(cells):
        if cell["cell_type"] == "markdown":
            text = cell_source(cell).strip()
            first = next((ln.strip() for ln in text.split("\n") if ln.strip()), "")
            if first.startswith("#"):
                if current[2]:
                    sections.append(current)
                current = (idx, first.lstrip("# ").strip().replace("**", ""), [])
                continue
        current[2].append(idx)
    if current[2]:
        sections.append(current)
    return sections


def main():
    ap = argparse.ArgumentParser(description="Convert the CLAID notebook to .py files")
    ap.add_argument("--notebook", default=DEFAULT_NB)
    ap.add_argument("--outdir", default=DEFAULT_OUT)
    args = ap.parse_args()

    with open(args.notebook, encoding="utf-8") as fh:
        nb = json.load(fh)
    cells = nb["cells"]
    os.makedirs(os.path.join(args.outdir, "figures"), exist_ok=True)
    os.makedirs(os.path.join(args.outdir, "parts"), exist_ok=True)

    fired, line_fired = [], []
    raw_cells, run_cells, table = [], [], []
    for idx, cell in enumerate(cells):
        src = cell_source(cell)
        if cell["cell_type"] == "markdown":
            raw_cells.append((idx, "md", src))
            run_cells.append((idx, "md", src))
            continue
        raw = apply_fixes(src, LINE_FIXES, line_fired)
        run = apply_fixes(raw, FILE_FIXES, fired)
        raw_cells.append((idx, "code", raw))
        run_cells.append((idx, "code", run))
        table.append((idx, len(src), len(run)))

    def dump(path, title, preamble, stream):
        out = [preamble, "# %s (%d cells)\n" % (title, len(cells))]
        for idx, kind, text in stream:
            out.append("\n# %% [cell %02d] %s" % (idx, kind))
            if kind == "md":
                for ln in text.split("\n"):
                    out.append("# " + ln if ln.strip() else "#")
            else:
                out.append(text)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out).rstrip() + "\n")
        return path

    written = [
        dump(
            os.path.join(args.outdir, "claid_workflow_verbatim.py"),
            "CLAID notebook, verbatim transcription",
            RAW_PREAMBLE,
            raw_cells,
        ),
        dump(
            os.path.join(args.outdir, "claid_workflow.py"),
            "CLAID study pipeline, executable export",
            RUNNABLE_PREAMBLE,
            run_cells,
        ),
    ]

    sections = split_sections(cells)
    for n, (start, title, idxs) in enumerate(sections, start=1):
        stream = [(i, raw_cells[i][1], run_cells[i][2]) for i in idxs]
        slug = SECTION_SLUG_OVERRIDES.get(slugify(title), slugify(title))
        name = os.path.join("parts", "part_%d_%s.py" % (n, slug))
        written.append(
            dump(os.path.join(args.outdir, name), "CLAID study - %s" % title,
                 SECTION_PREAMBLE % (n, title) + RUNNABLE_PREAMBLE, stream)
        )

    readme = [
        "# The exploratory study pipeline",
        "",
        "**Generated by `tools/export_notebook.py` - edit the notebook, not these",
        "files, and re-run the tool.**",
        "",
        "This folder keeps the CLAID study as plain Python so it can be read, diffed",
        "and executed without Jupyter. The reusable implementation of the report",
        "lives in `src/claid/` and is what the web application runs.",
        "",
        "| file | what it is |",
        "| --- | --- |",
        "| `claid_workflow.py` | the notebook as one executable workflow (**run this**) |",
        "| `claid_workflow_verbatim.py` | verbatim transcription, kept for reference |",
        "| `parts/part_*.py` | one file per notebook section, named after its algorithm |",
        "| `figures/` | PNGs written by `claid_show()` when the workflow runs |",
        "",
        "## Source",
        "",
        "* notebook: `%s`" % os.path.relpath(args.notebook, ROOT).replace(os.sep, "/"),
        "* cells: %d code / %d markdown" % (
            sum(1 for c in cells if c["cell_type"] == "code"),
            sum(1 for c in cells if c["cell_type"] == "markdown")),
        "* notebook sections: %d" % len(sections),
        "",
        "## Rewrites applied to both exports",
        "",
        "| id | what changed | replacements |",
        "| --- | --- | ---: |",
    ]
    for fid, desc, _, _ in LINE_FIXES:
        n = sum(c for f, _, c in line_fired if f == fid)
        readme.append("| `%s` | %s | %d |" % (fid, desc, n))

    readme += ["", "## Runtime fixes applied to `claid_workflow.py` only", "",
               "| id | what changed | replacements |", "| --- | --- | ---: |"]
    for fid, desc, n in fired:
        readme.append("| `%s` | %s | %d |" % (fid, desc, n))

    readme += ["", "<details><summary>Cell sizes (original &rarr; exported characters)"
               "</summary>", "", "| cell | original | exported |", "| ---: | ---: | ---: |"]
    for idx, a, b in table:
        readme.append("| %02d | %d | %d |" % (idx, a, b))
    readme += ["", "</details>", ""]

    checks = []
    for path in written:
        label = os.path.relpath(path, ROOT).replace(os.sep, "/")
        try:
            py_compile.compile(path, doraise=True)
            checks.append((True, label))
        except py_compile.PyCompileError as exc:
            checks.append((False, "%s: %s" % (label, exc)))

    readme += ["", "## Syntax check (`py_compile`)", ""]
    for ok, detail in checks:
        readme.append("* %s `%s`" % ("OK -" if ok else "**FAIL** -", detail))

    readme += ["", "## Generated files", ""]
    for path in written:
        readme.append("* `%s` - %d bytes" % (
            os.path.relpath(path, ROOT).replace(os.sep, "/"), os.path.getsize(path)))

    readme_path = os.path.join(args.outdir, "README.md")
    with open(readme_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(readme).rstrip() + "\n")

    print("exported %d Python files to %s"
          % (len(written), os.path.relpath(args.outdir, ROOT)))
    print("notes written to %s" % os.path.relpath(readme_path, ROOT))
    for ok, detail in checks:
        print("  %-4s %s" % ("OK" if ok else "FAIL", detail))
    return 0 if all(ok for ok, _ in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())


