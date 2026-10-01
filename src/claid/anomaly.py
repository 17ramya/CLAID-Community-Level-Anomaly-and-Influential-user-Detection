"""Module 2 - anomaly detection (doc 4.6: Isolation Forest).

Two detectors are provided:

``isolation_forest``
    The algorithm named in the report: it splits the (pre-processed) feature
    space at random and scores every point by its average path length.  It is
    applied both to individual nodes and, as described in doc 4.6, to whole
    communities ("identifying anomalous communities based on their deviation
    from normal behaviour").

``degree_rule``
    The reference rule drawn in doc figure 8 and implemented in the original
    notebook: degree centrality greater than mean + ``sigma`` * standard
    deviation marks a node as anomalous.  It is used as the reference labels
    against which Isolation Forest is scored (doc 5.2.5).
"""
from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from . import config


def _matrix(features):
    """Standardise the feature table for the forest."""
    values = features.select_dtypes(include=[np.number]).fillna(0.0)
    values = values.loc[:, values.std(axis=0) > 0]  # drop constant columns
    if values.empty:
        return np.zeros((len(features), 1)), values.columns
    return StandardScaler().fit_transform(values.values), values.columns


def isolation_forest(
    features,
    contamination=None,
    n_estimators=None,
    seed=None,
    score_column="score",
):
    """Fit an Isolation Forest and return per-row scores and flags.

    Returns a DataFrame indexed like ``features`` with ``score`` (higher means
    more anomalous), ``anomaly_score`` (0-1, as described in doc 4.6) and
    ``is_anomaly``.
    """
    contamination = config.IFOREST_CONTAMINATION if contamination is None else contamination
    n_estimators = config.IFOREST_N_ESTIMATORS if n_estimators is None else n_estimators
    seed = config.IFOREST_RANDOM_STATE if seed is None else seed
    matrix, columns = _matrix(features)
    contamination = float(min(max(contamination, 0.0001), 0.4999))

    model = IsolationForest(
        n_estimators=int(n_estimators),
        contamination=contamination,
        random_state=int(seed),
        n_jobs=1,
    )
    model.fit(matrix)
    raw = -model.score_samples(matrix)  # higher = more anomalous
    span = raw.max() - raw.min()
    normalised = (raw - raw.min()) / span if span > 0 else np.zeros_like(raw)
    frame = pd.DataFrame(index=features.index)
    frame["score"] = raw
    frame["anomaly_score"] = normalised
    frame["is_anomaly"] = model.predict(matrix) == -1
    frame.attrs["n_features"] = len(columns)
    frame.attrs["features"] = list(columns)
    frame.attrs["contamination"] = contamination
    return frame


def community_features(features, assignment):
    """Aggregate node features per community (doc 4.6: communities as points)."""
    grouped = features.copy()
    grouped["community"] = pd.Series(assignment).reindex(grouped.index).fillna(-1).astype(int)
    aggregated = grouped.groupby("community").mean()
    aggregated["members"] = grouped.groupby("community").size()
    aggregated.attrs["groups"] = {
        int(cid): sorted(members.index) for cid, members in grouped.groupby("community")
    }
    return aggregated


def degree_rule(graph, sigma=None):
    """Reference anomaly rule from doc figure 8: mean + sigma * std of degree centrality."""
    sigma = config.DEGREE_SIGMA if sigma is None else sigma
    centrality = nx.degree_centrality(graph)
    values = np.array(list(centrality.values()), dtype=float)
    mean = float(values.mean())
    std = float(values.std())
    threshold = mean + sigma * std
    flagged = {node for node, value in centrality.items() if value > threshold}
    return {
        "threshold": threshold,
        "mean": mean,
        "std": std,
        "sigma": sigma,
        "centrality": centrality,
        "anomalies": flagged,
    }


def describe_node_anomalies(graph, scores, assignment, features, top=25):
    """Rows for the anomaly table on the web dashboard."""
    ranked = scores.sort_values("score", ascending=False)
    rows = []
    for node, row in ranked.head(top).iterrows():
        rows.append(
            {
                "node": str(node),
                "score": round(float(row["score"]), 5),
                "anomaly_score": round(float(row["anomaly_score"]), 4),
                "is_anomaly": bool(row["is_anomaly"]),
                "community": int(assignment.get(node, -1)),
                "degree": int(features.at[node, "degree"]) if "degree" in features else 0,
                "followers_mean": round(float(features.at[node, "followers_mean"]), 2)
                if "followers_mean" in features
                else 0.0,
                "likes_sum": int(features.at[node, "likes_sum"])
                if "likes_sum" in features
                else 0,
                "comments_sum": int(features.at[node, "comments_sum"])
                if "comments_sum" in features
                else 0,
            }
        )
    return rows
