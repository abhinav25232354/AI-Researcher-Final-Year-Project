# ai_researcher_demo.py (v13 — improved gap generation)
"""AI‑Researcher demo – **now optimised for speed** on CPU or GPU
────────────────────────────────────────────────────────────────
Key upgrades
============
1. **Auto‑detects GPU** (CUDA / Colab) and loads models on GPU when available.
2. **Picks model size automatically**
   • GPU present   → uses *mistralai/Mistral‑7B‑Instruct‑v0.2* for gap discovery.
   • CPU only      → falls back to lightweight *tiiuae/falcon‑rw‑1b* (≈ 1 B params) ⇒ results in ≤ 30 s.
3. Summariser switched to **t5‑small** (tiny & fast) with cleaning for output.
4. Gap extractor now validates real gaps and falls back to heuristics when needed.
5. Output now hides non-essential system/debug messages.
6. 📌 NEW: Lists **all paper source links** at the end.

Install once:
    pip install transformers torch requests tqdm accelerate nltk
"""
from __future__ import annotations
import os, time, re, torch, textwrap
from collections import Counter
from typing import List
import requests
from tqdm import tqdm
from nltk.tokenize import sent_tokenize

# ───────────────────────────────────────────────────────────
# CONFIG
# ───────────────────────────────────────────────────────────
DEFAULT_N_PAPERS = 30
API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS  = "title,abstract,year,url"
API_KEY = os.getenv("SS_API_KEY")
HEADERS = {"x-api-key": API_KEY} if API_KEY else {}

CUDA   = torch.cuda.is_available()
DEVICE = 0 if CUDA else -1   # -1 = CPU for HF pipeline

SUMMARY_MODEL  = "google/flan-t5-small"   # 80 MB, <5 s even on CPU
SLOW_GAP_MODEL = "mistralai/Mistral-7B-Instruct-v0.2"
FAST_GAP_MODEL = "tiiuae/falcon-rw-1b"    # 1.3 B, fast on CPU
GAP_MODEL      = SLOW_GAP_MODEL if CUDA else FAST_GAP_MODEL

QUAL_KWS = {"interview","focus group","narrative","phenomenology","grounded theory","qualitative"}
QUANT_KWS = {"survey","questionnaire","regression","anova","statistical","randomized","experimental","quantitative"}
RE_WORD   = re.compile(r"[a-z]{4,}")

# ───────────────────────────────────────────────────────────
# HELPERS
# ───────────────────────────────────────────────────────────

def fetch_papers(query:str, limit:int)->List[dict]:
    params, delay = {"query":query,"limit":limit,"offset":0,"fields":FIELDS}, 1
    while True:
        r = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
        if r.status_code == 429:
            time.sleep(delay); delay = min(delay*2, 30); continue
        r.raise_for_status(); return r.json()["data"]

def classify(abst:str)->str:
    t=abst.lower()
    if any(k in t for k in QUAL_KWS): return "qualitative"
    if any(k in t for k in QUANT_KWS): return "quantitative"
    return "unknown"

def clean_summary(text: str) -> str:
    text = re.sub(r"(https?:\/\/\S+)", "", text)
    text = re.sub(r"\b(\w+)( \1\b)+", r"\1", text)
    sents = sent_tokenize(text)
    sents = [s for s in sents if len(s) > 20 and not any(s.lower().startswith(p) for p in ("summary:", "ess significance", "device set to use"))]
    return " ".join(sents)

def summarise(text:str)->str:
    from transformers import pipeline
    summ = pipeline("summarization", model=SUMMARY_MODEL, device=DEVICE)
    chunks = [text[i:i+1500] for i in range(0, len(text), 1500)] or [text]
    out = summ(chunks, max_new_tokens=120, do_sample=False)
    joined = " ".join(o['summary_text'] for o in out)
    return clean_summary(joined)

def find_gaps_llm(text: str, max_gaps: int = 5):
    from transformers import pipeline

    try:
        gen = pipeline("text-generation", model=GAP_MODEL, device=DEVICE, torch_dtype=torch.float16 if CUDA else None)
        prompt = textwrap.dedent(f"""
            You are a scholarly assistant. Based on the following research abstracts, list up to {max_gaps} specific research gaps.
            Format each gap as:
            **TITLE**: short phrase
            WHY: 1–2 sentences
            HOW: 1–2 concrete study ideas
            Only output gaps that are clearly missing in current research. Do not repeat vague or generic ideas.
            ---
{text[:4096]}
--- end
        """).strip()

        resp = gen(prompt, temperature=0.3, top_p=0.9, max_new_tokens=256)[0]["generated_text"]

        # Try to extract well-formed gaps
        gaps = []
        capture = False
        for line in resp.splitlines():
            if line.strip().startswith("**"):
                capture = True
                gaps.append(line.strip())
            elif capture and line.strip():
                gaps[-1] += f"\n{line.strip()}"
            elif not line.strip():
                capture = False

        # Keep only gaps that match the full pattern
        good = [g for g in gaps if "**" in g and "WHY:" in g and "HOW:" in g]

        if good:
            return good[:max_gaps]

        raise ValueError("Generated gaps didn't match format.")

    except Exception:
        print("⚠️  LLM gap extractor failed — using word rarity heuristic.")
        return heuristic_gaps(Counter(RE_WORD.findall(text.lower())))

def heuristic_gaps(counter:Counter):
    blacklist = {"just","left","right","additional","device"}
    rare = [w for w, c in counter.items() if c == 1 and w not in blacklist][:5]
    return [f"**{w.capitalize()}**: rarely mentioned — explore its role." for w in rare]

# ───────────────────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────────────────

def main():
    print("\n🔍 AI RESEARCHER TOOL (FAST)\n" + "="*30)
    topic = input("Enter research topic: ").strip() or "Transformers"
    try: n = int(input("Number of papers (default 30): ") or DEFAULT_N_PAPERS)
    except ValueError: n = DEFAULT_N_PAPERS

    papers = fetch_papers(topic, n)
    if not papers:
        print("No papers found"); return

    counts = Counter(); words = Counter(); abstracts = []; urls = []
    for p in tqdm(papers, desc="Processing", ncols=70):
        a = p.get("abstract") or ""
        abstracts.append(a)
        counts[classify(a)] += 1
        words.update(RE_WORD.findall(a.lower()))
        if url := p.get("url"):
            urls.append(url)

    print("\n===== Study Types =====")
    for k, v in counts.items():
        print(f"{k:<12}: {v}")

    print("\n===== Summary =====")
    print(summarise("\n".join(abstracts)))

    print("\n===== Research Gaps =====")
    gaps = find_gaps_llm("\n".join(abstracts))
    for g in gaps:
        print(g)

    print("\n===== Sources (URLs) =====")
    for i, u in enumerate(urls, 1):
        print(f"[{i}] {u}")

if __name__ == "__main__":
    main()
