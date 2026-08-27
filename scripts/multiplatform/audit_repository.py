"""Section 1-8 audit: compares the master hotel dataset against the three
platform direct-link CSVs and writes all audit report CSVs. Read-only —
never fabricates a missing URL or hotel record.

Usage:
    python scripts/multiplatform/audit_repository.py
"""
from __future__ import annotations

import _pathsetup  # noqa: F401  (must run before bodrum_intelligence imports)

import csv
from collections import Counter, defaultdict

from bodrum_intelligence.reviews.common import (
    PLATFORM_LINK_FILES,
    REPORTS_DIR,
    master_hotel_csv_path,
    read_csv_dicts,
)
from bodrum_intelligence.reviews.validation import (
    is_verified,
    name_match_status,
    normalize_name,
    url_format_status,
    url_present,
)


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    master_path = master_hotel_csv_path()
    if not master_path.exists():
        print(f"HATA: master hotel dataset bulunamadi: {master_path}")
        print("BODRUM_MASTER_HOTEL_CSV ortam degiskeni veya "
              "config/pipeline_settings.json ile yolu belirtin.")
        return 1

    master_rows = read_csv_dicts(master_path)
    master_by_id = {r["hotel_id"]: r for r in master_rows}
    master_ids = set(master_by_id)

    hotel_id_counts = Counter(r["hotel_id"] for r in master_rows)
    place_id_counts = Counter(r["place_id"] for r in master_rows)
    area_counts = Counter(r["area"] for r in master_rows)

    # ---- master_hotel_audit.csv ----
    with open(REPORTS_DIR / "multiplatform_master_hotel_audit.csv", "w",
              newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["total_rows", len(master_rows)])
        w.writerow(["unique_hotel_id", len(hotel_id_counts)])
        w.writerow(["unique_place_id", len(place_id_counts)])
        w.writerow(["duplicate_hotel_id_count", sum(1 for v in hotel_id_counts.values() if v > 1)])
        w.writerow(["duplicate_place_id_count", sum(1 for v in place_id_counts.values() if v > 1)])
        w.writerow(["missing_hotel_id_rows", sum(1 for r in master_rows if not r["hotel_id"].strip())])
        w.writerow(["unique_areas", len(area_counts)])
        for area, cnt in sorted(area_counts.items(), key=lambda x: -x[1]):
            w.writerow([f"area:{area}", cnt])

    link_data = {p: {r["hotel_id"]: r for r in read_csv_dicts(path)}
                 for p, path in PLATFORM_LINK_FILES.items()}

    url_seen: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for platform, by_id in link_data.items():
        for hid, r in by_id.items():
            if url_present(r.get("direct_url")):
                url_seen[platform][r["direct_url"].strip()].append(hid)

    missing_from_link: dict[str, list[str]] = defaultdict(list)
    platform_flags: dict[str, dict[str, bool]] = defaultdict(dict)
    inventory_rows: list[dict] = []
    name_conflicts: set[str] = set()
    area_mismatches: set[str] = set()

    for hid, mrow in master_by_id.items():
        for platform in PLATFORM_LINK_FILES:
            by_id = link_data[platform]
            lrow = by_id.get(hid)
            if lrow is None:
                missing_from_link[hid].append(platform)
                platform_flags[hid][platform] = False
                inventory_rows.append({
                    "hotel_id": hid, "platform": platform,
                    "hotel_name_master": mrow["hotel_name"], "hotel_name_link": "",
                    "area_master": mrow["area"], "area_link": "",
                    "in_master": True, "in_link_file": False,
                    "name_match_status": "MISSING_LINK_RECORD",
                    "area_mismatch_flag": "MISSING_LINK_RECORD",
                    "direct_url": "", "status": "MISSING_LINK_RECORD",
                    "url_format_status": "MISSING_LINK_RECORD",
                    "duplicate_url_flag": False,
                })
                continue
            link_name, link_area = lrow.get("hotel_name", ""), lrow.get("area", "")
            nm_status = name_match_status(mrow["hotel_name"], link_name)
            area_mismatch = "MISMATCH" if normalize_name(mrow["area"]) != normalize_name(link_area) else "OK"
            durl, status = lrow.get("direct_url", ""), lrow.get("status", "")
            verified = is_verified(status)
            platform_flags[hid][platform] = verified
            if nm_status in ("CONFLICT", "REVIEW_REQUIRED"):
                name_conflicts.add(hid)
            if area_mismatch == "MISMATCH":
                area_mismatches.add(hid)
            inventory_rows.append({
                "hotel_id": hid, "platform": platform,
                "hotel_name_master": mrow["hotel_name"], "hotel_name_link": link_name,
                "area_master": mrow["area"], "area_link": link_area,
                "in_master": True, "in_link_file": True,
                "name_match_status": nm_status,
                "area_mismatch_flag": area_mismatch,
                "direct_url": durl, "status": status,
                "url_format_status": url_format_status(platform, durl),
                "duplicate_url_flag": url_present(durl) and len(url_seen[platform][durl.strip()]) > 1,
            })

    extra_rows = [(p, hid) for p, by_id in link_data.items() for hid in by_id if hid not in master_ids]

    with open(REPORTS_DIR / "multiplatform_link_inventory_audit.csv", "w",
              newline="", encoding="utf-8-sig") as f:
        fieldnames = ["hotel_id", "platform", "hotel_name_master", "hotel_name_link", "area_master",
                      "area_link", "in_master", "in_link_file", "name_match_status",
                      "area_mismatch_flag", "direct_url", "status", "url_format_status", "duplicate_url_flag"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in inventory_rows:
            w.writerow(row)
        for platform, hid in extra_rows:
            w.writerow({"hotel_id": hid, "platform": platform, "name_match_status": "EXTRA_IN_LINK_FILE",
                        "in_master": False, "in_link_file": True})

    with open(REPORTS_DIR / "multiplatform_missing_hotel_ids.csv", "w",
              newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["hotel_id", "hotel_name", "area", "missing_from_platforms", "note"])
        for hid, platforms in sorted(missing_from_link.items()):
            m = master_by_id[hid]
            w.writerow([hid, m["hotel_name"], m["area"], "|".join(platforms),
                        "MISSING_LINK_RECORD - present in master, absent from listed platform "
                        "link file(s). No URL fabricated."])

    with open(REPORTS_DIR / "multiplatform_link_coverage_by_platform.csv", "w",
              newline="", encoding="utf-8-sig") as f:
        fieldnames = ["platform", "total_hotels_in_file", "verified_direct_count", "null_url_count",
                      "unknown_status_count", "duplicate_url_count", "duplicate_hotel_id_count",
                      "invalid_url_format_count", "missing_from_master_link_file_count"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for platform, by_id in link_data.items():
            rows = list(by_id.values())
            hid_counts = Counter(by_id.keys())
            w.writerow({
                "platform": platform,
                "total_hotels_in_file": len(rows),
                "verified_direct_count": sum(1 for r in rows if is_verified(r.get("status"))),
                "null_url_count": sum(1 for r in rows if not url_present(r.get("direct_url"))),
                "unknown_status_count": sum(1 for r in rows if (r.get("status") or "").strip().lower()
                                             not in ("verified_direct", "null", "")),
                "duplicate_url_count": sum(1 for urls in url_seen[platform].values() if len(urls) > 1),
                "duplicate_hotel_id_count": sum(1 for v in hid_counts.values() if v > 1),
                "invalid_url_format_count": sum(1 for r in rows if url_format_status(
                    platform, r.get("direct_url")) in ("INVALID_DOMAIN", "INVALID_URL")),
                "missing_from_master_link_file_count": len(master_ids - set(by_id.keys())),
            })

    with open(REPORTS_DIR / "multiplatform_link_coverage_by_area.csv", "w",
              newline="", encoding="utf-8-sig") as f:
        fieldnames = ["platform", "area", "total_hotels", "verified_direct_count", "coverage_pct"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for platform, by_id in link_data.items():
            area_total, area_verified = Counter(), Counter()
            for hid, r in by_id.items():
                m = master_by_id.get(hid)
                area = m["area"] if m else r.get("area", "UNKNOWN")
                area_total[area] += 1
                if is_verified(r.get("status")):
                    area_verified[area] += 1
            for area in sorted(area_total):
                tot, ver = area_total[area], area_verified[area]
                w.writerow({"platform": platform, "area": area, "total_hotels": tot,
                            "verified_direct_count": ver,
                            "coverage_pct": round(100 * ver / tot, 1) if tot else 0})

    coverage_hist: Counter = Counter()
    with open(REPORTS_DIR / "multiplatform_hotel_platform_coverage.csv", "w",
              newline="", encoding="utf-8-sig") as f:
        fieldnames = ["hotel_id", "hotel_name", "area", "has_google_travel_verified", "has_trip_verified",
                      "has_tripadvisor_verified", "platform_coverage_count"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for hid, m in sorted(master_by_id.items()):
            g = platform_flags[hid].get("google_travel", False)
            t = platform_flags[hid].get("trip", False)
            ta = platform_flags[hid].get("tripadvisor", False)
            cnt = sum([g, t, ta])
            coverage_hist[cnt] += 1
            w.writerow({"hotel_id": hid, "hotel_name": m["hotel_name"], "area": m["area"],
                        "has_google_travel_verified": g, "has_trip_verified": t,
                        "has_tripadvisor_verified": ta, "platform_coverage_count": cnt})

    print("=== AUDIT SUMMARY ===")
    print(f"Master hotels: {len(master_rows)} (unique hotel_id: {len(hotel_id_counts)}, "
          f"unique place_id: {len(place_id_counts)})")
    print(f"Missing link records: {dict(missing_from_link)}")
    print(f"Platform coverage histogram (count -> #hotels): {dict(sorted(coverage_hist.items(), reverse=True))}")
    print(f"Name mismatch/conflict hotel_ids: {sorted(name_conflicts)}")
    print(f"Area mismatch hotel_ids: {sorted(area_mismatches)}")
    for platform, by_id in link_data.items():
        verified = sum(1 for r in by_id.values() if is_verified(r.get("status")))
        print(f"  {platform}: {verified}/{len(by_id)} verified_direct")
    print(f"Reports written to: {REPORTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
