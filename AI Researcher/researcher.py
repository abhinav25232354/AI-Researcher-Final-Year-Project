import requests, time, re, traceback
from typing import List, Dict
from openai import OpenAI, OpenAIError

# ── Gemini/OpenRouter Config ──
OPENROUTER_API_KEY = "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"  # Replace with your full API key
MODEL_ID = "openrouter/horizon-alpha"
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

# ── OpenAI client init ──
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

# ── Semantic Scholar config ──
SS_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SS_FIELDS = "title,abstract,year,url"
RE_WORD = re.compile(r"[a-z]{4,}")

def fetch_papers(query: str, limit: int) -> List[Dict]:
    params, delay, retries = {"query": query, "limit": limit, "offset": 0, "fields": SS_FIELDS}, 1, 0
    while retries < MAX_RETRIES:
        try:
            r = requests.get(SS_API_URL, params=params, timeout=REQUEST_TIMEOUT)
            if r.status_code == 429:
                print(f"SemanticScholar rate-limited. Sleeping {delay}s…")
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            r.raise_for_status()
            return r.json().get("data", [])
        except requests.RequestException as e:
            retries += 1
            print(f"Network error ({retries}/{MAX_RETRIES}):", e)
            time.sleep(delay)
            delay *= 2
    print("Could not fetch papers after multiple retries.")
    return []

def call_gemini(prompt: str, max_tokens: int = 300, temperature: float = 0.7) -> str:
    retries, delay = 0, 1
    while retries < MAX_RETRIES:
        try:
            response = client.chat.completions.create(
                model=MODEL_ID,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                extra_headers={
                    "HTTP-Referer": "https://your-site.com",
                    "X-Title": "AI Researcher"
                }
            )
            return response.choices[0].message.content.strip()
        except OpenAIError as e:
            retries += 1
            print(f"[Retry {retries}] OpenRouter error:", e)
            time.sleep(delay); delay *= 2
        except Exception as e:
            retries += 1
            print(f"[Retry {retries}] Unexpected error:", e)
            traceback.print_exc()
            time.sleep(delay); delay *= 2
    return "[Gemini LLM call failed]"

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
    result = call_gemini(prompt, max_tokens=10, temperature=0)
    result = result.lower().strip()
    if "qualitative" in result:
        return "qualitative"
    if "quantitative" in result:
        return "quantitative"
    return "unknown"
