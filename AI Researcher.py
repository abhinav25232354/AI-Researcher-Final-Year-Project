# ai_researcher_demo.py (v2 – handles 429 & API‑key)
"""Minimal but **fully working** demo for the AI‑Researcher project.

USAGE (Windows Powershell example):
    python .\ai_researcher_demo.py "Machine Learning"

WHAT’S NEW IN v2
─────────────────
1.  Handles **HTTP 429 Too Many Requests** gracefully (retry w/ back‑off).
2.  Optional **Semantic Scholar API‑key** support – increases free quota.
3.  Lets you choose how many papers (default 30).
4.  Cleaner terminal output & error messages.

Install once:
    pip install requests tqdm sumy

NOTE – still uses micro‑heuristics for classification & TextRank for summary.
Swap in SciBERT & LED later.
"""
from __future__ import annotations

import os
import sys
import time
import re
from collections import Counter
from textwrap import shorten
from typing import List

import requests
from tqdm import tqdm



# ────────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────────────────────────────────────
DEFAULT_N_PAPERS = 30  # you can override via CLI «--n 100»
API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,abstract,year,url"
API_KEY = os.getenv("SS_API_KEY")  # put your key in an env‑var if you have one
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
    """Fetch papers and handle 429 with exponential back‑off."""
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

def summarise(all_text: str, max_sentences: int = 5) -> str:
    try:
        from sumy.parsers.plaintext import PlaintextParser
        
        from sumy.nlp.tokenizers import Tokenizer
        import nltk
        nltk.download('punkt_tab')
        
        from sumy.summarizers.text_rank import TextRankSummarizer
    except ImportError:
        return "(install 'sumy' for summaries)"
    parser = PlaintextParser.from_string(all_text, Tokenizer("english"))
    summarizer = TextRankSummarizer()
    sents = summarizer(parser.document, sentences_count=max_sentences)
    return " ".join(str(s) for s in sents)


def gap_keywords(counter: Counter, threshold: int = 1):
    return [w for w, c in counter.items() if c <= threshold][:10]

# ────────────────────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python ai_researcher_demo.py \"topic\" [--n 50]")
        sys.exit(1)

    topic_parts = []
    n_papers = DEFAULT_N_PAPERS
    for arg in sys.argv[1:]:
        if arg.startswith("--n"):
            try:
                n_papers = int(arg.split("=")[-1])
            except ValueError:
                print("Invalid --n value; using default.")
        else:
            topic_parts.append(arg)
    topic = " ".join(topic_parts)

    print(f"🔎 Topic: {topic!r}  |  Papers requested: {n_papers}\n")
    if API_KEY:
        print("✅ Using API‑key (higher quota)")
    else:
        print("⚠️  No API‑key set; may hit 429. Get one free at Semantic Scholar.")

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

    print("\n===== Combined Summary (TextRank) =====")
    summary = summarise("\n".join(abstracts))
    print(shorten(summary, 800))

    print("\n===== Potential Gap Keywords =====")
    for kw in gap_keywords(word_counts):
        print("•", kw)

if __name__ == "__main__":
    main()
