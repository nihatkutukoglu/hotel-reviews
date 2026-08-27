"""Phase 2, sections 2-3: fixes the two known data-quality issues in the
three platform link CSVs, in place, with an audit trail. Never invents a
URL. Never touches the master hotel_name.

  1. BOD192 (Yalıpark Beach Hotel, Yalıkavak) is completely absent from all
     three link files - append an explicit MISSING_LINK_RECORD row instead
     of leaving it silently missing.
  2. BOD135/BOD155/BOD175 have a literal "|" in their master hotel_name
     that the original link-file generator mis-split, shifting text into
     the area column. Standard CSV parsing was never the problem (csv.
     DictReader already parses these files correctly field-by-field) - the
     link files' hotel_name/area *values* are wrong. Fixed by copying the
     correct hotel_name/area straight from master for just these 3 rows.

Usage:
    python scripts/multiplatform/apply_data_quality_fixes.py
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import csv

from bodrum_intelligence.reviews.common import PLATFORM_LINK_FILES, REPORTS_DIR, master_hotel_csv_path, read_csv_dicts

BOD192_ID = "BOD192"
PIPE_BUG_IDS = ["BOD135", "BOD155", "BOD175"]


def fix_link_file(path, master_by_id: dict, pipe_fix_rows: list, bod192_rows: list) -> None:
    rows = read_csv_dicts(path)
    fieldnames = list(rows[0].keys()) if rows else [
        "hotel_id", "hotel_name", "area", "platform", "direct_url", "status", "checked_at", "note"]
    platform_value = rows[0]["platform"] if rows else ""
    by_id = {r["hotel_id"]: r for r in rows}

    for hid in PIPE_BUG_IDS:
        if hid not in by_id:
            continue
        r = by_id[hid]
        m = master_by_id[hid]
        before_name, before_area = r["hotel_name"], r["area"]
        r["hotel_name"] = m["hotel_name"]
        r["area"] = m["area"]
        pipe_fix_rows.append({
            "hotel_id": hid, "master_hotel_name": m["hotel_name"],
            "link_hotel_name_before": before_name, "link_area_before": before_area,
            "link_hotel_name_after": r["hotel_name"], "link_area_after": r["area"],
            "status": "FIXED",
        })

    if BOD192_ID not in by_id:
        m = master_by_id[BOD192_ID]
        new_row = {fn: "" for fn in fieldnames}
        new_row.update({
            "hotel_id": BOD192_ID, "hotel_name": m["hotel_name"], "area": m["area"],
            "platform": platform_value, "direct_url": "null", "status": "MISSING_LINK_RECORD",
            "checked_at": "2026-08-26",
            "note": "Master dataset contains BOD192 but no verified direct platform URL is available.",
        })
        rows.append(new_row)
        by_id[BOD192_ID] = new_row
        bod192_rows.append({"file": str(path.name), "hotel_id": BOD192_ID, "hotel_name": m["hotel_name"],
                             "area": m["area"], "action": "APPENDED_MISSING_LINK_RECORD"})

    rows.sort(key=lambda r: r["hotel_id"])
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> int:
    master_by_id = {r["hotel_id"]: r for r in read_csv_dicts(master_hotel_csv_path())}
    pipe_fix_rows: list[dict] = []
    bod192_rows: list[dict] = []

    for platform, path in PLATFORM_LINK_FILES.items():
        fix_link_file(path, master_by_id, pipe_fix_rows, bod192_rows)
        print(f"Updated {path}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(REPORTS_DIR / "multiplatform_pipe_character_fix_audit.csv", "w",
              newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hotel_id", "master_hotel_name", "link_hotel_name_before",
                                           "link_area_before", "link_hotel_name_after", "link_area_after",
                                           "status"])
        w.writeheader()
        for r in pipe_fix_rows:
            w.writerow(r)

    with open(REPORTS_DIR / "bod192_link_record_audit.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["file", "hotel_id", "hotel_name", "area", "action"])
        w.writeheader()
        for r in bod192_rows:
            w.writerow(r)

    with open(REPORTS_DIR / "phase2_data_quality_fixes.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["fix", "hotel_ids_affected", "files_affected", "url_fabricated", "master_hotel_name_changed"])
        w.writerow(["bod192_missing_link_record", BOD192_ID, len(bod192_rows), "NO", "NO"])
        w.writerow(["pipe_character_area_shift", "|".join(PIPE_BUG_IDS), len(pipe_fix_rows), "NO", "NO"])

    print(f"\npipe-fix rows: {len(pipe_fix_rows)}, bod192 rows appended: {len(bod192_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
