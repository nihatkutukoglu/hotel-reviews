"""Builds and executes notebooks/12_google_travel_all_hotels_audit_cleaning.ipynb."""
from __future__ import annotations

import nbformat as nbf
from nbclient import NotebookClient
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
NB_PATH = REPO_ROOT / "notebooks" / "12_google_travel_all_hotels_audit_cleaning.ipynb"

cells = []


def md(src): cells.append(nbf.v4.new_markdown_cell(src))
def code(src): cells.append(nbf.v4.new_code_cell(src))


md("""# Bodrum Hotel & Destination Intelligence
## 12 - Google Travel All-Hotels Review Audit & Cleaning""")

code(f"""
import sys
sys.path.insert(0, r"{SRC}")
import subprocess
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
%matplotlib inline

REPO_ROOT = r"{REPO_ROOT}"
FIG_DIR = REPO_ROOT + r"\\reports\\figures\\google_travel_all_hotels_audit"
import os
os.makedirs(FIG_DIR, exist_ok=True)
pd.set_option("display.max_columns", 50)
""")

md("""## B1-B2: Source of truth & rebuild
Authoritative input: `data/raw/reviews/google_travel/` (never modified). The clean dataset and
input inventory are rebuilt by `scripts/analysis/build_google_travel_clean_dataset.py`.""")

code(f"""
result = subprocess.run([sys.executable, REPO_ROOT + r"\\scripts\\analysis\\build_google_travel_clean_dataset.py"],
                         capture_output=True, text=True, cwd=REPO_ROOT)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr)
""")

code(f"""
clean = pd.read_csv(REPO_ROOT + r"\\data\\processed\\google_travel_all_hotels_reviews_clean.csv")
inventory = pd.read_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_input_inventory.csv")
dup_audit = pd.read_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_duplicate_audit.csv")
print("clean rows:", len(clean), "| hotels:", clean['hotel_id'].nunique(), "| files:", len(inventory))
clean.head(3)
""")

md("## B3: Raw vs clean totals, source distribution")
code("""
raw_total = inventory['row_count'].sum()
summary_b3 = {
    "raw_total_rows": int(raw_total),
    "clean_total_rows": int(len(clean)),
    "unique_hotels": int(clean['hotel_id'].nunique()),
    "cross_hotel_duplicate_hash_groups": int(len(dup_audit)),
}
print(summary_b3)
clean['review_source'].value_counts()
""")

md("## B7: Missing values (per column, and per-hotel coverage)")
code("""
key_cols = ["review_text_clean", "review_rating_numeric", "review_date_raw", "review_source",
            "review_details_raw", "hotel_id"]
missing_overall = clean[key_cols].isna().sum().rename("missing_count").to_frame()
missing_overall["missing_pct"] = (missing_overall["missing_count"] / len(clean) * 100).round(2)
missing_overall

per_hotel_missing = clean.groupby("hotel_id").apply(
    lambda g: pd.Series({
        "n_reviews": len(g),
        "rating_missing_pct": round(g["review_rating_numeric"].isna().mean() * 100, 1),
        "rooms_score_missing_pct": round(g["rooms_score"].isna().mean() * 100, 1),
    }), include_groups=False
).reset_index()
per_hotel_missing.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_missing_values.csv", index=False)
per_hotel_missing.head()
""")

md("## B10-B11: Rating parse & rating groups")
code("""
rating_audit = clean["rating_group"].value_counts(dropna=False)
invalid_rating_count = int(clean["quality_flags"].str.contains("INVALID_RATING", na=False).sum())
print("invalid_rating_count:", invalid_rating_count)
rating_audit.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_rating_audit.csv")

fig, ax = plt.subplots(figsize=(6,4))
rating_audit.reindex(["LOW","MID","HIGH"]).plot(kind="bar", ax=ax, color=["#d9534f","#f0ad4e","#5cb85c"])
ax.set_title("Rating group distribution (all hotels, Google Travel corpus)")
ax.set_ylabel("review count")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\rating_group_distribution.png", dpi=110)
plt.show()
""")

md("""### Grafik nasıl okunur?
Her çubuk bir puan grubunu (LOW=1-2, MID=3, HIGH=4-5) temsil eder; yükseklik o gruba düşen toplam yorum sayısıdır.
### Ne görüyoruz?
Google Travel korpusunda puan dağılımının hangi uca kaydığı görülür.
### Neden önemli?
Genel memnuniyet eğilimini ve aşırı pozitif/negatif çarpıklığı tek bakışta gösterir.
### Dikkat edilmesi gereken nokta
Bu, tüm otellerin karışık toplamıdır - otel bazlı farklar C bölümünde (EDA) ayrıca ele alınır.""")

md("## B12-B13: Source distribution & date audit")
code("""
source_counts = clean["review_source"].value_counts()
source_counts.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_source_audit.csv")

fig, ax = plt.subplots(figsize=(6,4))
source_counts.plot(kind="bar", ax=ax, color="#337ab7")
ax.set_title("Review source distribution (Google Travel aggregates multiple sources)")
ax.set_ylabel("review count")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\source_distribution.png", dpi=110)
plt.show()
""")

md("""### Grafik nasıl okunur?
Her çubuk, Google Travel panelinin yorumu hangi kaynaktan aldığını (GOOGLE/TRIPADVISOR/TRIP_COM/OTHER) gösterir.
### Ne görüyoruz?
Google Travel review paneli tek kaynaklı değildir - farklı platformlardan toplanan yorumları aynı panelde birleştirir.
### Neden önemli?
"Google Travel review" demek "yalnız Google yorumu" demek değildir; kaynak karışımını bilmeden coverage/comparison yapmak yanıltıcı olur.
### Dikkat edilmesi gereken nokta
review_source, ham 'tarih' metninden parse edilmiştir ve site tarafından etiketlenmiştir - bizim bir varsayımımız değildir.""")

code("""
age = clean["review_age_days_approx"].dropna()
fig, ax = plt.subplots(figsize=(6,4))
ax.hist(age, bins=20, color="#5bc0de")
ax.set_title("Approximate review age (days) - relative-date estimate")
ax.set_xlabel("days ago (approx)")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\review_age_distribution.png", dpi=110)
plt.show()
print("date_coverage_pct:", round(age.notna().mean()*100, 1) if len(clean) else 0)
""")

md("## B15: Details (rooms/service/location) coverage")
code("""
details_coverage = clean.groupby("hotel_id").agg(
    n_reviews=("hotel_id", "size"),
    rooms_score_coverage_pct=("rooms_score", lambda s: round(s.notna().mean()*100, 1)),
    service_score_coverage_pct=("service_score", lambda s: round(s.notna().mean()*100, 1)),
    location_score_coverage_pct=("location_score", lambda s: round(s.notna().mean()*100, 1)),
).reset_index()
details_coverage.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_details_coverage.csv", index=False)

fig, ax = plt.subplots(figsize=(6,4))
ax.hist(details_coverage["rooms_score_coverage_pct"], bins=10, color="#9370db")
ax.set_title("Per-hotel mini-score (rooms/service/location) coverage %")
ax.set_xlabel("coverage %")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\details_coverage_by_hotel.png", dpi=110)
plt.show()
details_coverage.describe()
""")

md("## B16: Hotel corpus imbalance")
code("""
balance = clean.groupby("hotel_id").size().rename("review_count").reset_index()
balance["share_of_total_pct"] = (balance["review_count"] / balance["review_count"].sum() * 100).round(2)
balance = balance.sort_values("review_count", ascending=False)
balance.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_hotel_balance.csv", index=False)

fig, ax = plt.subplots(figsize=(8,5))
top15 = balance.head(15)
ax.barh(top15["hotel_id"][::-1], top15["review_count"][::-1], color="#20b2aa")
ax.set_title("Top 15 hotels by review count (raw counts - NOT a quality signal)")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\hotel_corpus_imbalance_top15.png", dpi=110)
plt.show()
balance.describe()
""")

md("""### Grafik nasıl okunur?
En çok yorumu bulunan 15 otel, ham yorum sayısına göre sıralanmıştır.
### Ne görüyoruz?
Oteller arası korpus büyüklüğü ciddi biçimde dengesizdir.
### Neden önemli?
Sonraki karşılaştırmalarda ham sayı yerine oran/rate kullanılması gerektiğini gösterir.
### Dikkat edilmesi gereken nokta
Çok yorum almak "daha iyi otel" anlamına gelmez - yalnızca daha fazla örneklem demektir.""")

md("## B17: Language audit (lightweight, rule-based)")
code("""
lang_counts = clean["language_detected"].value_counts()
fig, ax = plt.subplots(figsize=(5,4))
lang_counts.plot(kind="bar", ax=ax, color="#ff8c69")
ax.set_title("Detected review language (lightweight heuristic)")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\language_distribution.png", dpi=110)
plt.show()
lang_counts
""")

md("## B22: Notebook 12 - Final Answers")
code("""
answers = {
    "raw_total_rows": int(raw_total),
    "clean_total_rows": int(len(clean)),
    "hotel_count": int(clean['hotel_id'].nunique()),
    "source_distribution": clean['review_source'].value_counts().to_dict(),
    "cross_hotel_duplicate_hash_groups": int(len(dup_audit)),
    "empty_text_dropped_during_cleaning": "see google_travel_all_hotels_audit_summary.txt",
    "invalid_rating_count": invalid_rating_count,
    "rating_coverage_pct": round(clean['review_rating_numeric'].notna().mean()*100, 1),
    "date_coverage_pct": round(clean['review_age_days_approx'].notna().mean()*100, 1),
    "avg_details_coverage_pct": round(details_coverage['rooms_score_coverage_pct'].mean(), 1),
    "largest_corpus_hotel": balance.iloc[0].to_dict() if len(balance) else None,
    "smallest_corpus_hotel": balance.iloc[-1].to_dict() if len(balance) else None,
    "analysis_readiness": "READY for EDA (notebook 13)" if len(clean) > 0 else "NOT READY - no clean rows",
}
for k, v in answers.items():
    print(f"{k}: {v}")
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
