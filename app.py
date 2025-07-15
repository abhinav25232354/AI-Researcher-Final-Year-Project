from flask import render_template, render_template_string, request, Flask
from collections import Counter
from researcher import fetch_papers, classify_gemini, call_gemini
from uuid import uuid4
import json, textwrap
import webbrowser
import threading
from flask import send_file
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
import tempfile
import fitz  # PyMuPDF
import re

app = Flask(__name__)
CACHE = {}  # cache for paper storage

@app.route("/")
def index():
    return render_template("index.html")

def open_browser():
    webbrowser.open("http://127.0.0.1:5000")

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
    import re, textwrap

    cache_id = request.form["cache_id"]
    cat      = request.form["cat"]
    mode     = request.form["summ"]

    sel            = CACHE.get(cache_id + "_sel", [])
    classifications = CACHE.get(cache_id + "_class", {})

    if cat in ("qualitative", "quantitative"):
        sel = [p for p in sel if classifications.get(p.get("abstract", "")) == cat]

    # ---------- SUMMARY ----------
    if mode == "each":
        blocks = []
        for p in sel:
            summ = call_gemini(f"Summarize:\n{p.get('abstract','')}", max_tokens=200, temperature=0.3)
            blocks.append(f"<h3 class='text-lg font-semibold mb-1'>{p.get('title')}</h3>"
                          + "".join(f"<p>{l.strip()}</p>" for l in summ.splitlines() if l.strip()))
        summary_html  = "<div class='space-y-6'>" + "".join(blocks) + "</div>"
        summary_clean = re.sub(r"<[^>]+>", "", summary_html)
    else:
        joined = "\n".join(p.get("abstract","") for p in sel)[:8000]
        summ   = call_gemini(f"Summarize:\n{joined}", max_tokens=300, temperature=0.3)
        summary_html  = "<div class='space-y-4'>" + "".join(f"<p>{l.strip()}</p>" for l in summ.splitlines() if l.strip()) + "</div>"
        summary_clean = summ

    # ---------- SOURCES ----------
    src_items = "".join(
        f"<a href='{p.get('url','#')}' target='_blank' class='block bg-gray-800 p-3 rounded hover:bg-gray-700 border border-gray-700 mb-2'>"
        f"<p class='text-blue-400 font-semibold'>{p.get('title')}</p>"
        f"<small class='text-gray-400'>{classifications.get(p.get('abstract',''),'unknown')}, {p.get('year','?')}</small></a>"
        for p in sel)
    sources_html  = f"<div class='space-y-2'>{src_items}</div>"
    sources_clean = re.sub(r"<[^>]+>", "", src_items)

    # ---------- GAPS ----------
    joined = "\n".join(p.get("abstract","") for p in sel)[:8000]
    gaps_raw = call_gemini("Identify 3 research gaps (TITLE: description):\n"+joined, max_tokens=400, temperature=0.4)
    gaps_html = "".join(
        f"<div class='bg-gray-800 border border-gray-700 rounded p-3 mb-4'><h3 class='font-semibold mb-2'>{b.split(':',1)[0].replace('TITLE','').strip()}</h3><p class='text-gray-300 text-sm leading-relaxed'>{b.split(':',1)[1].strip()}</p></div>"
        for b in re.split(r"\n\s*\n|---", gaps_raw) if ':' in b)
    gaps_clean = re.sub(r"<[^>]+>", "", gaps_html)

    # ---------- Cache clean versions for PDF export ----------
    CACHE[cache_id + "_summary"] = summary_clean
    CACHE[cache_id + "_gaps"]    = gaps_clean
    CACHE[cache_id + "_sources"] = sources_clean

    # ---------- Return HTML ----------
    return render_template_string("""
    <div id="main-pane" class="prose prose-invert max-w-none flex-1 min-w-0">{{summary|safe}}</div>
    <div hx-swap-oob="true" id="sources-pane"><h2 class="text-lg font-semibold mb-4">Sources</h2>{{sources|safe}}</div>
    <div hx-swap-oob="true" id="gaps-pane"><h2 class="text-lg font-semibold mb-4">Research Gaps</h2>{{gaps|safe}}</div>
    """, summary=summary_html, sources=sources_html, gaps=gaps_html)


@app.post("/api/export_pdf")
def export_pdf():
    # 1️⃣  Prefer uploaded summary if present
    if "uploaded_summary" in CACHE:
        summary_text = CACHE["uploaded_summary"]
        gaps_text    = CACHE["uploaded_gaps"]
        sources_text = CACHE["uploaded_sources"]
    else:
        # 2️⃣  Otherwise use the most‑recent search cache
        keys = [k for k in CACHE if k.endswith("_summary")]
        if not keys:
            return "<script>alert('Please search a topic or upload a paper first.')</script>"
        cid          = sorted(keys)[-1].replace("_summary", "")
        summary_text = CACHE[cid + "_summary"]
        gaps_text    = CACHE[cid + "_gaps"]
        sources_text = CACHE[cid + "_sources"]

    # 3️⃣  Guard: nothing cached yet
    if not summary_text.strip():
        return "<script>alert('Please search a topic or upload a paper first.')</script>"

    # strip any leftover HTML
    strip = lambda t: re.sub(r"<[^>]+>", "", t or "")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        c = canvas.Canvas(tmp.name, pagesize=LETTER)
        W, H = LETTER; y = H - 50

        def block(title, content):
            nonlocal y
            if not content.strip(): return
            c.setFont("Helvetica-Bold", 14); c.drawString(50, y, title); y -= 20
            c.setFont("Helvetica", 10)
            for ln in textwrap.wrap(strip(content), 95):
                if y < 50: c.showPage(); y = H - 50; c.setFont("Helvetica", 10)
                c.drawString(50, y, ln); y -= 15
            y -= 10

        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(W / 2, y, "DexterityCoder"); y -= 40

        block("Summary",       summary_text)
        block("Research Gaps", gaps_text)
        block("Sources",       sources_text)

        c.save()
        return send_file(tmp.name, as_attachment=True,
                         download_name="DexterityCoder_Research_Report.pdf")

    
@app.post("/api/upload_pdf")
def upload_pdf():
    file = request.files["pdf"]
    doc = fitz.open(stream=file.read(), filetype="pdf")
    full_text = "\n".join(page.get_text() for page in doc)

    # Summarize
    summary = call_gemini(f"Summarize this research paper:\n{full_text[:8000]}")
    gaps = call_gemini(f"Find 3 research gaps in the paper below:\n\n{full_text[:8000]}", temperature=0.4)

    # Extract links
    links = re.findall(r"https?://[^\s]+", full_text)
    link_items = "".join(
        f"<a href='{url}' target='_blank' class='block bg-gray-800 text-blue-400 p-2 rounded border border-gray-700 mb-2'>{url}</a>"
        for url in links
    )
    
    CACHE["uploaded_summary"] = summary
    CACHE["uploaded_gaps"] = gaps
    CACHE["uploaded_sources"] = link_items or "<p>No links found.</p>"

    return render_template_string(f"""
        <div class='prose prose-invert max-w-none space-y-6'>
            <h2 class="text-xl font-bold">Summary</h2>
            <p>{summary}</p>
            <h2 class="text-xl font-bold">Research Gaps</h2>
            <p>{gaps}</p>
        </div>
        <div hx-swap-oob="true" id="sources-pane">
            <h2 class="text-lg font-semibold mb-4">Sources</h2>
            {link_items}
        </div>
    """)

if __name__ == "__main__":
    threading.Timer(1.25, open_browser).start()  # opens browser automatically
    app.run(debug=True)
