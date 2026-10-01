"""CLAID - Community-Level Anomaly and Influential-user Detection.

Python implementation of the framework described in the project report
"CLAID: A Unified Social Network Analysis Framework for Community-Level Anomaly
and Influencer Detection" (chapters 4 and 5):

* doc 4.5 - community detection with Louvain modularity (:mod:`claid.community`)
* doc 4.6 - anomaly detection with Isolation Forest (:mod:`claid.anomaly`)
* doc 4.7 - influential users with betweenness centrality (:mod:`claid.influence`)
* doc 5.2.5 - precision / recall / F1 evaluation (:mod:`claid.evaluate`)

Example
-------
>>> from claid import run_claid
>>> result = run_claid(source="bestof")            # doctest: +SKIP
>>> result["community"]["modularity"]              # doctest: +SKIP
0.42
"""
from .config import PROJECT_ROOT, ensure_directories  # noqa: F401
from .pipeline import load_network, load_run, list_runs, run_claid  # noqa: F401

__version__ = "1.0.0"
__all__ = [
    "run_claid",
    "load_run",
    "list_runs",
    "load_network",
    "ensure_directories",
    "PROJECT_ROOT",
    "__version__",
]
