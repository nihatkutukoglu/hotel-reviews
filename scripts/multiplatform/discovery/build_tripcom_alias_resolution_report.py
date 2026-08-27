"""Phase (Trip.com cross-platform master prompt) A2: reports the resolution
status of the 5 previously-WRONG_ENTITY Trip.com hotels (BOD051/055/059/
072/073). All 5 aliases were added and verified in the prior session
(config/multiplatform_hotel_aliases.csv) - this just produces the
requested audit artifact from the current, real config state.

Usage:
    python scripts/multiplatform/discovery/build_tripcom_alias_resolution_report.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _pathsetup  # noqa: F401, E402

from bodrum_intelligence.reviews.common import CONFIG_DIR, REPORTS_DIR, master_hotel_csv_path, read_csv_dicts

PREVIOUS_WRONG_ENTITY_IDS = ["BOD051", "BOD055", "BOD059", "BOD072", "BOD073"]


def main() -> int:
    master = {r["hotel_id"]: r for r in read_csv_dicts(master_hotel_csv_path())}
    targets = {r["hotel_id"]: r for r in read_csv_dicts(CONFIG_DIR / "multiplatform_hotel_targets.csv")}
    aliases = read_csv_dicts(CONFIG_DIR / "multiplatform_hotel_aliases.csv")
    alias_by_hotel = {(a["hotel_id"], a["platform"]): a for a in aliases}

    rows = []
    for hid in PREVIOUS_WRONG_ENTITY_IDS:
        m = master.get(hid, {})
        t = targets.get(hid, {})
        a = alias_by_hotel.get((hid, "trip"))
        rows.append({
            "hotel_id": hid,
            "canonical_master_name": m.get("hotel_name", ""),
            "area": m.get("area", ""),
            "trip_url": t.get("trip_url", ""),
            "trip_status_in_config": t.get("trip_status", ""),
            "alias_added": bool(a),
            "accepted_alias_text": a["accepted_alias"] if a else "",
            "alias_reason": a["reason"] if a else "",
            "resolution": "RESOLVED_VIA_MANUAL_ALIAS" if a else "STILL_WRONG_ENTITY_UNRESOLVED",
        })

    out_path = REPORTS_DIR / "tripcom_manual_alias_resolution_phase4.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    resolved = sum(1 for r in rows if r["alias_added"])
    print(f"Wrote {out_path}: {resolved}/{len(rows)} previously-WRONG_ENTITY hotels resolved via alias")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
