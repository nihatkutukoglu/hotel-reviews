# Bodrum Multi-Platform Hotel Reviews & Policies Pipeline

Scrapes and audits hotel reviews (Google Travel, Trip.com, TripAdvisor) and
hotel policies (Trip.com) for the ~192 hotels tracked in the sibling
[Bodrum Hotel & Destination Intelligence](../../bodrum%20otel/bodrum-otel)
master dataset.

The original four single-hotel scripts (`google/yorum.py`, `trip/trip_yorum.py`,
`tripadvisor/tripadvisor_yorum.py`, `politikalar/politikalar.py`) still work
standalone exactly as before. On top of them, `scripts/multiplatform/` adds a
source-aware, hotel_id-based, resume/dedupe-safe batch layer that:

- verifies the on-page hotel name against the expected hotel **before**
  scraping (never scrapes the wrong entity),
- writes one raw file per hotel per platform in that platform's own schema
  (raw schemas are never merged or overwritten),
- never fabricates a URL for a hotel that has no verified direct link,
- runs strictly sequentially (one browser at a time), and
- never attempts to solve CAPTCHAs or bypass bot/human verification.

## Platforms

| Platform | Script | Legacy CSV | Notes |
|---|---|---|---|
| Google Travel | `google/yorum.py` | `google/yorum.csv` | rating format `"4/5"` |
| Trip.com | `trip/trip_yorum.py` | `trip/trip_yorum.csv` | rating format `0-10` |
| TripAdvisor | `tripadvisor/tripadvisor_yorum.py` | `tripadvisor/tripadvisor_yorum.csv` | rating format `1-5` |
| Trip.com policies | `politikalar/politikalar.py` | `politikalar/politikalar.csv` | one row per hotel |

## Folder structure

```
bodrum-otel-linkleri/     3 platform direct-link CSVs (hotel_id, direct_url, status, ...)
google/ trip/ tripadvisor/ politikalar/   original single-hotel scripts (unchanged, plus 2 small
                                          additive bugfixes - see "Changes to the legacy scripts")
config/                   generated: multiplatform_hotel_targets.csv, pipeline_settings.json (optional)
src/bodrum_intelligence/reviews/   reusable core: common.py, validation.py, runner.py,
                                    <platform>_adapter.py
scripts/multiplatform/    CLI entry points (see below)
data/raw/reviews/<platform>/<hotel_id>_<slug>.csv        one file per hotel per platform, raw schema
data/raw/hotel_policies/trip/<hotel_id>_<slug>.csv        one row per hotel
data/processed/           optional combined/normalized outputs (see build_combined_outputs.py)
reports/                  audit, coverage, validation, smoke-test and batch-status reports
tests/                    pytest suite
```

## Setup

```
pip install -r requirements.txt
pip install pytest   # for the test suite
```

Chrome must be installed; Selenium 4's built-in Selenium Manager downloads a
matching chromedriver automatically.

The master hotel dataset lives in a **sibling repository**, not inside this
one. By default it's resolved as
`../bodrum otel/bodrum-otel/bodrum_hotels_master_2026-08-24.csv` relative to
this repo's parent folder. Override with either:
- `BODRUM_MASTER_HOTEL_CSV=<path>` environment variable, or
- `config/pipeline_settings.json` with `{"master_hotel_csv": "<path relative to this repo's parent>"}`

## Commands

Run these in order:

```
# 1. Read-only audit: master vs link files, coverage, name/area/URL consistency
python scripts/multiplatform/audit_repository.py

# 2. Merge master + 3 link files into one per-hotel target config
python scripts/multiplatform/build_platform_config.py

# 3. Verify on-page hotel name vs expected name, WITHOUT scraping
python scripts/multiplatform/validate_entities.py --max-hotels 10

# 4. Scrape 5 hotels x up to 10 reviews/platform + 1 policies row each
python scripts/multiplatform/run_smoke_tests.py

# 5. Check reports/multiplatform_smoke_test.csv, then preview the full run
python scripts/multiplatform/run_batch.py --dry-run

# 6. Only once smoke tests pass: run for real, still sequential, still capped
python scripts/multiplatform/run_batch.py --platform tripadvisor --area Akyarlar --max-hotels 5 --max-reviews 20

# optional: single-platform wrappers over run_batch.py
python scripts/multiplatform/run_google_travel.py --max-hotels 5
python scripts/multiplatform/run_trip.py --max-hotels 5
python scripts/multiplatform/run_tripadvisor.py --max-hotels 5
python scripts/multiplatform/run_policies.py --max-hotels 5

# optional: combined/normalized processed outputs, built from whatever raw
# data already exists (never triggers new scraping)
python scripts/multiplatform/build_combined_outputs.py
```

`run_batch.py` CLI flags: `--platform`, `--hotel-id` (repeatable),
`--area` (repeatable), `--max-hotels`, `--max-reviews`, `--headless`,
`--resume/--no-resume` (default: resume), `--force` (policies only),
`--validate-only`, `--dry-run`.

## Resume / dedupe / safe-stop

- Google/Trip/TripAdvisor review scripts already hash-dedupe on every
  incremental write (their own logic, untouched) - re-running never
  duplicates a review and never overwrites the raw file.
- Policies are one row per hotel per file; `resume=True` (default) skips a
  hotel that already has a policies file unless `--force` is passed.
- A `WRONG_ENTITY` result (on-page name doesn't match the expected hotel)
  stops **before** any scraping starts for that hotel/platform.
- A CAPTCHA / "access temporarily restricted" / human-verification page is
  reported as `PAGE_ERROR` / `MANUAL_ACTION_REQUIRED` / `BLOCKED_SAFE_STOP`
  and skipped - never solved or bypassed.

## Outputs

Raw (platform-native schema, one file per hotel per platform, never overwritten):
`data/raw/reviews/<platform>/<hotel_id>_<slug>.csv`,
`data/raw/hotel_policies/trip/<hotel_id>_<slug>.csv`

Processed (optional, built only from existing raw data):
`data/processed/multiplatform_reviews_raw_normalized.csv` (metadata + `rating_5_scale` added,
sources never merged into one row),
`data/processed/hotel_policies_features.csv` (policy fields + binary amenity flags)

Reports: `reports/multiplatform_master_hotel_audit.csv`,
`multiplatform_link_inventory_audit.csv`, `multiplatform_missing_hotel_ids.csv`,
`multiplatform_link_coverage_by_platform.csv`, `multiplatform_link_coverage_by_area.csv`,
`multiplatform_hotel_platform_coverage.csv`, `multiplatform_entity_validation.csv`,
`multiplatform_smoke_test.csv`, `multiplatform_scrape_status.csv`,
`multiplatform_cross_source_duplicate_candidates.csv`

## Discovery + analysis layer (Google Travel & Trip.com)

On top of the raw scraping layer above, `src/bodrum_intelligence/discovery/` and
`src/bodrum_intelligence/analysis/` add a full URL-discovery -> entity-validation ->
scrape -> clean -> notebook pipeline for Google Travel and Trip.com (TripAdvisor
remains scraping-only/out of scope for this layer per explicit project instruction).

- `scripts/multiplatform/discovery/` - live, sequential, single-browser URL discovery
  (Google Travel search-result entity pages / Trip.com search box), transparent
  0-100 candidate scoring, and a narrow per-(hotel_id, platform) manual-alias
  override (`config/multiplatform_hotel_aliases.csv`) for confirmed same-property
  naming variants (translations, dropped suffixes, punctuation) - never a general
  fuzzy-matching rule, and brand-family collisions (e.g. Selectum Colours vs
  Selectum Collection) are explicitly regression-tested to never be affected.
- `data/processed/google_travel_all_hotels_reviews_clean.csv` and
  `data/processed/tripcom_reviews_clean.csv` - cleaned, source-labeled review
  corpora (raw rating and platform always preserved alongside any normalized
  5-scale value).
- `data/processed/hotel_policies_features.csv` - evidence-based policy/amenity
  flags (Trip.com only), never inferred without raw text evidence.
- `data/processed/hotel_360_intelligence.csv` - one row per master hotel,
  descriptive customer-voice/coverage archetypes with an explicit confidence
  tier (HIGH/MEDIUM/LOW/VERY_LOW); never a "best/worst hotel" ranking.
- `notebooks/12`-`20` - Google Travel audit/EDA/NLP-aspect/customer-voice
  (12-15), Trip.com audit/segment analysis (16-17), Google x Trip.com
  cross-platform comparison (18, hotel/aspect-summary level only, no
  row-level merge), policies/amenities enrichment (19), and the Hotel 360
  summary (20).

## Changes to the legacy scripts

Two small, additive bugfixes only - no selectors were touched:
- `trip/trip_yorum.py`: `daha_fazla_yorumu_ac()` no longer raises/aborts the
  whole run when a hotel has no "show more" button (some hotels don't have
  one); it now just continues with the reviews already visible.
- `trip/trip_yorum.py` and `tripadvisor/tripadvisor_yorum.py`:
  `yorumlari_cek()` gained an optional `maksimum_yorum` parameter
  (default `0` = unlimited, same as before) and a matching `--maksimum-yorum`
  CLI flag, mirroring what `google/yorum.py` already had - needed to cap
  smoke-test/batch runs.

`politikalar/politikalar.py`'s own writer aborts the whole hotel if even one
policy field is missing; rather than patch that, `policies_adapter.py`
calls the same underlying field-lookup helpers directly and tolerates
individual fields failing, producing a `PARTIAL` row instead of nothing.

## Known data-quality findings (see reports/ for full detail)

- All three platform link CSVs are missing exactly one hotel present in the
  master dataset: **BOD192 / Yalıpark Beach Hotel / Yalıkavak** (this is the
  191-vs-192 discrepancy). No URL was fabricated for it.
- Three hotels (**BOD135, BOD155, BOD175**) have a master `hotel_name` that
  contains a literal `|` character (e.g. `"Yılmaz Hotel | Bodrum Ortakent
  Otelleri"`); the link-file generator split on that `|`, shifting the
  suffix into the `area` column. Flagged as `manual_review_required`, not
  auto-corrected.
- After the full-coverage discovery pass, Google Travel has 108 and Trip.com
  has 96 `verified_direct` hotels (of 192 master hotels); 149 hotels are
  `enabled=TRUE` in `config/multiplatform_hotel_targets.csv` (at least one
  verified platform), the rest await further discovery or remain genuinely
  not found on that platform's public search.

## Limitations

- Selectors are tied to each site's current DOM; a front-end change on any
  of the three platforms can break scraping without warning.
- No CAPTCHA solving, proxy rotation, fingerprint spoofing, or login bypass
  is implemented or intended.
- Only Trip.com is scraped for policies; Google Travel/TripAdvisor policy
  data is out of scope.
