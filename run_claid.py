"""Zero-setup entry point for the CLAID framework.

    python run_claid.py --source bestof
    python run_claid.py --method "Label Propagation" --no-plots --quiet

The package lives in ``src/``, so ``python -m claid.cli`` only works when
``src`` is on ``PYTHONPATH``.  This wrapper adds it, which means the command
above works in a fresh clone with nothing installed beyond ``requirements.txt``.
A full run (nine figures included) takes roughly twenty to thirty seconds and
prints its progress while it works.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from claid.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
