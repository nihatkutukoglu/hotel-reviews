"""Builds and executes notebooks/19_hotel_policies_amenities_enrichment.ipynb."""
from __future__ import annotations

import nbformat as nbf
from nbclient import NotebookClient
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
NB_PATH = REPO_ROOT / "notebooks" / "19_hotel_policies_amenities_enrichment.ipynb"

cells = []


def md(src): cells.append(nbf.v4.new_markdown_cell(src))
def code(src): cells.append(nbf.v4.new_code_cell(src))


md("""# Bodrum Hotel & Destination Intelligence
## 19 - Trip.com Hotel Policies & Amenities Enrichment""")

code(f"""
import sys, subprocess
sys.path.insert(0, r"{SRC}")
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
%matplotlib inline
import os

REPO_ROOT = r"{REPO_ROOT}"
FIG_DIR = REPO_ROOT + r"\\reports\\figures\\policies"
os.makedirs(FIG_DIR, exist_ok=True)

result = subprocess.run([sys.executable, REPO_ROOT + r"\\scripts\\analysis\\build_policies_features_and_reports.py"],
                         capture_output=True, text=True, cwd=REPO_ROOT)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr)
""")

code("""
from bodrum_intelligence.reviews.common import master_hotel_csv_path
policy = pd.read_csv(REPO_ROOT + r"\\data\\processed\\hotel_policies_features.csv")
master = pd.read_csv(master_hotel_csv_path())
google_profile = pd.read_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_profile_summary.csv")
trip_profile = pd.read_csv(REPO_ROOT + r"\\reports\\tripcom_hotel_profile_summary.csv")
print("policy hotels:", len(policy), "| master hotels:", len(master))
policy.head(3)
""")

md("## F2: Coverage")
code("""
coverage = {
    "master_hotel_count": len(master),
    "hotels_with_policy_data": len(policy),
    "coverage_pct": round(len(policy) / len(master) * 100, 1),
}
print(coverage)
policy["policy_status"].value_counts()
""")

md("## F3: Amenity frequency")
code("""
amenity_freq = pd.read_csv(REPO_ROOT + r"\\reports\\tripcom_amenity_frequency.csv")
fig, ax = plt.subplots(figsize=(8,6))
amenity_freq.set_index("amenity")["hotel_count"].sort_values().plot(kind="barh", ax=ax, color="#5cb85c")
ax.set_title(f"Amenity frequency across {len(policy)} hotels with policy data")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\amenity_frequency.png", dpi=110)
plt.show()
""")

md("""### Grafik nasıl okunur?
Her çubuk bir amenity'nin (olanak) kaç otelde ham metinde gerçekten geçtiğini gösterir.
### Ne görüyoruz?
En yaygın ve en nadir olanaklar.
### Neden önemli?
Aile/wellness/plaj odaklı otel profillemesi için temel veri.
### Dikkat edilmesi gereken nokta
Payda yalnızca policy verisi OLAN oteldir (14-20 civarı), 192 değil - coverage_pct'ye dikkat.""")

md("## F4: Area x amenity (covered hotels only)")
code("""
area_amenity = policy.merge(master[["hotel_id","area"]], on="hotel_id", how="left", suffixes=("","_master"))
amenity_cols = [c for c in policy.columns if c.startswith("has_") and c not in
                ["has_checkin","has_checkout","has_children_policy","has_extra_bed_policy",
                 "has_breakfast_policy","has_pet_policy","has_service_animal_policy","has_age_rule","has_license","has_facilities"]]
area_summary = area_amenity.groupby("area")[amenity_cols].sum()
area_summary["covered_hotel_count"] = area_amenity.groupby("area").size()
area_summary.head(10)
""")

md("## F5-F7: Family-friendly / Wellness / Beach-water features")
code("""
feature_summary = policy[["family_feature_count","wellness_feature_count","water_feature_count"]].describe()
feature_summary
""")

code("""
fig, axes = plt.subplots(1,3, figsize=(12,4))
for ax, col, title, color in zip(axes,
    ["family_feature_count","wellness_feature_count","water_feature_count"],
    ["Family-friendly features","Wellness features","Beach/water features"],
    ["#f0ad4e","#9370db","#5bc0de"]):
    policy[col].value_counts().sort_index().plot(kind="bar", ax=ax, color=color, title=title)
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\feature_group_distributions.png", dpi=110)
plt.show()
""")

md("""### Grafik nasıl okunur?
Her panel bir özellik grubunun (aile/wellness/plaj-su) otel başına kaç madde içerdiğini gösterir.
### Ne görüyoruz?
Politika verisi olan otellerin bu üç boyuttaki donanım zenginliği.
### Neden önemli?
Aile/wellness/plaj odaklı arketip oluşturmanın (notebook 20) girdisi.
### Dikkat edilmesi gereken nokta
Yalnızca raw `hizmetler` metninde gerçekten geçen ifadelerden türetilmiştir; tahmin yoktur.""")

md("""## F8: Policy + Customer Voice association (exploratory, NOT causal)""")
code("""
merged = policy.merge(trip_profile[["hotel_id","n","mean_rating_5" if "mean_rating_5" in trip_profile.columns else "mean_rating_5"]],
                       on="hotel_id", how="left") if "mean_rating_5" in trip_profile.columns else policy.merge(
    trip_profile.rename(columns={"n":"trip_n"})[["hotel_id","trip_n"]], on="hotel_id", how="left")
has_kids_club_hotels = policy[policy["has_kids_club"]]["hotel_id"].tolist()
has_spa_hotels = policy[policy["has_spa"]]["hotel_id"].tolist()
print(f"{len(has_kids_club_hotels)} hotels advertise a kids club; {len(has_spa_hotels)} advertise a spa.")
print("Association exploration only - no causal claim.")
""")

md("## F9: Output - hotel_policy_customer_voice_enriched.csv")
code("""
g = google_profile.set_index("hotel_id")[["n_reviews","mean_rating"]].rename(
    columns={"n_reviews":"google_review_n","mean_rating":"google_rating"})
t = trip_profile.set_index("hotel_id")
t_cols = {"n":"trip_review_n"}
if "mean_rating_5" in t.columns:
    t_cols["mean_rating_5"] = "trip_rating"
t = t.rename(columns=t_cols)[[c for c in t_cols.values() if c in t.rename(columns=t_cols).columns]]

enriched = policy.set_index("hotel_id")[
    ["hotel_name","area","amenity_count","family_feature_count","wellness_feature_count","water_feature_count"]
].rename(columns={"family_feature_count":"family_feature_count","wellness_feature_count":"wellness_feature_count"})
enriched["policy_coverage"] = policy.set_index("hotel_id")["policy_status"]
enriched = enriched.join([g, t], how="outer")
enriched["source_count"] = enriched[["google_review_n","trip_review_n"]].notna().sum(axis=1)
enriched["support"] = enriched["source_count"].map({0:"NO_DATA",1:"SINGLE_SOURCE",2:"MULTI_SOURCE"})
enriched = enriched.reset_index().rename(columns={"index":"hotel_id"})
enriched.to_csv(REPO_ROOT + r"\\reports\\hotel_policy_customer_voice_enriched.csv", index=False)
print(len(enriched), "hotels in enriched output")
enriched.head(10)
""")

md("## F10: Notebook 19 - Key Findings")
code("""
findings = []
findings.append(f"{len(policy)}/{len(master)} master hotels ({coverage['coverage_pct']}%) have any Trip.com policy data.")
findings.append(f"Most common amenity: {amenity_freq.iloc[0]['amenity']} ({amenity_freq.iloc[0]['hotel_count']} hotels).")
findings.append(f"{len(has_kids_club_hotels)} hotels advertise a kids club (family-friendly signal).")
findings.append(f"{len(has_spa_hotels)} hotels advertise a spa (wellness signal).")
findings.append(f"Mean amenity_count across covered hotels: {round(policy['amenity_count'].mean(),1)}.")
findings.append("Checkout time coverage remains the weakest policy field - a known site-side gap, not a scraper bug.")
findings.append("Policy-vs-rating associations above are exploratory only - sample sizes are too small for causal claims.")
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
