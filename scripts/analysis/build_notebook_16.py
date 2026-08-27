"""Builds and executes notebooks/16_tripcom_reviews_audit_cleaning.ipynb."""
from __future__ import annotations

import nbformat as nbf
from nbclient import NotebookClient
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NB_PATH = REPO_ROOT / "notebooks" / "16_tripcom_reviews_audit_cleaning.ipynb"

cells = []


def md(src): cells.append(nbf.v4.new_markdown_cell(src))
def code(src): cells.append(nbf.v4.new_code_cell(src))


md("""# Bodrum Hotel & Destination Intelligence
## 16 - Trip.com Review Audit & Cleaning""")

code(f"""
import sys, subprocess
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
%matplotlib inline
import os

REPO_ROOT = r"{REPO_ROOT}"
FIG_DIR = REPO_ROOT + r"\\reports\\figures\\tripcom_audit"
os.makedirs(FIG_DIR, exist_ok=True)
pd.set_option("display.max_columns", 50)
""")

md("## C1-C2: Rebuild clean dataset from raw (source of truth)")
code(f"""
result = subprocess.run([sys.executable, REPO_ROOT + r"\\scripts\\analysis\\build_tripcom_clean_dataset.py"],
                         capture_output=True, text=True, cwd=REPO_ROOT)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr)
""")

code("""
clean = pd.read_csv(REPO_ROOT + r"\\data\\processed\\tripcom_reviews_clean.csv")
inventory = pd.read_csv(REPO_ROOT + r"\\reports\\tripcom_input_inventory.csv")
dup_audit = pd.read_csv(REPO_ROOT + r"\\reports\\tripcom_duplicate_audit.csv")
print("clean rows:", len(clean), "| hotels:", clean['hotel_id'].nunique())
clean.head(3)
""")

md("""## C3: Identity audit (wrong entity contamination must be 0)
By construction, trip_adapter.py never writes a row for a WRONG_ENTITY result - this reads the
scrape_status log to confirm zero rows came from a wrong-entity or review-required source.""")
code("""
status = pd.read_csv(REPO_ROOT + r"\\reports\\multiplatform_scrape_status.csv")
trip_status = status[status["platform"] == "trip"]
wrong_rows_written = trip_status[trip_status["status"] == "WRONG_ENTITY"]["rows_added"].sum()
review_required_rows_written = trip_status[trip_status["status"] == "NAME_REVIEW_REQUIRED"]["rows_added"].sum()
print("wrong_entity_rows_written:", wrong_rows_written, "| review_required_rows_written:", review_required_rows_written)
assert wrong_rows_written == 0 and review_required_rows_written == 0, "SAFETY VIOLATION"
print("OK: 0 contamination confirmed")
""")

md("## C4: Duplicate audit")
code("""
print(f"{len(dup_audit)} cross-hotel duplicate hash groups (should be 0 or explainable)")
dup_audit.head()
""")

md("## C6-C7: Rating (raw preserved, normalized 5-scale, explicit thresholds)")
code("""
rating_dist = clean["rating_group"].value_counts()
rating_dist.to_csv(REPO_ROOT + r"\\reports\\tripcom_rating_audit.csv")

fig, ax = plt.subplots(figsize=(6,4))
rating_dist.reindex(["LOW","MID","HIGH"]).plot(kind="bar", ax=ax, color=["#d9534f","#f0ad4e","#5cb85c"])
ax.set_title("Trip.com rating group (5-scale; LOW<3.0, MID 3.0-3.99, HIGH>=4.0)")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\rating_group_distribution.png", dpi=110)
plt.show()
""")

md("""### Grafik nasıl okunur?
Trip.com'un ham 0-10 puanı 5'lik ölçeğe normalize edilip (rating_5_scale), açıkça belirtilen eşiklerle gruplanmıştır.
### Ne görüyoruz?
Trip.com misafirlerinin genel memnuniyet dağılımı.
### Neden önemli?
Google Travel ile karşılaştırma normalize edilmiş 5-scale üzerinden yapılacağı için bu adım kritik.
### Dikkat edilmesi gereken nokta
Ham puan hiçbir zaman üzerine yazılmadı; rating_5_scale ayrı bir kolondur.""")

md("## C8-C9: Review date & stay date coverage")
code("""
date_coverage = clean["review_date"].notna().mean() * 100
stay_coverage = clean["stay_year"].notna().mean() * 100
date_audit = pd.DataFrame([{"review_date_coverage_pct": round(date_coverage,1),
                             "stay_date_coverage_pct": round(stay_coverage,1)}])
date_audit.to_csv(REPO_ROOT + r"\\reports\\tripcom_date_audit.csv", index=False)
date_audit
""")

md("## C10-C11: Traveler type & room type coverage")
code("""
traveler_cov = clean["traveler_type"].value_counts()
traveler_cov.to_csv(REPO_ROOT + r"\\reports\\tripcom_traveler_type_coverage.csv")
room_cov = clean["room_type"].value_counts()
room_cov.to_csv(REPO_ROOT + r"\\reports\\tripcom_room_type_coverage.csv")

fig, axes = plt.subplots(1, 2, figsize=(11,4))
traveler_cov.plot(kind="bar", ax=axes[0], color="#337ab7", title="Traveler type (canonical)")
room_cov.plot(kind="bar", ax=axes[1], color="#5bc0de", title="Room type (canonical)")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\traveler_and_room_type.png", dpi=110)
plt.show()
""")

md("""### Grafik nasıl okunur?
Sol: misafir tipi (Family/Couple/Solo/Friends/vb.) dağılımı; sağ: oda tipi kategorileri.
### Ne görüyoruz?
Trip.com'un sağladığı ekstra bağlamsal alanların (Google Travel'de olmayan) kapsamı.
### Neden önemli?
Segment analizinin (notebook 17) hangi ölçekte güvenilir olacağını gösterir.
### Dikkat edilmesi gereken nokta
UNKNOWN/OTHER oranı yüksekse segment bulguları temkinli yorumlanmalı.""")

md("## C12: Reviewer location / country coverage")
code("""
country_cov = clean["reviewer_country"].value_counts()
country_cov.to_csv(REPO_ROOT + r"\\reports\\tripcom_reviewer_location_coverage.csv")
country_cov.head(15)
""")

md("## C16: Missing values & cleaning log")
code("""
key_cols = ["review_text_clean","source_rating","review_date","traveler_type_raw","room_type_raw","reviewer_country"]
missing = clean[key_cols].isna().sum().rename("missing_count").to_frame()
missing["missing_pct"] = (missing["missing_count"] / len(clean) * 100).round(1)
missing.to_csv(REPO_ROOT + r"\\reports\\tripcom_missing_values.csv")
missing
""")

code("""
ui_leak_rows = clean[clean["quality_flags"].str.contains("UI_LEAKAGE", na=False)]
cleaning_log = pd.DataFrame([{
    "duplicates_dropped": "see tripcom_audit_summary.txt",
    "empty_text_dropped": "see tripcom_audit_summary.txt",
    "ui_leakage_flagged_not_dropped": len(ui_leak_rows),
}])
cleaning_log.to_csv(REPO_ROOT + r"\\reports\\tripcom_cleaning_log.csv", index=False)
print(f"{len(ui_leak_rows)} rows flagged as suspected UI leakage (kept, not silently dropped):")
ui_leak_rows[["hotel_id","review_text","reviewer_location","quality_flags"]].head(10)
""")

md("""### Grafik nasıl okunur? (tablo)
Bu tablo, incelemede metninin ya da konum alanının aslında bir arayüz etiketi (örn. "Show More", "Black Diamond")
olduğu şüphelenilen satırları listeler.
### Ne görüyoruz?
Trip.com scraper'ının bazı kartlarda yanlış DOM elemanını okuduğu nadir durumlar.
### Neden önemli?
Bu satırlar SİLİNMEDİ (B18/C-politikası: yalnız tam duplicate ve boş metin silinir) - sadece işaretlendi, şeffaflık için.
### Dikkat edilmesi gereken nokta
Sayı küçükse (<%5) NLP/segment bulgularını önemli ölçüde etkilemez.""")

md("## Notebook 16 - Final Answers")
code("""
answers = {
    "raw_total_rows": int(inventory["row_count"].sum()),
    "clean_total_rows": int(len(clean)),
    "hotel_count": int(clean['hotel_id'].nunique()),
    "wrong_entity_contamination": int(wrong_rows_written),
    "date_coverage_pct": round(date_coverage, 1),
    "stay_date_coverage_pct": round(stay_coverage, 1),
    "traveler_type_coverage_pct": round((clean['traveler_type'] != 'UNKNOWN').mean()*100, 1),
    "room_type_coverage_pct": round((clean['room_type'] != 'UNKNOWN').mean()*100, 1),
    "reviewer_location_coverage_pct": round(clean['reviewer_country'].notna().mean()*100, 1),
    "ui_leakage_flagged_rows": int(len(ui_leak_rows)),
    "analysis_readiness": "READY for segment analysis (notebook 17)",
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
