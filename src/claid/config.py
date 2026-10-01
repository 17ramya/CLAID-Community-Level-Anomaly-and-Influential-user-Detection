"""Central configuration for the CLAID framework.

Defaults follow the implementation chapter of the project report
("CLAID: A Unified Social Network Analysis Framework for Community-Level
Anomaly and Influencer Detection", doc sections 4.5 - 4.7).
"""
from __future__ import annotations

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
VAR_DIR = os.path.join(PROJECT_ROOT, "var")
RUNS_DIR = os.path.join(VAR_DIR, "runs")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "webapp", "static")

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
PLOT_DPI = 110
FIGURE_SIZE = (9.5, 7.0)


def ensure_directories():
    """Create the data/var directories used by the pipeline."""
    for path in (DATA_DIR, VAR_DIR, RUNS_DIR):
        os.makedirs(path, exist_ok=True)
    return {"data": DATA_DIR, "var": VAR_DIR, "runs": RUNS_DIR}
