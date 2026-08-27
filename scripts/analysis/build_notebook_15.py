"""Builds and executes notebooks/15_google_travel_customer_voice_intelligence_summary.ipynb.
Combines 12+13+14 outputs only - no new scraping/cleaning/heavy NLP here."""
from __future__ import annotations

import nbformat as nbf
from nbclient import NotebookClient
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
NB_PATH = REPO_ROOT / "notebooks" / "15_google_travel_customer_voice_intelligence_summary.ipynb"

cells = []


def md(src): cells.append(nbf.v4.new_markdown_cell(src))
def code(src): cells.append(nbf.v4.new_code_cell(src))


md("""# Bodrum Hotel & Destination Intelligence
## 15 - Google Travel Customer Voice Intelligence Summary

Bu notebook yeni scraping/cleaning/agir NLP modeli kurmaz; 12+13+14 sonuclarini birlestirir.""")

code(f"""
import sys
sys.path.insert(0, r"{SRC}")
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
%matplotlib inline
import os

from bodrum_intelligence.reviews.common import master_hotel_csv_path

REPO_ROOT = r"{REPO_ROOT}"
FIG_DIR = REPO_ROOT + r"\\reports\\figures\\google_travel_customer_voice_summary"
os.makedirs(FIG_DIR, exist_ok=True)

clean = pd.read_csv(REPO_ROOT + r"\\data\\processed\\google_travel_all_hotels_reviews_clean.csv")
rating_summary = pd.read_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_rating_summary.csv")
profile_summary = pd.read_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_profile_summary.csv")
area_summary = pd.read_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_area_summary.csv")
hotel_aspect = pd.read_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_hotel_aspect_mentions.csv")
aspect_rating = pd.read_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_aspect_rating_summary.csv")
voice_profiles = pd.read_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_customer_voice_profiles.csv")
sensitivity = pd.read_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_google_only_sensitivity.csv")
master = pd.read_csv(master_hotel_csv_path())
print("master hotels:", len(master), "| hotels with >=1 google travel review:", clean['hotel_id'].nunique())
""")

md("""## E2-E3: Dataset overview & coverage""")
code("""
hotels_with_reviews = set(clean["hotel_id"].unique())
no_review_hotels = master[~master["hotel_id"].isin(hotels_with_reviews)]
coverage = {
    "master_hotel_count": len(master),
    "hotels_with_google_travel_reviews": len(hotels_with_reviews),
    "hotels_with_no_google_travel_reviews": len(no_review_hotels),
    "coverage_pct": round(len(hotels_with_reviews) / len(master) * 100, 1),
    "review_count": len(clean),
    "area_count": clean["area"].nunique(),
    "rating_coverage_pct": round(clean["review_rating_numeric"].notna().mean() * 100, 1),
    "details_coverage_pct": round(clean["rooms_score"].notna().mean() * 100, 1),
}
for k, v in coverage.items():
    print(f"{k}: {v}")
""")

md("""## E4: Rating intelligence""")
code("""
fig, ax = plt.subplots(figsize=(6,4))
clean["rating_group"].value_counts().reindex(["LOW","MID","HIGH"]).plot(kind="bar", ax=ax,
    color=["#d9534f","#f0ad4e","#5cb85c"])
ax.set_title("Overall rating group distribution")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\overall_rating_distribution.png", dpi=110)
plt.show()
""")

md("""## E5: Customer voice themes (overall)""")
code("""
top_overall = aspect_rating.sort_values("n_mentions", ascending=False).head(10)
top_positive = aspect_rating.sort_values("high_rating_share_when_mentioned", ascending=False).head(5)
top_negative = aspect_rating.sort_values("low_rating_share_when_mentioned", ascending=False).head(5)
print("TOP OVERALL ASPECTS:\\n", top_overall[["aspect","n_mentions"]].to_string(index=False))
print("\\nTOP POSITIVE-CONTEXT ASPECTS:\\n", top_positive[["aspect","high_rating_share_when_mentioned"]].to_string(index=False))
print("\\nTOP NEGATIVE-CONTEXT ASPECTS:\\n", top_negative[["aspect","low_rating_share_when_mentioned"]].to_string(index=False))
""")

md("""## E6-E7: Hotel & area profiles (sample-adequate)""")
code("""
adequate = profile_summary[profile_summary["n_reviews"] >= 5].sort_values("n_reviews", ascending=False)
print(f"{len(adequate)} / {len(profile_summary)} hotels have n>=5 reviews (sample-adequate)")
adequate.head(10)
""")

code("""
area_summary.sort_values("review_count", ascending=False).head(10)
""")

md("""## E8-E9: Strength / concern signals (hotel + area)""")
code("""
strengths = voice_profiles[voice_profiles["top_high_context_aspects"].notna() &
                            (voice_profiles["top_high_context_aspects"] != "")]
concerns = voice_profiles[voice_profiles["top_low_context_aspects"].notna() &
                           (voice_profiles["top_low_context_aspects"] != "")]
print(f"{len(strengths)} hotels have an identified strength-signal aspect.")
print(f"{len(concerns)} hotels have an identified concern-signal aspect.")
strengths[["hotel_id","hotel_name","top_high_context_aspects"]].head(8)
""")

md("""## E10-E15: Aspect deep-dives (PRICE_VALUE, CLEANLINESS/HYGIENE, FOOD, STAFF/SERVICE, BEACH/POOL, FAMILY_KIDS)""")
code("""
deep_dive_aspects = ["PRICE_VALUE", "CLEANLINESS", "HYGIENE", "FOOD", "STAFF", "SERVICE",
                      "BEACH_SEA", "POOL", "FAMILY_KIDS"]
deep_dive = aspect_rating[aspect_rating["aspect"].isin(deep_dive_aspects)]
deep_dive
""")

md("""## E16: Source sensitivity (all-source vs Google-only)""")
code("""
sensitivity
""")

md("""## E17: Confidence framework""")
code("""
def tier(n):
    if n >= 50: return "HIGH"
    if n >= 20: return "MEDIUM"
    if n >= 5: return "LOW"
    return "VERY_LOW"
profile_summary["analysis_confidence"] = profile_summary["n_reviews"].apply(tier)
profile_summary["analysis_confidence"].value_counts()
""")

md("""## E19: What we CANNOT say (explicit limitations)
- Bu, tüm misafir evreni değil, Google Travel'in kamuya açık örneklemidir.
- Stable-end, tarihsel yorumların %100 tamlığının garantisi değildir.
- Google Travel review paneli aggregate bir kaynaktır (Google + TripAdvisor + Trip.com karışımı - bkz. notebook 12).
- Otel örneklemleri dengesizdir; ham sayı karşılaştırması yanıltıcıdır.
- Aspect sözlüğü kural-tabanlıdır, eğitilmiş bir model değildir.
- Puan (rating), genel deneyimi yansıtır; aspect-context bir sentiment skoru değildir.
- Aspect ile puan arasındaki ilişki bir korelasyon/coincidence sinyalidir, nedensellik değildir.
- Düşük n'li oteller için kesin kalite sonucu çıkarılamaz.""")

md("""## E21: Final Customer Voice Master Table""")
code("""
master_table = profile_summary.merge(
    voice_profiles[["hotel_id","top_aspects","top_high_context_aspects","top_low_context_aspects"]],
    on="hotel_id", how="left"
).rename(columns={"top_high_context_aspects": "top_strength_signals",
                   "top_low_context_aspects": "top_concern_signals"})
master_table.to_csv(REPO_ROOT + r"\\reports\\google_travel_customer_voice_master_summary.csv", index=False)
master_table.head(10)
""")

md("""## E22: Key Findings Master""")
code("""
finding_rows = []
fid = 1
for _, r in top_overall.iterrows():
    finding_rows.append({"finding_id": fid, "level": "OVERALL", "hotel_id": "", "hotel_name": "", "area": "",
                          "finding": f"{r['aspect']} is among the most-mentioned aspects overall",
                          "evidence_metric": "n_mentions", "evidence_value": r["n_mentions"],
                          "support_n": r["n_mentions"], "confidence": "See E17 tiers",
                          "limitation": "Rule-based dictionary, mention != sentiment"})
    fid += 1
for _, r in adequate.head(10).iterrows():
    finding_rows.append({"finding_id": fid, "level": "HOTEL", "hotel_id": r["hotel_id"], "hotel_name": r["hotel_name"],
                          "area": r["area"], "finding": f"mean_rating={r['mean_rating']}, high_share={r['high_share']}",
                          "evidence_metric": "n_reviews", "evidence_value": r["n_reviews"],
                          "support_n": r["n_reviews"], "confidence": r.get("sample_support", ""),
                          "limitation": "Google Travel sample only"})
    fid += 1
key_findings = pd.DataFrame(finding_rows)
key_findings.to_csv(REPO_ROOT + r"\\reports\\google_travel_customer_voice_key_findings_master.csv", index=False)
print(len(key_findings), "findings written")
key_findings.head(10)
""")

md("""## E23-E24: Final text summary & Top findings table""")
code("""
lines = []
lines.append("GOOGLE TRAVEL CUSTOMER VOICE - FINAL SUMMARY")
lines.append("=" * 50)
lines.append("")
lines.append("DATA COVERAGE")
for k, v in coverage.items():
    lines.append(f"  {k}: {v}")
lines.append("")
lines.append("RATING")
lines.append(f"  mean_rating: {round(clean['review_rating_numeric'].mean(), 2)}")
lines.append(f"  rating_group_distribution: {clean['rating_group'].value_counts().to_dict()}")
lines.append("")
lines.append("CUSTOMER VOICE")
lines.append(f"  top_overall_aspects: {top_overall['aspect'].tolist()}")
lines.append(f"  top_positive_context_aspects: {top_positive['aspect'].tolist()}")
lines.append(f"  top_negative_context_aspects: {top_negative['aspect'].tolist()}")
lines.append("")
lines.append("STRENGTHS")
lines.append(f"  {len(strengths)} hotels with an identified strength-signal aspect")
lines.append("")
lines.append("CONCERNS")
lines.append(f"  {len(concerns)} hotels with an identified concern-signal aspect")
lines.append("")
lines.append("HOTEL PROFILES")
lines.append(f"  {len(adequate)} / {len(profile_summary)} hotels are sample-adequate (n>=5)")
lines.append("")
lines.append("AREA PROFILES")
lines.append(f"  top area by review coverage: {area_summary.iloc[0]['area']}")
lines.append("")
lines.append("SOURCE SENSITIVITY")
lines.append(f"  {sensitivity.iloc[0].to_dict()}")
lines.append("")
lines.append("LIMITATIONS")
lines.append("  See notebook 15 section E19 for the full list (aggregate source, sample imbalance,")
lines.append("  rule-based aspects, no sentiment model, no causal claims, stable-end != historical 100%).")
lines.append("")
lines.append("NEXT STEP")
lines.append("  Trip.com discovery/scraping and TripAdvisor were explicitly out of scope this round.")

with open(REPO_ROOT + r"\\reports\\google_travel_customer_voice_final_summary.txt", "w", encoding="utf-8") as f:
    f.write("\\n".join(lines) + "\\n")
print("\\n".join(lines))
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
