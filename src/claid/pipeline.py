"""The CLAID framework: community detection, anomaly detection, influential users.

Chapter 4 of the project report is implemented here as a single pipeline:

1. doc 4.5 - Louvain modularity builds the communities (other algorithms are run
   alongside for the comparison in doc figure 14);
2. doc 4.6 - an Isolation Forest scores nodes *and* communities, and the
   degree-centrality rule of doc figure 8 provides the reference labels;
3. doc 4.7 - betweenness centrality picks the influential user of every
   non-anomalous community;
4. doc 5.2.4 - the ``focus`` block reports the communities interacting with a
   chosen source node, together with their anomalies and influencers;
5. doc 5.2.5 - precision / recall / F1 are tabulated for every method.

Every run is stored as ``var/runs/<run_id>/result.json`` plus PNG figures.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from . import anomaly, community, config, data, evaluate, influence, plots, progress

DEFAULT_PARAMS = {
    "source": None,
    "community_method": "Louvain Modularity",
    "resolution": config.LOUVAIN_RESOLUTION,
    "contamination": config.IFOREST_CONTAMINATION,
    "community_contamination": config.IFOREST_CONTAMINATION,
    "top_influencers": config.TOP_INFLUENCERS,
    "dataset": None,
}

_CACHE = {}


def cache_stats(dataset=None):
    """What is already memoised for a dataset (used by the smoke test).

    The graph, its features, the community comparison, the top-k influence
    baselines and the Isolation Forest fits are deterministic, so each of them
    is computed once per process and reused by every following run.
    """
    entry = _CACHE.get(str(data.dataset_path(dataset)), {})
    return {
        "graph": "graph" in entry,
        "features": "features" in entry,
        "comparison": sorted(entry.get("comparison", {})),
        "baselines": sorted(entry.get("baselines", {})),
        "forest": sorted("%s@%s" % (key[0], key[2] or key[1]) for key in entry.get("forest", {})),
    }


def _resolution_key(resolution):
    return "%.6f" % float(resolution)


def _cached_comparison(cache, graph, assignment, resolution):
    """Benchmark every community method once per (dataset, resolution).

    Greedy modularity alone costs seconds and all four partitions are
    deterministic, so the table is stored next to the graph and reused by later
    runs in the same process.
    """
    store = cache.setdefault("comparison", {})
    key = _resolution_key(resolution)
    if key in store:
        progress.say("community comparison for resolution %s reused from cache" % key)
        return store[key]
    comparison = {}
    nodes = list(graph.nodes())
    for name in community.METHODS:
        with progress.Stage(
            "comparison - %s" % name,
            lambda method=name: "comparison - %s done" % method,
        ):
            try:
                candidate = community.detect(graph, name, resolution=resolution)
            except Exception as exc:  # one failing method must not break a run
                comparison[name] = {"error": "%s: %s" % (type(exc).__name__, exc)}
                continue
            agreement = evaluate.partition_agreement(
                assignment, candidate["assignment"], nodes
            )
            metrics = evaluate.label_metrics(
                [assignment.get(node, -1) for node in nodes],
                [candidate["assignment"].get(node, -1) for node in nodes],
            )
            comparison[name] = {
                "num_communities": candidate["num_communities"],
                "modularity": round(community.modularity(graph, candidate["assignment"]), 4),
                "ari": round(agreement["ari"], 4),
                "nmi": round(agreement["nmi"], 4),
                "precision": round(metrics["precision"], 4),
                "recall": round(metrics["recall"], 4),
                "f1": round(metrics["f1"], 4),
                "sampled_subgraph": bool(candidate.get("sampled_subgraph", False)),
                "subgraph_nodes": candidate.get("subgraph_nodes"),
            }
    store[key] = comparison
    return comparison


def _cached_baseline(cache, graph, top):
    """Top-k degree and closeness rankings, computed once per (dataset, top).

    Exact closeness centrality is O(n*m), which makes it one of the slowest
    steps of a run, so it is reused instead of recomputed.
    """
    store = cache.setdefault("baselines", {})
    key = int(top)
    if key not in store:
        with progress.Stage(
            "influence baselines - top-%d by degree and by closeness" % key,
            "closeness and degree baselines ready",
        ):
            degree_top, _ = influence.degree_baseline(graph, top=key)
            closeness_top, _ = influence.closeness_baseline(graph, top=key)
        store[key] = {"degree": degree_top, "closeness": closeness_top}
    else:
        progress.say("top-%d influence baselines reused from cache" % key)
    return store[key]


def _cached_forest(cache, features, kind, contamination, variant=""):
    """Isolation Forest fits are deterministic, so each setting is fitted once."""
    store = cache.setdefault("forest", {})
    key = (kind, round(float(contamination), 6), variant)
    if key not in store:
        with progress.Stage(
            "module 2 - Isolation Forest over %s features" % kind,
            lambda: "Isolation Forest ready (%s, contamination %.3f)"
            % (kind, contamination),
        ):
            store[key] = anomaly.isolation_forest(features, contamination=contamination)
    else:
        progress.say("Isolation Forest fit for %s features reused from cache" % kind)
    return store[key]


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (np.str_,)):
        return str(value)
    return value


def load_graph(dataset=None):
    """Load the dataset and build the graph (cached per dataset file)."""
    dataset_file = data.dataset_path(dataset)
    key = str(dataset_file)
    entry = _CACHE.setdefault(key, {})
    if "graph" not in entry:
        frame, clean_report = data.clean_dataframe(pd.read_csv(dataset_file))
        entry.update(
            {
                "frame": frame,
                "graph": data.build_graph(frame),
                "clean_report": clean_report,
                "dataset_file": dataset_file,
            }
        )
    return entry


def load_network(dataset=None):
    """Extend :func:`load_graph` with the features the modules consume."""
    entry = load_graph(dataset)
    if "features" not in entry:
        betweenness, exact = influence.global_betweenness(entry["graph"])
        entry["betweenness"] = betweenness
        entry["betweenness_exact"] = exact
        entry["features"] = data.node_features(
            entry["graph"], entry["frame"], betweenness=betweenness
        )
    return entry


def _metrics_rows(cache, graph, comparison, anomalous_nodes, reference_nodes, node_scores,
                  reference, per_community):
    """doc 5.2.5 - one row per method, per module."""
    rows = []
    for name, entry in comparison.items():
        if "error" in entry:
            continue
        rows.append(
            evaluate.row(
                "Community detection",
                name,
                "Louvain partition (doc 4.5)",
                entry,
                note="modularity %.4f | ARI %.3f | %d communities%s"
                % (
                    entry["modularity"],
                    entry["ari"],
                    entry["num_communities"],
                    " | Girvan-Newman run on a %d-node subgraph (O(n*m^2))"
                    % entry["subgraph_nodes"]
                    if entry.get("sampled_subgraph")
                    else "",
                ),
            )
        )
    nodes = list(graph.nodes())
    predicted = [1 if node in anomalous_nodes else 0 for node in nodes]
    truth = [1 if node in reference_nodes else 0 for node in nodes]
    rows.append(
        evaluate.row(
            "Anomaly detection",
            "Isolation Forest",
            "degree rule (doc fig. 8)",
            evaluate.label_metrics(truth, predicted),
            note="contamination %.3f | %d flagged nodes"
            % (node_scores.attrs["contamination"], len(anomalous_nodes)),
        )
    )
    rows.append(
        evaluate.row(
            "Anomaly detection",
            "Degree centrality rule",
            "Isolation Forest (doc 4.6)",
            evaluate.label_metrics(predicted, truth),
            note="mean + %.1f sigma = %.4f" % (reference["sigma"], reference["threshold"]),
        )
    )
    leaders = {
        entry["influential_user"] for entry in per_community if entry["influential_user"]
    }
    k = max(len(leaders), 1)
    baselines = _cached_baseline(cache, graph, k)
    degree_top, closeness_top = baselines["degree"], baselines["closeness"]
    rows.append(
        evaluate.row(
            "Influential users",
            "Betweenness centrality (doc 4.7)",
            "top-%d by degree centrality" % k,
            evaluate.topk_metrics(degree_top, leaders, graph.number_of_nodes()),
            note="%d community leaders" % len(leaders),
        )
    )
    rows.append(
        evaluate.row(
            "Influential users",
            "Closeness centrality",
            "top-%d by degree centrality" % k,
            evaluate.topk_metrics(degree_top, closeness_top, graph.number_of_nodes()),
            note="comparison method",
        )
    )
    rows.append(
        evaluate.row(
            "Influential users",
            "Degree centrality",
            "reference ranking",
            evaluate.topk_metrics(degree_top, degree_top, graph.number_of_nodes()),
            note="reference (scored against itself)",
        )
    )
    return rows


def run_claid(make_plots=True, **overrides):
    """Execute the full CLAID pipeline and persist the run."""
    params = dict(DEFAULT_PARAMS)
    params.update({key: value for key, value in overrides.items() if value is not None})
    started = time.time()
    config.ensure_directories()
    progress.say("run start - a full pass takes roughly half a minute")

    with progress.Stage(
        "load the dataset, build the graph and extract node features",
        lambda: "graph ready: %s nodes, %s edges"
        % ("{:,}".format(cache["graph"].number_of_nodes()),
           "{:,}".format(cache["graph"].number_of_edges())),
    ):
        cache = load_network(params["dataset"])
    graph, frame, features = cache["graph"], cache["frame"], cache["features"]

    # ---- module 1: community detection (doc 4.5) -------------------------- #
    with progress.Stage(
        "module 1 - community detection (%s)" % params["community_method"],
        lambda: "module 1 done: %d communities, modularity %.4f"
        % (primary["num_communities"], modularity),
    ):
        primary = community.detect(
            graph, params["community_method"], resolution=params["resolution"]
        )
        assignment = primary["assignment"]
        modularity = community.modularity(graph, assignment)
        described = community.describe(graph, assignment)

    comparison = _cached_comparison(cache, graph, assignment, params["resolution"])

    # ---- module 2: anomaly detection (doc 4.6) ---------------------------- #
    node_scores = _cached_forest(cache, features, "node", params["contamination"])
    community_matrix = anomaly.community_features(features, assignment)
    community_scores = _cached_forest(
        cache,
        community_matrix,
        "community",
        params["community_contamination"],
        variant="%s@%s"
        % (params["community_method"], _resolution_key(params["resolution"])),
    )
    anomalous_nodes = {
        node for node in node_scores.index if bool(node_scores.at[node, "is_anomaly"])
    }
    anomalous_communities = sorted(
        int(cid) for cid in community_scores.index[community_scores["is_anomaly"]]
    )
    reference = anomaly.degree_rule(graph)
    node_rows = anomaly.describe_node_anomalies(
        graph, node_scores, assignment, features, top=30
    )
    community_rows = [
        {
            "community": int(cid),
            "size": int(community_matrix.at[cid, "members"]),
            "score": round(float(community_scores.at[cid, "score"]), 5),
            "anomaly_score": round(float(community_scores.at[cid, "anomaly_score"]), 4),
            "is_anomaly": bool(community_scores.at[cid, "is_anomaly"]),
            "top_nodes": sorted(community_matrix.attrs.get("groups", {}).get(int(cid), []))[:10],
        }
        for cid in sorted(
            community_scores.index, key=lambda cid: -community_scores.at[cid, "score"]
        )[:30]
    ]

    # ---- module 3: influential users (doc 4.7) ---------------------------- #
    with progress.Stage(
        "module 3 - betweenness centrality inside each community",
        lambda: "module 3 done: %d influencers, %d anomalous communities excluded"
        % (len(per_community), len(excluded)),
    ):
        per_community, excluded = influence.influencers(
            graph, assignment, anomalous_communities, top=params["top_influencers"]
        )
        top_users = influence.ranked_users(graph, cache["betweenness"], top=25)

    # ---- doc 5.2.4: communities interacting with the source node ---------- #
    with progress.Stage(
        "doc 5.2.4 - communities interacting with the source node",
        lambda: "focus ready: source '%s' touches %d communities"
        % (focus["source"], len(focus["communities"])),
    ):
        focus = _focus(
            graph,
            assignment,
            params["source"],
            anomalous_nodes,
            per_community,
            excluded_communities={entry["community"] for entry in excluded},
        )

    # ---- doc 5.2.5: evaluation metrics ------------------------------------ #
    with progress.Stage("doc 5.2.5 - precision, recall and F1 per method"):
        rows = _metrics_rows(
            cache, graph, comparison, anomalous_nodes, set(reference["anomalies"]),
            node_scores, reference, per_community,
        )

    # ---- one-glance counters (feed the dashboard figure and the web KPIs) -- #
    counts = {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "communities": primary["num_communities"],
        "modularity": round(modularity, 4),
        "anomalous_nodes": len(anomalous_nodes),
        "anomalous_communities": len(anomalous_communities),
        "influencers": len(per_community),
    }
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    run_dir = _run_directory(run_id)
    warnings = []
    plot_files = {}
    if make_plots:
        figure_jobs = (
            ("overview", lambda: plots.plot_overview(counts, comparison, run_dir)),
            ("communities", lambda: plots.plot_communities(graph, assignment, run_dir)),
            ("distributions", lambda: plots.plot_distributions(graph, assignment, run_dir)),
            ("anomalies", lambda: plots.plot_anomalies(graph, assignment, anomalous_nodes, run_dir)),
            ("anomaly_scores", lambda: plots.plot_anomaly_scores(
                node_scores, anomalous_nodes, reference, run_dir)),
            ("influencers", lambda: plots.plot_influencers(
                graph, assignment, per_community, run_dir)),
            ("influencer_ranking", lambda: plots.plot_influencer_ranking(
                top_users, assignment, run_dir)),
            ("focus", lambda: plots.plot_focus(graph, assignment, focus["source"], focus, run_dir)),
            ("metrics", lambda: plots.plot_metrics(rows, run_dir)),
        )
        progress.say("rendering %d figures into %s" % (len(figure_jobs), run_dir))
        for label, factory in figure_jobs:
            try:
                with progress.Stage("figure %s.png" % label):
                    plot_files[label] = factory()
            except Exception as exc:  # a plotting problem must not lose the analysis
                plot_files[label] = None
                warnings.append("%s plot failed: %s: %s" % (label, type(exc).__name__, exc))

    result = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration_seconds": round(time.time() - started, 2),
        "params": _json_safe(params),
        "warnings": warnings,
        "network": data.summary(graph, frame, cache["dataset_file"], cache["clean_report"]),
        "community": {
            "method": primary["method"],
            "num_communities": primary["num_communities"],
            "modularity": round(modularity, 4),
            "sizes": primary["sizes"][:50],
            "communities": described[:50],
            "assignment": assignment,
            "comparison": comparison,
        },
        "anomaly": {
            "method": "Isolation Forest",
            "features": list(node_scores.attrs["features"]),
            "contamination": node_scores.attrs["contamination"],
            "community_contamination": community_scores.attrs["contamination"],
            "n_anomalies": len(anomalous_nodes),
            "nodes": node_rows,
            "anomaly_nodes": sorted(anomalous_nodes),
            "communities": community_rows,
            "anomalous_communities": anomalous_communities,
            "reference_rule": {
                "name": "degree centrality > mean + %.1f sigma (doc figure 8)" % reference["sigma"],
                "sigma": reference["sigma"],
                "mean": round(reference["mean"], 6),
                "std": round(reference["std"], 6),
                "threshold": round(reference["threshold"], 6),
                "count": len(reference["anomalies"]),
            },
        },
        "influence": {
            "metric": "Betweenness centrality (doc 4.7)",
            "exact_betweenness": cache["betweenness_exact"],
            "per_community": per_community,
            "excluded_communities": excluded,
            "top_users": top_users,
        },
        "metrics": {
            "rows": rows,
            "note": "The dataset ships no ground-truth labels, so scores are computed "
                    "against the reference method named in each row (doc 5.2.5).",
        },
        "focus": focus,
        "plots": plot_files,
    }
    with open(run_dir / "result.json", "w", encoding="utf-8") as handle:
        json.dump(_json_safe(result), handle, indent=2)
    progress.say(
        "run %s stored in %s after %.1fs - %d communities, %d anomalies, %d influencers"
        % (run_id, run_dir, result["duration_seconds"], primary["num_communities"],
           len(anomalous_nodes), len(per_community))
    )
    return result


def _focus(graph, assignment, source, anomalous_nodes, per_community, top=20,
           excluded_communities=()):
    """doc 5.2.4 - communities that interact with the source node."""
    excluded = set(excluded_communities)
    if source not in graph:
        source = max(graph.degree, key=lambda item: item[1])[0]
    groups = {}
    for node, cid in assignment.items():
        groups.setdefault(cid, set()).add(node)
    influencer_map = {
        entry["community"]: entry["influential_user"] for entry in per_community
    }
    source_community = assignment.get(source, -1)
    neighbour_ids = sorted(
        {assignment.get(node, -1) for node in graph.neighbors(source)} - {source_community}
    )
    communities = []
    for cid in neighbour_ids:
        members = groups.get(cid, set())
        communities.append(
            {
                "id": cid,
                "size": len(members),
                "members_preview": sorted(members)[:top],
                "anomalies": sorted(members & anomalous_nodes)[:10],
                "influential_user": influencer_map.get(cid),
                "excluded": cid in excluded,
                "note": "excluded from influencer detection (doc 4.7 skips anomalous communities)"
                if cid in excluded
                else "",
                "top_nodes": [
                    node
                    for node, _ in sorted(graph.degree(members), key=lambda item: -item[1])[:top]
                ],
            }
        )
    return {
        "source": source,
        "requested_source": source,
        "source_community": source_community,
        "source_community_size": len(groups.get(source_community, set())),
        "degree": int(graph.degree(source)),
        "neighbours": [
            {
                "node": str(node),
                "weight": float(graph[source][node].get("weight", 1)),
                "community": assignment.get(node, -1),
            }
            for node in sorted(graph.neighbors(source), key=lambda n: -graph[source][n].get("weight", 1))[:top]
        ],
        "communities": communities,
        "anomaly_nodes": sorted(anomalous_nodes & set(graph.nodes()))[:top],
        "influential_users": sorted(
            {value for value in influencer_map.values() if value}
        ),
    }


def _run_directory(run_id):
    directory = Path(config.RUNS_DIR) / run_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def load_run(run_id):
    """Read a stored run (used by the results page and the JSON API)."""
    path = Path(config.RUNS_DIR) / run_id / "result.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def list_runs(limit=10):
    """Most recent runs first (for the dashboard history list)."""
    runs_dir = Path(config.RUNS_DIR)
    if not runs_dir.exists():
        return []
    entries = []
    for path in sorted(runs_dir.glob("*/result.json"), reverse=True)[:limit]:
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            continue
        entries.append(
            {
                "run_id": payload.get("run_id", path.parent.name),
                "generated_at": payload.get("generated_at", ""),
                "dataset": payload.get("network", {}).get("dataset", ""),
                "community_method": payload.get("community", {}).get("method", ""),
                "num_communities": payload.get("community", {}).get("num_communities", 0),
                "modularity": payload.get("community", {}).get("modularity", 0),
                "n_anomalies": payload.get("anomaly", {}).get("n_anomalies", 0),
                "n_influencers": len(payload.get("influence", {}).get("per_community", [])),
                "focus_source": payload.get("focus", {}).get("source", ""),
            }
        )
    return entries

