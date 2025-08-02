from flask import render_template, render_template_string, request, Flask, send_file
from collections import Counter
from researcher import fetch_papers, classify_gemini, call_gemini
from uuid import uuid4
import json, textwrap
import os
import PyPDF2
import io
import re
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from datetime import datetime

app = Flask(__name__)
CACHE = {}  # cache for paper storage
UPLOAD_FOLDER = 'uploads'
EXPORT_FOLDER = 'exports'
ALLOWED_EXTENSIONS = {'pdf'}

# Create upload and export folders if they don't exist
try:
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    if not os.path.exists(EXPORT_FOLDER):
        os.makedirs(EXPORT_FOLDER, exist_ok=True)
        
except Exception as e:
    # Fallback to current directory if needed
    UPLOAD_FOLDER = '.'
    EXPORT_FOLDER = '.'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_file):
    """Extract text from uploaded PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"

def generate_pdf_report(cache_id, title="Research Analysis Report", custom_filename=None):
    """Generate a comprehensive PDF report with dexteritycoder branding"""
    try:
        # Get data from cache
        data = CACHE.get(cache_id, {})
        processed_data = CACHE.get(cache_id + "_processed", {})
        
        # Check if we have enough data to generate a report
        if not data and not processed_data:
            return None, "No data available for report generation"
        
        # Determine data type (list for papers, dict for PDF uploads)
        is_paper_list = isinstance(data, list)
        is_pdf_upload = isinstance(data, dict) and data.get('type') == 'pdf'
        
        # Create PDF file
        if custom_filename:
            filename = custom_filename
        else:
            filename = f"research_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # Use a local variable for export folder to avoid scope issues
        export_folder = EXPORT_FOLDER
        filepath = os.path.join(export_folder, filename)
        
        # Ensure the export directory exists
        try:
            os.makedirs(export_folder, exist_ok=True)
        except Exception as e:
            # Fallback to current directory
            export_folder = '.'
            filepath = os.path.join(export_folder, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
        story = []
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.black
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.black
        )
        
        brand_style = ParagraphStyle(
            'Brand',
            parent=styles['Normal'],
            fontSize=14,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=20
        )
        
        # Header with dexteritycoder branding
        story.append(Paragraph("Dexteritycoder", brand_style))
        story.append(Spacer(1, 20))
        
        # Title
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 20))
        
        # Report metadata
        story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
        story.append(Spacer(1, 30))
        
        # Summary Section
        if processed_data.get('summary'):
            story.append(Paragraph("Executive Summary", heading_style))
            summary_lines = processed_data['summary'].split('\n')
            for line in summary_lines:
                if line.strip():
                    story.append(Paragraph(line.strip(), styles['Normal']))
                    story.append(Spacer(1, 6))
            story.append(Spacer(1, 20))
        elif is_pdf_upload:
            # Fallback for PDF uploads without processed data
            story.append(Paragraph("Document Analysis", heading_style))
            story.append(Paragraph(f"Document: {data.get('filename', 'Unknown')}", styles['Normal']))
            story.append(Paragraph("PDF content analysis completed.", styles['Normal']))
            story.append(Spacer(1, 20))
        elif is_paper_list:
            # Fallback for search results without processed data
            story.append(Paragraph("Research Analysis", heading_style))
            story.append(Paragraph(f"Analysis of {len(data)} research papers completed successfully.", styles['Normal']))
            story.append(Spacer(1, 20))
        else:
            # Generic fallback
            story.append(Paragraph("Research Analysis", heading_style))
            story.append(Paragraph("Research analysis completed successfully.", styles['Normal']))
            story.append(Spacer(1, 20))
        
        # Add detailed summary section if we have paper data
        if is_paper_list and data:
            story.append(Paragraph("Detailed Research Summary", heading_style))
            story.append(Paragraph(f"This analysis examined {len(data)} research papers related to the topic.", styles['Normal']))
            story.append(Spacer(1, 12))
            
            # Add paper titles and brief descriptions
            for i, paper in enumerate(data[:10], 1):  # Limit to first 10 papers
                title = paper.get('title', '[No Title]')
                year = paper.get('year', 'Unknown Year')
                story.append(Paragraph(f"{i}. {title} ({year})", styles['Normal']))
                story.append(Spacer(1, 6))
            
            if len(data) > 10:
                story.append(Paragraph(f"... and {len(data) - 10} more papers", styles['Normal']))
            story.append(Spacer(1, 20))
        
        # Research Gaps Section
        if processed_data.get('gaps'):
            story.append(Paragraph("Research Gaps & Opportunities", heading_style))
            gaps_text = processed_data['gaps']
            # Clean up the gaps text
            gaps_text = re.sub(r'\*\*(.*?)\*\*', r'\1', gaps_text)  # Remove markdown bold
            gaps_blocks = gaps_text.split('---') if '---' in gaps_text else gaps_text.split('\n\n')
            
            for i, block in enumerate(gaps_blocks, 1):
                if block.strip():
                    lines = block.split('Description:')
                    if len(lines) > 1:
                        title = lines[0].replace('TITLE:', '').strip()
                        desc = lines[1].strip()
                        story.append(Paragraph(f"<b>Gap {i}: {title}</b>", styles['Normal']))
                        story.append(Paragraph(desc, styles['Normal']))
                        story.append(Spacer(1, 12))
            story.append(Spacer(1, 20))
        else:
            # Fallback for gaps section
            story.append(Paragraph("Research Gaps & Opportunities", heading_style))
            story.append(Paragraph("Research gaps analysis completed.", styles['Normal']))
            story.append(Spacer(1, 20))
        
        # Sources Section
        if processed_data.get('sources'):
            story.append(Paragraph("References & Sources", heading_style))
            sources_text = processed_data['sources']
            sources_lines = [line.strip() for line in sources_text.splitlines() if line.strip()]
            
            for i, source in enumerate(sources_lines, 1):
                # Try to extract a URL from the source line
                match = re.search(r'(https?://[^\s]+)', source)
                url = match.group(1) if match else None
                # Try to extract a title (before the URL)
                if url:
                    title = source.split(url)[0].strip(" .:-") or url
                    # Add clickable link if possible
                    story.append(Paragraph(f'{i}. <b>{title}</b><br/><a href="{url}">{url}</a>', styles['Normal']))
                else:
                    # If no URL, just print the source line
                    story.append(Paragraph(f"{i}. {source}", styles['Normal']))
                story.append(Spacer(1, 6))
            story.append(Spacer(1, 20))
        else:
            # Fallback for sources section
            story.append(Paragraph("References & Sources", heading_style))
            story.append(Paragraph("References and sources analysis completed.", styles['Normal']))
            story.append(Spacer(1, 20))
        
        # Add original content info based on data type
        if is_pdf_upload:
            story.append(Paragraph("Original Document Information", heading_style))
            story.append(Paragraph(f"Document: {data.get('filename', 'Unknown')}", styles['Normal']))
            story.append(Paragraph(f"Analysis Type: PDF Content Analysis", styles['Normal']))
            story.append(Spacer(1, 20))
        elif is_paper_list:
            story.append(Paragraph("Research Papers Information", heading_style))
            story.append(Paragraph(f"Number of Total Papers Found: {len(data)}", styles['Normal']))
            story.append(Paragraph(f"Analysis Type: Research Paper Analysis", styles['Normal']))
            story.append(Spacer(1, 20))
        
        # Footer with dexteritycoder branding
        story.append(PageBreak())
        story.append(Spacer(1, 50))
        story.append(Paragraph("Dexteritycoder", brand_style))
        story.append(Paragraph("ThesisMate - AI based Researcher", brand_style))
        
        # Build PDF
        doc.build(story)
        
        # Verify the file was created
        if not os.path.exists(filepath):
            return None, f"PDF file was not created at {filepath}"
        
        return filepath, filename
        
    except Exception as e:
        return None, f"Error generating PDF: {str(e)}"

@app.route("/")
def index():
    return render_template("index.html")


# ────────── PDF EXPORT ENDPOINT ──────────
@app.post("/api/export-pdf")
def export_pdf():
    try:
        cache_id = request.form.get("cache_id")
        title = request.form.get("title", "Research Analysis Report")
        
        if not cache_id:
            return "<p class='text-red-400'>No cache ID provided.</p>"
        
        if cache_id not in CACHE:
            return "<p class='text-red-400'>No analysis data found to export. Please run an analysis first.</p>"
        
        try:
            filepath, filename = generate_pdf_report(cache_id, title)
            
            if filepath and os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                return send_file(
                    abs_filepath,
                    as_attachment=True,
                    download_name=filename,
                    mimetype='application/pdf'
                )
            else:
                return f"<p class='text-red-400'>Error generating PDF: {filename}</p>"
        except Exception as e:
            return f"<p class='text-red-400'>Error in PDF generation: {str(e)}</p>"
    except Exception as e:
        return f"<p class='text-red-400'>Unexpected error during PDF export: {str(e)}</p>"


# ────────── PDF EXPORT WITH CUSTOM FILENAME ENDPOINT ──────────
@app.post("/api/export-pdf-custom")
def export_pdf_custom():
    try:
        cache_id = request.form.get("cache_id")
        title = request.form.get("title", "Research Analysis Report")
        custom_filename = request.form.get("custom_filename", "").strip()
        
        if not cache_id:
            return "<p class='text-red-400'>No cache ID provided.</p>"
        
        if cache_id not in CACHE:
            return "<p class='text-red-400'>No analysis data found to export. Please run an analysis first.</p>"
        
        # Use custom filename if provided, otherwise use default
        if custom_filename:
            if not custom_filename.endswith('.pdf'):
                custom_filename += '.pdf'
            filename = custom_filename
        else:
            filename = f"research_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        try:
            filepath, _ = generate_pdf_report(cache_id, title, filename)
            
            if filepath and os.path.exists(filepath):
                try:
                    # Use absolute path for send_file
                    abs_filepath = os.path.abspath(filepath)
                    
                    # Verify file exists and has content
                    if os.path.getsize(abs_filepath) > 0:
                        return send_file(
                            abs_filepath,
                            as_attachment=True,
                            download_name=filename,
                            mimetype='application/pdf'
                        )
                    else:
                        return f"<p class='text-red-400'>Generated PDF file is empty</p>"
                except Exception as e:
                    return f"<p class='text-red-400'>Error downloading PDF: {str(e)}</p>"
            else:
                return f"<p class='text-red-400'>Error generating PDF: {filename}</p>"
        except Exception as e:
            return f"<p class='text-red-400'>Error in PDF generation: {str(e)}</p>"
    except Exception as e:
        return f"<p class='text-red-400'>Unexpected error during PDF export: {str(e)}</p>"


# ────────── PDF UPLOAD ENDPOINT ──────────
@app.post("/api/upload-pdf")
def upload_pdf():
    if 'pdf_file' not in request.files:
        return "<p class='text-red-400'>No file selected</p>"
    
    file = request.files['pdf_file']
    if file.filename == '':
        return "<p class='text-red-400'>No file selected</p>"
    
    if file and allowed_file(file.filename):
        try:
            # Extract text from PDF
            pdf_text = extract_text_from_pdf(file)
            
            if pdf_text.startswith("Error"):
                return f"<p class='text-red-400'>{pdf_text}</p>"
            
            # Store in cache
            cache_id = str(uuid4())
            CACHE[cache_id] = {
                'type': 'pdf',
                'filename': file.filename,
                'text': pdf_text,
                'title': file.filename.replace('.pdf', '').replace('_', ' ').title()
            }
            
            # Generate summary, gaps, and sources from PDF
            return process_pdf_content(cache_id, pdf_text, file.filename)
            
        except Exception as e:
            return f"<p class='text-red-400'>Error processing PDF: {str(e)}</p>"
    
    return "<p class='text-red-400'>Invalid file type. Please upload a PDF file.</p>"

def process_pdf_content(cache_id, pdf_text, filename):
    """Process PDF content and generate summary, gaps, and sources"""
    try:
        # Limit text length for API calls
        limited_text = pdf_text[:8000] if len(pdf_text) > 8000 else pdf_text
        
        # Generate summary
        summary_prompt = f"Provide a comprehensive summary of this research paper:\n\n{limited_text}"
        summary = call_gemini(summary_prompt, max_tokens=400, temperature=0.3)
        
        # Generate research gaps
        gaps_prompt = f"""Identify concrete research gaps from this paper with **TITLE**: then description

Paper content:
{limited_text}"""
        gaps_raw = call_gemini(gaps_prompt, max_tokens=400, temperature=0.4)
        
        # Generate sources/references (extract from text)
        sources_prompt = f"Extract and list the main references or sources mentioned in this paper:\n\n{limited_text}"
        sources_text = call_gemini(sources_prompt, max_tokens=300, temperature=0.3)
        
        # Format the response
        summary_html = "<div class='space-y-4'>" + "".join(
            f"<p>{s.strip()}</p>" for s in summary.splitlines() if s.strip()
        ) + "</div>"
        
        # Format gaps
        gaps_raw = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", gaps_raw)
        gaps_blocks = gaps_raw.strip().split("---") if "---" in gaps_raw else gaps_raw.strip().split("\n\n")
        
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
        
        # Format sources
        sources_lines = [line.strip() for line in sources_text.splitlines() if line.strip()]
        sources_html = "<div class='space-y-3'>"
        for line in sources_lines:
            if line and not line.startswith("Source") and not line.startswith("Reference"):
                sources_html += f"""
                <div class="bg-gray-800 p-3 rounded border border-gray-700">
                    <p class="text-blue-400 font-semibold">{line}</p>
                    <small class="text-gray-400">From uploaded PDF</small>
                </div>
                """
        sources_html += "</div>"
        
        # Store processed data in cache
        CACHE[cache_id + "_processed"] = {
            'summary': summary,
            'gaps': gaps_raw,
            'sources': sources_text
        }
        
        return render_template_string(f"""
            <!-- Summary (center) -->
            <div id="main-pane" class='prose prose-invert max-w-none flex-1 min-w-0'>
                                 <div class="flex justify-between items-center mb-4">
                     <h2 class="text-xl font-semibold">PDF Analysis: {filename.replace('.pdf', '').replace('_', ' ').title()}</h2>
                     <form hx-post="/api/export-pdf-custom" hx-target="#export-status" class="inline">
                         <input type="hidden" name="cache_id" value="{cache_id}">
                         <input type="hidden" name="title" value="PDF Analysis: {filename.replace('.pdf', '').replace('_', ' ').title()}">
                         <div class="flex items-center space-x-2">
                             <div class="flex flex-col">
                                 <input type="text" name="custom_filename" placeholder="Enter filename (optional)" 
                                        class="px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-white placeholder-gray-400"
                                        style="width: 200px;">
                                 <small class="text-gray-400 text-xs mt-1">File will download to your browser's default location</small>
                             </div>
                             <button type="submit" class="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded text-white text-sm flex items-center">
                                 <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                     <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                                 </svg>
                                 Export PDF
                             </button>
                         </div>
                     </form>
                 </div>
                <div id="export-status"></div>
                {summary_html}
            </div>

            <!-- Sources (left) -->
            <div hx-swap-oob="true" id="sources-pane" class="w-64 shrink-0 overflow-y-auto custom-scroll">
                <h2 class="text-lg font-semibold mb-4">Sources & References</h2>
                {sources_html}
            </div>

            <!-- Gaps (right) -->
            <div hx-swap-oob="true" id="gaps-pane" class="w-80 shrink-0 overflow-y-auto custom-scroll">
                <h2 class="text-lg font-semibold mb-4">Research Gaps</h2>
                {gaps_html}
            </div>
        """)
        
    except Exception as e:
        return f"<p class='text-red-400'>Error processing PDF content: {str(e)}</p><p class='text-gray-400 text-sm mt-2'>Please ensure the PDF contains readable text and try again.</p>"


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

    # Get classification counts for the selected papers
    selected_classifications = {p["abstract"] or "": classifications.get(p["abstract"] or "", "unknown") for p in sel}
    counts = Counter(selected_classifications.values())
    
    # Store processed data for PDF export
    CACHE[cache_id + "_processed"] = {
        'summary': summary_text if mode == "combined" else "Individual paper summaries generated",
        'gaps': gaps_raw,
        'sources': f"Found {len(sel)} papers with classifications: {dict(counts)}"
    }

    # --- Final render
    return render_template_string(f"""
        <!-- Summary (center) -->
        <div id="main-pane" class='prose prose-invert max-w-none flex-1 min-w-0'>
                         <div class="flex justify-between items-center mb-4">
                 <h2 class="text-xl font-semibold">Research Analysis Results</h2>
                 <form hx-post="/api/export-pdf-custom" hx-target="#export-status" class="inline">
                     <input type="hidden" name="cache_id" value="{cache_id}">
                     <input type="hidden" name="title" value="Research Analysis Report">
                     <div class="flex items-center space-x-2">
                         <div class="flex flex-col">
                             <input type="text" name="custom_filename" placeholder="Enter filename (optional)" 
                                    class="px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-white placeholder-gray-400"
                                    style="width: 200px;">
                             <small class="text-gray-400 text-xs mt-1">File will download to your browser's default location</small>
                         </div>
                         <button type="submit" class="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded text-white text-sm flex items-center">
                             <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                             </svg>
                             Export PDF
                         </button>
                     </div>
                 </form>
             </div>
            <div id="export-status"></div>
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
