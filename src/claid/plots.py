"""Matplotlib rendering for the CLAID web application (doc 4.4.3).

Every function writes a PNG into the run directory and returns its file name, so
the Flask layer only ever serves a static file name.

All figures share one visual language - the ``THEME`` below and the palette that
the stylesheet also uses - so a results page reads as a single report instead of
a pile of unrelated images.
"""
from __future__ import annotations

from collections import Counter

import matplotlib

matplotlib.use("Agg")  # headless rendering: the Flask process never opens a window
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from . import config  # noqa: E402

# --- palette: the same tokens the stylesheet uses -------------------------- #
INK = "#10192b"
MUTED = "#5b6b83"
GRID = "#e3e8f0"
BLUE = "#2563eb"
TEAL = "#0f766e"
AMBER = "#f59e0b"
RED = "#dc2626"
VIOLET = "#7c3aed"

COMMUNITY_COLOURS = (
    BLUE, TEAL, AMBER, VIOLET, "#0891b2", "#db2777", "#65a30d", "#ea580c",
    "#4f46e5", "#0d9488", "#b45309", "#9333ea", "#0284c7", "#be123c",
    "#15803d", "#c2410c", "#4338ca", "#0e7490", "#a21caf", "#1d4ed8",
)
COMMUNITY_CMAP = ListedColormap(COMMUNITY_COLOURS)

NORMAL_COLOUR = "#cbd5e1"
ANOMALY_COLOUR = RED
INFLUENCER_COLOUR = AMBER
FOCUS_COLOUR = BLUE

THEME = {
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "font.family": "DejaVu Sans",
    "font.size": 9.5,
    "axes.titlesize": 11.5,
    "axes.titlelocation": "left",
    "axes.titlepad": 9,
    "axes.labelsize": 9.5,
    "axes.labelcolor": MUTED,
    "axes.edgecolor": GRID,
    "axes.linewidth": 0.8,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "legend.frameon": False,
    "legend.fontsize": 8.5,
}
plt.rcParams.update(THEME)


# --- shared helpers -------------------------------------------------------- #
def _save(fig, out_dir, name):
    path = out_dir / name
    fig.savefig(path, dpi=config.PLOT_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return name


def _caption(fig, text):
    """One small line under the figure explaining how to read it.

    Placed below the axes (a figure-level text at a negative y) so it can never
    collide with an x-axis label; ``bbox_inches="tight"`` still keeps it.
    """
    fig.text(0.005, -0.06, text, ha="left", va="top", fontsize=8.3, color=MUTED)


def _despine(axes, keep=("left", "bottom")):
    for side in ("top", "right", "left", "bottom"):
        axes.spines[side].set_visible(side in keep)


def _value_labels(axes, bars, fmt="%.2f", fontsize=7.8, color=INK):
    """Print each bar's value above it - charts should not need a ruler."""
    for bar in bars:
        height = bar.get_height()
        if height is None or height <= 0:
            continue
        axes.annotate(
            fmt % height,
            (bar.get_x() + bar.get_width() / 2.0, height),
            xytext=(0, 2.5), textcoords="offset points",
            ha="center", va="bottom", fontsize=fontsize, color=color,
        )


def _network_legend(axes, entries, location="lower left"):
    """Colour key for the network figures, so they read like a map."""
    handles = [Patch(facecolor=colour, edgecolor="white", label=label)
               for colour, label in entries]
    axes.legend(handles=handles, loc=location, fontsize=8.2, handlelength=1.1,
                borderpad=0.2, labelspacing=0.45)


def _subgraph_title(count, total, noun="nodes"):
    if count < total:
        return "%s %s of %s shown for legibility" % ("{:,}".format(count), noun,
                                                     "{:,}".format(total))
    return "all %s shown" % ("{:,}".format(total), noun)


# --- graph preparation ----------------------------------------------------- #
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
        subgraph, positions, ax=axes, alpha=0.22,
        width=[0.4 + 0.22 * w for w in weights], edge_color="#94a3b8",
    )


def plot_communities(graph, assignment, out_dir):
    """doc 5.2.1 - the clusters formed with Louvain modularity."""
    subgraph = plot_graph(graph)
    positions = _layout(subgraph)
    communities = sorted({assignment.get(node, 0) for node in subgraph.nodes()})
    colours = [COMMUNITY_CMAP(assignment.get(node, 0) % len(COMMUNITY_COLOURS))
               for node in subgraph.nodes()]
    sizes = [35 + 9 * subgraph.degree(node) for node in subgraph.nodes()]
    fig, axes = plt.subplots(figsize=config.FIGURE_SIZE)
    _draw_base(axes, subgraph, positions)
    nx.draw_networkx_nodes(
        subgraph, positions, ax=axes, node_color=colours, node_size=sizes,
        linewidths=0.5, edgecolors="white",
    )
    labelled = {node: node for node, _ in sorted(subgraph.degree(), key=lambda item: -item[1])[:12]}
    nx.draw_networkx_labels(subgraph, positions, labels=labelled, ax=axes,
                            font_size=7, font_color=INK,
                            bbox=dict(boxstyle="round,pad=0.12", facecolor="white",
                                      edgecolor="none", alpha=.75))
    axes.set_title("Communities found by Louvain modularity")
    axes.axis("off")
    _network_legend(axes, [(COMMUNITY_COLOURS[index % len(COMMUNITY_COLOURS)],
                            "community #%d" % cid) for index, cid in enumerate(communities[:5])])
    _caption(fig, "%s. Node size grows with degree, so hubs are visible at a glance."
             % _subgraph_title(subgraph.number_of_nodes(), graph.number_of_nodes()))
    return _save(fig, out_dir, "communities.png")


def plot_anomalies(graph, assignment, anomaly_nodes, out_dir,
                   title="Anomalous nodes found by the Isolation Forest"):
    """doc 5.2.2 - anomalous users picked out of their communities."""
    flagged = set(anomaly_nodes)
    subgraph = plot_graph(graph)
    positions = _layout(subgraph)
    normal = [node for node in subgraph.nodes() if node not in flagged]
    marked = [node for node in subgraph.nodes() if node in flagged]
    fig, axes = plt.subplots(figsize=config.FIGURE_SIZE)
    _draw_base(axes, subgraph, positions)
    if normal:
        nx.draw_networkx_nodes(subgraph, positions, ax=axes, nodelist=normal,
                               node_color=NORMAL_COLOUR, node_size=26, linewidths=0.0)
    if marked:
        nx.draw_networkx_nodes(subgraph, positions, ax=axes, nodelist=marked,
                               node_color=ANOMALY_COLOUR, node_size=110,
                               linewidths=0.7, edgecolors="white")
        nx.draw_networkx_labels(subgraph, positions, ax=axes, font_size=7,
                                font_color=INK,
                                labels={node: node for node in marked[:24]})
    axes.set_title(title)
    axes.axis("off")
    _network_legend(axes, [
        (ANOMALY_COLOUR, "flagged node (%d in the whole graph)" % len(flagged)),
        (NORMAL_COLOUR, "regular node"),
    ])
    _caption(fig, "%s. Scores and the reference rule are listed in the tables below."
             % _subgraph_title(subgraph.number_of_nodes(), graph.number_of_nodes()))
    return _save(fig, out_dir, "anomalies.png")


def plot_influencers(graph, assignment, per_community, out_dir):
    """doc 5.2.3 - the most influential user of every non-anomalous community."""
    subgraph = plot_graph(graph)
    positions = _layout(subgraph)
    influencers = {entry["influential_user"] for entry in per_community}
    colours, sizes = [], []
    for node in subgraph.nodes():
        if node in influencers:
            colours.append(INFLUENCER_COLOUR)
            sizes.append(230)
        else:
            colours.append(COMMUNITY_CMAP(assignment.get(node, 0) % len(COMMUNITY_COLOURS)))
            sizes.append(26)
    fig, axes = plt.subplots(figsize=config.FIGURE_SIZE)
    _draw_base(axes, subgraph, positions)
    nx.draw_networkx_nodes(subgraph, positions, ax=axes, node_color=colours,
                           node_size=sizes, linewidths=0.7, edgecolors="white")
    shown = [node for node in subgraph.nodes() if node in influencers][:20]
    if shown:
        nx.draw_networkx_labels(subgraph, positions, ax=axes, font_size=7.5,
                                font_color=INK, labels={node: node for node in shown})
    axes.set_title("Influential users - betweenness centrality per community")
    axes.axis("off")
    _network_legend(axes, [
        (INFLUENCER_COLOUR, "community influencer (%d found)" % len(per_community)),
        ("#cbd5e1", "node coloured by community"),
    ])
    _caption(fig, "%s. One leader is reported per healthy community (doc 4.7); "
                  "anomalous communities are excluded."
             % _subgraph_title(subgraph.number_of_nodes(), graph.number_of_nodes()))
    return _save(fig, out_dir, "influencers.png")


def plot_focus(graph, assignment, source, focus, out_dir):
    """doc 5.2.4 - the source node, its communities, their anomalies and leaders."""
    members = {source}
    for entry in (focus or {}).get("neighbours", []):
        if entry.get("node") is not None:
            members.add(entry["node"])
    for entry in (focus or {}).get("communities", []):
        for key in ("nodes", "members", "members_preview"):
            for node in entry.get(key) or []:
                members.add(node)
    members = [node for node in members if node in graph]
    subgraph = plot_graph(graph.subgraph(members)) if members else plot_graph(graph)
    positions = _layout(subgraph)
    anomalies = set((focus or {}).get("anomaly_nodes", []))
    influencers = {
        entry["influential_user"]
        for entry in (focus or {}).get("communities", [])
        if entry.get("influential_user")
    }
    colours, sizes = [], []
    for node in subgraph.nodes():
        if node == source:
            colours.append(FOCUS_COLOUR)
            sizes.append(420)
        elif node in anomalies:
            colours.append(ANOMALY_COLOUR)
            sizes.append(170)
        elif node in influencers:
            colours.append(INFLUENCER_COLOUR)
            sizes.append(150)
        else:
            colours.append(COMMUNITY_CMAP(assignment.get(node, 0) % len(COMMUNITY_COLOURS)))
            sizes.append(55)
    fig, axes = plt.subplots(figsize=config.FIGURE_SIZE)
    _draw_base(axes, subgraph, positions)
    nx.draw_networkx_nodes(subgraph, positions, ax=axes, node_color=colours,
                           node_size=sizes, linewidths=0.7, edgecolors="white")
    important = [node for node in subgraph.nodes()
                 if node == source or node in anomalies or node in influencers][:24]
    if important:
        nx.draw_networkx_labels(subgraph, positions, ax=axes, font_size=7, font_color=INK,
                                labels={node: node for node in important},
                                bbox=dict(boxstyle="round,pad=0.12", facecolor="white",
                                          edgecolor="none", alpha=.75))
    axes.set_title("Source node '%s' - interacting communities at a glance" % source)
    axes.axis("off")
    _network_legend(axes, [
        (FOCUS_COLOUR, "source node '%s'" % source),
        (ANOMALY_COLOUR, "anomalous neighbour"),
        (INFLUENCER_COLOUR, "community influencer"),
        ("#cbd5e1", "other member (coloured by community)"),
    ])
    _caption(fig, "%d nodes reachable from '%s' through its own and neighbouring "
                  "communities (doc 5.2.4)." % (subgraph.number_of_nodes(), source))
    return _save(fig, out_dir, "focus.png")


def _wrap(label, width=13):
    """Wrap a method name so axis labels stay readable."""
    lines, current = [], ""
    for word in str(label).split():
        candidate = (current + " " + word).strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines)


def plot_metrics(rows, out_dir):
    """doc 5.2.5 - precision / recall / F1 for every method and module."""
    modules = []
    for row in rows:
        if row["module"] not in modules:
            modules.append(row["module"])
    if not modules:
        return None
    fig, grid = plt.subplots(1, len(modules), figsize=(5.0 * len(modules), 4.7), squeeze=False)
    width = 0.26
    series = (("precision", BLUE), ("recall", TEAL), ("f1", AMBER))
    for index, module in enumerate(modules):
        axes = grid[0][index]
        module_rows = [row for row in rows if row["module"] == module]
        positions = list(range(len(module_rows)))
        for offset, (metric, colour) in zip((-width, 0.0, width), series):
            bars = axes.bar(
                [position + offset for position in positions],
                [row[metric] for row in module_rows],
                width=width, label=metric.capitalize(), color=colour, zorder=3,
            )
            _value_labels(axes, bars, fontsize=6.8)
        axes.set_xticks(positions)
        axes.set_xticklabels([_wrap(row["method"]) for row in module_rows], fontsize=7.4)
        axes.set_ylim(0, 1.14)
        axes.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        axes.set_title(module)
        _despine(axes)
        axes.grid(axis="y", zorder=0)
        if index == 0:
            axes.set_ylabel("score")
    handles, labels = grid[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=3, loc="upper right", bbox_to_anchor=(0.995, 1.04))
    _caption(fig, "Each method is scored against the reference named in the table, "
                  "because the dataset ships no ground-truth labels (doc 5.2.5).")
    return _save(fig, out_dir, "metrics.png")


def plot_distributions(graph, assignment, out_dir):
    """Degree distribution and community size distribution of the network."""
    degrees = sorted((degree for _, degree in graph.degree()), reverse=True)
    sizes = sorted(Counter(assignment.values()).values(), reverse=True)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))

    axes[0].hist(degrees, bins=28, color=BLUE, alpha=.92, zorder=3)
    axes[0].set_yscale("log")
    axes[0].set_title("Degree distribution")
    axes[0].set_xlabel("degree")
    axes[0].set_ylabel("nodes (log scale)")
    axes[0].text(
        0.97, 0.95,
        "max %d\nmean %.2f" % (degrees[0] if degrees else 0,
                               (sum(degrees) / len(degrees)) if degrees else 0.0),
        transform=axes[0].transAxes, ha="right", va="top", fontsize=8.4, color=MUTED,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fbfcfe", edgecolor=GRID),
    )

    shown = sizes[:30]
    axes[1].bar(range(1, len(shown) + 1), shown, color=TEAL, zorder=3, width=.7)
    axes[1].set_title("Community sizes (largest 30)")
    axes[1].set_xlabel("community rank")
    axes[1].set_ylabel("nodes")
    axes[1].text(
        0.97, 0.95, "%d communities\nlargest %d" % (len(sizes), sizes[0] if sizes else 0),
        transform=axes[1].transAxes, ha="right", va="top", fontsize=8.4, color=MUTED,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fbfcfe", edgecolor=GRID),
    )

    for axes_handle in axes:
        _despine(axes_handle)
    _caption(fig, "A long tail of low-degree nodes and a handful of large communities is "
                  "what social-interaction graphs normally look like.")
    return _save(fig, out_dir, "distributions.png")


def _score_column(frame):
    for name in ("score", "anomaly_score"):
        if name in frame.columns:
            return name
    return frame.columns[0]


def plot_anomaly_scores(node_scores, anomalous_nodes, reference, out_dir):
    """doc 4.6 / 5.2.2 - score distribution, the cut-off and the worst offenders."""
    column = _score_column(node_scores)
    scores = node_scores[column].astype(float)
    flagged = set(anomalous_nodes)
    contamination = float(node_scores.attrs.get("contamination") or 0.0)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))

    axes[0].hist(scores, bins=40, color=BLUE, alpha=.92, zorder=3)
    cut_scores = sorted(float(node_scores.at[node, column])
                        for node in flagged if node in set(node_scores.index))
    if cut_scores:
        cut = min(cut_scores)
        axes[0].axvline(cut, color=RED, linewidth=1.5, zorder=4)
        axes[0].annotate(
            "%d nodes flagged (contamination %.1f%%)" % (len(cut_scores), 100 * contamination),
            xy=(cut, axes[0].get_ylim()[1] * 0.9), xytext=(6, 0),
            textcoords="offset points", fontsize=8.4, color=RED, va="center",
        )
    axes[0].set_title("Isolation Forest score distribution")
    axes[0].set_xlabel("anomaly score")
    axes[0].set_ylabel("nodes")

    top = node_scores.sort_values(column, ascending=False).head(15).iloc[::-1]
    names = [str(index) for index in top.index]
    values = [float(value) for value in top[column]]
    colours = [RED if index in flagged else "#93b4f7" for index in top.index]
    axes[1].barh(names, values, color=colours, zorder=3)
    for bar, value in zip(axes[1].patches, values):
        axes[1].annotate("%.4f" % value,
                         (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                         xytext=(4, 0), textcoords="offset points", va="center",
                         fontsize=7.4, color=INK)
    axes[1].set_xlim(0, (max(values) if values else 1) * 1.2)
    axes[1].set_title("Highest scoring nodes")
    axes[1].set_xlabel("anomaly score")
    axes[1].tick_params(axis="y", labelsize=7.8)

    _despine(axes[0])
    _despine(axes[1], keep=("bottom",))
    axes[1].grid(axis="x", zorder=0)
    reference = reference or {}
    _caption(fig, "Red bars are nodes the Isolation Forest flagged; the reference rule "
                  "(doc figure 8: degree > mean + %.1f sigma) flagged %d nodes."
             % (float(reference.get("sigma") or config.DEGREE_SIGMA),
                int(reference.get("count") or 0)))
    return _save(fig, out_dir, "anomaly_scores.png")


def plot_influencer_ranking(top_users, assignment, out_dir):
    """doc 4.7 - the graph-wide betweenness ranking, coloured by community."""
    if not top_users:
        return None
    rows = list(top_users)[:15][::-1]
    names = [str(row["node"]) for row in rows]
    values = [float(row["score"]) for row in rows]
    colours = [COMMUNITY_COLOURS[int(assignment.get(row["node"], 0)) % len(COMMUNITY_COLOURS)]
               for row in rows]
    fig, axes = plt.subplots(figsize=(9.2, 5.6))
    bars = axes.barh(names, values, color=colours, zorder=3)
    for bar, value in zip(bars, values):
        axes.annotate("%.4f" % value,
                      (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                      xytext=(4, 0), textcoords="offset points", va="center",
                      fontsize=7.6, color=INK)
    axes.set_xlim(0, (max(values) or 1) * 1.18)
    axes.set_title("Global betweenness-centrality ranking")
    axes.set_xlabel("betweenness centrality")
    axes.tick_params(axis="y", labelsize=8.2)
    _despine(axes, keep=("bottom",))
    axes.grid(axis="x", zorder=0)
    _caption(fig, "Bars are coloured by the community of each node, so the ranking shows "
                  "which groups the graph's bridges live in.")
    return _save(fig, out_dir, "influencer_ranking.png")


def plot_overview(counts, comparison, out_dir):
    """One-glance summary: modularity by method and what the run produced."""
    counts = counts or {}
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.6))

    entries = [(name, entry.get("modularity")) for name, entry in (comparison or {}).items()]
    entries = [(name, float(value)) for name, value in entries
               if isinstance(value, (int, float))]
    if entries:
        entries.sort(key=lambda item: item[1])
        best = max(entries, key=lambda item: item[1])[0]
        names = [_wrap(name, 12) for name, _ in entries]
        values = [value for _, value in entries]
        colours = [BLUE if name == best else "#93b4f7" for name, _ in entries]
        bars = axes[0].barh(names, values, color=colours, zorder=3)
        for bar, value in zip(bars, values):
            axes[0].annotate("%.3f" % value,
                             (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                             xytext=(4, 0), textcoords="offset points", va="center",
                             fontsize=7.6, color=INK)
        axes[0].set_xlim(0, max(values) * 1.22)
        axes[0].set_title("Modularity by community method")
        axes[0].set_xlabel("modularity (higher is a crisper split)")
        axes[0].tick_params(axis="y", labelsize=8.2)
        _despine(axes[0], keep=("bottom",))
        axes[0].grid(axis="x", zorder=0)
    else:
        axes[0].axis("off")
        axes[0].text(0.5, 0.5, "no method comparison available", ha="center",
                     va="center", color=MUTED, fontsize=9.5)

    labels = ["communities", "anomalous\nnodes", "anomalous\ncommunities",
              "community\ninfluencers"]
    values = [counts.get("communities", 0), counts.get("anomalous_nodes", 0),
              counts.get("anomalous_communities", 0), counts.get("influencers", 0)]
    bars = axes[1].bar(labels, values, color=(BLUE, RED, AMBER, TEAL), zorder=3, width=.62)
    _value_labels(axes[1], bars, fmt="%d", fontsize=8.6)
    axes[1].set_ylim(0, (max(values) if values else 1) * 1.24)
    axes[1].set_title("What the run produced")
    axes[1].set_ylabel("count")
    axes[1].tick_params(axis="x", labelsize=8.2)
    _despine(axes[1])
    axes[1].grid(axis="y", zorder=0)

    _caption(fig, "%s nodes and %s edges analysed; modularity %.4f for the selected method."
             % ("{:,}".format(int(counts.get("nodes", 0))),
                "{:,}".format(int(counts.get("edges", 0))),
                float(counts.get("modularity", 0.0))))
    return _save(fig, out_dir, "overview.png")
