"""Phase 3, sections 14-16, 19-23, 28: turns whatever discovery candidates
exist so far (data/interim/discovery/*_candidates.csv) plus the existing,
already-verified v1 links into:

  - bodrum-otel-linkleri/*_v2.csv               (section 19, v1 untouched)
  - reports/platform_link_discovery_v1_v2_diff.csv (section 20)
  - reports/all_hotel_discovery_coverage.csv     (section 21)
  - reports/all_hotel_multiplatform_coverage.csv (section 23)
  - config/multiplatform_hotel_targets_v2.csv    (section 28)

Safe to re-run at any point (smoke-only data, partial full-run data, or a
completed full-run) - always reflects exactly what's on disk, never invents
a status for a hotel that hasn't been discovered yet (NOT_ATTEMPTED).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _pathsetup  # noqa: F401, E402

from bodrum_intelligence.reviews.common import (
    REPO_ROOT, REPORTS_DIR, CONFIG_DIR, LINK_DIR, PLATFORM_LINK_FILES,
    master_hotel_csv_path, read_csv_dicts, utcnow_iso,
)

CANDIDATE_DIR = REPO_ROOT / "data" / "interim" / "discovery"
FOUND_STATUSES = {"FOUND_EXACT", "FOUND_HIGH_CONFIDENCE"}

V2_FIELDS = ["hotel_id", "hotel_name", "area", "platform", "direct_url", "status",
             "checked_at", "note", "discovery_method", "confidence_score", "detected_hotel_name"]


def load_candidates(platform: str) -> dict:
    path = CANDIDATE_DIR / f"{platform}_candidates.csv"
    if not path.exists():
        return {}
    rows = read_csv_dicts(path)
    by_hotel = {}
    for r in rows:
        by_hotel[r["hotel_id"]] = r  # last row wins if a hotel was ever re-run
    return by_hotel


def build_v2_row(hotel, platform, v1_row, candidate) -> dict:
    hotel_id, hotel_name, area = hotel["hotel_id"], hotel["hotel_name"], hotel["area"]
    if v1_row and v1_row.get("status") == "verified_direct":
        return {
            "hotel_id": hotel_id, "hotel_name": hotel_name, "area": area, "platform": platform,
            "direct_url": v1_row["direct_url"], "status": "verified_direct",
            "checked_at": v1_row.get("checked_at", ""),
            "note": "carried over from v1 (already live-verified in phase 1/2)",
            "discovery_method": "phase1_2_manual_or_prior", "confidence_score": 100,
            "detected_hotel_name": "",
        }
    if candidate is None:
        return {
            "hotel_id": hotel_id, "hotel_name": hotel_name, "area": area, "platform": platform,
            "direct_url": "", "status": "NOT_ATTEMPTED", "checked_at": "",
            "note": "not yet run through phase-3 discovery", "discovery_method": "",
            "confidence_score": "", "detected_hotel_name": "",
        }
    vstatus = candidate["validation_status"]
    if vstatus in FOUND_STATUSES:
        status = "verified_direct"
    elif vstatus == "REVIEW_REQUIRED":
        status = "review_required"
    elif vstatus in ("NOT_FOUND", "REJECTED_CANDIDATE"):
        status = "NOT_FOUND"
    else:
        status = vstatus  # ERROR, BLOCKED
    return {
        "hotel_id": hotel_id, "hotel_name": hotel_name, "area": area, "platform": platform,
        "direct_url": candidate["candidate_url"] if status == "verified_direct" else "",
        "status": status, "checked_at": candidate.get("discovered_at", ""),
        "note": candidate.get("validation_note", ""), "discovery_method": candidate.get("candidate_source", ""),
        "confidence_score": candidate.get("candidate_score", ""),
        "detected_hotel_name": candidate.get("candidate_detected_name", ""),
    }


def diff_change_type(v1_status: str, v2_row: dict) -> str:
    v1v = (v1_status or "").strip()
    v2v = v2_row["status"]
    if v1v == "verified_direct" and v2v == "verified_direct":
        return "UNCHANGED_VERIFIED"
    if v1v != "verified_direct" and v2v == "verified_direct":
        return "NEW_VERIFIED"
    if v1v == "verified_direct" and v2v != "verified_direct":
        return "DOWNGRADED"
    if v2v == "review_required":
        return "REVIEW_REQUIRED"
    if v2v == "NOT_ATTEMPTED":
        return "NOT_ATTEMPTED"
    return "STILL_NOT_FOUND"


def main() -> int:
    master = read_csv_dicts(master_hotel_csv_path())
    platforms = ["google_travel", "trip"]
    v1_rows = {p: {r["hotel_id"]: r for r in read_csv_dicts(PLATFORM_LINK_FILES[p])} for p in platforms}
    candidates = {p: load_candidates(p) for p in platforms}

    v2_by_platform = {}
    diff_rows = []
    coverage_rows = []
    for p in platforms:
        v2_rows = []
        for hotel in master:
            hid = hotel["hotel_id"]
            v1r = v1_rows[p].get(hid)
            cand = candidates[p].get(hid)
            v2r = build_v2_row(hotel, p, v1r, cand)
            v2_rows.append(v2r)
            diff_rows.append({
                "hotel_id": hid, "hotel_name": hotel["hotel_name"], "platform": p,
                "v1_status": v1r.get("status") if v1r else "MISSING",
                "v2_status": v2r["status"],
                "change_type": diff_change_type(v1r.get("status") if v1r else "", v2r),
            })
        v2_by_platform[p] = v2_rows

        out_path = LINK_DIR / f"bodrum_hotels_{'google_travel' if p == 'google_travel' else 'trip_com'}_direct_links_v2.csv"
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=V2_FIELDS)
            w.writeheader()
            for r in v2_rows:
                w.writerow(r)
        print(f"Wrote {out_path} ({len(v2_rows)} rows)")

        total = len(v2_rows)
        verified = sum(1 for r in v2_rows if r["status"] == "verified_direct")
        exact = sum(1 for r in v2_rows if candidates[p].get(r["hotel_id"], {}).get("validation_status") == "FOUND_EXACT")
        high_conf = verified - exact if verified >= exact else 0
        review = sum(1 for r in v2_rows if r["status"] == "review_required")
        not_found = sum(1 for r in v2_rows if r["status"] == "NOT_FOUND")
        not_attempted = sum(1 for r in v2_rows if r["status"] == "NOT_ATTEMPTED")
        error = sum(1 for r in v2_rows if r["status"] in ("ERROR", "BLOCKED"))
        coverage_rows.append({
            "platform": p, "total_master": total, "verified_exact": exact,
            "verified_high_confidence": high_conf, "review_required": review,
            "not_found": not_found, "not_attempted": not_attempted, "blocked_or_error": error,
        })

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    diff_path = REPORTS_DIR / "platform_link_discovery_v1_v2_diff.csv"
    with open(diff_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hotel_id", "hotel_name", "platform", "v1_status", "v2_status", "change_type"])
        w.writeheader()
        for r in diff_rows:
            w.writerow(r)
    print(f"Wrote {diff_path}")

    cov_path = REPORTS_DIR / "all_hotel_discovery_coverage.csv"
    with open(cov_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["platform", "total_master", "verified_exact", "verified_high_confidence",
                                           "review_required", "not_found", "not_attempted", "blocked_or_error"])
        w.writeheader()
        for r in coverage_rows:
            w.writerow(r)
    print(f"Wrote {cov_path}")

    # multiplatform coverage + targets v2
    g_by_id = {r["hotel_id"]: r for r in v2_by_platform["google_travel"]}
    t_by_id = {r["hotel_id"]: r for r in v2_by_platform["trip"]}
    multi_rows = []
    targets_rows = []
    two_platform = one_platform = zero_platform = 0
    for hotel in master:
        hid = hotel["hotel_id"]
        gv = g_by_id[hid]["status"] == "verified_direct"
        tv = t_by_id[hid]["status"] == "verified_direct"
        cnt = int(gv) + int(tv)
        if cnt == 2:
            two_platform += 1
        elif cnt == 1:
            one_platform += 1
        else:
            zero_platform += 1
        multi_rows.append({"hotel_id": hid, "hotel_name": hotel["hotel_name"], "area": hotel["area"],
                            "google_verified": gv, "trip_verified": tv, "platform_coverage_count": cnt})
        targets_rows.append({
            "hotel_id": hid, "hotel_name": hotel["hotel_name"], "area": hotel["area"],
            "google_travel_url": g_by_id[hid]["direct_url"], "google_travel_status": g_by_id[hid]["status"],
            "google_travel_confidence": g_by_id[hid]["confidence_score"],
            "trip_url": t_by_id[hid]["direct_url"], "trip_status": t_by_id[hid]["status"],
            "trip_confidence": t_by_id[hid]["confidence_score"],
            "policy_trip_url": t_by_id[hid]["direct_url"] if tv else "",
            "platform_coverage_count": cnt,
            "manual_review_required": g_by_id[hid]["status"] == "review_required" or t_by_id[hid]["status"] == "review_required",
            "enabled_google": gv, "enabled_trip": tv, "enabled_policies": tv,
        })

    multi_path = REPORTS_DIR / "all_hotel_multiplatform_coverage.csv"
    with open(multi_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hotel_id", "hotel_name", "area", "google_verified", "trip_verified", "platform_coverage_count"])
        w.writeheader()
        for r in multi_rows:
            w.writerow(r)
    print(f"Wrote {multi_path}")
    print(f"  2-platform verified: {two_platform} | 1-platform: {one_platform} | 0-platform: {zero_platform}")

    targets_path = CONFIG_DIR / "multiplatform_hotel_targets_v2.csv"
    with open(targets_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(targets_rows[0].keys()))
        w.writeheader()
        for r in targets_rows:
            w.writerow(r)
    print(f"Wrote {targets_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
