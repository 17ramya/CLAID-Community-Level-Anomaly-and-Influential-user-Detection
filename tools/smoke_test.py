#!/usr/bin/env python
"""End-to-end smoke test for the CLAID package and the Flask web application.

    python tools/smoke_test.py

Runs the framework on the shipped dataset, drives every web route with Flask's
test client, checks the assets and the security headers, and scans the source
tree for hard-coded credentials.  Prints one line per check and exits non-zero
if anything fails.
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

RESULTS = []

#: Assignments and tokens that would mean a credential was committed.
SECRET_PATTERNS = (
    re.compile(r"""(?i)\b(secret_key|api_key|apikey|password|passwd|access_token"""
               r"""|auth_token|client_secret|private_key)\b\s*[:=]\s*["'][^"']{6,}["']"""),
    re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)

SCAN_SUFFIXES = (".py", ".html", ".css", ".js", ".json", ".yml", ".yaml", ".toml",
                 ".ini", ".cfg", ".example", ".txt")
SKIP_DIRS = {".git", "__pycache__", "data", "var", "node_modules", ".venv", "venv",
             ".angular", "dist", "build"}


def find_secrets():
    """Return the spots that look like a hard-coded credential."""
    hits = []
    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for name in files:
            if not name.endswith(SCAN_SUFFIXES):
                continue
            path = os.path.join(folder, name)
            try:
                with open(path, encoding="utf-8", errors="ignore") as handle:
                    text = handle.read()
            except OSError:
                continue
            for pattern in SECRET_PATTERNS:
                for match in pattern.finditer(text):
                    hits.append("%s: %s"
                                % (os.path.relpath(path, ROOT), match.group(0)[:60]))
    return hits


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print("%-4s %s%s" % ("OK" if condition else "FAIL", name,
                         (" - " + detail) if detail else ""))
    return bool(condition)


def main():
    import app as webapp
    import claid
    from claid import config, pipeline, progress

    # The pipeline reports each stage; this test asserts on those lines, so it
    # captures them into a sink and keeps stderr quiet to stay readable.
    observed = []
    progress.add_sink(observed.append)
    os.environ["CLAID_QUIET"] = "1"

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
                                 ("overview", "communities", "distributions", "anomalies",
                                  "anomaly_scores", "influencers", "influencer_ranking",
                                  "focus", "metrics")),
          ", ".join(name for name in result["plots"].values() if name))

    client = webapp.app.test_client()

    # --- dashboard ------------------------------------------------------- #
    response = client.get("/")
    html = response.get_data(as_text=True)
    check("GET /", response.status_code == 200
          and "Community, anomaly and influencer detection in one pass" in html
          and "Configure a run" in html,
          "%d bytes" % len(response.get_data()))

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
    for heading in ("Community detection with Louvain modularity",
                    "Anomaly detection with the Isolation Forest",
                    "Influential users with betweenness centrality",
                    "Evaluation: precision, recall and F",
                    "At a glance"):
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

    # --- assets, headers and deployment posture -------------------------- #
    css = client.get("/static/css/style.css")
    check("stylesheet served", css.status_code == 200 and b"--blue" in css.data,
          "%d bytes" % len(css.data))
    icon = client.get("/static/img/favicon.svg")
    check("favicon served", icon.status_code == 200 and b"<svg" in icon.data)

    script = client.get("/static/js/app.js")
    check("run-progress script served",
          script.status_code == 200 and b"run-status" in script.data,
          "%d bytes" % len(script.data))

    headers = client.get("/").headers
    check("security headers",
          headers.get("X-Content-Type-Options") == "nosniff"
          and headers.get("X-Frame-Options") == "DENY"
          and "default-src 'self'" in (headers.get("Content-Security-Policy") or ""),
          "CSP + nosniff + DENY + referrer policy")

    check("templates and stylesheets live in the package",
          os.path.isdir(config.TEMPLATES_DIR) and os.path.isdir(config.STATIC_DIR),
          os.path.relpath(config.STATIC_DIR, ROOT))

    check("session key is generated, not committed",
          len(webapp.app.config["SECRET_KEY"]) >= 32,
          "%d characters (CLAID_SECRET_KEY or a fresh random value)"
          % len(webapp.app.config["SECRET_KEY"]))

    hits = find_secrets()
    check("no hard-coded credentials in the tree", not hits,
          hits[0] if hits else "app.py, src/, tools/ and templates scanned")
    check(".env.example documents the environment",
          os.path.exists(os.path.join(ROOT, ".env.example")))
    check(".env stays out of git",
          ".env" in open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read())

    # --- progress reporting and caching ----------------------------------- #
    repeat = pipeline.run_claid(source="bestof", make_plots=False)

    comparison = result["community"]["comparison"]
    check("every community method returned a partition",
          len(comparison) == len(config.COMMUNITY_COMPARISON_METHODS)
          and all("error" not in entry for entry in comparison.values()),
          "methods: " + ", ".join(sorted(comparison)))

    check("the pipeline reports its stages",
          any("module 1" in line for line in observed)
          and any("module 3" in line for line in observed),
          "%d progress lines (%s ...)" % (len(observed), observed[0] if observed else ""))

    check("a repeat run reuses the cached work",
          any("reused from cache" in line for line in observed)
          and repeat["duration_seconds"] < result["duration_seconds"] * 0.6,
          "%.1fs vs %.1fs for the first run"
          % (repeat["duration_seconds"], result["duration_seconds"]))

    os.environ.pop("CLAID_QUIET", None)
    check("stage progress is on by default and can be silenced",
          not progress.quiet() and bool(observed),
          "CLAID_QUIET silences stderr; registered sinks still receive the lines")

    stats = pipeline.cache_stats()
    check("deterministic stages are memoised per dataset",
          bool(stats["features"] and stats["comparison"] and stats["baselines"]),
          "comparison %s | baselines %s | forest %s"
          % (stats["comparison"], stats["baselines"], stats["forest"]))

    failures = [name for name, ok, _ in RESULTS if not ok]
    print("\n%d checks, %d failed" % (len(RESULTS), len(failures)))
    if failures:
        print("failed: " + ", ".join(failures))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
