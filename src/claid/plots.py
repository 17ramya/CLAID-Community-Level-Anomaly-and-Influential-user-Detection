"""Matplotlib rendering for the CLAID web application (doc 4.4.3).

Every function writes a PNG into the run directory and returns its file name,
so the Flask layer only needs to serve static file names.
"""
from __future__ import annotations

from collections import Counter

import matplotlib

matplotlib.use("Agg")  # headless rendering: the Flask process never opens a window
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402

from . import config  # noqa: E402

COMMUNITY_CMAP = plt.cm.tab20
NORMAL_COLOUR = "#c9d3e0"
ANOMALY_COLOUR = "#e5484d"
INFLUENCER_COLOUR = "#f5a524"
FOCUS_COLOUR = "#2e7dd7"


def _save(fig, out_dir, name):
    path = out_dir / name
    fig.savefig(path, dpi=config.PLOT_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return name


def plot_graph(graph, limit=None):
    """A readable subgraph: the biggest component, capped by node count."""
    limit = limit or config.MAX_PLOT_NODES
    if graph.number_of_nodes() <= limit:
        return graph
    largest = max(nx.connected_components(graph), key=len)
    subgraph = graph.subgraph(largest)
    if subgraph.number_of_nodes() <= limit:
        return subgraph.copy()
    ranked = sorted(subgraph.degree(weight="weight"), key=lambda item: -item[1])[:limit]
    return subgraph.subgraph([node for node, _ in ranked]).copy()


def _layout(subgraph):
    nodes = max(subgraph.number_of_nodes(), 1)
    iterations = 60 if nodes <= 150 else 30
    return nx.spring_layout(
        subgraph, seed=config.LOUVAIN_RANDOM_STATE, k=1.5 / nodes**0.5, iterations=iterations
    )


def _draw_base(axes, subgraph, positions):
    weights = [subgraph[u][v].get("weight", 1) for u, v in subgraph.edges()]
    nx.draw_networkx_edges(
        subgraph, positions, ax=axes, alpha=0.25, width=[0.4 + 0.25 * w for w in weights],
        edge_color="#8899aa",
    )


def plot_communities(graph, assignment, out_dir):
    """doc 5.2.1 - clusters formed with Louvain modularity."""
    subgraph = plot_graph(graph)
    positions = _layout(subgraph)
    colours = [
        COMMUNITY_CMAP(assignment.get(node, 0) % 20) for node in subgraph.nodes()
    ]
    sizes = [40 + 9 * subgraph.degree(node) for node in subgraph.nodes()]
    fig, axes = plt.subplots(figsize=config.FIGURE_SIZE)
    _draw_base(axes, subgraph, positions)
    nx.draw_networkx_nodes(
        subgraph, positions, ax=axes, node_color=colours, node_size=sizes,
        linewidths=0.4, edgecolors="white",
    )
    labels = {
        node: node
        for node, _ in sorted(subgraph.degree(), key=lambda item: -item[1])[:18]
    }
    nx.draw_networkx_labels(subgraph, positions, labels=labels, ax=axes, font_size=7)
    axes.set_title(
        "Community detection - Louvain modularity (%d nodes shown, %d communities)"
        % (subgraph.number_of_nodes(), len(set(assignment.values())))
    )
    axes.axis("off")
    return _save(fig, out_dir, "communities.png")


def plot_anomalies(graph, assignment, anomaly_nodes, out_dir, title="Anomaly detection - Isolation Forest"):
    """doc 5.2.2 - anomalous nodes isolated inside the communities."""
    flagged = set(anomaly_nodes)
    subgraph = plot_graph(graph)
    positions = _layout(subgraph)
    normal = [node for node in subgraph.nodes() if node not in flagged]
    marked = [node for node in subgraph.nodes() if node in flagged]
    fig, axes = plt.subplots(figsize=config.FIGURE_SIZE)
    _draw_base(axes, subgraph, positions)
    if normal:
        nx.draw_networkx_nodes(
            subgraph, positions, nodelist=normal, ax=axes, node_color=NORMAL_COLOUR,
            node_size=45, linewidths=0.3, edgecolors="white",
        )
    if marked:
        nx.draw_networkx_nodes(
            subgraph, positions, nodelist=marked, ax=axes, node_color=ANOMALY_COLOUR,
            node_size=190, linewidths=0.6, edgecolors="#7a1c1f",
        )
        labels = {
            node: node for node in sorted(marked, key=lambda n: -subgraph.degree(n))[:15]
        }
        nx.draw_networkx_labels(subgraph, positions, labels=labels, ax=axes, font_size=7)
    axes.set_title(
        "%s - %d anomalous node(s) of %d shown" % (title, len(marked), subgraph.number_of_nodes())
    )
    axes.axis("off")
    return _save(fig, out_dir, "anomalies.png")


def plot_influencers(graph, assignment, per_community, out_dir):
    """doc 5.2.3 - most influential user of each non-anomalous community."""
    subgraph = plot_graph(graph)
    positions = _layout(subgraph)
    influencers = {
        entry["influential_user"]: entry["community"]
        for entry in per_community
        if entry.get("influential_user")
    }
    colours = [
        INFLUENCER_COLOUR
        if node in influencers
        else COMMUNITY_CMAP(assignment.get(node, 0) % 20)
        for node in subgraph.nodes()
    ]
    sizes = [
        190 if node in influencers else 40 + 7 * subgraph.degree(node)
        for node in subgraph.nodes()
    ]
    fig, axes = plt.subplots(figsize=config.FIGURE_SIZE)
    _draw_base(axes, subgraph, positions)
    nx.draw_networkx_nodes(
        subgraph, positions, ax=axes, node_color=colours, node_size=sizes,
        linewidths=0.5, edgecolors="white",
    )
    shown = {node: node for node in influencers if node in subgraph}
    nx.draw_networkx_labels(
        subgraph, positions, labels=shown, ax=axes, font_size=8,
        font_color="#7a4a00", font_weight="bold",
    )
    axes.set_title(
        "Influential users - betweenness centrality (%d communities analysed)" % len(influencers)
    )
    axes.axis("off")
    return _save(fig, out_dir, "influencers.png")


def plot_focus(graph, assignment, source, focus, out_dir):
    """doc 5.2.4 - source node, its interacting communities, anomalies, influencers."""
    members = {source}
    for entry in (focus or {}).get("communities", []):
        members.update(entry.get("members_preview", []))
    for entry in (focus or {}).get("neighbours", []):
        members.add(entry.get("node"))
    members = [node for node in members if node in graph]
    subgraph = plot_graph(graph.subgraph(members)) if members else plot_graph(graph)
    positions = _layout(subgraph)
    anomalies = set((focus or {}).get("anomaly_nodes", []))
    influencers = set((focus or {}).get("influential_users", []))
    colours, sizes = [], []
    for node in subgraph.nodes():
        if node == source:
            colours.append(FOCUS_COLOUR)
            sizes.append(420)
        elif node in anomalies:
            colours.append(ANOMALY_COLOUR)
            sizes.append(210)
        elif node in influencers:
            colours.append(INFLUENCER_COLOUR)
            sizes.append(180)
        else:
            colours.append(COMMUNITY_CMAP(assignment.get(node, 0) % 20))
            sizes.append(70)
    fig, axes = plt.subplots(figsize=config.FIGURE_SIZE)
    _draw_base(axes, subgraph, positions)
    nx.draw_networkx_nodes(
        subgraph, positions, ax=axes, node_color=colours, node_size=sizes,
        linewidths=0.5, edgecolors="white",
    )
    nx.draw_networkx_labels(subgraph, positions, ax=axes, font_size=7)
    axes.set_title(
        "Source node '%s' - interacting communities, anomalies, influencers" % source
    )
    axes.axis("off")
    return _save(fig, out_dir, "focus.png")


def plot_metrics(rows, out_dir):
    """doc 5.2.5 - precision / recall / F1 comparison for every method."""
    modules = []
    for row in rows:
        if row["module"] not in modules:
            modules.append(row["module"])
    if not modules:
        return None
    fig, axes = plt.subplots(
        1, len(modules), figsize=(4.7 * len(modules), 4.8), squeeze=False
    )
    width = 0.26
    for index, module in enumerate(modules):
        module_rows = [row for row in rows if row["module"] == module]
        positions = list(range(len(module_rows)))
        axes_handle = axes[0][index]
        for offset, metric, colour in (
            (-width, "precision", "#2e7dd7"),
            (0.0, "recall", "#2fa36b"),
            (width, "f1", "#f5a524"),
        ):
            axes_handle.bar(
                [position + offset for position in positions],
                [row[metric] for row in module_rows],
                width=width,
                label=metric.capitalize(),
                color=colour,
            )
        axes_handle.set_xticks(positions)
        axes_handle.set_xticklabels(
            [row["method"] for row in module_rows], fontsize=8, rotation=18, ha="right"
        )
        axes_handle.set_ylim(0, 1.05)
        axes_handle.set_title(module, fontsize=10)
        axes_handle.grid(axis="y", alpha=0.25)
        axes_handle.legend(fontsize=7)
        if index == 0:
            axes_handle.set_ylabel("score")
    fig.suptitle("Evaluation metrics (doc 5.2.5) - reference based, weighted average", fontsize=11)
    return _save(fig, out_dir, "metrics.png")


def plot_distributions(graph, assignment, out_dir):
    """Degree distribution and community size distribution of the network."""
    degrees = sorted((degree for _, degree in graph.degree()), reverse=True)
    sizes = sorted(Counter(assignment.values()).values(), reverse=True)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
    axes[0].hist(degrees, bins=30, color="#2e7dd7", alpha=0.85)
    axes[0].set_yscale("log")
    axes[0].set_title("Degree distribution")
    axes[0].set_xlabel("degree")
    axes[0].set_ylabel("nodes (log scale)")
    axes[0].grid(alpha=0.25)
    shown = sizes[:40]
    axes[1].bar(range(1, len(shown) + 1), shown, color="#2fa36b")
    axes[1].set_title("Community sizes (largest 40)")
    axes[1].set_xlabel("community rank")
    axes[1].set_ylabel("nodes")
    axes[1].grid(axis="y", alpha=0.25)
    fig.tight_layout()
    return _save(fig, out_dir, "distributions.png")


