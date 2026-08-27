"""Builds and executes notebooks/17_tripcom_customer_voice_segment_analysis.ipynb."""
from __future__ import annotations

import nbformat as nbf
from nbclient import NotebookClient
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NB_PATH = REPO_ROOT / "notebooks" / "17_tripcom_customer_voice_segment_analysis.ipynb"

cells = []


def md(src): cells.append(nbf.v4.new_markdown_cell(src))
def code(src): cells.append(nbf.v4.new_code_cell(src))


md("""# Bodrum Hotel & Destination Intelligence
## 17 - Trip.com Customer Voice & Guest Segment Analysis""")

code(f"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
%matplotlib inline
import os

REPO_ROOT = r"{REPO_ROOT}"
FIG_DIR = REPO_ROOT + r"\\reports\\figures\\tripcom_customer_voice"
os.makedirs(FIG_DIR, exist_ok=True)
pd.set_option("display.max_columns", 50)

clean = pd.read_csv(REPO_ROOT + r"\\data\\processed\\tripcom_reviews_clean.csv")
print("rows:", len(clean), "hotels:", clean['hotel_id'].nunique())
""")

md("## D1: Overall KPI")
code("""
kpi = {
    "total_reviews": len(clean),
    "hotel_count": clean["hotel_id"].nunique(),
    "mean_rating_5": round(clean["rating_5_scale"].mean(), 2),
    "median_rating_5": clean["rating_5_scale"].median(),
    "low_share_pct": round((clean["rating_group"]=="LOW").mean()*100, 1),
    "high_share_pct": round((clean["rating_group"]=="HIGH").mean()*100, 1),
    "traveler_type_coverage_pct": round((clean["traveler_type"]!="UNKNOWN").mean()*100, 1),
    "room_type_coverage_pct": round((clean["room_type"]!="UNKNOWN").mean()*100, 1),
    "stay_date_coverage_pct": round(clean["stay_year"].notna().mean()*100, 1),
    "reviewer_location_coverage_pct": round(clean["reviewer_country"].notna().mean()*100, 1),
}
for k, v in kpi.items():
    print(f"{k}: {v}")
""")

md("## D2: Hotel rating summary")
code("""
def support_tier(n):
    if n < 5: return "VERY_LOW_SUPPORT"
    if n < 20: return "LOW_SUPPORT"
    if n < 50: return "MODERATE"
    return "STRONGER"

hotel_rating = clean.groupby(["hotel_id","hotel_name","area"]).agg(
    n=("rating_5_scale","count"), mean_rating_5=("rating_5_scale","mean"),
    median_rating_5=("rating_5_scale","median"), std=("rating_5_scale","std"),
).reset_index()
low = clean[clean["rating_group"]=="LOW"].groupby("hotel_id").size()
mid = clean[clean["rating_group"]=="MID"].groupby("hotel_id").size()
high = clean[clean["rating_group"]=="HIGH"].groupby("hotel_id").size()
hotel_rating = hotel_rating.set_index("hotel_id")
hotel_rating["low_share"] = (low/hotel_rating["n"]).fillna(0).round(3)
hotel_rating["mid_share"] = (mid/hotel_rating["n"]).fillna(0).round(3)
hotel_rating["high_share"] = (high/hotel_rating["n"]).fillna(0).round(3)
hotel_rating["sample_support"] = hotel_rating["n"].apply(support_tier)
hotel_rating = hotel_rating.reset_index()
hotel_rating.sort_values("n", ascending=False)
""")

md("## D3-D4: Traveler type distribution & rating by segment")
code("""
traveler_summary = clean["traveler_type"].value_counts().rename("n").to_frame()
traveler_summary["share_pct"] = (traveler_summary["n"] / len(clean) * 100).round(1)
traveler_summary.to_csv(REPO_ROOT + r"\\reports\\tripcom_traveler_type_summary.csv")

traveler_rating = clean.groupby("traveler_type").agg(
    n=("rating_5_scale","count"), mean=("rating_5_scale","mean"), median=("rating_5_scale","median"),
).reset_index()
low_t = clean[clean["rating_group"]=="LOW"].groupby("traveler_type").size()
high_t = clean[clean["rating_group"]=="HIGH"].groupby("traveler_type").size()
traveler_rating = traveler_rating.set_index("traveler_type")
traveler_rating["low_share"] = (low_t/traveler_rating["n"]).fillna(0).round(3)
traveler_rating["high_share"] = (high_t/traveler_rating["n"]).fillna(0).round(3)
traveler_rating = traveler_rating.reset_index()
traveler_rating.to_csv(REPO_ROOT + r"\\reports\\tripcom_traveler_type_rating.csv", index=False)

fig, ax = plt.subplots(figsize=(7,4))
traveler_rating.set_index("traveler_type")["mean"].plot(kind="bar", ax=ax, color="#337ab7")
ax.set_title("Mean rating (5-scale) by traveler type")
ax.set_ylim(0,5)
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\rating_by_traveler_type.png", dpi=110)
plt.show()
traveler_rating
""")

md("""### Grafik nasıl okunur?
Her çubuk bir misafir tipini (Family/Couple/Solo/Friends/vb.) ve o segmentin ortalama puanını gösterir.
### Ne görüyoruz?
Segmentler arası memnuniyet farkları (varsa).
### Neden önemli?
Otel bazlı "hangi segmentte güçlü/zayıf" analizinin temelini oluşturur.
### Dikkat edilmesi gereken nokta
UNKNOWN/OTHER segmentleri düşük güvenilirliktedir; n değerlerine dikkat edin.""")

md("## D5: Family / Couple / Solo (explicit)")
code("""
fcs = traveler_rating[traveler_rating["traveler_type"].isin(["FAMILY","COUPLE","SOLO"])]
fcs
""")

md("## D6: Room type x rating, x traveler type, hotel x room type")
code("""
room_rating = clean.groupby("room_type")["rating_5_scale"].agg(["count","mean","median"])
room_rating.to_csv(REPO_ROOT + r"\\reports\\tripcom_room_type_summary.csv")

room_x_traveler = pd.crosstab(clean["room_type"], clean["traveler_type"])
room_x_traveler
""")

md("## D7: Reviewer country / location")
code("""
country_summary = clean["reviewer_country"].value_counts().rename("n").to_frame()
country_summary["share_pct"] = (country_summary["n"] / clean["reviewer_country"].notna().sum() * 100).round(1)
country_summary.to_csv(REPO_ROOT + r"\\reports\\tripcom_country_summary.csv")

fig, ax = plt.subplots(figsize=(7,4))
country_summary.head(10)["n"].plot(kind="barh", ax=ax, color="#5cb85c")
ax.set_title("Top 10 reviewer countries (Trip.com sample - platform bias likely, see limitations)")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\top_reviewer_countries.png", dpi=110)
plt.show()
""")

md("""### Grafik nasıl okunur?
En sık görülen 10 yorumcu ülkesi.
### Ne görüyoruz?
Trip.com kullanıcı tabanının coğrafi dağılımı - bu Google Travel'de mevcut olmayan bir sinyaldir.
### Neden önemli?
Hangi pazarlardan geldiğimiz konusunda fikir verir.
### Dikkat edilmesi gereken nokta
Bu, Trip.com'un kendi kullanıcı tabanının bir yansımasıdır - genel misafir evrenini temsil etmeyebilir (platform bias).""")

md("## D8: Stay month x rating x traveler")
code("""
stay = clean.dropna(subset=["stay_month"])
if len(stay):
    stay_month_summary = stay.groupby("stay_month")["rating_5_scale"].agg(["count","mean"])
    stay_month_summary.to_csv(REPO_ROOT + r"\\reports\\tripcom_stay_month_summary.csv")
    stay_month_summary
else:
    print("No stay_month data yet.")
""")

md("## D9: Review length vs rating")
code("""
clean["word_count"] = clean["review_text_clean"].fillna("").str.split().apply(len)
by_group = clean.groupby("rating_group")["word_count"].median()
fig, ax = plt.subplots(figsize=(5,4))
by_group.reindex(["LOW","MID","HIGH"]).plot(kind="bar", ax=ax, color="#9370db")
ax.set_title("Median review word count by rating group (Trip.com)")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\review_length_vs_rating.png", dpi=110)
plt.show()

valid = clean.dropna(subset=["rating_5_scale"])
if len(valid) > 5:
    corr = valid["rating_5_scale"].corr(valid["word_count"], method="spearman")
    print("Spearman(rating_5, word_count) =", round(corr,3), "(exploratory)")
""")

md("## D10: Lightweight text themes")
code("""
import re, unicodedata
from collections import Counter

STOP = {"the","and","was","for","with","very","room","hotel","this","that","were","are","have",
        "had","not","but","from","its","our","you","they","also"}

def tokenize(t):
    if not isinstance(t, str) or not t:
        return []
    s = unicodedata.normalize("NFKD", t.lower()).encode("ascii","ignore").decode("ascii")
    words = re.findall(r"[a-z]{3,}", s)
    return [w for w in words if w not in STOP]

clean["tokens"] = clean["review_text_clean"].apply(tokenize)
term_freq = Counter(t for toks in clean["tokens"] for t in set(toks))
term_freq_df = pd.DataFrame(term_freq.most_common(20), columns=["term","document_frequency"])
term_freq_df
""")

md("## D11: Trip hotel profile summary")
code("""
tt_by_hotel = clean.groupby("hotel_id")["traveler_type"].agg(lambda s: s.value_counts().idxmax() if len(s) else "UNKNOWN").rename("top_traveler_type")
family_share = clean.groupby("hotel_id")["traveler_type"].apply(lambda s: round((s=="FAMILY").mean()*100,1)).rename("family_share_pct")
couple_share = clean.groupby("hotel_id")["traveler_type"].apply(lambda s: round((s=="COUPLE").mean()*100,1)).rename("couple_share_pct")
country_cov = clean.groupby("hotel_id")["reviewer_country"].apply(lambda s: s.nunique()).rename("distinct_countries")

profile = hotel_rating.set_index("hotel_id").join([tt_by_hotel, family_share, couple_share, country_cov]).reset_index()
profile.to_csv(REPO_ROOT + r"\\reports\\tripcom_hotel_profile_summary.csv", index=False)
profile.head(10)
""")

md("## D12: Notebook 17 - Key Findings")
code("""
findings = []
findings.append(f"Trip.com corpus covers {clean['hotel_id'].nunique()} hotels, {len(clean)} reviews.")
findings.append(f"Traveler type coverage: {kpi['traveler_type_coverage_pct']}% (raw values preserved in traveler_type_raw).")
top_seg = traveler_rating.sort_values('n', ascending=False).iloc[0]
findings.append(f"Largest traveler segment: {top_seg['traveler_type']} (n={int(top_seg['n'])}, mean={round(top_seg['mean'],2)}).")
findings.append(f"Reviewer country coverage: {kpi['reviewer_location_coverage_pct']}% - top country: "
                 f"{country_summary.index[0] if len(country_summary) else 'N/A'}.")
findings.append("Room type coverage is limited (many blanks) - room-type findings should be treated as exploratory only.")
findings.append("Stay-month seasonality analysis is limited by current sample size - see tripcom_stay_month_summary.csv.")
with open(REPO_ROOT + r"\\reports\\tripcom_segment_key_findings.txt", "w", encoding="utf-8") as f:
    f.write("\\n".join(f"{i+1}. {x}" for i, x in enumerate(findings)) + "\\n")
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
