"""Builds and executes notebooks/20_hotel_360_intelligence_summary.ipynb.
Combines Google Travel + Trip.com + Trip segments + Policies + master data
into one hotel-level intelligence layer. No new scraping. No "best hotel"
ranking - descriptive/archetypal labels only (per master prompt G4)."""
from __future__ import annotations

import nbformat as nbf
from nbclient import NotebookClient
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
NB_PATH = REPO_ROOT / "notebooks" / "20_hotel_360_intelligence_summary.ipynb"

cells = []


def md(src): cells.append(nbf.v4.new_markdown_cell(src))
def code(src): cells.append(nbf.v4.new_code_cell(src))


md("""# Bodrum Hotel & Destination Intelligence
## 20 - Hotel 360° Intelligence Summary

Google Travel customer voice + Trip.com customer voice + Trip traveler segments + Trip policies/amenities
+ master hotel data tek hotel-level katmanda birleştirilir. "En iyi otel" sıralaması YAPILMAZ (G4).""")

code(f"""
import sys
sys.path.insert(0, r"{SRC}")
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
%matplotlib inline
import os

from bodrum_intelligence.reviews.common import master_hotel_csv_path

REPO_ROOT = r"{REPO_ROOT}"
FIG_DIR = REPO_ROOT + r"\\reports\\figures\\hotel_360"
os.makedirs(FIG_DIR, exist_ok=True)

master = pd.read_csv(master_hotel_csv_path())
g_profile = pd.read_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_profile_summary.csv")
t_profile = pd.read_csv(REPO_ROOT + r"\\reports\\tripcom_hotel_profile_summary.csv")
policy = pd.read_csv(REPO_ROOT + r"\\data\\processed\\hotel_policies_features.csv")
voice_profiles = pd.read_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_customer_voice_profiles.csv")
print("master:", len(master), "| google profiled:", len(g_profile), "| trip profiled:", len(t_profile), "| policy:", len(policy))
""")

md("## G2: Hotel 360 Master Table")
code("""
base = master[["hotel_id","hotel_name","area","google_rating","google_review_count"]].rename(
    columns={"google_rating": "master_google_rating", "google_review_count": "master_google_review_count"})

g = g_profile.set_index("hotel_id")[["n_reviews","mean_rating","low_share","high_share"]].rename(
    columns={"n_reviews":"google_travel_review_n","mean_rating":"google_travel_mean_rating",
             "low_share":"google_travel_low_share","high_share":"google_travel_high_share"})
voice = voice_profiles.set_index("hotel_id")[["top_aspects","top_high_context_aspects","top_low_context_aspects"]].rename(
    columns={"top_high_context_aspects":"google_strength_signals","top_low_context_aspects":"google_concern_signals",
             "top_aspects":"google_top_aspects"})

t_cols = {"n":"trip_review_n"}
for c in ["mean_rating_5","low_share","high_share","top_traveler_type","family_share_pct","couple_share_pct","distinct_countries"]:
    if c in t_profile.columns:
        t_cols[c] = {"mean_rating_5":"trip_mean_rating_5","low_share":"trip_low_share","high_share":"trip_high_share",
                     "top_traveler_type":"trip_top_traveler_type","family_share_pct":"trip_family_share",
                     "couple_share_pct":"trip_couple_share","distinct_countries":"trip_country_coverage"}[c]
t = t_profile.set_index("hotel_id").rename(columns=t_cols)[[v for v in t_cols.values() if v in t_profile.rename(columns=t_cols).columns]]

pol = policy.set_index("hotel_id")[["policy_status","amenity_count","family_feature_count",
                                     "wellness_feature_count","water_feature_count"]]
pol["has_policy_data"] = True

hotel_360 = base.set_index("hotel_id").join([g, voice, t, pol], how="left").reset_index()
hotel_360["has_policy_data"] = hotel_360["has_policy_data"].fillna(False)
hotel_360["source_count"] = hotel_360[["google_travel_review_n","trip_review_n"]].notna().sum(axis=1)

DATA_PROCESSED = REPO_ROOT + r"\\data\\processed\\hotel_360_intelligence.csv"
hotel_360.to_csv(DATA_PROCESSED, index=False)
assert hotel_360["hotel_id"].is_unique, "hotel_360 primary key (hotel_id) is not unique!"
print(f"Wrote {DATA_PROCESSED} ({len(hotel_360)} hotels, primary key unique confirmed)")
hotel_360.head(5)
""")

md("## G5: Confidence framework")
code("""
def confidence(row):
    n_google = row.get("google_travel_review_n") or 0
    n_trip = row.get("trip_review_n") or 0
    has_policy = bool(row.get("has_policy_data"))
    sources = row.get("source_count") or 0
    if sources == 2 and (n_google >= 20 or n_trip >= 20) and has_policy:
        return "HIGH"
    if sources == 2 or (sources == 1 and max(n_google, n_trip) >= 20 and has_policy):
        return "MEDIUM"
    if sources >= 1:
        return "LOW"
    return "VERY_LOW"

hotel_360["customer_voice_support"] = hotel_360.apply(confidence, axis=1)
hotel_360.to_csv(DATA_PROCESSED, index=False)
hotel_360["customer_voice_support"].value_counts()
""")

md("## Cross-platform rating gap / consistency (joined in, where available)")
code("""
try:
    cross = pd.read_csv(REPO_ROOT + r"\\reports\\cross_platform_rating_comparison.csv")
    hotel_360 = hotel_360.merge(cross[["hotel_id","rating_gap_mean","comparison_support"]], on="hotel_id", how="left")
    hotel_360 = hotel_360.rename(columns={"rating_gap_mean":"cross_platform_rating_gap",
                                           "comparison_support":"cross_platform_consistency"})
    hotel_360.to_csv(DATA_PROCESSED, index=False)
    print("Cross-platform columns joined.")
except FileNotFoundError:
    print("cross_platform_rating_comparison.csv not found - skipping join.")
""")

md("""## G4: Rule-based archetypes (descriptive only - NO "best hotel" ranking)""")
code("""
def archetype(row):
    tags = []
    if row.get("customer_voice_support") in ("HIGH","MEDIUM"):
        gh = row.get("google_travel_high_share") or 0
        th = row.get("trip_high_share") or 0
        gl = row.get("google_travel_low_share") or 0
        tl = row.get("trip_low_share") or 0
        if gh >= 0.7 and (pd.isna(th) or th >= 0.6):
            tags.append("platform_consistent_strong_profile")
        if gl >= 0.3 or (pd.notna(tl) and tl >= 0.3):
            tags.append("platform_consistent_concern_profile")
    if (row.get("family_feature_count") or 0) >= 2 or (row.get("trip_family_share") or 0) >= 40:
        tags.append("family_oriented_profile")
    if (row.get("water_feature_count") or 0) >= 2:
        tags.append("beach_oriented_profile")
    if (row.get("wellness_feature_count") or 0) >= 2:
        tags.append("wellness_oriented_profile")
    cc = row.get("cross_platform_consistency")
    if cc == "SUPPORTED_COMPARISON" and abs(row.get("cross_platform_rating_gap") or 0) > 0.7:
        tags.append("source_divergent_profile")
    if row.get("customer_voice_support") == "VERY_LOW":
        tags.append("low_data_profile")
    return ";".join(tags) if tags else "insufficient_signal"

hotel_360["archetypes"] = hotel_360.apply(archetype, axis=1)
hotel_360.to_csv(DATA_PROCESSED, index=False)
hotel_360["archetypes"].value_counts().head(15)
""")

md("## G6: Hotel 360 profiles (sufficient-support hotels)")
code("""
profiles = hotel_360[hotel_360["customer_voice_support"].isin(["HIGH","MEDIUM"])].copy()
profile_cols = ["hotel_id","hotel_name","area","customer_voice_support","google_travel_mean_rating",
                 "trip_mean_rating_5" if "trip_mean_rating_5" in profiles.columns else "google_travel_mean_rating",
                 "google_strength_signals","google_concern_signals","archetypes"]
profile_cols = [c for c in dict.fromkeys(profile_cols) if c in profiles.columns]
profiles_out = profiles[profile_cols]
profiles_out.to_csv(REPO_ROOT + r"\\reports\\hotel_360_profiles.csv", index=False)
print(f"{len(profiles_out)} hotels with HIGH/MEDIUM confidence profiled")
profiles_out.head(10)
""")

md("## Coverage summary")
code("""
coverage = pd.DataFrame([{
    "master_hotel_count": len(master),
    "hotel_360_row_count": len(hotel_360),
    "google_only": int(((hotel_360["google_travel_review_n"].notna()) & (hotel_360["trip_review_n"].isna())).sum()),
    "trip_only": int(((hotel_360["trip_review_n"].notna()) & (hotel_360["google_travel_review_n"].isna())).sum()),
    "both_sources": int(((hotel_360["google_travel_review_n"].notna()) & (hotel_360["trip_review_n"].notna())).sum()),
    "no_review_source": int(((hotel_360["google_travel_review_n"].isna()) & (hotel_360["trip_review_n"].isna())).sum()),
    "has_policy_data_count": int(hotel_360["has_policy_data"].sum()),
}])
coverage.to_csv(REPO_ROOT + r"\\reports\\hotel_360_coverage.csv", index=False)
coverage
""")

code("""
fig, ax = plt.subplots(figsize=(5,4))
hotel_360["customer_voice_support"].value_counts().reindex(["HIGH","MEDIUM","LOW","VERY_LOW"]).plot(
    kind="bar", ax=ax, color=["#5cb85c","#5bc0de","#f0ad4e","#d9534f"])
ax.set_title("Customer voice confidence tier - all 192 master hotels")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\confidence_tier_distribution.png", dpi=110)
plt.show()
""")

md("""### Grafik nasıl okunur?
Master listedeki 192 otelin her biri güven seviyesine (HIGH/MEDIUM/LOW/VERY_LOW) göre gruplanmıştır.
### Ne görüyoruz?
Kaç otel için gerçekten güvenilir bir customer-voice profili çıkarabildiğimiz.
### Neden önemli?
360° katmanın gerçek kapsamını abartısız gösterir.
### Dikkat edilmesi gereken nokta
VERY_LOW/LOW oteller için hiçbir iddia güvenilir değildir - bu segment gelecekteki discovery/scraping turları için hedef olabilir.""")

md("## G6: Final Key Findings (15-20)")
code("""
findings = []
findings.append(f"Hotel 360 layer covers all {len(hotel_360)} master hotels, but only "
                 f"{(hotel_360['customer_voice_support'].isin(['HIGH','MEDIUM'])).sum()} have HIGH/MEDIUM confidence.")
findings.append(f"{coverage.iloc[0]['both_sources']} hotels have both Google Travel and Trip.com review data.")
findings.append(f"{coverage.iloc[0]['google_only']} hotels are Google-only, {coverage.iloc[0]['trip_only']} are Trip-only.")
findings.append(f"{coverage.iloc[0]['no_review_source']} master hotels still have zero review-source data from this pipeline.")
findings.append(f"{int(hotel_360['has_policy_data'].sum())} hotels have any Trip.com policy/amenity data.")
arch_counts = hotel_360["archetypes"].value_counts()
for arch, cnt in arch_counts.head(6).items():
    findings.append(f"Archetype '{arch}': {cnt} hotels.")
findings.append("No 'best hotel' ranking was produced - archetypes are descriptive, not comparative rankings.")
findings.append("Cross-platform rating gaps are a divergence signal only, not a quality verdict (see notebook 18).")
findings.append("Family/wellness/water feature counts come only from raw Trip.com policy text evidence, never inferred.")

key_findings_df = pd.DataFrame({"finding_id": range(1, len(findings)+1), "finding": findings})
key_findings_df.to_csv(REPO_ROOT + r"\\reports\\hotel_360_key_findings.csv", index=False)

with open(REPO_ROOT + r"\\reports\\hotel_360_summary.txt", "w", encoding="utf-8") as f:
    f.write("HOTEL 360 INTELLIGENCE SUMMARY\\n" + "="*40 + "\\n\\n")
    for i, f_ in enumerate(findings, 1):
        f.write(f"{i}. {f_}\\n")
for i, f_ in enumerate(findings, 1):
    print(f"{i}. {f_}")
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}}

client = NotebookClient(nb, kernel_name="python3", timeout=600)
client.execute()

NB_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(NB_PATH, "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print(f"Wrote executed notebook: {NB_PATH}")
