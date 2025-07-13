# ai_researcher_advanced.py
"""
AI Researcher – Fully Interactive Version using Gemini 2.5 (OpenRouter)
All network and runtime exceptions are gracefully handled to prevent crashes.
"""
import os, re, time, requests, textwrap, sys, traceback
from typing import List, Dict
from tqdm import tqdm
from collections import Counter
from openai import OpenAI, OpenAIError

# ─────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────
OPENROUTER_API_KEY = "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"
MODEL_ID            = "google/gemini-2.5-flash-preview-05-20"
DEFAULT_N_PAPERS    = 30
MAX_RETRIES         = 3
REQUEST_TIMEOUT     = 30

client: OpenAI | None = None
if OPENROUTER_API_KEY:
    try:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
    except Exception as e:
        print("Failed to initialise OpenAI client:", e)
else:
    print("No OpenRouter API key provided; exiting.")
    sys.exit(1)

SS_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SS_FIELDS  = "title,abstract,year,url"
RE_WORD    = re.compile(r"[a-z]{4,}")

# ─────────────────────────────────────────────────────────
# SAFE HELPERS
# ─────────────────────────────────────────────────────────

def safe_int(val:str, default:int)->int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def fetch_papers(query:str, limit:int)->List[Dict]:
    params, delay, retries = {"query":query, "limit":limit, "offset":0, "fields":SS_FIELDS}, 1, 0
    while retries < MAX_RETRIES:
        try:
            r = requests.get(SS_API_URL, params=params, timeout=REQUEST_TIMEOUT)
            if r.status_code == 429:
                print(f"SemanticScholar rate-limited. Sleeping {delay}s…")
                time.sleep(delay); delay = min(delay*2, 30); continue
            r.raise_for_status()
            return r.json().get("data", [])
        except requests.RequestException as e:
            retries += 1
            print(f"Network error ({retries}/{MAX_RETRIES}):", e)
            time.sleep(delay); delay *= 2
    print("Could not fetch papers after multiple retries.")
    return []


def classify_gemini(abstract: str) -> str:
    if not abstract.strip():
        return "unknown"
    prompt = f"""
You are an academic assistant. Given the following research abstract, classify it into one of these three types:
1. Qualitative
2. Quantitative
3. Unknown

Return only one word: either qualitative, quantitative, or unknown.

Abstract:
{abstract.strip()}
"""
    reply = call_gemini(prompt, max_tokens=10, temperature=0)
    reply = reply.lower().strip()
    if "qualitative" in reply:
        return "qualitative"
    if "quantitative" in reply:
        return "quantitative"
    return "unknown"


def call_gemini(prompt:str, max_tokens:int=300, temperature:float=0.7)->str:
    if client is None:
        return "[LLM unavailable]"
    retries, delay = 0, 1
    while retries < MAX_RETRIES:
        try:
            resp = client.chat.completions.create(
                model=MODEL_ID,
                messages=[{"role":"user","content":prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                extra_headers={
                    "HTTP-Referer":"https://your-site.com",
                    "X-Title":"AI Researcher"
                }
            )
            return resp.choices[0].message.content.strip()
        except OpenAIError as e:
            retries += 1
            print(f"OpenRouter error ({retries}/{MAX_RETRIES}):", e)
            time.sleep(delay); delay *= 2
        except Exception as e:
            retries += 1
            print(f"Unexpected LLM error ({retries}/{MAX_RETRIES}):", e)
            traceback.print_exc()
            time.sleep(delay); delay *= 2
    return "[LLM call failed after retries]"


def summarize_each(papers:List[Dict]):
    for p in papers:
        title = p.get("title", "[No Title]")
        abstract = p.get("abstract") or ""
        print(f"\n{title}\n{'-'*len(title)}")
        if not abstract:
            print("(No abstract available)")
            continue
        print(call_gemini(f"Summarize this abstract:\n{abstract}", max_tokens=200, temperature=0.3))


def summarize_combined(abstracts:List[str]):
    clean_abstracts = [a for a in abstracts if isinstance(a, str) and a.strip()]
    if not clean_abstracts:
        print("No abstracts to summarize.")
        return
    joined = "\n".join(clean_abstracts)
    print("\nCombined Summary:\n")
    print(call_gemini(f"Summarize these abstracts:\n{joined[:8000]}", max_tokens=300, temperature=0.3))


def print_formatted_sources(papers:List[Dict], classifications:Dict[str,str]):
    if not papers:
        print("\n(No sources to display)")
        return
    print("\nFormatted Sources:\n")
    for p in papers:
        title = p.get("title", "[No Title]")
        year  = p.get("year", "?")
        url   = p.get("url", "[No URL]")
        abstract = p.get("abstract") or ""
        chars  = len(abstract)
        words  = len(abstract.split()) if abstract else 0
        pages  = round(words/500,1) if words else 0
        read_t = round(words/200,1) if words else 0
        category = classifications.get(abstract, "unknown")

        print(textwrap.dedent(f"""
        --------------------------------------------------
        Title     : {title}
        Type      : {category}
        Published : {year}
        Read Time : {read_t} min
        Pages     : ~{pages}
        Characters: {chars}
        URL       : {url}
        """))

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────

def main():
    try:
        print("\nADVANCED AI RESEARCHER – Gemini 2.5")
        print("="*50)
        topic = input("Enter research topic: ").strip()
        if not topic:
            print("Topic cannot be empty."); return

        print("\nFetching metadata to estimate total research...")
        full_results = fetch_papers(topic, 100)
        total_results = len(full_results)
        print(f"\nTotal research papers found: {total_results}")
        if not full_results:
            print("Try again with a broader topic.")
            return

        try:
            use_all = input("\nAnalyze all found papers? (y/n): ").strip().lower()
            if use_all == "n":
                custom_n = int(input("How many papers to analyze?: ").strip())
                if custom_n > total_results:
                    print(f"You requested more than available. Using all {total_results} papers.")
                else:
                    full_results = full_results[:custom_n]
        except Exception:
            print("Invalid input. Defaulting to all results.")

        print("\nAnalyzing research types using Gemini model...")
        classifications = {}
        for p in tqdm(full_results):
            abstract = p.get("abstract") or ""
            classifications[abstract] = classify_gemini(abstract)

        type_counts = Counter(classifications.values())
        print("\nResearch Types Found:")
        for t, count in type_counts.items():
            print(f"- {t.capitalize()}: {count}")

        print("\nSelect a research type to explore:")
        print("1 → Qualitative\n2 → Quantitative\n3 → Both")
        user_type = input("Your choice (1/2/3): ").strip()
        if user_type not in {"1","2","3"}:
            print("Invalid choice. Defaulting to both.")
            user_type = "3"

        selected_papers = []
        for p in full_results:
            a = p.get("abstract") or ""
            t = classifications.get(a, "unknown")
            if user_type == "1" and t == "qualitative":
                selected_papers.append(p)
            elif user_type == "2" and t == "quantitative":
                selected_papers.append(p)
            elif user_type == "3":
                selected_papers.append(p)

        print(f"\n{len(selected_papers)} papers selected from chosen category.")

        print("\nHow would you like the summary?")
        print("1 → Summarize each paper separately")
        print("2 → Summarize all selected papers together")
        summ_type = input("Your choice (1/2): ").strip()
        if summ_type == "1":
            summarize_each(selected_papers)
        else:
            summarize_combined([p.get("abstract", "") for p in selected_papers])

        ask_gaps = input("\nDo you want to discover research gaps? (y/n): ").strip().lower()
        if ask_gaps == "y":
            valid_papers = [p for p in selected_papers if p.get("abstract")]
            abstracts = "\n".join(p["abstract"] for p in valid_papers)
            # abstracts = "\n".join(p.get("abstract", "") for p in selected_papers)
            prompt = f"""
You are a research assistant. Based on these abstracts, list 5 concrete research gaps.
Each gap should begin with **TITLE**: and explain briefly.

---
{abstracts[:8000]}
---
"""
            print("\nResearch Gaps:\n")
            print(call_gemini(prompt, max_tokens=400, temperature=0.4))

        ask_sources = input("\nDo you want to view source details? (y/n): ").strip().lower()
        if ask_sources == "y":
            all_or_sel = input("Show (1) all papers or (2) only selected category? ").strip()
            if all_or_sel == "1":
                print_formatted_sources(full_results, classifications)
            else:
                print_formatted_sources(selected_papers, classifications)

    except KeyboardInterrupt:
        print("\nExecution interrupted by user.")
    except Exception as e:
        print("An unexpected error occurred:", e)
        traceback.print_exc()

# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
