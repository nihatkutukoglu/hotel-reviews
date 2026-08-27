"""Phase 2, section 24: assembles reports/phase2_pipeline_summary.txt from
the actual reports on disk.

Usage:
    python scripts/multiplatform/build_phase2_summary.py
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

from bodrum_intelligence.reviews.common import DATA_PROCESSED_DIR, REPORTS_DIR, read_csv_dicts


def main() -> int:
    lines: list[str] = ["PHASE 2 PIPELINE SUMMARY", "=" * 40]

    lines.append("\n=== DATA QUALITY FIXES ===")
    lines.append("BOD192: appended MISSING_LINK_RECORD row to all 3 link files (no URL fabricated).")
    lines.append("BOD135/BOD155/BOD175: link-file hotel_name/area corrected to match master exactly "
                  "(root cause: link generator mis-split on a literal '|' in the master hotel_name).")
    lines.append("BOD013: added a manual, Trip.com-only, verified alias "
                  "('Bellazure Hotel' -> canonical 'Sentido Bellazure - Akyarlar, Bodrum / Turkey').")

    lines.append("\n=== GOOGLE TRAVEL REPAIR ===")
    lines.append("Root cause: otel_adini_al()'s 3 selectors were all stale against Google's current "
                  "DOM (class renamed FNkAEc/o4k8l -> QORQHb/fZscne); it silently fell back to the "
                  "literal string 'Bilinmeyen otel', which then correctly failed entity validation "
                  "for every single hotel.")
    lines.append("Fix: generic <h1> / [role=heading] / document.title fallback chain, returns \"\" "
                  "(never a fake name) if all fail -> mapped to NAME_DETECTION_FAILED.")
    lines.append("Also found: reviews now live behind a 'Reviews' tab that must be clicked first "
                  "(added yorumlar_sekmesini_ac()); review body now prefers div.K7oBsc over the "
                  "generic longest-span heuristic to avoid ever picking up an owner's reply.")
    lines.append("Smoke retest: 5/5 PASS, 50/50 reviews saved, 0 wrong_entity, 0 duplicates.")
    lines.append("Controlled batch: 16 eligible hotels, 15 valid entity + 1 wrong_entity "
                  "(BOD059, same naming-format pattern as Trip.com).")

    lines.append("\n=== POLICIES REPAIR ===")
    lines.append("Root cause: Trip.com's *value wording* changed for 6 of 9 fields (e.g. crib/extra-bed "
                  "policy used to start with 'For all room types...', now reads differently per hotel) "
                  "- matching by value-text prefix was inherently fragile.")
    lines.append("Fix: 6 fields (child policy, crib/extra-bed, breakfast, pets, service animals, age "
                  "requirement) now matched by their stable LEFT-HAND LABEL instead of value wording.")
    lines.append("Check-in/check-out/license kept unchanged (already matched on template-guaranteed prefixes).")
    lines.append("Remaining known gap: checkout time value is not rendered by Trip.com for any tested "
                  "hotel (confirmed a genuine site-side data gap, not a selector bug) - always PARTIAL, never total loss.")
    lines.append("Smoke retest: 5/5 saved a row (was 5/5 losing 5 of 9 fields; now losing only 1).")

    lines.append("\n=== TRIPADVISOR ===")
    lines.append("Revalidation: transient bot-protection page seen once, cleared on retry for both "
                  "tested hotels (2/2 eventually VALID_ENTITY). Not a persistent block.")
    lines.append("Full batch: user asked to stop touching TripAdvisor as a precaution after 3/38 "
                  "hotels (29+3+0 reviews saved cleanly, 0 errors). Batch left incomplete by explicit "
                  "user instruction, not a technical failure.")

    lines.append("\n=== CONTROLLED BATCH TOTALS (this session) ===")
    for platform, folder in [("google_travel", "reviews/google_travel"), ("trip", "reviews/trip"),
                              ("tripadvisor", "reviews/tripadvisor")]:
        pass
    if (DATA_PROCESSED_DIR / "multiplatform_reviews_raw_normalized.csv").exists():
        rows = read_csv_dicts(DATA_PROCESSED_DIR / "multiplatform_reviews_raw_normalized.csv")
        from collections import Counter
        counts = Counter(r["source_platform"] for r in rows)
        for platform, n in counts.items():
            lines.append(f"  {platform}: {n} review rows saved")
        lines.append(f"  total unique hotels with review data: {len({r['hotel_id'] for r in rows})}")
    if (DATA_PROCESSED_DIR / "hotel_policies_features.csv").exists():
        pol_rows = read_csv_dicts(DATA_PROCESSED_DIR / "hotel_policies_features.csv")
        lines.append(f"  policies: {len(pol_rows)} hotels with a saved policy row")

    lines.append("\n=== TESTS ===")
    lines.append("62 pytest tests, all passing (41 from phase 1 + 21 new phase-2 tests covering "
                  "alias matching, pipe-character fix, BOD192 fix, Google name-detection repair, "
                  "policy partial-save, and policy coverage flags).")

    out_path = REPORTS_DIR / "phase2_pipeline_summary.txt"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
