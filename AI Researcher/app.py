from flask import render_template, render_template_string, request, Flask
from collections import Counter
from researcher import fetch_papers, classify_gemini, call_gemini
from uuid import uuid4
import json, textwrap

app = Flask(__name__)
CACHE = {}  # cache for paper storage

@app.route("/")
def index():
    return render_template("index.html")


# ────────── STEP 0 : user typed a topic ──────────
@app.post("/api/step0")
def step0():
    topic = request.form.get("topic", "").strip()
    papers = fetch_papers(topic, 100)

    if not papers:
        return "<p class='text-red-400'>No exact papers found. Try a related keyword.</p>"

    cache_id = str(uuid4())
    CACHE[cache_id] = papers  # store in cache

    html = f"""
    <h2 class="text-xl font-semibold mb-2">Found {len(papers)} papers on <span class='text-blue-400'>{topic}</span></h2>

    <form hx-post="/api/step1" hx-target="#main-pane" hx-swap="innerHTML">
      <input type="hidden" name="topic" value="{topic}">
      <input type="hidden" name="cache_id" value="{cache_id}">

      <label class="block mb-1">How many papers to analyze? (Leave blank for all)</label>
      <input type="number" name="n" min="1" max="{len(papers)}"
             class="w-full p-2 rounded bg-gray-800 border border-gray-700 mb-4">

      <button class="py-2 px-4 bg-blue-600 hover:bg-blue-700 rounded">
        Next
      </button>
    </form>"""
    return html


# ────────── STEP 1 : user chose paper count ──────────
@app.post("/api/step1")
def step1():
    topic     = request.form["topic"]
    cache_id  = request.form["cache_id"]
    n_raw     = request.form.get("n", "").strip()

    papers_all = CACHE.get(cache_id, [])
    sel = papers_all if not n_raw else papers_all[:int(n_raw)]

    classifications = {p["abstract"] or "": classify_gemini(p["abstract"] or "") for p in sel}
    counts = Counter(classifications.values())

    html_counts = "".join(f"<li>{k.capitalize()}: {v}</li>" for k,v in counts.items())

    # Re-cache selected and classified data
    CACHE[cache_id + "_sel"] = sel
    CACHE[cache_id + "_class"] = classifications

    html = f"""
    <h2 class="text-xl font-semibold mb-2">Type distribution</h2>
    <ul class="list-disc pl-6 mb-4">{html_counts}</ul>

    <form hx-post="/api/step2" hx-target="#main-pane" hx-swap="innerHTML">
      <input type="hidden" name="cache_id" value="{cache_id}">

      <label class="block mb-1">Choose category to analyze:</label>
      <select name="cat" class="w-full p-2 rounded bg-gray-800 border border-gray-700 mb-4">
        <option value="all">All</option>
        <option value="qualitative">Qualitative</option>
        <option value="quantitative">Quantitative</option>
      </select>

      <label class="block mb-1">Summarize:</label>
      <select name="summ" class="w-full p-2 rounded bg-gray-800 border border-gray-700 mb-4">
        <option value="combined">All selected papers together</option>
        <option value="each">Each paper separately</option>
      </select>

      <button class="py-2 px-4 bg-blue-600 hover:bg-blue-700 rounded">
        Generate summary
      </button>
    </form>
    """
    return html


# ────────── STEP 2 : build summary + populate sidebars ──────────
# ────────── STEP 2 : build summary + populate sidebars ──────────
@app.post("/api/step2")
def step2():
    import re

    cache_id = request.form["cache_id"]
    cat = request.form["cat"]
    mode = request.form["summ"]

    sel = CACHE.get(cache_id + "_sel", [])
    classifications = CACHE.get(cache_id + "_class", {})

    if cat in ("qualitative", "quantitative"):
        sel = [p for p in sel if classifications.get(p["abstract"] or "") == cat]

    # --- Summary
    if mode == "each":
        blocks = []
        for p in sel:
            title = p.get("title", "[No Title]")
            abs_ = p.get("abstract") or ""
            summ = call_gemini(f"Summarize this abstract:\n{abs_}", max_tokens=200, temperature=0.3)

            paragraphs = "".join(f"<p>{line.strip()}</p>" for line in summ.splitlines() if line.strip())
            blocks.append(f"""
                <div class='mb-6'>
                    <h3 class='text-lg font-semibold mb-1'>{title}</h3>
                    <div class='space-y-2'>
                        {paragraphs}
                    </div>
                </div>
            """)
        summary_html = "".join(blocks)

    else:
        joined = "\n".join([p.get("abstract") or "" for p in sel])[:8000]
        summary_text = call_gemini(f"Summarize these abstracts:\n{joined}", max_tokens=300, temperature=0.3)
        summary_html = "<div class='space-y-4'>" + "".join(
            f"<p>{s.strip()}</p>" for s in summary_text.splitlines() if s.strip()
        ) + "</div>"

    # --- Sources
    src_items = []
    for p in sel:
        t = p.get("title", "[No Title]")
        typ = classifications.get(p["abstract"] or "", "unknown")
        yr = p.get("year", "?")
        url = p.get("url", "#")

        src_items.append(f"""
        <a href="{url}" target="_blank" class="block bg-gray-800 p-3 rounded hover:bg-gray-700 border border-gray-700 transition">
            <p class="text-blue-400 font-semibold">{t}</p>
            <small class="text-gray-400">{typ}, {yr}</small>
        </a>
        """)
    sources_html = "<div class='space-y-3'>" + "".join(src_items) + "</div>"

    # --- Research Gaps
    joined = "\n".join([p.get("abstract") or "" for p in sel])[:8000]
    gaps_raw = call_gemini(
        "Identify concrete research gaps with **TITLE**: then description\n\n---\n" + joined,
        max_tokens=400, temperature=0.4,
    )

    # Convert markdown to HTML (bold) and spacing
    gaps_raw = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", gaps_raw)
    gaps_blocks = gaps_raw.strip().split("---") if "---" in gaps_raw else gaps_raw.strip().split("\n\n")
    # gaps_html = "<div class='space-y-6'>" + "".join(
    #     f"<div class='gap-item'>{block.strip()}</div>" for block in gaps_blocks if block.strip()
    # ) + "</div>"
    def format_gap_block(text):
        lines = text.split("Description:")
        title = lines[0].replace("TITLE:", "").strip()
        desc = "Description:" + lines[1].strip() if len(lines) > 1 else ""
        return f"""
        <div class="gap-item p-2 rounded bg-gray-800 border border-gray-700">
            <h3 class="font-semibold text-white mb-2">{title}</h3>
            <p class="text-gray-300 text-sm leading-relaxed">{desc}</p>
        </div>
        """
    gaps_html = "<div class='space-y-6'>" + "".join(
    format_gap_block(block.strip()) for block in gaps_blocks if block.strip()
    ) + "</div>"


    # --- Final render
    return render_template_string(f"""
        <!-- Summary (center) -->
        <div id="main-pane" class='prose prose-invert max-w-none flex-1 min-w-0'>
            {summary_html}
        </div>

        <!-- Sources (left) -->
        <div hx-swap-oob="true" id="sources-pane" class="w-64 shrink-0 overflow-y-auto custom-scroll">
            <h2 class="text-lg font-semibold mb-4">Sources</h2>
            {sources_html}
        </div>

        <!-- Gaps (right) -->
        <div hx-swap-oob="true" id="gaps-pane" class="w-80 shrink-0 overflow-y-auto custom-scroll">
            <h2 class="text-lg font-semibold mb-4">Research Gaps</h2>
            {gaps_html}
        </div>
    """)

if __name__ == "__main__":
    app.run(debug=True)
