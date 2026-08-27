"""Builds and executes notebooks/14_google_travel_all_hotels_nlp_aspect_analysis.ipynb."""
from __future__ import annotations

import nbformat as nbf
from nbclient import NotebookClient
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
NB_PATH = REPO_ROOT / "notebooks" / "14_google_travel_all_hotels_nlp_aspect_analysis.ipynb"

cells = []


def md(src): cells.append(nbf.v4.new_markdown_cell(src))
def code(src): cells.append(nbf.v4.new_code_cell(src))


md("""# Bodrum Hotel & Destination Intelligence
## 14 - Google Travel All-Hotels NLP & Aspect Analysis

Ana soru: "Müşteriler en çok neyi övüyor, neyi eleştiriyor?" """)

code(f"""
import sys
sys.path.insert(0, r"{SRC}")
import re
import unicodedata
from collections import Counter
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
%matplotlib inline
import os

from bodrum_intelligence.analysis.aspect_dictionary import detect_aspects, ASPECT_KEYWORDS

REPO_ROOT = r"{REPO_ROOT}"
FIG_DIR = REPO_ROOT + r"\\reports\\figures\\google_travel_all_hotels_nlp"
os.makedirs(FIG_DIR, exist_ok=True)

clean = pd.read_csv(REPO_ROOT + r"\\data\\processed\\google_travel_all_hotels_reviews_clean.csv")
tr = clean[clean["language_detected"] == "tr"].copy()
print("total rows:", len(clean), "| Turkish-detected rows used for NLP:", len(tr))
""")

md("""## D3-D4: Text normalization & brand stopwords""")
code("""
_TR_MAP = str.maketrans({"ı":"i","İ":"i","ş":"s","ğ":"g","ü":"u","ö":"o","ç":"c"})
BRAND_STOPWORDS = {"otel","hotel","resort","spa","bodrum","turkey","turkiye","bir","ve","bu","de","da",
                    "ile","icin","cok","gayet","genel","olarak","olan","gibi"}

def tokenize(text):
    if not isinstance(text, str) or not text:
        return []
    s = unicodedata.normalize("NFKD", text.lower().translate(_TR_MAP)).encode("ascii","ignore").decode("ascii")
    words = re.findall(r"[a-z]{3,}", s)
    return [w for w in words if w not in BRAND_STOPWORDS]

tr["tokens"] = tr["review_text_clean"].apply(tokenize)
tr["token_set"] = tr["tokens"].apply(set)
print("sample tokens:", tr["tokens"].iloc[0][:15] if len(tr) else [])
""")

md("""## D5: Document frequency (top terms)""")
code("""
df_counter = Counter()
for toks in tr["token_set"]:
    df_counter.update(toks)
n_docs = max(len(tr), 1)
term_freq = pd.DataFrame(
    [{"term": t, "document_frequency": c, "document_frequency_pct": round(c/n_docs*100, 2)}
     for t, c in df_counter.most_common(40)]
)
term_freq.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_term_frequency.csv", index=False)
term_freq.head(20)
""")

md("""## D6: Bigrams""")
code("""
bigram_counter = Counter()
for toks in tr["tokens"]:
    for a, b in zip(toks, toks[1:]):
        bigram_counter[f"{a} {b}"] += 1
bigram_df = pd.DataFrame(
    [{"bigram": k, "count": v} for k, v in bigram_counter.most_common(30) if v >= 2]
)
bigram_df.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_bigram_frequency.csv", index=False)
bigram_df.head(15)
""")

md("""## D7-D8: LOW vs HIGH rating-group language""")
code("""
def top_terms_for(mask, n=15):
    c = Counter()
    for toks in tr.loc[mask, "token_set"]:
        c.update(toks)
    return c.most_common(n)

low_terms = top_terms_for(tr["rating_group"] == "LOW")
high_terms = top_terms_for(tr["rating_group"] == "HIGH")
distinctive = pd.DataFrame({
    "low_rating_top_terms": [t for t, _ in low_terms] + [""]*(15-len(low_terms)),
    "high_rating_top_terms": [t for t, _ in high_terms] + [""]*(15-len(high_terms)),
})
distinctive.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_rating_group_distinctive_terms.csv", index=False)
distinctive
""")

md("""## D12-D13: Aspect mention detection & hotel x aspect""")
code("""
tr["aspects"] = tr["review_text_clean"].apply(lambda t: detect_aspects(t) if isinstance(t, str) else set())

rows = []
for hotel_id, g in tr.groupby("hotel_id"):
    n = len(g)
    for aspect in ASPECT_KEYWORDS:
        mentioned = g["aspects"].apply(lambda s: aspect in s)
        cnt = int(mentioned.sum())
        if cnt == 0:
            continue
        rows.append({"hotel_id": hotel_id, "aspect": aspect, "mention_count": cnt,
                      "mention_rate_pct": round(cnt/n*100, 1), "support_n": n})
hotel_aspect = pd.DataFrame(rows)
hotel_aspect.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_hotel_aspect_mentions.csv", index=False)
print(len(hotel_aspect), "hotel x aspect rows with >=1 mention")
hotel_aspect.sort_values("mention_count", ascending=False).head(10)
""")

md("""## D14: Area x aspect""")
code("""
area_rows = []
for area, g in tr.groupby("area"):
    n = len(g)
    for aspect in ASPECT_KEYWORDS:
        mentioned = g["aspects"].apply(lambda s: aspect in s)
        cnt = int(mentioned.sum())
        if cnt == 0:
            continue
        area_rows.append({"area": area, "aspect": aspect, "mention_rate_pct": round(cnt/n*100, 1),
                           "support_n": n, "hotel_count": g["hotel_id"].nunique()})
area_aspect = pd.DataFrame(area_rows)
area_aspect.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_area_aspect_mentions.csv", index=False)
area_aspect.sort_values("mention_rate_pct", ascending=False).head(10)
""")

md("""## D15-D16: Aspect x rating (rating-context proxy, NOT sentiment)""")
code("""
aspect_rows = []
for aspect in ASPECT_KEYWORDS:
    mask = tr["aspects"].apply(lambda s: aspect in s)
    sub = tr[mask]
    if len(sub) == 0:
        continue
    aspect_rows.append({
        "aspect": aspect, "n_mentions": len(sub),
        "mean_rating_when_mentioned": round(sub["review_rating_numeric"].mean(), 2),
        "median_rating_when_mentioned": sub["review_rating_numeric"].median(),
        "low_rating_share_when_mentioned": round((sub["rating_group"]=="LOW").mean()*100, 1),
        "high_rating_share_when_mentioned": round((sub["rating_group"]=="HIGH").mean()*100, 1),
    })
aspect_rating = pd.DataFrame(aspect_rows).sort_values("n_mentions", ascending=False)
aspect_rating.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_aspect_rating_summary.csv", index=False)
aspect_rating
""")

md("""## D17-D18: Hotel x aspect x rating-context (min support flagged)""")
code("""
hac_rows = []
for (hotel_id, aspect), g in tr.explode("aspects").dropna(subset=["aspects"]).groupby(["hotel_id","aspects"]):
    n = len(g)
    hac_rows.append({
        "hotel_id": hotel_id, "aspect": aspect, "mention_rate_n": n,
        "low_context_share": round((g["rating_group"]=="LOW").mean()*100,1),
        "high_context_share": round((g["rating_group"]=="HIGH").mean()*100,1),
        "mean_rating": round(g["review_rating_numeric"].mean(),2),
        "support_flag": "LOW_SUPPORT" if n < 3 else "OK",
    })
hotel_aspect_context = pd.DataFrame(hac_rows)
hotel_aspect_context.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_hotel_aspect_rating_context.csv", index=False)
hotel_aspect_context.sort_values("mention_rate_n", ascending=False).head(10)
""")

md("""## D19: Heatmap - top hotels x top aspects (mention rate %)""")
code("""
top_hotels = tr["hotel_id"].value_counts().head(15).index.tolist()
top_aspects = aspect_rating["aspect"].head(12).tolist()
pivot = hotel_aspect[hotel_aspect["hotel_id"].isin(top_hotels) & hotel_aspect["aspect"].isin(top_aspects)]
pivot_table = pivot.pivot(index="hotel_id", columns="aspect", values="mention_rate_pct").reindex(
    index=top_hotels, columns=top_aspects)

fig, ax = plt.subplots(figsize=(10, max(4, 0.4*len(top_hotels))))
im = ax.imshow(pivot_table.fillna(0).values, cmap="YlOrRd", aspect="auto")
ax.set_xticks(range(len(top_aspects))); ax.set_xticklabels(top_aspects, rotation=45, ha="right")
ax.set_yticks(range(len(top_hotels))); ax.set_yticklabels(top_hotels)
ax.set_title("Aspect mention rate % (top 15 hotels by review count x top 12 aspects)")
plt.colorbar(im, ax=ax, label="mention rate %")
plt.tight_layout()
plt.savefig(FIG_DIR + r"\\hotel_aspect_heatmap.png", dpi=110)
plt.show()
""")

md("""### Grafik nasıl okunur?
Satırlar otel, sütunlar aspect (konu); renk koyulaştıkça o otelde o konudan bahsedilme oranı artar.
### Ne görüyoruz?
Hangi otellerde hangi konuların öne çıktığı tek bakışta karşılaştırılabilir.
### Neden önemli?
Otel bazlı güçlü/zayıf yön analizinin temelini oluşturur.
### Dikkat edilmesi gereken nokta
Yalnızca en çok yorum alan 15 otel gösterilmiştir; az örneklemli oteller için oranlar güvenilmezdir.""")

md("""## D21-D22: Low-rating vs high-rating themes""")
code("""
low_aspect_rates = aspect_rating.sort_values("low_rating_share_when_mentioned", ascending=False).head(8)
high_aspect_rates = aspect_rating.sort_values("high_rating_share_when_mentioned", ascending=False).head(8)
print("Top LOW-context aspects:\\n", low_aspect_rates[["aspect","low_rating_share_when_mentioned","n_mentions"]])
print("\\nTop HIGH-context aspects:\\n", high_aspect_rates[["aspect","high_rating_share_when_mentioned","n_mentions"]])
""")

md("""## D23: Customer voice profiles (sample-adequate hotels)""")
code("""
profiles = []
for hotel_id, g in tr.groupby("hotel_id"):
    n = len(g)
    if n < 5:
        continue
    ha = hotel_aspect[hotel_aspect["hotel_id"] == hotel_id].sort_values("mention_count", ascending=False)
    top_aspects_list = ha["aspect"].head(5).tolist()
    hac = hotel_aspect_context[hotel_aspect_context["hotel_id"] == hotel_id]
    strengths = hac[hac["high_context_share"] >= 60].sort_values("mention_rate_n", ascending=False)["aspect"].head(3).tolist()
    concerns = hac[hac["low_context_share"] >= 40].sort_values("mention_rate_n", ascending=False)["aspect"].head(3).tolist()
    profiles.append({
        "hotel_id": hotel_id, "hotel_name": g["hotel_name"].iloc[0], "area": g["area"].iloc[0],
        "review_n": n, "rating_profile": round(g["review_rating_numeric"].mean(), 2),
        "top_aspects": ";".join(top_aspects_list), "top_low_context_aspects": ";".join(concerns),
        "top_high_context_aspects": ";".join(strengths),
        "confidence_note": "MODERATE" if n < 20 else "STRONGER",
    })
voice_profiles = pd.DataFrame(profiles)
voice_profiles.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_customer_voice_profiles.csv", index=False)
print(len(voice_profiles), "hotels with n>=5 profiled")
voice_profiles.head(5)
""")

md("""## D25: Google-only NLP sensitivity""")
code("""
google_only_tr = tr[tr["review_source"] == "GOOGLE"]
sens = pd.DataFrame([{
    "all_sources_n": len(tr), "google_only_n": len(google_only_tr),
    "all_sources_top_term": term_freq.iloc[0]["term"] if len(term_freq) else None,
    "google_only_top_term": Counter(t for toks in google_only_tr["token_set"] for t in toks).most_common(1)[0][0]
        if len(google_only_tr) else None,
}])
sens.to_csv(REPO_ROOT + r"\\reports\\google_travel_all_hotels_nlp_source_sensitivity.csv", index=False)
sens
""")

md("""## D26: Topic modeling - SKIPPED
Corpus henüz çok küçük / hızla büyüyor; kararsız/aşırı-yorumlanabilir topic çıktısı riski var. Optional adım
olarak bilinçli şekilde atlandı (D26 kuralı: yalnız stabilse dahil et).""")

md("""## D28: Notebook 14 - Key Findings""")
code("""
findings = []
findings.append(f"NLP corpus: {len(tr)} Turkish-detected reviews across {tr['hotel_id'].nunique()} hotels.")
if len(aspect_rating):
    findings.append("Top 10 aspects overall (by mention count): " + ", ".join(aspect_rating["aspect"].head(10).tolist()))
    findings.append("Top LOW-rating-context aspects: " + ", ".join(low_aspect_rates["aspect"].head(5).tolist()))
    findings.append("Top HIGH-rating-context aspects: " + ", ".join(high_aspect_rates["aspect"].head(5).tolist()))
findings.append(f"{len(voice_profiles)} hotels have n>=5 Turkish reviews and got a customer-voice profile; "
                 f"the rest need more data before aspect-level claims are reliable.")
findings.append("Rating-context shares are a proxy signal (co-occurrence with LOW/HIGH ratings), not a trained sentiment model.")
findings.append("Topic modeling (D26) was skipped - corpus not yet stable/large enough for interpretable topics.")
for i, f_ in enumerate(findings, 1):
    print(f"{i}. {f_}")
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}}

client = NotebookClient(nb, kernel_name="python3", timeout=900)
client.execute()

NB_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(NB_PATH, "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print(f"Wrote executed notebook: {NB_PATH}")
