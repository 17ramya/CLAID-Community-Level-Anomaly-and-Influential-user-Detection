"""Evaluation metrics (doc 5.2.5: precision, recall and F1 score).

The shipped dataset carries no ground-truth labels, so - exactly like the
notebook, which used a hand-written ``ground_truth_communities`` list - the
scores here are computed against *reference* labels:

* community detection -> the Louvain partition (the method chosen in doc 4.5),
  plus the label-free modularity and ARI/NMI agreement;
* anomaly detection   -> the doc figure 8 degree-centrality rule;
* influential users   -> the top-k degree-centrality ranking.

If real labels become available, pass them to :func:`label_metrics` (the rest of
the framework is unchanged).
"""
from __future__ import annotations

from sklearn.metrics import (
    adjusted_rand_score,
    f1_score,
    normalized_mutual_info_score,
    precision_score,
    recall_score,
)

HEADERS = ("module", "method", "reference", "precision", "recall", "f1", "note")


def label_metrics(y_true, y_pred, average="weighted"):
    """Precision / recall / F1 for two label sequences (doc 5.2.5)."""
    if len(y_true) == 0 or len(y_true) != len(y_pred):
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    return {
        "precision": float(precision_score(y_true, y_pred, average=average, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, average=average, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, average=average, zero_division=0)),
    }


def partition_agreement(assignment_a, assignment_b, nodes=None):
    """ARI and NMI between two {node: community} maps (label-free agreement)."""
    nodes = list(nodes) if nodes is not None else sorted(set(assignment_a) & set(assignment_b))
    left = [assignment_a.get(node, -1) for node in nodes]
    right = [assignment_b.get(node, -1) for node in nodes]
    if len(nodes) < 2:
        return {"ari": 0.0, "nmi": 0.0}
    return {
        "ari": float(adjusted_rand_score(left, right)),
        "nmi": float(normalized_mutual_info_score(left, right)),
    }


def topk_metrics(reference, candidate, universe_size=None):
    """Precision / recall / F1 of one top-k node set against another.

    Both sets are treated as positive predictions over the whole node universe.
    """
    reference, candidate = set(reference), set(candidate)
    universe_size = universe_size or max(len(reference | candidate), 1)
    true_positive = len(reference & candidate)
    precision = true_positive / len(candidate) if candidate else 0.0
    recall = true_positive / len(reference) if reference else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "overlap": true_positive,
        "reference_size": len(reference),
        "candidate_size": len(candidate),
        "universe": int(universe_size),
    }


def row(module, method, reference, metrics, note=""):
    """One line of the comparison table shown on the results page."""
    return {
        "module": module,
        "method": method,
        "reference": reference,
        "precision": round(float(metrics.get("precision", 0.0)), 4),
        "recall": round(float(metrics.get("recall", 0.0)), 4),
        "f1": round(float(metrics.get("f1", 0.0)), 4),
        "note": note,
    }
