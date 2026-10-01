"""CLAID web application - the Flask front end for the framework (doc 4.4.6).

Run it from the repository root::

    python app.py                  # http://127.0.0.1:5000
    python app.py --port 8000 --debug

Routes
------
``/``                        dashboard: dataset summary, run form, run history
``POST /analyze``            run the CLAID framework, redirect to the results
``/results/<run_id>``        communities, anomalies, influential users, metrics
``/runs/<run_id>/<figure>``  figures produced for a run
``/api/claid``               JSON API (same parameters as the form)
``/api/runs``                JSON list of stored runs
``/download/<run_id>/<t>.csv``  CSV export of a result table
``/about``                   module -> report-section map, tooling, dataset notes

The writable state - the extracted dataset and one folder per run - lives in
``var/`` beside the repository. A host that mounts the deployed tree read-only
(Vercel, Lambda, Cloud Run) gets a temporary directory instead: see
``CLAID_STATE_DIR`` in :mod:`claid.config`.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import time

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from claid import config, data, pipeline, progress  # noqa: E402

config.load_environment()  # .env / shell variables; nothing secret is stored here

app = Flask(
    __name__,
    template_folder=config.TEMPLATES_DIR,
    static_folder=config.STATIC_DIR,
)
app.config.update(
    # No credential lives in the source tree: the key comes from CLAID_SECRET_KEY
    # or is generated for this process (see .env.example).
    SECRET_KEY=config.secret_key(),
    JSON_SORT_KEYS=False,
    MAX_CONTENT_LENGTH=config.MAX_REQUEST_BYTES,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# The pipeline prints its stage timings while it works; mirror them into the
# Flask log so the terminal that serves the site shows what a run is doing.
progress.add_sink(app.logger.info)


@app.after_request
def _security_headers(response):
    """Sensible defaults for a site that loads nothing from a third party."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    )
    return response

METHODS = list(config.COMMUNITY_COMPARISON_METHODS)
NODE_CHOICES = 150


def _float(value, default, low=None, high=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if low is not None:
        number = max(number, low)
    if high is not None:
        number = min(number, high)
    return number


def _int(value, default, low=1, high=100):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _params_from(payload):
    """Collect the framework parameters from a form or a query string."""
    method = payload.get("community_method") or "Louvain Modularity"
    if method not in METHODS:
        method = "Louvain Modularity"
    source = (payload.get("source") or "").strip() or None
    return {
        "source": source,
        "community_method": method,
        "resolution": _float(payload.get("resolution"), config.LOUVAIN_RESOLUTION, 0.05, 10.0),
        "contamination": _float(payload.get("contamination"), config.IFOREST_CONTAMINATION, 0.001, 0.49),
        "community_contamination": _float(
            payload.get("community_contamination"), config.IFOREST_CONTAMINATION, 0.001, 0.49
        ),
        "top_influencers": _int(payload.get("top_influencers"), config.TOP_INFLUENCERS, 1, 50),
    }


def dataset_overview():
    """Dataset summary plus the node list used by the source-node selector."""
    cache = pipeline.load_graph()
    graph = cache["graph"]
    summary = data.summary(graph, cache["frame"], cache["dataset_file"], cache["clean_report"])
    ranked = sorted(
        graph.degree(weight="weight"), key=lambda item: (-item[1], str(item[0]))
    )[:NODE_CHOICES]
    choices = [
        {"node": str(node), "degree": int(graph.degree(node)), "weighted_degree": int(weight)}
        for node, weight in ranked
    ]
    return summary, choices


@app.route("/")
def dashboard():
    summary, choices = dataset_overview()
    return render_template(
        "index.html",
        summary=summary,
        node_choices=choices,
        methods=METHODS,
        defaults={
            "resolution": config.LOUVAIN_RESOLUTION,
            "contamination": config.IFOREST_CONTAMINATION,
            "top_influencers": config.TOP_INFLUENCERS,
        },
        runs=pipeline.list_runs(limit=8),
        storage=_storage_view(),
        active="dashboard",
    )


@app.route("/analyze", methods=["POST"])
def analyze():
    """Run the framework and redirect to the stored results.

    A full run takes about half a minute, so the pipeline logs each stage (and
    the two lines below bracket the request in the server log).
    """
    params = _params_from(request.form)
    started = time.time()
    app.logger.info("POST /analyze %s", params)
    result = pipeline.run_claid(**params)
    app.logger.info("POST /analyze -> /results/%s in %.1fs",
                    result["run_id"], time.time() - started)
    return redirect(url_for("results", run_id=result["run_id"]))


def _storage_view():
    """How the dashboard should describe where runs are kept."""
    state = config.state_summary()
    return {
        "root": state["root"],
        "ephemeral": state["ephemeral"],
        "runs_label": "var/runs/" if state["in_project"] else state["runs"],
    }


def _missing_run_message(run_id):
    """404 text for a run that is not stored (or no longer stored)."""
    if config.is_ephemeral():
        return ("run %s is not on this instance - this deployment keeps the runs "
                "in a temporary directory, so a finished run has to be opened right "
                "away" % run_id)
    return "unknown run %s" % run_id


@app.route("/results/<run_id>")
def results(run_id):
    result = pipeline.load_run(run_id)
    if result is None:
        abort(404, _missing_run_message(run_id))
    return render_template("results.html", result=result, active="results")


@app.route("/runs/<run_id>/<figure>")
def run_figure(run_id, figure):
    """Serve the PNG figures produced for a run."""
    if not figure.endswith(".png") or os.sep in figure or ".." in figure:
        abort(404)
    directory = os.path.join(config.RUNS_DIR, run_id)
    if not os.path.isdir(directory):
        abort(404, _missing_run_message(run_id))
    return send_from_directory(directory, figure, mimetype="image/png")


@app.route("/api/claid")
def api_claid():
    """JSON API: same parameters as the form, figures skipped for speed."""
    result = pipeline.run_claid(make_plots=False, **_params_from(request.args))
    return jsonify(result)


@app.route("/api/runs")
def api_runs():
    limit = _int(request.args.get("limit"), 10, 1, 100)
    return jsonify({"runs": pipeline.list_runs(limit=limit)})


CSV_BUILDERS = {
    "communities": lambda result: (
        ["community", "size", "internal_edges", "density", "top_nodes"],
        [
            [row["id"], row["size"], row["internal_edges"], row["density"],
             " | ".join(row["top_nodes"][:8])]
            for row in result["community"]["communities"]
        ],
    ),
    "anomalies": lambda result: (
        ["node", "score", "anomaly_score", "is_anomaly", "community", "degree", "followers_mean"],
        [
            [row["node"], row["score"], row["anomaly_score"], row["is_anomaly"],
             row["community"], row["degree"], row["followers_mean"]]
            for row in result["anomaly"]["nodes"]
        ],
    ),
    "anomalous_communities": lambda result: (
        ["community", "size", "score", "anomaly_score", "is_anomaly"],
        [
            [row["community"], row["size"], row["score"], row["anomaly_score"], row["is_anomaly"]]
            for row in result["anomaly"]["communities"]
        ],
    ),
    "influencers": lambda result: (
        ["community", "size", "influential_user", "score", "metric"],
        [
            [row["community"], row["size"], row["influential_user"],
             row["influential_score"], row["metric"]]
            for row in result["influence"]["per_community"]
        ],
    ),
    "metrics": lambda result: (
        ["module", "method", "reference", "precision", "recall", "f1", "note"],
        [
            [row["module"], row["method"], row["reference"], row["precision"],
             row["recall"], row["f1"], row["note"]]
            for row in result["metrics"]["rows"]
        ],
    ),
    "focus": lambda result: (
        ["community", "size", "influential_user", "excluded", "note"],
        [
            [row["id"], row["size"], row["influential_user"], row["excluded"], row["note"]]
            for row in (result.get("focus") or {}).get("communities", [])
        ],
    ),
}


@app.route("/download/<run_id>/<table>.csv")
def download(run_id, table):
    result = pipeline.load_run(run_id)
    if result is None:
        abort(404, _missing_run_message(run_id))
    builder = CSV_BUILDERS.get(table)
    if builder is None:
        abort(404, "unknown table %s" % table)
    headers, rows = builder(result)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=claid_%s_%s.csv" % (run_id, table)
        },
    )


@app.route("/about")
def about():
    return render_template("about.html", methods=METHODS, active="about",
                           secret_from_env=bool(os.environ.get("CLAID_SECRET_KEY")))


@app.errorhandler(404)
def not_found(error):
    return render_template(
        "error.html", code=404, heading="Not found",
        message=getattr(error, "description", "that page does not exist"),
    ), 404


@app.errorhandler(500)
def server_error(error):  # pragma: no cover - exercised only on a real failure
    return render_template(
        "error.html", code=500, heading="The run could not be completed",
        message="Something went wrong while analysing the graph. "
                "The server log holds the traceback.",
    ), 500


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the CLAID web application")
    parser.add_argument("--host", default=config.web_host(),
                        help="interface to bind (CLAID_HOST, default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=config.web_port(),
                        help="port to bind (CLAID_PORT, default 5000)")
    parser.add_argument("--debug", action="store_true", default=config.debug_enabled(),
                        help="Flask debugger (CLAID_DEBUG) - never on a public interface")
    args = parser.parse_args(argv)
    config.ensure_directories()
    state = config.state_summary()
    print("CLAID state directory: %s" % state["root"])
    if state["ephemeral"]:
        print("note: the project tree is not writable, so the dataset cache and the "
              "runs go to a temporary directory and may not survive a restart "
              "(set %s to choose the location)." % config.STATE_ENV_VAR)
    if args.debug and args.host not in ("127.0.0.1", "localhost"):
        print("warning: the debugger is on while binding %s - do not expose this." % args.host)
    if not os.environ.get("CLAID_SECRET_KEY"):
        print("note: CLAID_SECRET_KEY is unset, so an ephemeral session key was "
              "generated for this process (copy .env.example to .env to fix one).")
    print("CLAID web application running on http://%s:%d" % (args.host, args.port))
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()

