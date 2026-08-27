"""Builds and executes notebooks/13_google_travel_all_hotels_eda.ipynb."""
from __future__ import annotations

import nbformat as nbf
from nbclient import NotebookClient
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NB_PATH = REPO_ROOT / "notebooks" / "13_google_travel_all_hotels_eda.ipynb"

cells = []


def md(src): cells.append(nbf.v4.new_markdown_cell(src))
def code(src): cells.append(nbf.v4.new_code_cell(src))


md("""# Bodrum Hotel & Destination Intelligence
## 13 - Google Travel All-Hotels Review EDA""")

code(f"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
%matplotlib inline
import os

REPO_ROOT = r"{REPO_ROOT}"
FIG_DIR = REPO_ROOT + r"\\reports\\figures\\google_travel_all_hotels_eda"
os.makedirs(FIG_DIR, exist_ok=True)
pd.set_option("display.max_columns", 50)

clean = pd.read_csv(REPO_ROOT + r"\\data\\processed\\google_travel_all_hotels_reviews_clean.csv")
print("rows:", len(clean), "hotels:", clean['hotel_id'].nunique())
clean.head(2)
""")

md("""## C2: Overall KPI""")
code("""
kpi = {
    "total_reviews": len(clean),
    "hotel_count": clean["hotel_id"].nunique(),
    "area_count": clean["area"].nunique(),
    "mean_rating": round(clean["review_rating_numeric"].mean(), 2),
    "median_rating": clean["review_rating_numeric"].median(),
    "low_rating_share_pct": round((clean["rating_group"]=="LOW").mean()*100, 1),
    "high_rating_share_pct": round((clean["rating_group"]=="HIGH").mean()*100, 1),
    "details_coverage_pct": round(clean["rooms_score"].notna().mean()*100, 1),
    "google_source_share_pct": round((clean["review_source"]=="GOOGLE").mean()*100, 1),
}
for k, v in kpi.items():
    print(f"{k}: {v}")
""")

md("""## C4-C5: Hotel rating summary + sample support tiers""")
code("""
def support_tier(n):
    if n < 5: return "VERY_LOW_SUPPORT"
    if n < 20: return "LOW_SUPPORT"
    if n < 50: return "MODERATE"
    return "STRONGER"

hotel_rating = clean.groupby(["hotel_id", "hotel_name", "area"]).agg(
    n=("review_rating_numeric", "count"),
    mean_rating=("review_rating_numeric", "mean"),
    median_rating=("review_rating_numeric", "median"),
    std=("review_rating_numeric", "std"),
    q25=("review_rating_numeric", lambda s: s.quantile(0.25)),
    q75=("review_rating_numeric", lambda s: s.quantile(0.75)),
).reset_index()
low = clean[clean["rating_group"]=="LOW"].groupby("hotel_id").size()
mid = clean[clean["rating_group"]=="MID"].groupby("hotel_id").size()
high = clean[clean["rating_group"]=="HIGH"].groupby("hotel_id").size()
hotel_rating = hotel_rating.set_index("hotel_id")
hotel_rating["low_share"] = (low / hotel_rating["n"]).fillna(0).round(3)
hotel_rating["mid_share"] = (mid / hotel_rating["n"]).fillna(0).round(3)
hotel_rating["high_share"] = (high / hotel_rating["n"]).fillna(0).round(3)
hotel_rating["sample_support"] = hotel_rating["n"].apply(support_tier)
hotel_rating = hotel_rating.reset_index()
hotel_rating.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_rating_summary.csv", index=False)
hotel_rating["sample_support"].value_counts()
""")

md("""## C6-C7: Normalized rating distribution (supported hotels only)""")
code("""
supported = hotel_rating[hotel_rating["n"] >= 5].sort_values("n", ascending=False).head(20)
if len(supported):
    fig, ax = plt.subplots(figsize=(9, max(4, 0.35*len(supported))))
    ax.barh(supported["hotel_id"], supported["low_share"], color="#d9534f", label="LOW")
    ax.barh(supported["hotel_id"], supported["mid_share"], left=supported["low_share"], color="#f0ad4e", label="MID")
    ax.barh(supported["hotel_id"], supported["high_share"],
            left=supported["low_share"]+supported["mid_share"], color="#5cb85c", label="HIGH")
    ax.set_title("Normalized rating share by hotel (n>=5, top 20 by sample size)")
    ax.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR + r"\\normalized_rating_distribution.png", dpi=110)
    plt.show()
else:
    print("No hotel with n>=5 yet - skipping this chart.")
""")

md("""### Grafik nasıl okunur?
Her satır bir oteli temsil eder; çubuk toplamı %100'dür, renkler LOW/MID/HIGH pay yüzdesidir.
### Ne görüyoruz?
Ham sayı yerine ORAN kullanıldığı için oteller adil biçimde karşılaştırılabilir.
### Neden önemli?
Az örneklemli bir otelin tesadüfen yüksek/düşük çıkması ile gerçek eğilim ayrıştırılır.
### Dikkat edilmesi gereken nokta
Yalnızca n>=5 olan oteller gösterilmiştir; daha küçük örneklemler yorumlanmamalıdır.""")

md("""## C8: Area-level rating summary""")
code("""
area_summary = clean.groupby("area").agg(
    hotel_count_with_reviews=("hotel_id", "nunique"),
    review_count=("hotel_id", "size"),
    review_weighted_mean_rating=("review_rating_numeric", "mean"),
).reset_index()
med_by_hotel = hotel_rating.groupby("area")["median_rating"].median().rename("median_hotel_rating")
area_summary = area_summary.merge(med_by_hotel, on="area", how="left")
low_by_area = hotel_rating.groupby("area")["low_share"].median().rename("median_low_share")
high_by_area = hotel_rating.groupby("area")["high_share"].median().rename("median_high_share")
area_summary = area_summary.merge(low_by_area, on="area").merge(high_by_area, on="area")
area_summary = area_summary.sort_values("review_count", ascending=False)
area_summary.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_area_summary.csv", index=False)
area_summary.head(10)
""")

md("""## C9: Review length vs rating""")
code("""
by_group = clean.groupby("rating_group")["review_word_count"].median()
fig, ax = plt.subplots(figsize=(5,4))
by_group.reindex(["LOW","MID","HIGH"]).plot(kind="bar", ax=ax, color="#337ab7")
ax.set_title("Median review word count by rating group")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\review_length_vs_rating.png", dpi=110)
plt.show()

valid = clean.dropna(subset=["review_rating_numeric", "review_word_count"])
if len(valid) > 5:
    corr = valid["review_rating_numeric"].corr(valid["review_word_count"], method="spearman")
    print("Spearman(rating, word_count) =", round(corr, 3), "(exploratory, not causal)")
""")

md("""## C10-C11: Source distribution & Google-only sensitivity""")
code("""
overall_mean = clean["review_rating_numeric"].mean()
google_only = clean[clean["review_source"]=="GOOGLE"]
google_only_mean = google_only["review_rating_numeric"].mean()
sensitivity = pd.DataFrame([{
    "all_sources_mean_rating": round(overall_mean, 3),
    "google_only_mean_rating": round(google_only_mean, 3),
    "all_sources_n": len(clean),
    "google_only_n": len(google_only),
    "difference": round(overall_mean - google_only_mean, 3),
}])
sensitivity.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_google_only_sensitivity.csv", index=False)
sensitivity
""")

md("""## C12: Details (rooms/service/location) score analysis""")
code("""
detail_summary = clean[["rooms_score","service_score","location_score"]].agg(["count","mean","median"]).T
detail_summary["coverage_pct"] = (detail_summary["count"] / len(clean) * 100).round(1)
detail_summary.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_detail_score_summary.csv")

fig, ax = plt.subplots(figsize=(5,4))
detail_summary["mean"].plot(kind="bar", ax=ax, color="#9370db")
ax.set_title("Mean sub-score (rooms / service / location)")
ax.set_ylim(0,5)
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\detail_score_means.png", dpi=110)
plt.show()
detail_summary
""")

md("""## C14: Main rating vs details correlation (exploratory)""")
code("""
corr_rows = []
for col in ["rooms_score","service_score","location_score"]:
    sub = clean.dropna(subset=["review_rating_numeric", col])
    if len(sub) > 5:
        corr_rows.append({"detail": col, "spearman_vs_main_rating": round(
            sub["review_rating_numeric"].corr(sub[col], method="spearman"), 3), "n": len(sub)})
corr_df = pd.DataFrame(corr_rows)
corr_df.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_detail_score_correlations.csv", index=False)
corr_df
""")

md("""## C17: Hotel profile table""")
code("""
word_median = clean.groupby("hotel_id")["review_word_count"].median().rename("median_word_count")
details_cov = clean.groupby("hotel_id")["rooms_score"].apply(lambda s: round(s.notna().mean()*100,1)).rename("details_coverage_pct")
google_share = clean.groupby("hotel_id")["review_source"].apply(lambda s: round((s=="GOOGLE").mean()*100,1)).rename("google_source_share_pct")

profile = hotel_rating.set_index("hotel_id").join([word_median, details_cov, google_share]).reset_index()
profile = profile.rename(columns={"n": "n_reviews"})
profile = profile[["hotel_id","hotel_name","area","n_reviews","mean_rating","median_rating",
                    "low_share","high_share","median_word_count","details_coverage_pct",
                    "google_source_share_pct","sample_support"]]
profile.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_profile_summary.csv", index=False)
profile.sort_values("n_reviews", ascending=False).head(10)
""")

md("""## C21: Notebook 13 - Key Findings""")
code("""
findings = []
findings.append(f"Corpus covers {clean['hotel_id'].nunique()} hotels across {clean['area'].nunique()} areas, {len(clean)} reviews total.")
findings.append(f"Sample support: {(hotel_rating['sample_support']=='VERY_LOW_SUPPORT').sum()} hotels VERY_LOW_SUPPORT (n<5) - "
                 f"their rating shares should not be over-interpreted.")
top_high = hotel_rating[hotel_rating['n']>=5].sort_values('high_share', ascending=False).head(3)
findings.append("Highest supported HIGH-rating-share hotels (n>=5): " + ", ".join(top_high['hotel_id'].tolist()) if len(top_high) else "No hotel yet clears n>=5.")
top_low = hotel_rating[hotel_rating['n']>=5].sort_values('low_share', ascending=False).head(3)
findings.append("Highest supported LOW-rating-share hotels (n>=5): " + ", ".join(top_low['hotel_id'].tolist()) if len(top_low) else "No hotel yet clears n>=5.")
findings.append(f"Google-only sensitivity: overall mean {round(overall_mean,2)} vs Google-only mean {round(google_only_mean,2)} "
                 f"(difference {round(overall_mean-google_only_mean,3)}).")
findings.append(f"Area with most review coverage: {area_summary.iloc[0]['area']} ({int(area_summary.iloc[0]['review_count'])} reviews).")
findings.append("Raw review counts are heavily hotel-imbalanced (see notebook 12) - all comparisons above use rates/shares, not raw counts.")
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
