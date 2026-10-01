"""Command line entry point for the CLAID framework.

    python -m claid.cli --source bestof
    python -m claid.cli --method "Label Propagation" --contamination 0.08 --json run.json
"""
from __future__ import annotations

import argparse
import json
import sys

from . import config, pipeline


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m claid.cli",
        description="Run the CLAID framework (doc 4.5-4.7) on the shipped dataset.",
    )
    parser.add_argument("--source", help="source node (subreddit) to focus on")
    parser.add_argument(
        "--method",
        default="Louvain Modularity",
        choices=list(config.COMMUNITY_COMPARISON_METHODS),
        help="community detection method (doc 4.5)",
    )
    parser.add_argument("--resolution", type=float, default=config.LOUVAIN_RESOLUTION,
                        help="Louvain resolution parameter")
    parser.add_argument("--contamination", type=float, default=config.IFOREST_CONTAMINATION,
                        help="Isolation Forest contamination for nodes (doc 4.6)")
    parser.add_argument("--community-contamination", dest="community_contamination",
                        type=float, default=config.IFOREST_CONTAMINATION,
                        help="Isolation Forest contamination for communities")
    parser.add_argument("--top", dest="top_influencers", type=int,
                        default=config.TOP_INFLUENCERS,
                        help="influential users kept per community (doc 4.7)")
    parser.add_argument("--dataset", help="CSV to analyse (default: doc 4.3 dataset)")
    parser.add_argument("--no-plots", action="store_true", help="skip figure generation")
    parser.add_argument("--json", dest="json_path", help="also dump the result JSON here")
    parser.add_argument("--quiet", action="store_true", help="only print the headline numbers")
    return parser


def _table(headers, rows):
    widths = [
        max(len(str(headers[index])), *(len(str(row[index])) for row in rows))
        for index in range(len(headers))
    ]
    lines = ["  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))]
    lines.append("  ".join("-" * width for width in widths))
    for row in rows:
        lines.append("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


def format_report(result):
    out = []
    network = result["network"]
    out.append("CLAID run %s (%s, %.2fs)"
               % (result["run_id"], result["generated_at"], result["duration_seconds"]))
    out.append("")
    out.append("Network: %s | rows %s | nodes %s | edges %s | components %s | density %s"
               % (network["dataset"], network["rows"], network["nodes"], network["edges"],
                  network["components"], network["density"]))
    community = result["community"]
    out.append("")
    out.append("1. Community detection (doc 4.5): %s -> %d communities, modularity %.4f"
               % (community["method"], community["num_communities"], community["modularity"]))
    out.append(_table(
        ("method", "communities", "modularity", "ARI", "NMI", "precision", "recall", "F1"),
        [(name, entry.get("num_communities", "-"), entry.get("modularity", "-"),
          entry.get("ari", "-"), entry.get("nmi", "-"), entry.get("precision", "-"),
          entry.get("recall", "-"), entry.get("f1", "-"))
         for name, entry in community["comparison"].items() if "error" not in entry],
    ))
    anomaly = result["anomaly"]
    out.append("")
    out.append("2. Anomaly detection (doc 4.6): Isolation Forest flagged %d nodes, %d communities"
               % (anomaly["n_anomalies"], len(anomaly["anomalous_communities"])))
    out.append("   reference rule: %s -> %d nodes"
               % (anomaly["reference_rule"]["name"], anomaly["reference_rule"]["count"]))
    out.append(_table(("node", "score", "anomaly", "community"),
                      [(row["node"], row["score"], row["is_anomaly"], row["community"])
                       for row in anomaly["nodes"][:8]]))
    influence = result["influence"]
    out.append("")
    out.append("3. Influential users (doc 4.7): betweenness centrality per community%s"
               % ("" if influence["exact_betweenness"] else " (sampled estimate)"))
    out.append(_table(("community", "size", "influential user", "score"),
                      [(row["community"], row["size"], row["influential_user"],
                        row["influential_score"]) for row in influence["per_community"][:10]]))
    focus = result.get("focus") or {}
    if focus.get("communities"):
        out.append("")
        out.append("4. Communities interacting with source '%s' (doc 5.2.4):" % focus["source"])
        out.append(_table(("community", "size", "influential user"),
                          [(entry["id"], entry["size"], entry["influential_user"])
                           for entry in focus["communities"][:10]]))
    out.append("")
    out.append("5. Evaluation metrics (doc 5.2.5)")
    out.append(_table(("module", "method", "reference", "precision", "recall", "F1"),
                      [(row["module"], row["method"], row["reference"], row["precision"],
                        row["recall"], row["f1"]) for row in result["metrics"]["rows"]]))
    figures = [name for name in (result.get("plots") or {}).values() if name]
    if figures:
        out.append("")
        out.append("Figures written to var/runs/%s/: %s" % (result["run_id"], ", ".join(figures)))
    if result.get("warnings"):
        out.append("")
        out.append("Warnings: " + "; ".join(result["warnings"]))
    return "\n".join(out)


def main(argv=None):
    args = build_parser().parse_args(argv)
    result = pipeline.run_claid(
        source=args.source,
        community_method=args.method,
        resolution=args.resolution,
        contamination=args.contamination,
        community_contamination=args.community_contamination,
        top_influencers=args.top_influencers,
        dataset=args.dataset,
        make_plots=not args.no_plots,
    )
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
    if args.quiet:
        print("run %s | %d communities | modularity %.4f | %d anomalies | %d influencers"
              % (result["run_id"], result["community"]["num_communities"],
                 result["community"]["modularity"], result["anomaly"]["n_anomalies"],
                 len(result["influence"]["per_community"])))
    else:
        print(format_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

