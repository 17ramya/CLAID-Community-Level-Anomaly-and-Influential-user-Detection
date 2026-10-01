#!/usr/bin/env python
"""End-to-end smoke test for the CLAID package and the Flask web application.

    python tools/smoke_test.py

Runs the framework on the shipped dataset, drives every web route with Flask's
test client, checks the assets and the security headers, and scans the source
tree for hard-coded credentials.  Prints one line per check and exits non-zero
if anything fails.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

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


#: Run in a fresh interpreter: the writable state has to follow CLAID_STATE_DIR.
CHILD_STATE = """
import json, os, sys
sys.path.insert(0, os.path.join(__ROOT__, "src"))
from claid import config

dirs = config.ensure_directories()
print(json.dumps({
    "root": config.STATE_ROOT,
    "runs": config.RUNS_DIR,
    "data": config.DATA_DIR,
    "ephemeral": config.is_ephemeral(),
    "in_project": config.state_summary()["in_project"],
    "dirs_exist": all(os.path.isdir(path) for path in dirs.values()),
}))
"""

#: The deployed shape: a finished run moved outside the project is still served.
CHILD_APP = """
import json, os, shutil, sys
sys.path.insert(0, os.path.join(__ROOT__, "src"))
sys.path.insert(0, __ROOT__)

import app as webapp
from claid import config

run_id = os.environ["CLAID_SMOKE_RUN_ID"]
config.ensure_directories()
shutil.copytree(os.environ["CLAID_SMOKE_RUN_DIR"], os.path.join(config.RUNS_DIR, run_id))

client = webapp.app.test_client()
dashboard = client.get("/")
page = client.get("/results/%s" % run_id)
figure = client.get("/runs/%s/communities.png" % run_id)
stored = client.get("/api/runs").get_json() or {}
print(json.dumps({
    "state": config.STATE_ROOT,
    "data": config.DATA_DIR,
    "dashboard": dashboard.status_code,
    "storage_note": "temporary directory" in dashboard.get_data(as_text=True),
    "results": page.status_code,
    "figure": figure.status_code,
    "api_runs": len(stored.get("runs", [])),
    "dataset": os.path.isfile(os.path.join(config.DATA_DIR, "Dataset(1).csv")),
    "outside_project": not config.state_summary()["in_project"],
}))
"""


def run_child(script, env):
    """Run ``script`` in a fresh interpreter and return the JSON it printed."""
    folder = tempfile.mkdtemp(prefix="claid-child-")
    try:
        path = os.path.join(folder, "child.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(script.replace("__ROOT__", "%r" % ROOT))
        done = subprocess.run([sys.executable, path], env=env, cwd=ROOT,
                              capture_output=True, text=True, timeout=900)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    for line in reversed((done.stdout or "").splitlines()):
        if line.strip().startswith("{"):
            try:
                return json.loads(line), done.stdout + done.stderr
            except ValueError:
                break
    return {}, done.stdout + done.stderr


def child_env(state_dir):
    """Environment for a child process whose writable state lives elsewhere."""
    env = dict(os.environ)
    env["CLAID_STATE_DIR"] = state_dir
    env["CLAID_QUIET"] = "1"
    env.pop("MPLCONFIGDIR", None)  # let the child pick its own cache directory
    return env


def last_line(text):
    """The child's last output line - the traceback when it died."""
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1][:120] if lines else "the child process printed nothing"


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

    # --- deployment: the writable state can live outside the project -------- #
    # Serverless hosts (Vercel, Lambda, Cloud Run) mount the deployed tree
    # read-only and offer /tmp, so the writes have to follow CLAID_STATE_DIR and
    # fall back on their own when even that is impossible.
    state_dir = os.path.join(tempfile.mkdtemp(prefix="claid-state-"), "state")
    moved, moved_log = run_child(CHILD_STATE, child_env(state_dir))
    check("CLAID_STATE_DIR moves the writable state",
          os.path.normcase(os.path.abspath(moved.get("root", "")))
          == os.path.normcase(os.path.abspath(state_dir))
          and moved.get("dirs_exist") is True and moved.get("in_project") is False,
          ("root %s, data/var/runs created" % moved["root"]) if moved
          else last_line(moved_log))

    blocked_file = os.path.join(tempfile.mkdtemp(prefix="claid-blocked-"), "not-a-directory")
    with open(blocked_file, "w", encoding="utf-8") as handle:
        handle.write("a file cannot hold a directory")
    blocked, blocked_log = run_child(CHILD_STATE, child_env(os.path.join(blocked_file, "state")))
    temp_root = os.path.join(tempfile.gettempdir(), "claid")
    check("an unwritable state directory falls back to the temp directory",
          os.path.normcase(os.path.abspath(blocked.get("root", "")))
          == os.path.normcase(os.path.abspath(temp_root))
          and blocked.get("ephemeral") is True,
          ("root %s (ephemeral)" % blocked["root"]) if blocked else last_line(blocked_log))

    env = child_env(state_dir)
    env["CLAID_SMOKE_RUN_DIR"] = os.path.join(config.RUNS_DIR, run_id)
    env["CLAID_SMOKE_RUN_ID"] = run_id
    served, served_log = run_child(CHILD_APP, env)
    check("the dashboard works with the state outside the project",
          served.get("dashboard") == 200 and served.get("storage_note") is True
          and served.get("outside_project") is True,
          ("state %s, note shown" % served["state"]) if served else last_line(served_log))
    check("a run stored outside the project is served",
          served.get("results") == 200 and served.get("figure") == 200
          and served.get("api_runs", 0) >= 1,
          ("results %s, figure %s, %s run(s) listed"
           % (served.get("results"), served.get("figure"), served.get("api_runs")))
          if served else last_line(served_log))
    check("the dataset is extracted into the relocated data directory",
          served.get("dataset") is True,
          served.get("data", "") if served else last_line(served_log))

    # the deployment checks wrote into the system temp directory - take them back
    for folder in (os.path.dirname(state_dir), os.path.dirname(blocked_file), temp_root):
        shutil.rmtree(folder, ignore_errors=True)

    failures = [name for name, ok, _ in RESULTS if not ok]
    print("\n%d checks, %d failed" % (len(RESULTS), len(failures)))
    if failures:
        print("failed: " + ", ".join(failures))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
