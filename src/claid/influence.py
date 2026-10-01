"""Module 3 - influential user detection (doc 4.7: betweenness centrality).

Doc 4.7: "The influential user detection process begins by inputting
non-anomalous communities into the algorithm ... and compiles a list of
influential users for each community."  Betweenness is therefore computed on
each community subgraph, exactly as the pseudo-code in doc 4.7.1 describes
(breadth-first shortest paths, dependency accumulation, undirected /2).
"""
from __future__ import annotations

import networkx as nx

from . import config


def global_betweenness(graph, exact_max=None, sample_k=None, seed=None):
    """Betweenness centrality for the whole graph, exact when affordable.

    Returns ``(scores, exact)``; for graphs above
    ``config.BETWEENNESS_EXACT_MAX_NODES`` an ``k``-source estimate is used
    because exact Brandes betweenness is O(n*m).
    """
    nodes = graph.number_of_nodes()
    if nodes == 0:
        return {}, True
    exact_max = config.BETWEENNESS_EXACT_MAX_NODES if exact_max is None else exact_max
    if nodes <= exact_max:
        return nx.betweenness_centrality(graph, normalized=True), True
    sample = min(config.BETWEENNESS_SAMPLE_K if sample_k is None else sample_k, nodes)
    scores = nx.betweenness_centrality(
        graph, k=sample, seed=seed or config.LOUVAIN_RANDOM_STATE, normalized=True
    )
    return scores, False


def community_betweenness(graph, members):
    """Betweenness centrality inside one community (doc 4.7.1).

    Returns ``(scores, metric_name)``.  Communities with fewer than three nodes
    have no shortest path between two other nodes, so degree centrality is used
    as a documented fallback.
    """
    subgraph = graph.subgraph(list(members))
    if subgraph.number_of_nodes() < 3:
        return nx.degree_centrality(subgraph), "degree centrality (community too small for paths)"
    return nx.betweenness_centrality(subgraph, normalized=True), "betweenness centrality"


def influencers(graph, assignment, anomalous_communities=(), top=None):
    """Rank users by betweenness inside every non-anomalous community (doc 4.7)."""
    top = config.TOP_INFLUENCERS if top is None else top
    excluded = set(anomalous_communities)
    groups = {}
    for node, cid in assignment.items():
        groups.setdefault(cid, set()).add(node)

    per_community, skipped = [], []
    for cid in sorted(groups):
        members = groups[cid]
        if cid in excluded:
            skipped.append(
                {
                    "community": cid,
                    "size": len(members),
                    "reason": "community flagged anomalous by doc 4.6 (excluded per doc 4.7)",
                }
            )
            continue
        scores, metric = community_betweenness(graph, members)
        ordered = sorted(scores.items(), key=lambda item: (-item[1], str(item[0])))
        per_community.append(
            {
                "community": cid,
                "size": len(members),
                "metric": metric,
                "influential_user": ordered[0][0] if ordered else None,
                "influential_score": round(float(ordered[0][1]), 6) if ordered else 0.0,
                "top": [
                    {
                        "node": str(node),
                        "score": round(float(score), 6),
                        "degree": int(graph.degree(node)),
                    }
                    for node, score in ordered[:top]
                ],
            }
        )
    return per_community, skipped


def ranked_users(graph, scores, top=25):
    """Global ranking used by the dashboard and the JSON API."""
    ordered = sorted(scores.items(), key=lambda item: (-item[1], str(item[0])))[:top]
    return [
        {
            "node": str(node),
            "score": round(float(score), 6),
            "degree": int(graph.degree(node)),
            "weighted_degree": int(graph.degree(node, weight="weight")),
        }
        for node, score in ordered
    ]


def degree_baseline(graph, top=None):
    """Top-k nodes by degree centrality - the reference ranking for doc 5.2.5."""
    top = config.TOP_INFLUENCERS if top is None else top
    centrality = nx.degree_centrality(graph)
    ranking = sorted(centrality.items(), key=lambda item: (-item[1], str(item[0])))
    return {node for node, _ in ranking[:top]}, centrality


def closeness_baseline(graph, top=None):
    """Top-k nodes by closeness centrality - the second comparison method."""
    top = config.TOP_INFLUENCERS if top is None else top
    centrality = nx.closeness_centrality(graph)
    ranking = sorted(centrality.items(), key=lambda item: (-item[1], str(item[0])))
    return {node for node, _ in ranking[:top]}, centrality
