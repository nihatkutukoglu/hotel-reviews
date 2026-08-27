"""Single-platform convenience wrapper over run_batch.py --platform tripadvisor.
All CLI flags from run_batch.py apply (see its --help).

Usage:
    python scripts/multiplatform/run_tripadvisor.py --area Akyarlar --max-hotels 5
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

from _platform_wrapper import run_with_forced_platform

if __name__ == "__main__":
    raise SystemExit(run_with_forced_platform("tripadvisor"))
