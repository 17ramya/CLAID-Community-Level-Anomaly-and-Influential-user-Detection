# CLAID — Community-Level Anomaly and Influential-user Detection

Implementation of the framework described in the project report
**“CLAID: A Unified Social Network Analysis Framework for Community-Level Anomaly
and Influencer Detection”** (Ramya S, Rupesh A, Akilan K — Department of Computer
Technology, Anna University MIT Campus, May 2024).

CLAID joins three analyses that are usually run separately:

| Module | Algorithm | Report section | Code |
| --- | --- | --- | --- |
| Community detection | Louvain modularity | §4.5 (fig. 7, pseudocode §4.5.1) | `src/claid/community.py` |
| Anomaly detection | Isolation Forest | §4.6 (fig. 8, pseudocode §4.6.1) | `src/claid/anomaly.py` |
| Influential users | Betweenness centrality | §4.7 (fig. 9, pseudocode §4.7.1) | `src/claid/influence.py` |
| Framework view | source node + interacting communities | §5.2.4 (fig. 13) | `src/claid/pipeline.py` |
| Evaluation | precision · recall · F1 | §5.2.5 (figs. 14–16) | `src/claid/evaluate.py` |

The original work shipped as a single Jupyter notebook. In this repository the
notebook is **converted to Python**, the three modules are **implemented as a
reusable package**, and the whole framework is **served as a Flask website**
(the web framework listed in §4.4.6 of the report).

```
CLAID_...ipynb ──convert──▶ notebook_to_py/*.py        (runnable notebook files)
                            src/claid/*.py             (the framework, doc §4.5–4.7)
                            app.py + webapp/           (Flask website, doc §4.4.6)
```

---

## Quick start

```bash
python -m pip install -r requirements.txt

# 1. the website
python app.py                     # http://127.0.0.1:5000

# 2. the framework from the command line
set PYTHONPATH=src                # Windows:  set PYTHONPATH=src
python -m claid.cli --source bestof

# 3. the converted notebook
python notebook_to_py/CLAID_notebook.py

# 4. verify everything
python tools/smoke_test.py
```

The dataset zip is extracted to `data/` automatically on first use
(`data/Dataset(1).csv`, the 11-column layout documented in report §4.3).

### The website

| Page | What it shows |
| --- | --- |
| `/` | dataset/graph summary, framework parameters, run history |
| `POST /analyze` | runs the pipeline, redirects to the results page |
| `/results/<run_id>` | communities, anomalies, influential users, metrics + figures |
| `/about` | module → report-section map, tools, dataset and runtime notes |
| `/runs/<run_id>/<figure>.png` | the figures generated for a run |
| `/download/<run_id>/<table>.csv` | `communities`, `anomalies`, `anomalous_communities`, `influencers`, `metrics`, `focus` |
| `/api/claid?source=bestof&contamination=0.05` | the full result as JSON |
| `/api/runs?limit=10` | stored runs as JSON |

The parameters exposed by the form and the API are the ones the report defines:
community method and Louvain resolution (§4.5), node and community contamination
for the Isolation Forest (§4.6), how many influential users to keep per community
(§4.7), and the source node used by the framework view (§5.2.4).

Every run is stored under `var/runs/<run_id>/` as `result.json` plus six figures:

| Figure | Report |
| --- | --- |
| `communities.png` | §5.2.1 clusters formed with Louvain modularity (fig. 10) |
| `anomalies.png` | §5.2.2 anomalous nodes isolated by the Isolation Forest (fig. 11) |
| `influencers.png` | §5.2.3 influential nodes from betweenness centrality (fig. 12) |
| `focus.png` | §5.2.4 the source node with its interacting communities |
| `metrics.png` | §5.2.5 precision / recall / F1 per method (figs. 14–16) |
| `distributions.png` | degree distribution and community-size distribution |


---

## Converting and executing the notebook

`tools/convert_notebook.py` reads the `.ipynb` and writes the Python files below
into `notebook_to_py/`:

| File | Content |
| --- | --- |
| `CLAID_notebook_raw.py` | the notebook verbatim — only `%magics`, `!shell` escapes and bare `pip install` lines become comments so the file parses |
| `CLAID_notebook.py` | the same code with the runtime fixes applied — **this file executes** |
| `section_1_intro.py` … `section_7_calculate_centrality_measures.py` | one file per markdown section of the notebook |
| `conversion_report.txt` | cell map, fixes applied per cell, `py_compile` results |
| `output/fig_01.png …` | the figures produced when the script runs |

```bash
python tools/convert_notebook.py            # regenerate everything
python notebook_to_py/CLAID_notebook.py     # 12 figures, ~1 minute
```

The notebook is not runnable as-is. The converter applies these documented
changes (all listed in `conversion_report.txt`, so they can be audited against
the original work):

| Fix | Why |
| --- | --- |
| `%matplotlib inline`, `!pip install …`, bare `pip install Flask` → comments | IPython magics and shell escapes are not Python |
| `plt.show()` → `claid_show()` | saves every figure to `notebook_to_py/output/` in a headless run |
| `colors[counter]` → `colors[counter % len(colors)]` | the counter counts nodes, not colours → `IndexError` after a few nodes |
| `for community, mod_value in …` → `for comm_set, mod_value in …` | the loop variable shadowed the imported `networkx.community` module, so the later `community.greedy_modularity_communities(G)` call crashed |
| `"/content/Dataset.csv"` → the repository dataset | hard-coded Google Colab path |
| `if __name__ == "__main__"` → `… and RUN_SCRAPER` | the `example.com` word-graph demo needs internet access and is unrelated to CLAID |
| `import igraph as ig` wrapped in `try/except` | optional dependency (report §4.4.1); only the notebook's first cell used it |

Two properties of the original notebook are worth knowing before reading its
output: the `lst_b` community generator is consumed in an earlier cell, so the
max-modularity cell prints *“No community found with maximum modularity.”*, and
its final F1 table compares a ground-truth list with itself (1.000 for
“Community Detection” and “Betweenness Centrality”). The package in `src/claid/`
computes those numbers against the reference methods instead — see
[Evaluation metrics](#evaluation-metrics-doc-525).

---

## Project structure

```
CLAID/
├── CLAID_Community_Level_Anomaly_and_Influential_user_Detection.ipynb   notebook
├── Dataset-20250808T064225Z-1-001.zip       Dataset.csv + Dataset(1).csv (§4.3)
├── cip main_merged (2).pdf                  the project report ("the doc")
├── app.py                                   Flask application (§4.4.6)
├── requirements.txt
├── tools/
│   ├── convert_notebook.py                  .ipynb  ->  .py
│   └── smoke_test.py                        end-to-end check (24 assertions)
├── notebook_to_py/                          generated Python + figures
├── src/claid/
│   ├── config.py        paths and algorithm defaults (§4.5-§4.7)
│   ├── data.py          dataset loading, cleaning, graph, node features
│   ├── community.py     module 1 - Louvain + 3 comparison methods
│   ├── anomaly.py       module 2 - Isolation Forest + degree rule (fig. 8)
│   ├── influence.py     module 3 - betweenness centrality per community
│   ├── evaluate.py      precision / recall / F1, ARI, NMI
│   ├── plots.py         the six figures
│   ├── pipeline.py      runs the modules, saves var/runs/<run_id>/
│   └── cli.py           python -m claid.cli
├── webapp/
│   ├── templates/       base - index - results - about - error
│   └── static/css/style.css
├── data/                extracted CSVs (created on first use, git-ignored)
└── var/runs/<run_id>/   result.json + figures (created per run, git-ignored)
```

---

## How the framework works

### Module 1 — community detection (doc §4.5)

Louvain modularity (`python-louvain`'s `best_partition`, exactly the algorithm the
report selects) partitions the interaction graph and the resulting modularity is
reported. Report figure 14 compares it with the other methods the notebook used,
so all four run on every analysis:

| Method | Implementation |
| --- | --- |
| Louvain Modularity | `community_louvain.best_partition` (§4.5) |
| Greedy Modularity | `networkx.algorithms.community.greedy_modularity_communities` |
| Label Propagation | `networkx.algorithms.community.label_propagation_communities` |
| Edge Betweenness | `girvan_newman` (§4.5.1), capped — see the runtime notes |

### Module 2 — anomaly detection (doc §4.6)

An **Isolation Forest** (`sklearn.ensemble.IsolationForest`) is fitted twice, as
the report describes:

* **nodes** — 16 features per node: `posts`, `followers_mean/max`,
  `likes_mean/sum`, `comments_mean/sum`, `sentiment_mean`, `properties_mean/std`
  (from the 86-value `PROPERTIES` vector), `degree`, `weighted_degree`,
  `degree_centrality`, `clustering`, `betweenness`, `pagerank`.
  `anomaly_score` is the normalised average path length of §4.6.
* **communities** — the same features averaged per community, so whole
  communities are scored and the anomalous ones are listed.

The reference rule of figure 8 (`degree centrality > mean + 2σ`) is computed at
the same time and used to score the forest.

### Module 3 — influential users (doc §4.7)

Following §4.7 the algorithm starts from the **non-anomalous** communities
(anomalous ones are listed separately as excluded) and computes betweenness
centrality *inside each community subgraph*, i.e. the breadth-first dependency
accumulation of pseudocode §4.7.1. The highest scoring node is that community's
influential user; closeness and degree centrality provide the comparison
rankings of figure 16.

### Evaluation metrics (doc §5.2.5)

`src/claid/evaluate.py` provides weighted precision/recall/F1, ARI, NMI, and a
top-k overlap score. The results table has one row per method per module.

> **These scores are reference-based.** The shipped dataset has no ground-truth
> labels — the original notebook worked around this with a hand-written
> `ground_truth_communities` list — so each row states the *reference method* it
> is scored against: Louvain's partition (§4.5) for community detection, the
> figure-8 degree rule for anomaly detection, and the top-k degree centrality
> ranking for influential users. To score against real labels, pass them to
> `evaluate.label_metrics(y_true, y_pred)`; nothing else in the framework
> changes. Modularity and ARI/NMI are label-free and are shown next to them.

---

## The shipped dataset (doc §4.3)

| Property | Value |
| --- | --- |
| File | `data/Dataset(1).csv` (from `Dataset-20250808T064225Z-1-001.zip`) |
| Rows | 5,029 posts |
| Columns | `SOURCE_SUBREDDIT`, `TARGET_SUBREDDIT`, `POST_ID`, `TIMESTAMP`, `ADDRESS`, `FOLLOWERS`, `PHONE NO`, `LIKES`, `COMMENTS`, `LINK_SENTIMENT`, `PROPERTIES` (86 floats) |
| Graph | 2,599 nodes, 3,779 edges, 242 components (largest 2,030 nodes), density 0.00112 |

Rows whose endpoint is the literal `NaN` (present in the 6-column
`Dataset.csv`) and self loops are dropped; the counts are reported on the
dashboard and in every `result.json`. The alternative file is selectable with
`--dataset Dataset.csv` or the `dataset` parameter of the pipeline.

A default run (`--source bestof`, contamination 5 %) reports:

```
271 Louvain communities        modularity 0.6762
130 anomalous nodes            14 anomalous communities (Isolation Forest)
42  nodes by the degree rule   mean + 2 sigma (doc fig. 8)
257 community leaders          bestof: degree 208, 23 interacting communities
```

---

## Verification

```bash
python tools/smoke_test.py
```

drives the framework and every web route and prints one line per check — 24
assertions covering the pipeline (run id, graph, communities, modularity range,
assignment coverage, anomalies, influencers, focus node, metrics table, figures)
and the site (`/`, `POST /analyze`, `/results/<run_id>`, figure serving, CSV
download, `/api/claid`, `/api/runs`, `/about`, unknown-run 404).

`python tools/convert_notebook.py` syntax-checks all generated `.py` files with
`py_compile` and prints the result in `conversion_report.txt`.

---

## Runtime notes and limits

* **Betweenness centrality** is exact below 800 nodes; above that the graph-wide
  ranking uses a 200-source estimate because Brandes' algorithm is O(n·m). The
  §4.7 per-community scores are always exact.
* **Girvan-Newman** is O(n·m²), so the §4.5 comparison runs it on a 90-node
  subgraph and says so in the table note (the other 2,509 nodes are singletons in
  that partition, which is why its F1 is low).
* **Figures** show the largest component trimmed to the 400 best-connected nodes.
* **`igraph`** (§4.4.1) is optional — only the original notebook imported it.
* **Gradle** (§4.4.7) is not needed by this implementation; `requirements.txt`
  and `python app.py` cover install and run.
* `python app.py` starts Flask's development server. For a real deployment put
  it behind a WSGI server (`waitress-serve --port=8000 app:app` on Windows,
  `gunicorn app:app` elsewhere) and a reverse proxy.

---

## Credits

The framework, the dataset and the report are the work of **Ramya S, Rupesh A and
Akilan K** (Department of Computer Technology, Anna University MIT Campus,
May 2024). This repository adds the Python conversion, the modular
implementation of chapters 4–5, and the Flask web application.


