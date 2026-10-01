"""Dataset handling for CLAID: loading, cleaning and feature extraction (doc 4.3).

The repository ships ``Dataset-20250808T064225Z-1-001.zip`` containing

* ``Dataset(1).csv`` - 11 columns, the layout described in doc section 4.3
  (SOURCE_SUBREDDIT, TARGET_SUBREDDIT, POST_ID, TIMESTAMP, ADDRESS, FOLLOWERS,
  PHONE NO, LIKES, COMMENTS, LINK_SENTIMENT, PROPERTIES) - used by default;
* ``Dataset.csv`` - the 6 column variant (source_node, target_node, ...).

Both are normalised to the canonical column names ``SOURCE`` / ``TARGET``.
"""
from __future__ import annotations

import os
import shutil
import zipfile

import networkx as nx
import numpy as np
import pandas as pd

from . import config

NAN_TOKENS = {"nan", "NaN", "NAN", "none", "None", "null", "NULL", "", " "}

#: attributes aggregated per source node and used by the Isolation Forest
NODE_FEATURES = (
    "posts",
    "followers_mean",
    "followers_max",
    "likes_mean",
    "likes_sum",
    "comments_mean",
    "comments_sum",
    "sentiment_mean",
    "properties_mean",
    "properties_std",
    "degree",
    "weighted_degree",
    "degree_centrality",
    "clustering",
    "betweenness",
    "pagerank",
)


def ensure_dataset_dir():
    """Extract the dataset zip into ``data/`` when the CSVs are not there yet."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    present = [
        name
        for name in (config.PREFERRED_DATASET, config.FALLBACK_DATASET)
        if os.path.exists(os.path.join(config.DATA_DIR, name))
    ]
    if present:
        return config.DATA_DIR
    if not os.path.exists(config.DATASET_ZIP):
        raise FileNotFoundError(
            "no dataset in %s and %s is missing" % (config.DATA_DIR, config.DATASET_ZIP)
        )
    with zipfile.ZipFile(config.DATASET_ZIP) as archive:
        for name in archive.namelist():
            base = os.path.basename(name)
            if not base:
                continue
            with archive.open(name) as src, open(
                os.path.join(config.DATA_DIR, base), "wb"
            ) as dst:
                shutil.copyfileobj(src, dst)
    return config.DATA_DIR


def dataset_path(preferred=None):
    """Return the CSV that should be analysed (doc 4.3 layout first)."""
    ensure_dataset_dir()
    order = [preferred] if preferred else [config.PREFERRED_DATASET, config.FALLBACK_DATASET]
    order += [config.PREFERRED_DATASET, config.FALLBACK_DATASET]
    for name in order:
        if name and os.path.exists(os.path.join(config.DATA_DIR, name)):
            return os.path.join(config.DATA_DIR, name)
    raise FileNotFoundError("no dataset CSV found in %s" % config.DATA_DIR)


def _canonical_columns(frame):
    rename = {}
    for column in frame.columns:
        upper = str(column).strip().upper().replace(" ", "_")
        if column in config.SOURCE_ALIASES or upper in config.SOURCE_ALIASES:
            rename[column] = "SOURCE"
        elif column in config.TARGET_ALIASES or upper in config.TARGET_ALIASES:
            rename[column] = "TARGET"
        else:
            rename[column] = upper
    return frame.rename(columns=rename)


def clean_dataframe(frame):
    """Drop rows/nodes that cannot take part in the network and report what went."""
    report = {"rows_in": int(len(frame))}
    frame = _canonical_columns(frame)
    for column in ("SOURCE", "TARGET"):
        frame[column] = frame[column].astype(str).str.strip()
        # a literal "NaN" is written into Dataset.csv; treat it as missing
        frame.loc[frame[column].isin(NAN_TOKENS), column] = np.nan
    before = len(frame)
    frame = frame.dropna(subset=["SOURCE", "TARGET"]).copy()
    report["rows_dropped_missing_endpoints"] = int(before - len(frame))
    before = len(frame)
    frame = frame[frame["SOURCE"] != frame["TARGET"]]
    report["rows_dropped_self_loops"] = int(before - len(frame))
    for column in ("FOLLOWERS", "PHONE_NO", "LIKES", "COMMENTS", "LINK_SENTIMENT"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    report["rows_out"] = int(len(frame))
    report["nodes"] = int(pd.unique(pd.concat([frame["SOURCE"], frame["TARGET"]])).size)
    return frame.reset_index(drop=True), report


def load_dataframe(path=None, preferred=None):
    """Load the dataset as a cleaned DataFrame with SOURCE/TARGET columns."""
    path = path or dataset_path(preferred)
    frame = pd.read_csv(path)
    frame, _ = clean_dataframe(frame)
    return frame


def parse_properties(frame):
    """Expand the comma separated PROPERTIES vector into mean/std columns."""
    if "PROPERTIES" not in frame.columns:
        return pd.DataFrame(index=frame.index)
    values = []
    for raw in frame["PROPERTIES"].astype(str):
        try:
            numbers = [float(x) for x in raw.split(",") if x.strip() != ""]
        except ValueError:
            numbers = []
        values.append(numbers or [np.nan])
    return pd.DataFrame(
        {
            "properties_mean": [float(np.nanmean(v)) for v in values],
            "properties_std": [float(np.nanstd(v)) for v in values],
        },
        index=frame.index,
    )


def build_graph(frame, directed=False):
    """Build the social-interaction graph (doc 4.4.2, NetworkX).

    Repeated interactions between the same pair of nodes become an edge weight.
    """
    graph = nx.DiGraph() if directed else nx.Graph()
    counts = {}
    for source, target in zip(frame["SOURCE"], frame["TARGET"]):
        key = (source, target) if directed else tuple(sorted((source, target)))
        counts[key] = counts.get(key, 0) + 1
    graph.add_weighted_edges_from((s, t, w) for (s, t), w in counts.items())
    graph.graph["name"] = "CLAID social interaction graph"
    return graph


def node_features(graph, frame, betweenness=None):
    """Per-node attribute matrix consumed by the Isolation Forest (doc 4.6).

    Attributes of a post (followers, likes, comments, sentiment, properties)
    are aggregated onto its source node; graph attributes are added on top.
    """
    props = parse_properties(frame)
    enriched = pd.concat(
        [frame.reset_index(drop=True), props.reset_index(drop=True)], axis=1
    )
    grouped = enriched.groupby("SOURCE")
    features = pd.DataFrame(index=sorted(graph.nodes()))
    features.index.name = "node"

    def take(series, name, default=0.0):
        column = series.reindex(features.index).astype(float).fillna(default)
        features[name] = column

    take(grouped.size(), "posts")
    aggregations = (
        ("FOLLOWERS", (("followers_mean", "mean"), ("followers_max", "max"))),
        ("LIKES", (("likes_mean", "mean"), ("likes_sum", "sum"))),
        ("COMMENTS", (("comments_mean", "mean"), ("comments_sum", "sum"))),
        ("LINK_SENTIMENT", (("sentiment_mean", "mean"),)),
        ("properties_mean", (("properties_mean", "mean"),)),
        ("properties_std", (("properties_std", "mean"),)),
    )
    for column, wanted in aggregations:
        if column not in enriched.columns:
            continue
        grouped_column = enriched.groupby("SOURCE")[column]
        for name, how in wanted:
            take(grouped_column.agg(how), name)

    take(pd.Series(dict(graph.degree()), dtype=float), "degree")
    take(pd.Series(dict(graph.degree(weight="weight")), dtype=float), "weighted_degree")
    take(pd.Series(nx.degree_centrality(graph), dtype=float), "degree_centrality")
    take(pd.Series(nx.clustering(graph), dtype=float), "clustering")
    take(pd.Series(nx.pagerank(graph, weight="weight"), dtype=float), "pagerank")
    take(pd.Series(betweenness or {}, dtype=float), "betweenness")
    return features


def summary(graph, frame, dataset=None, clean_report=None):
    """Dataset/network description shown on the web dashboard (doc 4.3)."""
    degrees = [degree for _, degree in graph.degree()]
    components = sorted(
        (len(nodes) for nodes in nx.connected_components(graph)), reverse=True
    )
    dataset = dataset or "<in memory>"
    return {
        "dataset": os.path.basename(dataset),
        "rows": int(len(frame)),
        "nodes": int(graph.number_of_nodes()),
        "edges": int(graph.number_of_edges()),
        "components": len(components),
        "largest_component": components[0] if components else 0,
        "density": round(float(nx.density(graph)), 6),
        "average_degree": round(float(np.mean(degrees)) if degrees else 0.0, 3),
        "max_degree": int(max(degrees)) if degrees else 0,
        "isolated_nodes": int(sum(1 for degree in degrees if degree == 0)),
        "columns": list(frame.columns),
        "cleaning": clean_report or {},
    }

