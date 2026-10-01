# CLAID — Community-Level Anomaly and Influential-user Detection

CLAID is a social-network analysis framework that answers three questions in one
pass over an interaction graph:

1. **Which communities exist?** — Louvain modularity (report §4.5), benchmarked
   against greedy modularity, label propagation and Girvan–Newman.
2. **Which nodes and communities are anomalous?** — an Isolation Forest over node
   and community features (§4.6), compared with the degree-centrality rule of
   figure 8.
3. **Who influences each healthy community?** — betweenness centrality inside every
   non-anomalous community (§4.7), compared with closeness and degree centrality.

Everything is scored with precision, recall and F<sub>1</sub> (§5.2.5) and exported as
JSON, CSV and figures. The framework is served through a Flask web application
(§4.4.6) whose charts are rendered by the framework itself — no charting library,
no CDN, nothing loaded from a third party.

The original Jupyter notebook of the study is kept as plain Python under
`exploratory/`, so the study can be read, diffed and re-run without Jupyter.

---

## Quick start

```bash
python -m pip install -r requirements.txt

python app.py                              # web application on http://127.0.0.1:5000
python run_claid.py --source bestof        # command line, prints its progress
python tools/smoke_test.py                 # end-to-end checks, exits non-zero on failure
python tools/export_notebook.py            # re-export the notebook to exploratory/
python exploratory/claid_workflow.py       # run the study pipeline (12 figures)
```

## Live Demo Link

```bash
https://claidframework.vercel.app/
```

`python app.py` and `python run_claid.py` put `src/` on the import path by
themselves, as does the smoke test. The module form `python -m claid.cli` is
equivalent once `src` is on `PYTHONPATH` (`set PYTHONPATH=src` on Windows,
`export PYTHONPATH=src` elsewhere).

A dataset extraction and a `var/` directory are created on first use; both are
git-ignored.

---

## The web application

| route | what it does |
| --- | --- |
| `GET /` | dashboard: dataset summary, KPI tiles, run form, recent runs |
| `POST /analyze` | runs the framework with the submitted parameters, then redirects |
| `GET /results/<run_id>` | the full report: at-a-glance figure, four module sections, metrics |
| `GET /runs/<run_id>/<figure>.png` | one figure of a finished run |
| `GET /download/<run_id>/<table>.csv` | CSV export: communities, anomalies, anomalous communities, influencers, metrics, focus |
| `GET /api/claid` | JSON API, same parameters as the form (`source`, `community_method`, `resolution`, `contamination`, `community_contamination`, `top_influencers`) |
| `GET /api/runs` | JSON list of stored runs |
| `GET /about` | module → report mapping, tooling, dataset notes, configuration |

Each run writes `result.json` and its figures into `var/runs/<run_id>/`, so the
results page is a permanent, shareable report.

---

## Configuration and secrets

**No key, token or password is stored in this repository.** Anything that depends
on the machine or on a deployment is read from the environment, or from a
git-ignored `.env` file:

| variable | meaning | default |
| --- | --- | --- |
| `CLAID_SECRET_KEY` | signs session cookies | generated per process |
| `CLAID_HOST` | interface to bind | `127.0.0.1` |
| `CLAID_PORT` | port to bind | `5000` |
| `CLAID_DEBUG` | Flask debugger, local use only | off |
| `CLAID_STATE_DIR` | where `data/` and `var/` are written | the repository |

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste into CLAID_SECRET_KEY
```

`src/claid/config.py` reads those variables (`load_environment()`, `secret_key()`,
`web_host()`, `web_port()`, `debug_enabled()`); `.env` and `.env.*` are ignored by
git while `.env.example` is committed. The application also sets a self-only
content-security policy, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`
and a 64 KB request-body cap, and it refuses to advertise the debugger on a public
interface. `tools/smoke_test.py` scans the tree and fails if a credential-shaped
assignment is ever committed.

## Deploying

The application writes exactly two things: the dataset it extracts from the
shipped zip (`data/`) and one folder per run (`var/runs/`). Everything else is
read-only, so a deployment only has to decide where those writes may go.

| host | what works | where the state goes |
| --- | --- | --- |
| a host that keeps a disk - Render, Railway, Fly.io, Cloud Run, a VPS, `deploy/Dockerfile` | the full run, persistent history | `CLAID_STATE_DIR` on the mounted volume |
| Vercel, AWS Lambda and other serverless filesystems | the app runs; runs are temporary | automatic fallback to `<tmp>/claid` |

### Vercel

`app.py` is a zero-configuration Flask entrypoint - Vercel picks the framework
preset from `requirements.txt` and bundles the whole repository, so no
`vercel.json` is needed - and one run sits comfortably inside the Hobby function
budget (300 s, 2 GB).

Serverless functions mount the deployed tree **read-only** and offer `/tmp` as the
only writable place. `src/claid/config.py` probes this at import time and moves
`data/` and `var/` to `<tmp>/claid`, so the dashboard, a run and its figures all
work with no setting to change. Two consequences worth knowing:

* the extracted dataset and the runs live in that instance's temporary directory.
  Open a run right after it finishes; a URL served by a fresh instance answers
  with a short explanation instead of a bare error, and the dashboard carries the
  same note while the state is outside the project;
* set `CLAID_SECRET_KEY` in the project's environment variables, or every instance
  will sign its cookies with a key of its own.

### A host with a disk (keeps the run history)

```bash
docker build -f deploy/Dockerfile -t claid .
docker run -p 8000:8000 -v claid-data:/data claid        # http://127.0.0.1:8000
```

`deploy/Dockerfile` installs the requirements plus gunicorn, runs one worker (the
pipeline memoises the graph, the §4.5 comparison and the Isolation Forest fits per
process, so a single worker keeps that cache warm for every request) and points
`CLAID_STATE_DIR` at the `/data` volume, so runs and the extracted dataset survive
restarts. On Render, Railway or Fly.io, give the same path as the Dockerfile.

## Repository layout

```
.
├── app.py                          Flask front end: routes, JSON API, CSV export
├── run_claid.py                    zero-setup CLI entry point (puts src/ on the path)
├── requirements.txt
├── deploy/Dockerfile
    container image for a host that keeps a disk (see "Deploying")
├── .env.example                    documented environment variables (no secrets)
├── src/claid/                      the framework, importable as `claid`
│   ├── config.py                   paths, algorithm defaults (§4.5–§4.7), environment
│   ├── data.py                     dataset extraction, cleaning, graph construction
│   ├── community.py                Louvain, greedy modularity, label propagation, Girvan–Newman
│   ├── anomaly.py                  Isolation Forest on nodes and communities, degree rule
│   ├── influence.py                betweenness / closeness / degree centrality per community
│   ├── evaluate.py                 precision, recall, F1, ARI, NMI against a named reference
│   ├── plots.py                    every figure, one shared theme and palette
│   ├── pipeline.py                 runs the modules, writes var/runs/<run_id>/
│   ├── progress.py                 stage-by-stage reporting while a run is working
│   ├── cli.py                      argument parsing for run_claid.py / -m claid.cli
│   └── web/                        templates, stylesheets, JS and favicon served by Flask
├── exploratory/                    the original notebook as Python (generated)
│   ├── claid_workflow.py           the whole study as one executable script
│   ├── claid_workflow_verbatim.py  verbatim transcription, kept for reference
│   ├── parts/part_1…part_7_*.py    one file per notebook section, named after its algorithm
│   ├── figures/                    PNGs written when the workflow runs (git-ignored)
│   └── README.md                   generated: cell map, rewrites applied, file list
├── tools/
│   ├── export_notebook.py          notebook  →  exploratory/*.py
│   └── smoke_test.py               end-to-end checks: framework, routes, assets, secrets
├── data/                           extracted dataset (git-ignored)
└── var/runs/<run_id>/              result.json plus the figures of one run (git-ignored)
```

## The three modules

| module | algorithm | report | implementation |
| --- | --- | --- | --- |
| Community detection | Louvain modularity, compared with greedy modularity, label propagation, Girvan–Newman | §4.5, §5.2.1 (figure 14) | `src/claid/community.py` |
| Anomaly detection | Isolation Forest over node and community features; degree-centrality reference rule | §4.6, §5.2.2 (figure 15) | `src/claid/anomaly.py` |
| Influential users | betweenness centrality inside each non-anomalous community | §4.7, §5.2.3 (figure 16) | `src/claid/influence.py` |
| Evaluation | precision, recall, F<sub>1</sub>, ARI, NMI | §5.2.5 | `src/claid/evaluate.py` |
| Framework view | source node, its communities, their anomalies and influencers | §5.2.4 (figure 13) | `pipeline._focus()` |
| Web application | Flask routes, JSON API, CSV export | §4.4.6 | `app.py`, `src/claid/web/` |

Each run produces nine figures: an at-a-glance summary, the community structure, the
degree and community-size distributions, the flagged anomalies, the anomaly-score
distribution with its cut-off, the community influencers, the graph-wide betweenness
ranking, the source-node view and the metric comparison. All of them share one theme
and palette so a results page reads as a single report.

### Performance guards

* Exact Brandes betweenness is O(n·m); above 800 nodes the **graph-wide** ranking
  switches to a 200-source estimate. The §4.7 per-community scores stay exact.
* Girvan–Newman is O(n·m²), so the §4.5 comparison runs it on a 90-node subgraph —
  the table says so.
* Network pictures draw at most 400 nodes of the largest component, trimmed to the
  best-connected nodes, and the caption states the ratio.

### Runtime and stage progress

A first run takes roughly 15–30 seconds on the shipped dataset — the spread is
machine load, and writing the figures into a synced OneDrive folder is the slowest
part: greedy modularity (~5 s), closeness centrality (~4 s), the graph-wide
betweenness estimate (~2 s), the Isolation Forest fits (~1 s) and nine figures
(~6 s). The pipeline therefore reports every stage with its duration, so a run never
looks hung:

```
[claid]   ...  module 1 - community detection (Louvain Modularity)
[claid]   0.5s  module 1 done: 271 communities, modularity 0.6762
[claid]   ...  comparison - Greedy Modularity
[claid]   5.2s  comparison - Greedy Modularity done
```

`python app.py` mirrors the same lines into the Flask log, the run form says the
run takes about half a minute and spins while the POST is in flight, and
`--quiet` keeps only the headline line.

Every deterministic stage — the graph and its features, the §4.5 comparison, the
top-k influence baselines and the Isolation Forest fits — is memoised per dataset
inside the running process, so **a repeat run finishes in about a second** instead of
recomputing all of it; `pipeline.cache_stats()` reports what is already cached.

## Dataset

`Dataset(1).csv` (5,029 rows) ships in the committed zip and is extracted into
`data/` on first use: `SOURCE_SUBREDDIT`, `TARGET_SUBREDDIT`, `POST_ID`, `TIMESTAMP`,
`ADDRESS`, `FOLLOWERS`, `PHONE NO`, `LIKES`, `COMMENTS`, `LINK_SENTIMENT` and an
86-value `PROPERTIES` vector. The smaller 6-column `Dataset.csv` from the same zip is
supported too (`python run_claid.py --dataset Dataset.csv`).

The graph built from it has 2,599 nodes, 3,779 edges and 242 components. Rows whose
endpoints are missing (the literal `NaN`) and self loops are dropped, and the
dashboard reports how many.


## Verification

```bash
python tools/smoke_test.py
```

runs the framework twice on the shipped dataset, exercises every route with Flask's
test client, checks the assets, the security headers and the deployment posture, and
scans the source tree for credential-shaped assignments. Latest result: **39 checks,
0 failed** — 271 communities (modularity 0.6762), 130 anomalous nodes in 14 anomalous
communities, 257 community influencers, all four §4.5 methods returning a partition
(label propagation included), nine figures per run, a repeat run served from the
in-process cache in about half a second, and no secrets in the repository.

## Credits

Framework: *CLAID — A Unified Social Network Analysis Framework for Community-Level
Anomaly and Influencer Detection*, project report by Ramya S, Rupesh A and Akilan K,
Department of Computer Technology, Anna University MIT Campus (May 2024).

