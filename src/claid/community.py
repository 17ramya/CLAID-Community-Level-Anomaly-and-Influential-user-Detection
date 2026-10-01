"""Module 1 - community detection (doc 4.5: Louvain modularity).

The report selects Louvain modularity and benchmarks it against the other
community algorithms the notebook exercised, so all of them are exposed here
through one interface (:func:`detect`).
"""
from __future__ import annotations

import networkx as nx
from networkx.algorithms import community as nx_community

from . import config

try:  # python-louvain ships the reference implementation used in doc 4.5
    import community as community_louvain
except ImportError:  # pragma: no cover - optional dependency
    community_louvain = None

METHODS = config.COMMUNITY_COMPARISON_METHODS


def _partition_to_assignment(partition):
    """python-louvain returns {node: community_id}; normalise it."""
    return {node: int(cid) for node, cid in partition.items()}


def _groups_to_assignment(groups):
    assignment = {}
    for cid, members in enumerate(groups):
        for node in members:
            assignment[node] = cid
    return assignment


def louvain(graph, resolution=None, seed=None):
    """Louvain modularity - the algorithm chosen for CLAID (doc 4.5)."""
    resolution = config.LOUVAIN_RESOLUTION if resolution is None else resolution
    seed = config.LOUVAIN_RANDOM_STATE if seed is None else seed
    if community_louvain is not None:
        partition = community_louvain.best_partition(
            graph, weight="weight", resolution=resolution, random_state=seed
        )
        assignment = _partition_to_assignment(partition)
    else:  # NetworkX 3.x fallback with the same semantics
        assignment = _groups_to_assignment(
            nx_community.louvain_communities(
                graph, weight="weight", resolution=resolution, seed=seed
            )
        )
    return _result("Louvain Modularity", assignment)


def greedy_modularity(graph, resolution=None, seed=None):
    """Greedy modularity maximisation (the notebook's modularity baseline)."""
    resolution = config.LOUVAIN_RESOLUTION if resolution is None else resolution
    groups = list(
        nx_community.greedy_modularity_communities(
            graph, weight="weight", resolution=resolution
        )
    )
    return _result("Greedy Modularity", _groups_to_assignment(groups))


def label_propagation(graph, resolution=None, seed=None):
    """Asynchronous label propagation (notebook markdown section 4)."""
    groups = list(nx_community.label_propagation_communities(graph, weight="weight"))
    return _result("Label Propagation", _groups_to_assignment(groups))


def edge_betweenness(graph, resolution=None, seed=None, max_nodes=None, max_levels=4):
    """Girvan-Newman edge betweenness (doc 4.5 alternative).

    Girvan-Newman is O(n*m^2), so it runs on the densest subgraph that fits in
    ``config.MAX_GIRVAN_NEWMAN_NODES`` and stops after ``max_levels`` levels.
    Nodes outside that subgraph become their own singleton community.
    """
    max_nodes = max_nodes or config.MAX_GIRVAN_NEWMAN_NODES
    if graph.number_of_nodes() > max_nodes:
        ranked = sorted(graph.degree(), key=lambda item: -item[1])[:max_nodes]
        subgraph = graph.subgraph([node for node, _ in ranked]).copy()
        sampled = True
    else:
        subgraph = graph
        sampled = False
    assignment = {}
    best = None
    try:
        levels = nx_community.girvan_newman(subgraph)
        for _ in range(max_levels):
            candidate = _groups_to_assignment(next(levels))
            score = modularity(subgraph, candidate)
            if best is None or score > best[1]:
                best = (candidate, score)
    except StopIteration:
        pass
    if best is not None:
        assignment = best[0]
    for node in graph.nodes():
        assignment.setdefault(node, -1)  # 0..len(best)-1 are taken, -1 is free
    result = _result("Edge Betweenness", assignment)
    result["sampled_subgraph"] = sampled
    result["subgraph_nodes"] = subgraph.number_of_nodes()
    return result


def detect(graph, method="Louvain Modularity", resolution=None, seed=None):
    """Dispatch to one of the four community detection methods."""
    lookup = {
        "Louvain Modularity": louvain,
        "Greedy Modularity": greedy_modularity,
        "Label Propagation": label_propagation,
        "Edge Betweenness": edge_betweenness,
    }
    key = method if method in lookup else "Louvain Modularity"
    return lookup[key](graph, resolution=resolution, seed=seed)


def _result(method, assignment):
    groups = {}
    for node, cid in assignment.items():
        groups.setdefault(cid, set()).add(node)
    ordered = sorted(groups.values(), key=lambda members: (-len(members), min(members)))
    entries = [{"id": cid, "nodes": sorted(members)} for cid, members in enumerate(ordered)]
    relabelled = {}
    for entry in entries:
        for node in entry["nodes"]:
            relabelled[node] = entry["id"]
    return {
        "method": method,
        "assignment": relabelled,
        "communities": entries,
        "num_communities": len(entries),
        "sizes": [len(entry["nodes"]) for entry in entries],
    }


def modularity(graph, assignment):
    """Newman modularity of a {node: community} assignment (doc 4.5)."""
    groups = {}
    for node, cid in assignment.items():
        groups.setdefault(cid, set()).add(node)
    if len(groups) < 2:
        return 0.0
    return float(nx_community.modularity(graph, list(groups.values()), weight="weight"))


def describe(graph, assignment, top_nodes=20):
    """Per-community statistics for the web dashboard."""
    groups = {}
    for node, cid in assignment.items():
        groups.setdefault(cid, set()).add(node)
    described = []
    for cid in sorted(groups, key=lambda c: (-len(groups[c]), c)):
        members = groups[cid]
        subgraph = graph.subgraph(members)
        internal_weight = subgraph.size(weight="weight")
        volume = sum(dict(graph.degree(members, weight="weight")).values())
        described.append(
            {
                "id": cid,
                "size": len(members),
                "internal_edges": int(subgraph.number_of_edges()),
                "internal_weight": float(internal_weight),
                "cut_weight": float(volume - 2 * internal_weight),
                "density": round(float(nx.density(subgraph)), 5) if len(members) > 1 else 0.0,
                "top_nodes": [
                    node
                    for node, _ in sorted(graph.degree(members), key=lambda item: -item[1])[
                        :top_nodes
                    ]
                ],
                "members_preview": sorted(members)[:top_nodes],
            }
        )
    return described

