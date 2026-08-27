"""Phase 2, section 22: TripAdvisor revalidation ONLY - checks 1-2
verified URLs for normal access. No CAPTCHA solving, no proxy, no stealth
bypass, no human-verification bypass. At most 1-2 attempts.

Usage:
    python scripts/multiplatform/run_tripadvisor_revalidation.py
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import csv

from bodrum_intelligence.reviews.common import REPORTS_DIR
from bodrum_intelligence.reviews.runner import load_targets, run_review_platform

CHECK_HOTEL_IDS = ["BOD012", "BOD056"]

FIELDNAMES = ["hotel_id", "hotel_name", "source_url", "attempt", "page_accessible",
              "blocked", "detected_name", "status", "error"]


def main() -> int:
    targets = {r["hotel_id"]: r for r in load_targets()}
    rows_out = []

    for hid in CHECK_HOTEL_IDS:
        row = targets.get(hid)
        if row is None or not row.get("tripadvisor_url"):
            continue
        print(f"\n[tripadvisor-revalidation] {hid} {row['hotel_name']}")
        result = run_review_platform(row, "tripadvisor", headless=False, validate_only=True)
        blocked = result["status"] == "BLOCKED_SAFE_STOP"
        print(f"  -> status={result['status']} blocked={blocked}")
        rows_out.append({
            "hotel_id": hid, "hotel_name": row["hotel_name"], "source_url": row["tripadvisor_url"],
            "attempt": 1, "page_accessible": result["page_accessible"], "blocked": blocked,
            "detected_name": result["detected_hotel_name"], "status": result["status"],
            "error": result.get("error", ""),
        })

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "tripadvisor_revalidation.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    any_blocked = any(r["blocked"] for r in rows_out)
    tripadvisor_ready = "NO" if any_blocked or not rows_out else "YES"
    print(f"\n=== TRIPADVISOR REVALIDATION SUMMARY ===")
    print(f"TRIPADVISOR_READY = {tripadvisor_ready}"
          + (" (reason=BLOCKED_BY_PLATFORM)" if any_blocked else ""))
    print(f"Rapor: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
