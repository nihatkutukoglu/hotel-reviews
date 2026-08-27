"""Thin wrapper around the existing, untouched politikalar/politikalar.py
scraper.

politikalar.py's own writer (csvye_yaz) raises RuntimeError and produces
*zero* output if even one policy field is missing (e.g. no explicit pet
policy, no license number) - a real bug for batch use across ~190 hotels
that phrase things differently. This adapter therefore does not call
calistir()/csvye_yaz(); it reads each field independently and tolerates
one failing, producing a PARTIAL row with whatever it did find.

Live DOM inspection (2026-08-26, phase 2) found the ROOT cause of most
missing fields wasn't a broken CSS class - it's that Trip.com's *value
wording* for several fields changed (e.g. crib/extra-bed policy used to
start with "For all room types...", now reads "Extra bed and crib
policies may vary...") and varies per hotel (e.g. not every property has
an explicit checkout time or age-requirement phrase using the exact old
wording). Matching by the STABLE LEFT-HAND LABEL ("Child policies",
"Cribs and Extra Beds", "Breakfast", "Pets", "Service animals", "Age
Requirements") and reading whatever value sits in that item's right-hand
box - instead of matching a specific value-text prefix - is far more
robust to per-hotel wording differences and future copy changes.
Check-in/check-out and license number already matched on structurally
guaranteed prefixes ("After"/"Before"/"License number:") that Trip.com's
own template inserts, so those two extraction paths are unchanged.

One row per hotel per file (section 16/24); resume=True skips a hotel that
already has a policies file unless force=True.
"""
from __future__ import annotations

import csv

from selenium.common.exceptions import TimeoutException

from .aliases import resolve_entity_status
from .common import REPO_ROOT, per_hotel_csv_path, load_legacy_module, utcnow_iso, DATA_RAW_DIR
from .validation import WRONG_ENTITY

_MODULE = None

_LABEL_TO_FIELD = {
    "Child policies": "cocuk_politikası",
    "Cribs and Extra Beds": "bebek_ve_ek_yatak",
    "Breakfast": "kahvalti",
    "Pets": "evcil_hayvan",
    "Service animals": "hizmet_hayvanları",
    "Age Requirements": "yas_sarti",
}

_VALUE_BY_LABEL_JS = """
const label = arguments[0];
const lefts = document.querySelectorAll("[class*='hotelPolicy-item_leftA']");
for (const left of lefts) {
    if ((left.textContent || '').trim() === label) {
        const item = left.closest("[class*='hotelPolicy-item__']");
        if (!item) continue;
        const right = item.querySelector("[class*='hotelPolicy-item_right']");
        if (!right) continue;
        return (right.textContent || '').trim();
    }
}
return null;
"""


def _module():
    global _MODULE
    if _MODULE is None:
        _MODULE = load_legacy_module("legacy_politikalar", REPO_ROOT / "politikalar" / "politikalar.py")
    return _MODULE


def _safe_text(fn, *args) -> tuple[str, bool]:
    try:
        return fn(*args), True
    except TimeoutException:
        return "", False


def _value_by_label(driver, label: str) -> tuple[str, bool]:
    try:
        raw = driver.execute_script(_VALUE_BY_LABEL_JS, label)
    except Exception:  # noqa: BLE001 - treat any JS/DOM error as "not found"
        return "", False
    return (raw, True) if raw else ("", False)


def _read_policy_fields_tolerant(m, driver, otel_adi: str, hizmetler: str) -> tuple[dict, list[str]]:
    giris, ok_giris = _safe_text(
        m.ilk_metin, driver,
        "//strong[contains(@class,'hotelPolicyNew_hotelPolicy-check_desc') "
        "and starts-with(normalize-space(.),'After')]")
    cikis, ok_cikis = _safe_text(
        m.ilk_metin, driver,
        "//strong[contains(@class,'hotelPolicyNew_hotelPolicy-check_desc') "
        "and starts-with(normalize-space(.),'Before')]")
    sertifika, ok_sert = _safe_text(
        m.ilk_metin, driver,
        "//span[contains(@class,'hotelPolicyNew_hotelPolicy-item_description') "
        "and starts-with(normalize-space(.),'License number:')]")

    label_values: dict[str, str] = {}
    label_oks: dict[str, bool] = {}
    for label, field in _LABEL_TO_FIELD.items():
        raw, ok = _value_by_label(driver, label)
        label_values[field] = m.temizle(raw) if ok else ""
        label_oks[field] = ok

    row = {
        "otel_adi": otel_adi, "giris_saati": giris, "cıkıs_saati": cikis,
        "sertifika_numarasi": sertifika, "hizmetler": hizmetler,
        **label_values,
    }
    oks = {
        "giris_saati": ok_giris, "cıkıs_saati": ok_cikis, "sertifika_numarasi": ok_sert,
        **label_oks,
    }
    missing = [k for k, ok in oks.items() if not ok]
    return row, missing


def compute_policy_status_and_coverage(missing: list[str], has_facilities: bool) -> tuple[str, dict]:
    """Section 16/17: derive the overall policy_status and per-field
    coverage flags from the list of fields that failed to be found.
    Pure function, independent of Selenium, for direct unit testing.
    """
    if len(missing) == 9 and not has_facilities:
        policy_status = "VALID_ENTITY_NO_POLICY_DATA"
    elif missing:
        policy_status = "PARTIAL"
    else:
        policy_status = "COMPLETE"

    coverage = {
        "has_checkin": "giris_saati" not in missing,
        "has_checkout": "cıkıs_saati" not in missing,
        "has_children_policy": "cocuk_politikası" not in missing,
        "has_extra_bed_policy": "bebek_ve_ek_yatak" not in missing,
        "has_breakfast_policy": "kahvalti" not in missing,
        "has_pet_policy": "evcil_hayvan" not in missing,
        "has_service_animal_policy": "hizmet_hayvanları" not in missing,
        "has_age_rule": "yas_sarti" not in missing,
        "has_license": "sertifika_numarasi" not in missing,
        "has_facilities": has_facilities,
    }
    return policy_status, coverage


def scrape_hotel(hotel_id: str, expected_hotel_name: str, area: str, direct_url: str,
                  headless: bool = False, resume: bool = True, force: bool = False,
                  validate_only: bool = False) -> dict:
    m = _module()
    out_path = per_hotel_csv_path(DATA_RAW_DIR / "hotel_policies" / "trip",
                                   hotel_id, expected_hotel_name)
    result = {
        "hotel_id": hotel_id, "hotel_name_expected": expected_hotel_name, "area": area,
        "platform": "policies_trip", "source_url": direct_url,
        "detected_hotel_name": "", "name_match_status": "", "page_accessible": False,
        "review_section_found": False, "validation_status": "", "rows_added": 0,
        "status": "", "error": "", "checked_at": utcnow_iso(),
    }

    if not validate_only and resume and out_path.exists() and not force:
        result["status"] = "SKIPPED_RESUME"
        result["rows_added"] = 0
        return result

    driver = None
    try:
        driver = m.tarayici_olustur(headless)
        driver.get(direct_url)
        m.arama_butonuna_bas(driver)
        result["page_accessible"] = True
        detected = m.otel_adini_al(driver)
        result["detected_hotel_name"] = detected
        nm, vstatus = resolve_entity_status(hotel_id, "trip", expected_hotel_name, detected)
        result["name_match_status"] = nm
        result["validation_status"] = vstatus
        if vstatus == WRONG_ENTITY:
            result["status"] = "WRONG_ENTITY"
            return result
        if validate_only:
            result["status"] = vstatus
            return result

        m.bes_kademe_asagi_in(driver)
        try:
            hizmetler = m.hizmetleri_al(driver)
        except TimeoutException:
            hizmetler = ""
        m.politikalar_sekmesini_ac(driver)
        row, missing = _read_policy_fields_tolerant(m, driver, detected, hizmetler)
        has_facilities = bool(hizmetler)
        policy_status, coverage = compute_policy_status_and_coverage(missing, has_facilities)

        out_row = {
            "hotel_id": hotel_id, "hotel_name_expected": expected_hotel_name, "area": area,
            "source_url": direct_url, "collected_at": result["checked_at"], "policy_status": policy_status,
            **row, **coverage,
        }
        fieldnames = ["hotel_id", "hotel_name_expected", "area", "source_url", "collected_at",
                      "policy_status"] + list(m.CSV_ALANLARI) + list(coverage.keys())
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow({k: out_row.get(k, "") for k in fieldnames})

        result["review_section_found"] = True
        result["rows_added"] = 1
        result["status"] = policy_status
        if missing:
            result["error"] = "missing fields: " + ", ".join(missing)
    except TimeoutException as exc:
        msg = str(exc).split("Stacktrace:", 1)[0].strip()
        result["status"] = "MANUAL_ACTION_REQUIRED" if not msg else "PAGE_ERROR"
        result["error"] = msg
    except Exception as exc:  # noqa: BLE001 - report, never crash the batch
        result["status"] = "ERROR"
        result["error"] = str(exc)
    finally:
        if driver is not None:
            driver.quit()
    return result
