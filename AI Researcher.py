# ai_researcher_demo.py (v6 – fixed gap keyword duplication)
"""Advanced demo for the AI‑Researcher project with transformer-based summarization.

WHAT’S NEW IN v6
─────────────────
1. User input interface retained
2. Transformer summarization enhanced
3. Gap keywords now include contextual suggestions, possible reasons, and research directions
4. Fixed duplicate or irrelevant gap keyword display

Install required packages:
    pip install transformers torch requests tqdm
"""
from __future__ import annotations

import os
import time
import re
from collections import Counter
from typing import List

import requests
from tqdm import tqdm

# ────────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────────────────────────────────────
DEFAULT_N_PAPERS = 30
API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,abstract,year,url"
API_KEY = os.getenv("SS_API_KEY")
HEADERS = {"x-api-key": API_KEY} if API_KEY else {}

QUAL_KWS = {
    "interview", "focus group", "narrative", "thematic", "phenomenology",
    "grounded theory", "qualitative"
}
QUANT_KWS = {
    "survey", "questionnaire", "regression", "anova", "statistical",
    "randomized", "experimental", "quantitative"
}

RE_WORD = re.compile(r"[a-z]{4,}")

# ────────────────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────────────────

def fetch_papers(query: str, limit: int) -> List[dict]:
    params = {"query": query, "limit": limit, "offset": 0, "fields": FIELDS}
    delay = 1
    while True:
        r = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
        if r.status_code == 429:
            print(f"⚠️  429 rate‑limit. Sleeping {delay}s …")
            time.sleep(delay)
            delay = min(delay * 2, 60)
            continue
        r.raise_for_status()
        return r.json().get("data", [])

def classify(abstract: str) -> str:
    text = abstract.lower()
    if any(k in text for k in QUAL_KWS):
        return "qualitative"
    if any(k in text for k in QUANT_KWS):
        return "quantitative"
    return "unknown"

def summarise(text: str, max_tokens: int = 256) -> str:
    try:
        from transformers import pipeline
        summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
        chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
        summaries = summarizer(chunks, max_length=150, min_length=30, do_sample=False)
        return " ".join(s['summary_text'] for s in summaries)
    except Exception as e:
        return f"(Transformer summary unavailable: {e})"

def gap_keywords(counter: Counter, threshold: int = 1):
    # Remove uninformative or generic words that commonly appear once but add no value
    blacklist = {"just", "left", "right", "additional", "device"}
    top_keywords = [w for w, c in counter.items() if c <= threshold and w not in blacklist][:10]
    explanations = []
    for word in top_keywords:
        explanation = (
            f"• {word.capitalize()} — This keyword was mentioned in only {counter[word]} of the papers analyzed, "
            f"suggesting a potential underexplored area. It may represent a concept, method, or variable that is relevant to '{word}' "
            f"but hasn't been deeply examined. Consider researching: How does '{word}' relate to your topic? Is it missing in current methods or datasets? "
            f"What impact might exploring it have on the field? Could you design a study that incorporates this element?"
        )
        explanations.append(explanation)
    return explanations

# ────────────────────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────────────────────

def main():
    print("\n🔍 AI RESEARCHER TOOL\n" + "=" * 25)
    topic = input("Enter research topic: ").strip()
    try:
        n_papers = int(input("Enter number of papers to analyze (default 30): ") or DEFAULT_N_PAPERS)
    except ValueError:
        n_papers = DEFAULT_N_PAPERS

    print(f"\n🔎 Topic: {topic!r}  |  Papers requested: {n_papers}\n")
    if API_KEY:
        print("✅ Using API‑key (higher quota)")
    else:
        print("⚠️  No API‑key set; may hit 429. Get one free at Semantic Scholar.")

    papers = fetch_papers(topic, n_papers)
    if not papers:
        print("No papers found!")
        return

    type_counts = Counter()
    word_counts = Counter()
    abstracts = []

    for p in tqdm(papers, desc="Analysing"):
        abst = p.get("abstract") or ""
        abstracts.append(abst)
        type_counts[classify(abst)] += 1
        word_counts.update(RE_WORD.findall(abst.lower()))

    # ─── RESULTS ────────────────────────────────────────────────────────────
    print("\n===== Study‑Type Breakdown =====")
    for k, v in type_counts.items():
        print(f"{k.title():<12}: {v}")

    print("\n===== Combined Summary (Transformer) =====")
    combined_text = "\n".join(abstracts)
    summary = summarise(combined_text)
    print(summary)

    print("\n===== Potential Gap Keywords =====")
    for explanation in gap_keywords(word_counts):
        print(explanation)

if __name__ == "__main__":
    main()
