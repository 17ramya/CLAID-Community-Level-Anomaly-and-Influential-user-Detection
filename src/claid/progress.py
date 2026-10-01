"""Stage-level progress reporting.

A full run spends its time in a handful of expensive steps - greedy modularity,
betweenness centrality, closeness centrality and the Isolation Forest - so a
silent run looks like a hung program.  Every stage therefore announces itself
with the wall-clock time it took::

    [claid]   ...  module 1 - community detection (Louvain Modularity)
    [claid]   0.7s  module 1 done: 271 communities, modularity 0.6762

Set ``CLAID_QUIET=1`` to silence the lines (the CLI's ``--quiet`` does), and use
:func:`add_sink` to mirror them into a log - the Flask application registers its
logger, so the terminal that serves the site shows the same progress.
"""
from __future__ import annotations

import os
import sys
import time

QUIET_VALUES = ("1", "true", "yes", "on")

_SINKS = []
_START = time.perf_counter()


def quiet():
    """True when ``CLAID_QUIET`` asks for silence."""
    return os.environ.get("CLAID_QUIET", "").strip().lower() in QUIET_VALUES


def add_sink(function):
    """Send every line to ``function`` as well (e.g. ``app.logger.info``)."""
    if function not in _SINKS:
        _SINKS.append(function)
    return function


def emit(message):
    """Write one line to stderr and to every registered sink."""
    if not quiet():
        sys.stderr.write("[claid] %s\n" % message)
        sys.stderr.flush()
    for sink in list(_SINKS):
        try:
            sink("[claid] %s" % message)
        except Exception:  # logging must never break a run
            pass


def say(message):
    """A one-off line, e.g. the closing summary."""
    emit(message)


def elapsed():
    """Seconds since this module was imported - handy for a header line."""
    return time.perf_counter() - _START


class Stage:
    """``with Stage("module 2 - anomaly detection") as stage:``

    Prints the label when the block starts and the duration when it ends, so a
    long run always shows what it is doing.  Pass ``done`` to describe the
    outcome, either as text or as a callable that reads the values the block
    produced (it is only called on exit).
    """

    def __init__(self, label, done=None):
        self.label = label
        self.done = done
        self.started = None

    def __enter__(self):
        self.started = time.perf_counter()
        emit("  ...  %s" % self.label)
        return self

    def __exit__(self, exc_type, exc, traceback):
        seconds = time.perf_counter() - self.started
        if exc_type is not None:
            emit("%5.1fs  %s -> %s" % (seconds, self.label, exc_type.__name__))
            return False
        if self.done is None:
            message = self.label
        elif callable(self.done):
            message = self.done()
        else:
            message = self.done
        emit("%5.1fs  %s" % (seconds, message))
        return False
