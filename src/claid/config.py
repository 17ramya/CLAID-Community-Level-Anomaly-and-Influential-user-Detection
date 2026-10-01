"""Central configuration for the CLAID framework.

Defaults follow the implementation chapter of the project report
("CLAID: A Unified Social Network Analysis Framework for Community-Level
Anomaly and Influencer Detection", doc sections 4.5 - 4.7).

Nothing secret is stored in this file. Every value that depends on the machine
or on a deployment is read from the environment, so no key, token or password
ever has to be committed - see ``.env.example`` and :func:`load_environment`.

The writable state (the extracted dataset and one folder per run) normally lives
in the repository as ``data/`` and ``var/``. A host that mounts the deployed tree
read-only - Vercel, AWS Lambda, Cloud Run - gets ``/tmp`` instead, so the state
root is probed at import time and moved there automatically; ``CLAID_STATE_DIR``
picks the location by hand (point it at a volume to keep runs between restarts).
"""
from __future__ import annotations

import os
import secrets
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: Move the writable state (dataset cache + runs) with this variable.
STATE_ENV_VAR = "CLAID_STATE_DIR"


def _is_writable(path):
    """True when ``path`` can be created and a probe file written inside it."""
    probe = os.path.join(path, ".claid-write-probe")
    try:
        os.makedirs(path, exist_ok=True)
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write("ok")
    except OSError:
        return False
    try:
        os.remove(probe)
    except OSError:  # the probe was written, so the directory is usable
        pass
    return True


def _temporary_state_root():
    """``<tmp>/claid`` - the one writable place a serverless host offers."""
    return os.path.join(tempfile.gettempdir(), "claid")


def _resolve_state_root():
    """Pick the directory that holds ``data/`` and ``var/``.

    ``CLAID_STATE_DIR`` wins when it is set (a volume keeps runs across
    restarts); without it the repository root is used as long as it accepts a
    write, which leaves the local workflow untouched.  When neither works the
    state moves to the system temp directory, which is what makes the application
    run on a read-only serverless filesystem.
    """
    override = os.environ.get(STATE_ENV_VAR, "").strip()
    candidates = ([os.path.abspath(override)] if override else [PROJECT_ROOT])
    fallback = _temporary_state_root()
    if fallback not in candidates:
        candidates.append(fallback)
    for candidate in candidates:
        if _is_writable(os.path.join(candidate, "var")):
            return candidate
    return candidates[-1]  # nothing is writable - fail loudly on the first write


STATE_ROOT = _resolve_state_root()
DATA_DIR = os.path.join(STATE_ROOT, "data")
VAR_DIR = os.path.join(STATE_ROOT, "var")
RUNS_DIR = os.path.join(VAR_DIR, "runs")
#: matplotlib's config/font cache - kept writable so a read-only image still draws
CACHE_DIR = os.path.join(VAR_DIR, "cache")
os.environ.setdefault("MPLCONFIGDIR", CACHE_DIR)
try:  # matplotlib only builds its font cache when the directory already exists
    os.makedirs(CACHE_DIR, exist_ok=True)
except OSError:  # a read-only mount: matplotlib will warn and fall back on its own
    pass

#: Flask assets live inside the package: <package>/web/{templates,static}.
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(PACKAGE_DIR, "web")
TEMPLATES_DIR = os.path.join(WEB_DIR, "templates")
STATIC_DIR = os.path.join(WEB_DIR, "static")

DATASET_ZIP = os.path.join(PROJECT_ROOT, "Dataset-20250808T064225Z-1-001.zip")
#: 11 columns described in doc section 4.3 (source, target, post id, timestamp,
#: sentiment, address, followers, phone no, likes, comments, properties).
PREFERRED_DATASET = "Dataset(1).csv"
#: 6 column variant shipped in the same zip (source_node, target_node, ...).
FALLBACK_DATASET = "Dataset.csv"

SOURCE_ALIASES = ("SOURCE_SUBREDDIT", "source_node")
TARGET_ALIASES = ("TARGET_SUBREDDIT", "target_node")

# --- doc 4.5: community detection with Louvain modularity ------------------ #
LOUVAIN_RESOLUTION = 1.0
LOUVAIN_RANDOM_STATE = 42
COMMUNITY_COMPARISON_METHODS = (
    "Louvain Modularity",
    "Greedy Modularity",
    "Label Propagation",
    "Edge Betweenness",
)

# --- doc 4.6: anomaly detection with Isolation Forest ---------------------- #
IFOREST_CONTAMINATION = 0.05
IFOREST_N_ESTIMATORS = 200
IFOREST_RANDOM_STATE = 42
#: doc figure 8 reference rule: degree centrality > mean + DEGREE_SIGMA * std
DEGREE_SIGMA = 2.0

# --- doc 4.7: influential users with Betweenness Centrality ---------------- #
TOP_INFLUENCERS = 5
#: exact betweenness is O(n*m); above this node count a sampled estimate is used
BETWEENNESS_EXACT_MAX_NODES = 800
BETWEENNESS_SAMPLE_K = 200

# --- plotting / performance guards ---------------------------------------- #
MAX_PLOT_NODES = 400
MAX_GIRVAN_NEWMAN_NODES = 90  # Girvan-Newman is O(n*m^2): run on a capped subgraph
PLOT_DPI = 140
FIGURE_SIZE = (9.5, 7.0)

# --- deployment ----------------------------------------------------------- #
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
#: the run form is a handful of small fields - anything larger is rejected early.
MAX_REQUEST_BYTES = 64 * 1024
SESSION_COOKIE_OPTIONS = {"httponly": True, "samesite": "Lax"}


def load_environment(path=None):
    """Copy ``KEY=VALUE`` lines from ``.env`` into ``os.environ``.

    Variables already present in the real environment win, so a deployment can
    export credentials in its own shell or drop them in a git-ignored ``.env``
    file. Returns the names that were loaded.
    """
    path = path or ENV_FILE
    loaded = []
    if not os.path.exists(path):
        return loaded
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded.append(key)
    return loaded


def secret_key():
    """Session-signing secret - never a literal in the source tree.

    ``CLAID_SECRET_KEY`` wins. Without it a fresh random key is generated per
    process, which is fine for local runs and keeps the repository free of
    credentials. Set the variable in a real deployment so sessions survive
    restarts.
    """
    return os.environ.get("CLAID_SECRET_KEY") or secrets.token_hex(32)


def debug_enabled():
    """True only when ``CLAID_DEBUG`` asks for it - the debugger is never a default."""
    return os.environ.get("CLAID_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")


def web_host():
    return os.environ.get("CLAID_HOST") or DEFAULT_HOST


def web_port():
    try:
        return int(os.environ.get("CLAID_PORT") or DEFAULT_PORT)
    except ValueError:
        return DEFAULT_PORT


def ensure_directories():
    """Create the data/var directories used by the pipeline."""
    for path in (DATA_DIR, VAR_DIR, RUNS_DIR, CACHE_DIR):
        os.makedirs(path, exist_ok=True)
    return {"data": DATA_DIR, "var": VAR_DIR, "runs": RUNS_DIR, "cache": CACHE_DIR}


def is_ephemeral():
    """True when the state lives in the system temp directory.

    That is what happens on a serverless host: the writes succeed, but the host
    may hand the next request to a fresh instance, so the run folders (and the
    extracted dataset) do not survive. Callers use this to say so instead of
    letting a missing run look like a bug.
    """
    temp = os.path.normcase(os.path.abspath(tempfile.gettempdir()))
    root = os.path.normcase(os.path.abspath(STATE_ROOT))
    return root == temp or root.startswith(temp + os.sep)


def state_summary():
    """Where the writable state lives - printed at startup and shown in the UI."""
    return {
        "root": STATE_ROOT,
        "runs": RUNS_DIR,
        "dataset": DATA_DIR,
        "in_project": os.path.normcase(os.path.abspath(STATE_ROOT))
        == os.path.normcase(os.path.abspath(PROJECT_ROOT)),
        "ephemeral": is_ephemeral(),
        "from_env": bool(os.environ.get(STATE_ENV_VAR, "").strip()),
    }

