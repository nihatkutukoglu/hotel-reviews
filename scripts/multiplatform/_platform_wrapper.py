"""Shared helper for the thin per-platform run_*.py scripts: strips any
user-supplied --platform flag (this script's platform always wins) and
delegates to run_batch.main().
"""
from __future__ import annotations

import sys


def strip_platform_flag(argv: list[str]) -> list[str]:
    out = []
    skip_next = False
    for arg in argv:
        if skip_next:
            skip_next = False
            continue
        if arg == "--platform":
            skip_next = True
            continue
        if arg.startswith("--platform="):
            continue
        out.append(arg)
    return out


def run_with_forced_platform(platform: str) -> int:
    from run_batch import main
    return main(["--platform", platform, *strip_platform_flag(sys.argv[1:])])
