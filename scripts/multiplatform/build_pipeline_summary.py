"""Section 49: assembles reports/multiplatform_pipeline_summary.txt from
whichever reports have actually been produced so far. Never invents a
number - a section is marked "not yet run" if its source report is missing.

Usage:
    python scripts/multiplatform/build_pipeline_summary.py
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import csv
from collections import Counter

from bodrum_intelligence.reviews.common import CONFIG_DIR, REPORTS_DIR


def read_csv(path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    lines: list[str] = []

    def h(title):
        lines.append("")
        lines.append(f"=== {title} ===")

    master_audit = read_csv(REPORTS_DIR / "multiplatform_master_hotel_audit.csv")
    h("MASTER")
    if master_audit is None:
        lines.append("Henuz calistirilmadi: audit_repository.py")
    else:
        metrics = {r["metric"]: r["value"] for r in master_audit if not r["metric"].startswith("area:")}
        lines.append(f"master hotel count: {metrics.get('total_rows')}")
        lines.append(f"unique hotel_id: {metrics.get('unique_hotel_id')}")
        lines.append(f"duplicate hotel_id: {metrics.get('duplicate_hotel_id_count')}")
        lines.append(f"duplicate place_id: {metrics.get('duplicate_place_id_count')}")

    h("LINK FILES")
    missing = read_csv(REPORTS_DIR / "multiplatform_missing_hotel_ids.csv")
    coverage_by_platform = read_csv(REPORTS_DIR / "multiplatform_link_coverage_by_platform.csv")
    if coverage_by_platform is None:
        lines.append("Henuz calistirilmadi: audit_repository.py")
    else:
        for r in coverage_by_platform:
            lines.append(f"{r['platform']}: {r['total_hotels_in_file']} hotel, "
                         f"verified_direct={r['verified_direct_count']}, null_url={r['null_url_count']}")
    if missing:
        lines.append(f"191 vs 192 discrepancy: {len(missing)} hotel_id present in master but "
                     "missing from link file(s):")
        for r in missing:
            lines.append(f"  {r['hotel_id']} | {r['hotel_name']} | {r['area']} | "
                         f"missing_from={r['missing_from_platforms']}")
    elif missing == []:
        lines.append("191 vs 192 discrepancy: none found (all link files match master 1:1).")

    h("COVERAGE")
    coverage = read_csv(REPORTS_DIR / "multiplatform_hotel_platform_coverage.csv")
    if coverage is None:
        lines.append("Henuz calistirilmadi: audit_repository.py")
    else:
        hist = Counter(r["platform_coverage_count"] for r in coverage)
        for n in ("3", "2", "1", "0"):
            lines.append(f"{n} platformda verified: {hist.get(n, 0)} hotel")

    h("SCRIPTS")
    lines.append("google/yorum.py: audit edildi, degisiklik yok (calisan secicilere dokunulmadi).")
    lines.append("trip/trip_yorum.py: 'show more' dugmesi yoksa artik crash etmiyor (bugfix); "
                 "--maksimum-yorum eklendi.")
    lines.append("tripadvisor/tripadvisor_yorum.py: --maksimum-yorum eklendi.")
    lines.append("politikalar/politikalar.py: degisiklik yok; tum-ya-da-hic yazma davranisi "
                 "policies_adapter.py tarafindan bypass edilip PARTIAL satir uretilebiliyor.")

    h("SMOKE")
    smoke = read_csv(REPORTS_DIR / "multiplatform_smoke_test.csv")
    if smoke is None:
        lines.append("Henuz calistirilmadi: run_smoke_tests.py")
        full_batch_ready = False
    else:
        hotels = sorted({(r["hotel_id"], r["hotel_name"]) for r in smoke})
        for hid, hname in hotels:
            lines.append(f"  {hid} | {hname}")
        for r in smoke:
            lines.append(f"    {r['hotel_id']} / {r['platform']}: status={r['status']} "
                         f"rows_scraped={r['rows_scraped']} duplicate_rows={r['duplicate_rows']}")
        wrong_entity = sum(1 for r in smoke if r["status"] == "WRONG_ENTITY")
        errors = sum(1 for r in smoke if r["status"] in ("ERROR", "PAGE_ERROR", "MANUAL_ACTION_REQUIRED"))
        lines.append(f"wrong-entity count: {wrong_entity}")
        lines.append(f"error/blocked count: {errors}")
        passed = sum(1 for r in smoke if r["status"] in ("COMPLETED", "PARTIAL")
                     and r["duplicate_rows"] == "0" and r["entity_valid"] == "True")
        full_batch_ready = wrong_entity == 0 and len(smoke) > 0 and passed >= max(1, len(smoke) // 2)

    h("READY")
    lines.append(f"FULL_BATCH_READY = {'YES' if full_batch_ready else 'NO'}")

    h("NEXT COMMANDS")
    if full_batch_ready:
        lines.append("python scripts/multiplatform/run_batch.py --dry-run")
        lines.append("python scripts/multiplatform/run_batch.py --platform google_travel --max-reviews 20")
        lines.append("python scripts/multiplatform/run_batch.py --platform trip --max-reviews 20")
        lines.append("python scripts/multiplatform/run_batch.py --platform tripadvisor --max-reviews 20")
        lines.append("python scripts/multiplatform/run_batch.py --platform policies")
    else:
        lines.append("python scripts/multiplatform/run_smoke_tests.py  # once smoke passes, re-run this summary")

    out_path = REPORTS_DIR / "multiplatform_pipeline_summary.txt"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
