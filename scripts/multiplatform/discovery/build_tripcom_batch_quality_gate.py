"""Trip.com Phase A5: quality gate for a batch run, scoped to rows written
at or after --since. Mirrors build_google_batch_quality_gate.py's logic
(see that file's docstring for the wrong_entity_rows_written rationale).

Usage:
    python scripts/multiplatform/discovery/build_tripcom_batch_quality_gate.py --since 2026-08-26T15:00:00Z --label controlled
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _pathsetup  # noqa: F401, E402

from bodrum_intelligence.reviews.common import (
    DATA_RAW_DIR, REPORTS_DIR, evaluate_raw_csv_quality, per_hotel_csv_path, read_csv_dicts,
)

STATUS_PATH = REPORTS_DIR / "multiplatform_scrape_status.csv"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--label", default="controlled")
    args = ap.parse_args()

    rows = [r for r in read_csv_dicts(STATUS_PATH)
            if r["platform"] == "trip" and r["started_at"] >= args.since]

    wrong_entity_rows = [r for r in rows if r["status"] == "WRONG_ENTITY"]
    wrong_entity = len(wrong_entity_rows)
    wrong_entity_rows_written = sum(int(r.get("rows_added") or 0) for r in wrong_entity_rows)
    review_required_rows = [r for r in rows if r["status"] == "NAME_REVIEW_REQUIRED"]
    review_required_sourced = sum(int(r.get("rows_added") or 0) for r in review_required_rows)
    completed = [r for r in rows if r["status"] in ("COMPLETED", "VALID_ENTITY_NO_REVIEWS")]
    blocked = [r for r in rows if r["status"] in ("BLOCKED_SAFE_STOP", "MANUAL_ACTION_REQUIRED")]
    errored = [r for r in rows if r["status"] in ("PAGE_ERROR", "ERROR")]

    total_added = 0
    total_empty_text = 0
    total_invalid_rating = 0
    total_dup_in_file = 0
    per_hotel_counts = []
    for r in completed:
        hotel_id, hotel_name = r["hotel_id"], r["hotel_name"]
        raw_path = per_hotel_csv_path(DATA_RAW_DIR / "reviews" / "trip", hotel_id, hotel_name)
        q = evaluate_raw_csv_quality(raw_path, platform="trip")
        total_empty_text += q["empty_review_text"]
        total_invalid_rating += q["invalid_rating"]
        total_dup_in_file += q["duplicate_rows"]
        total_added += int(r.get("rows_added") or 0)
        per_hotel_counts.append({"hotel_id": hotel_id, "hotel_name": hotel_name,
                                  "rows_added_this_batch": r.get("rows_added"),
                                  "unique_rows_in_file": q["unique_rows"]})

    gate_pass = (wrong_entity_rows_written == 0 and review_required_sourced == 0
                 and total_empty_text == 0 and total_dup_in_file == 0)

    out_path = REPORTS_DIR / f"tripcom_{args.label}_batch_quality.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["hotels_processed_this_batch", len(rows)])
        w.writerow(["completed", len(completed)])
        w.writerow(["wrong_entity_attempts", wrong_entity])
        w.writerow(["wrong_entity_rows_written", wrong_entity_rows_written])
        w.writerow(["review_required_attempts", len(review_required_rows)])
        w.writerow(["review_required_rows_written", review_required_sourced])
        w.writerow(["blocked_or_manual_action", len(blocked)])
        w.writerow(["error", len(errored)])
        w.writerow(["reviews_added_this_batch", total_added])
        w.writerow(["empty_review_text_in_touched_files", total_empty_text])
        w.writerow(["invalid_rating_in_touched_files", total_invalid_rating])
        w.writerow(["duplicate_rows_in_touched_files", total_dup_in_file])
        w.writerow(["QUALITY_GATE", "PASS" if gate_pass else "FAIL"])

    per_hotel_path = REPORTS_DIR / f"tripcom_{args.label}_batch_per_hotel.csv"
    with open(per_hotel_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hotel_id", "hotel_name", "rows_added_this_batch", "unique_rows_in_file"])
        w.writeheader()
        for r in per_hotel_counts:
            w.writerow(r)

    print(f"Wrote {out_path}")
    print(f"Wrote {per_hotel_path}")
    print(f"GATE: {'PASS' if gate_pass else 'FAIL'} | processed={len(rows)} completed={len(completed)} "
          f"wrong_entity_attempts={wrong_entity} wrong_entity_rows_written={wrong_entity_rows_written} "
          f"blocked={len(blocked)} error={len(errored)} added={total_added} "
          f"empty_text={total_empty_text} invalid_rating={total_invalid_rating} dup={total_dup_in_file}")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
