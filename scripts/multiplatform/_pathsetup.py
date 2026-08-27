"""Adds src/ to sys.path so scripts/multiplatform/*.py can `import
bodrum_intelligence...` without installing the package. Import this module
first (before any bodrum_intelligence import) from every script in this
directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
