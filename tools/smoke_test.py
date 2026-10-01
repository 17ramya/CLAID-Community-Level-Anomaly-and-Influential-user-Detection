#!/usr/bin/env python
"""End-to-end smoke test for the CLAID package and the Flask web application.

    python tools/smoke_test.py

Runs the framework on the shipped dataset and then drives every web route with
Flask's test client.  Prints one line per check and exits non-zero on failure.
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print("%-4s %s%s" % ("OK" if condition else "FAIL", name,
                         (" - " + detail) if detail else ""))
    return bool(condition)


def main():
    import app as webapp
    import claid
    from claid import pipeline

    check("claid imports", claid.__version__ == "1.0.0", "version %s" % claid.__version__)

    # --- the framework itself ------------------------------------------- #
    result = pipeline.run_claid(source="bestof")
    check("run id", bool(re.match(r"^\d{8}-\d{6}-\w{6}$", result["run_id"])), result["run_id"])
    check("network loaded", result["network"]["nodes"] > 1000,
          "%d nodes / %d edges" % (result["network"]["nodes"], result["network"]["edges"]))
    check("communities found", result["community"]["num_communities"] > 10,
          "%d communities" % result["community"]["num_communities"])
    check("modularity in range", 0.0 < result["community"]["modularity"] <= 1.0,
          "modularity %.4f" % result["community"]["modularity"])
    assignment = result["community"]["assignment"]
    check("assignment covers the graph",
          len(assignment) == result["network"]["nodes"]
          and len(set(assignment.values())) == result["community"]["num_communities"],
          "%d nodes in %d communities" % (len(assignment), len(set(assignment.values()))))
    check("anomalies detected", result["anomaly"]["n_anomalies"] > 0,
          "%d nodes, %d communities"
          % (result["anomaly"]["n_anomalies"], len(result["anomaly"]["anomalous_communities"])))
    check("influencers detected", len(result["influence"]["per_community"]) > 0,
          "%d community leaders" % len(result["influence"]["per_community"]))
    focus = result["focus"]
    check("focus node reported", focus["source"] == "bestof" and focus["degree"] > 0,
          "%s (degree %d, %d interacting communities)"
          % (focus["source"], focus["degree"], len(focus["communities"])))
    check("metrics table populated", len(result["metrics"]["rows"]) >= 6,
          "%d rows" % len(result["metrics"]["rows"]))
    check("figures written", all(result["plots"].get(key) for key in
                                 ("communities", "anomalies", "influencers", "focus", "metrics")),
          ", ".join(name for name in result["plots"].values() if name))

    client = webapp.app.test_client()

    # --- dashboard ------------------------------------------------------- #
    response = client.get("/")
    html = response.get_data(as_text=True)
    check("GET /", response.status_code == 200 and "Run the CLAID framework" in html)

    # --- run the framework through the form ------------------------------ #
    response = client.post(
        "/analyze",
        data={"source": "bestof", "community_method": "Louvain Modularity",
              "resolution": "1.0", "contamination": "0.05",
              "community_contamination": "0.05", "top_influencers": "5"},
    )
    check("POST /analyze redirects", response.status_code == 302,
          response.headers.get("Location", ""))
    location = response.headers.get("Location", "")
    run_id = location.rstrip("/").split("/")[-1] if location else ""

    response = client.get("/results/%s" % run_id)
    html = response.get_data(as_text=True)
    check("GET /results", response.status_code == 200 and "Analysis run" in html,
          "%d bytes" % len(response.get_data()))
    for heading in ("Community detection with Louvain", "Anomaly detection with Isolation Forest",
                    "Influential users with betweenness", "Evaluation metrics"):
        check("results shows '%s'" % heading, heading in html)

    figure = client.get("/runs/%s/communities.png" % run_id)
    check("figure served", figure.status_code == 200 and figure.data[:4] == b"\x89PNG",
          "%d bytes" % len(figure.data))

    csv_response = client.get("/download/%s/metrics.csv" % run_id)
    check("metrics.csv download", csv_response.status_code == 200
          and csv_response.headers["Content-Type"].startswith("text/csv"),
          "%d bytes" % len(csv_response.data))

    # --- JSON API -------------------------------------------------------- #
    api = client.get("/api/claid?source=switcharoo&contamination=0.03")
    payload = api.get_json() or {}
    check("GET /api/claid", api.status_code == 200 and payload.get("run_id") is not None
          and payload.get("focus", {}).get("source") == "switcharoo",
          "focus %s" % payload.get("focus", {}).get("source"))
    runs = client.get("/api/runs").get_json() or {}
    check("GET /api/runs", api.status_code == 200 and isinstance(runs.get("runs"), list),
          "%d stored runs" % len(runs.get("runs", [])))

    # --- static pages and error handling --------------------------------- #
    about = client.get("/about")
    check("GET /about", about.status_code == 200
          and "Module &rarr; project report mapping".replace("&rarr;", "→")
          in about.get_data(as_text=True).replace("&rarr;", "→"))
    missing = client.get("/results/does-not-exist")
    check("unknown run -> 404", missing.status_code == 404)

    failures = [name for name, ok, _ in RESULTS if not ok]
    print("\n%d checks, %d failed" % (len(RESULTS), len(failures)))
    if failures:
        print("failed: " + ", ".join(failures))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
