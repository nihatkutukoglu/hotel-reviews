"""Phase 2, section 18: retests the same eligible smoke hotels' policies
(Trip.com) against the repaired, label-based field reader. Includes
BOD013's Trip.com alias support.

Usage:
    python scripts/multiplatform/run_policies_repair_smoke_test.py
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import csv

from bodrum_intelligence.reviews.common import REPORTS_DIR
from bodrum_intelligence.reviews.runner import load_targets, run_policies

SMOKE_HOTEL_IDS = ["BOD012", "BOD056", "BOD058", "BOD007", "BOD013"]

FIELDNAMES = ["hotel_id", "hotel_name", "entity_status", "checkin_found", "checkout_found",
              "children_found", "extra_bed_found", "breakfast_found", "pets_found", "age_found",
              "license_found", "facilities_found", "status", "error"]


def main() -> int:
    targets = {r["hotel_id"]: r for r in load_targets()}
    rows_out = []

    for hid in SMOKE_HOTEL_IDS:
        row = targets.get(hid)
        if row is None or not row.get("policy_trip_url"):
            rows_out.append({"hotel_id": hid, "hotel_name": "", "entity_status": "NO_VERIFIED_URL",
                              "checkin_found": False, "checkout_found": False, "children_found": False,
                              "extra_bed_found": False, "breakfast_found": False, "pets_found": False,
                              "age_found": False, "license_found": False, "facilities_found": False,
                              "status": "NO_VERIFIED_URL", "error": ""})
            continue

        print(f"\n[policies-repair-smoke] {hid} {row['hotel_name']}")
        result = run_policies(row, headless=False, resume=False, force=True)
        print(f"  -> status={result['status']} error={result.get('error', '')!r}")

        found = {}
        if result["status"] in ("COMPLETE", "PARTIAL", "VALID_ENTITY_NO_POLICY_DATA"):
            from bodrum_intelligence.reviews.common import DATA_RAW_DIR, per_hotel_csv_path, read_csv_dicts
            csv_path = per_hotel_csv_path(DATA_RAW_DIR / "hotel_policies" / "trip", hid, row["hotel_name"])
            saved = read_csv_dicts(csv_path)[0] if csv_path.exists() else {}
            found = {
                "checkin_found": saved.get("has_checkin") == "True",
                "checkout_found": saved.get("has_checkout") == "True",
                "children_found": saved.get("has_children_policy") == "True",
                "extra_bed_found": saved.get("has_extra_bed_policy") == "True",
                "breakfast_found": saved.get("has_breakfast_policy") == "True",
                "pets_found": saved.get("has_pet_policy") == "True",
                "age_found": saved.get("has_age_rule") == "True",
                "license_found": saved.get("has_license") == "True",
                "facilities_found": saved.get("has_facilities") == "True",
            }
        else:
            found = {k: False for k in ["checkin_found", "checkout_found", "children_found",
                                         "extra_bed_found", "breakfast_found", "pets_found",
                                         "age_found", "license_found", "facilities_found"]}

        rows_out.append({
            "hotel_id": hid, "hotel_name": row["hotel_name"], "entity_status": result["validation_status"],
            **found, "status": result["status"], "error": result.get("error", ""),
        })

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "policies_repair_smoke_test.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    ok = sum(1 for r in rows_out if r["status"] in ("COMPLETE", "PARTIAL"))
    wrong_entity = sum(1 for r in rows_out if r["status"] == "WRONG_ENTITY")
    print(f"\n=== POLICIES REPAIR SMOKE SUMMARY ===")
    print(f"{len(rows_out)} hotels checked, {ok} saved a row, wrong_entity={wrong_entity}")
    policies_batch_ready = wrong_entity == 0 and ok >= 1
    print(f"POLICIES_BATCH_READY = {'YES' if policies_batch_ready else 'NO'}")
    print(f"Rapor: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
