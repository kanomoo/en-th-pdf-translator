"""
PDF Translator Web App — Translate any PDF to Thai with a beautiful web interface.

Usage:
    .venv/bin/python app.py

Then open http://localhost:5000 in your browser.
"""

import concurrent.futures
import json
import os
import re
import statistics
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

# pyrefly: ignore [missing-import]
import fitz
# pyrefly: ignore [missing-import]
import pythainlp
# pyrefly: ignore [missing-import]
from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / "cache"

for d in (UPLOAD_DIR, OUTPUT_DIR, CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB max upload

# ---------------------------------------------------------------------------
# Font discovery (cross-platform)
# ---------------------------------------------------------------------------

def _find_font(candidates):
    """Return the first font path that exists."""
    for path in candidates:
        if Path(path).exists():
            return str(path)
    return None


FONT_REG = _find_font([
    # Linux — Noto Sans Thai
    "/usr/share/fonts/noto/NotoSansThai-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
    "/usr/share/fonts/google-noto/NotoSansThai-Regular.ttf",
    # Linux — Noto Sans Thai Looped
    "/usr/share/fonts/noto/NotoSansThaiLooped-Regular.ttf",
    # Linux — Droid Sans Thai
    "/usr/share/fonts/droid/DroidSansThai.ttf",
    # Windows
    "C:/Windows/Fonts/LeelawUI.ttf",
    # macOS
    "/Library/Fonts/Thonburi.ttf",
])

FONT_BOLD = _find_font([
    "/usr/share/fonts/noto/NotoSansThai-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansThai-Bold.ttf",
    "/usr/share/fonts/google-noto/NotoSansThai-Bold.ttf",
    "/usr/share/fonts/noto/NotoSansThaiLooped-Bold.ttf",
    "C:/Windows/Fonts/LeelaUIb.ttf",
    "/Library/Fonts/Thonburi Bold.ttf",
])

if not FONT_REG:
    print("⚠️  WARNING: No Thai font found. Install noto-fonts-extra or similar.")

# ---------------------------------------------------------------------------
# Bullet substitutions & helpers
# ---------------------------------------------------------------------------

BULLETS = {
    "\uf0a7": "▪",
    "\uf0b7": "•",
    "\uf0d8": "◦",
    "\uf0fc": "✓",
    "\uf061": "▪",
    "\uf062": "•",
    "²": "•",
    "§": "▪",
}


def clean_text(text):
    for src, dst in BULLETS.items():
        text = text.replace(src, dst)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Language detection & text sanitization
# ---------------------------------------------------------------------------

def is_thai_char(ch):
    """Check if a character is in the Thai Unicode block (U+0E00–U+0E7F)."""
    return '\u0E00' <= ch <= '\u0E7F'


def is_mostly_thai(text, threshold=0.4):
    """Return True if >= threshold of alphabetic characters are Thai.

    A threshold of 0.4 catches blocks like
    'Computer Network and Internet | เครือข่ายคอมพิวเตอร์'
    which are already bilingual and should NOT be re-translated.
    """
    alpha_chars = [ch for ch in text if ch.isalpha()]
    if not alpha_chars:
        return False
    thai_count = sum(1 for ch in alpha_chars if is_thai_char(ch))
    return thai_count / len(alpha_chars) >= threshold


def sanitize_text(text):
    """Remove/replace characters that NotoSansThai cannot render.

    This prevents null-byte (\x00) artefacts in the output PDF.
    """
    # Remove null bytes and most control characters (keep \n, \t)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Remove zero-width / invisible Unicode characters
    text = text.replace('\u200b', '')   # zero-width space
    text = text.replace('\u200c', '')   # zero-width non-joiner
    text = text.replace('\u200d', '')   # zero-width joiner
    text = text.replace('\ufeff', '')   # BOM
    # Replace common PUA / symbol chars that break rendering
    for src, dst in BULLETS.items():
        text = text.replace(src, dst)
    text = text.replace('□', '•').replace('▪', '•')
    return text


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_items(doc, parsing_mode="auto"):
    import statistics
    import re
    
    # Determine gap threshold based on parsing mode
    # Default auto: 1.5
    # Dense: 0.5 (for tables)
    # Continuous: 1.8 (for justified text)
    if parsing_mode == "dense":
        gap_threshold_multiplier = 0.5
    elif parsing_mode == "continuous":
        gap_threshold_multiplier = 1.8
    else:
        gap_threshold_multiplier = 1.5
        
    items = []
    for page_number, page in enumerate(doc):
        page_dict = page.get_text("dict")
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
                
            # 1. Flatten all spans in the block
            all_spans = []
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        all_spans.append(span)
                        
            if not all_spans:
                continue

            # 2. Group spans into physical rows based on y-coordinate centers
            rows = []
            for span in all_spans:
                py0, py1 = span["bbox"][1], span["bbox"][3]
                py_center = (py0 + py1) / 2
                placed = False
                for row in rows:
                    ry0, ry1 = row["core_bbox"][1], row["core_bbox"][3]
                    ry_center = (ry0 + ry1) / 2
                    
                    min_height = min(py1 - py0, ry1 - ry0)
                    # They belong to the same row if their vertical centers are close
                    if abs(py_center - ry_center) < min_height * 0.4:
                        row["spans"].append(span)
                        row["bbox"] = [
                            min(row["bbox"][0], span["bbox"][0]),
                            min(row["bbox"][1], py0),
                            max(row["bbox"][2], span["bbox"][2]),
                            max(row["bbox"][3], py1)
                        ]
                        placed = True
                        break
                if not placed:
                    rows.append({
                        "spans": [span],
                        "bbox": span["bbox"],
                        "core_bbox": span["bbox"]
                    })
                    
            # 3. Sort spans within each row from left to right, and group into phrases
            is_table = False
            row_phrases = []
            
            # 3.1 Pre-calculate column boundaries for robust table detection
            column_x0s = []
            for row in rows:
                sorted_spans = sorted(row["spans"], key=lambda s: s["bbox"][0])
                for i, span in enumerate(sorted_spans):
                    gap = 9999
                    if i > 0:
                        prev_span = sorted_spans[i-1]
                        estimated_width = len(prev_span.get("text", "").strip()) * prev_span.get("size", 12) * 0.8
                        real_x1 = min(prev_span["bbox"][2], prev_span["bbox"][0] + estimated_width)
                        gap = span["bbox"][0] - real_x1
                        
                    # Ignore spans that have a normal word space gap (0 to 1.2 ems)
                    if gap < 0 or gap > span.get("size", 12) * 1.2 or gap == 9999:
                        column_x0s.append({
                            "x0": span["bbox"][0],
                            "gap": gap,
                            "size": span.get("size", 12)
                        })
                    
            clusters = []
            for item in sorted(column_x0s, key=lambda x: x["x0"]):
                if not clusters:
                    clusters.append([item])
                elif item["x0"] - clusters[-1][-1]["x0"] < 3.0:
                    clusters[-1].append(item)
                else:
                    clusters.append([item])
            
            column_boundaries = []
            for c in clusters:
                if len(c) >= 2:
                    is_valid = len(c) >= 3 or any(item["gap"] > item["size"] * 1.5 or item["gap"] == 9999 for item in c)
                    if is_valid:
                        column_boundaries.append(sum(item["x0"] for item in c) / len(c))
            
            for row in rows:
                sorted_spans = sorted(row["spans"], key=lambda s: s["bbox"][0])
                phrases = []
                current_spans = []
                for span in sorted_spans:
                    if not current_spans:
                        current_spans.append(span)
                        continue
                    
                    last_span = current_spans[-1]
                    
                    # Fix artificially wide bounding boxes
                    last_text = "".join(s["text"] for s in current_spans).strip()
                    estimated_width = len(last_text) * span.get("size", 12) * 0.8
                    real_x1 = min(last_span["bbox"][2], current_spans[0]["bbox"][0] + estimated_width)
                    
                    gap = span["bbox"][0] - real_x1
                    
                    # Force split if the new span perfectly aligns with a known column boundary
                    # (and the current phrase isn't already part of that same column)
                    is_col_boundary = False
                    for b in column_boundaries:
                        if abs(span["bbox"][0] - b) < 5.0:
                            if abs(current_spans[0]["bbox"][0] - b) > 5.0:
                                is_col_boundary = True
                            break
                            
                    if is_col_boundary or gap > (span.get("size", 12) * gap_threshold_multiplier):
                        prev_text = "".join(s["text"] for s in current_spans).strip()
                        if bool(re.match(r'^(\d+[\.\)]|[•\-\*>])$', prev_text)):
                            # Treat bullet point as part of the same phrase
                            current_spans.append(span)
                        else:
                            phrases.append(current_spans)
                            is_table = True
                            current_spans = [span]
                    else:
                        current_spans.append(span)
                if current_spans:
                    phrases.append(current_spans)
                row_phrases.append(phrases)

            # 4. Create chunks based on is_table heuristic
            chunks = []
            if is_table:
                # Keep each phrase as its own chunk
                for phrases in row_phrases:
                    for i, phrase_spans in enumerate(phrases):
                        px0 = min(s["bbox"][0] for s in phrase_spans)
                        py0 = min(s["bbox"][1] for s in phrase_spans)
                        px1 = max(s["bbox"][2] for s in phrase_spans)
                        py1 = max(s["bbox"][3] for s in phrase_spans)
                        
                        # Expand y0 and y1
                        h = py1 - py0
                        py0 = max(0, py0 - h * 0.3)
                        py1 = min(page.rect.height, py1 + h * 0.3)
                        
                        # Expand x1
                        if i < len(phrases) - 1:
                            next_px0 = min(s["bbox"][0] for s in phrases[i+1])
                            expanded_x1 = max(px1, next_px0 - 5)
                        else:
                            expanded_x1 = max(px1, page.rect.width - 20)
                            
                        chunks.append({
                            "phrases": [phrase_spans],
                            "bbox": [px0, py0, expanded_x1, py1]
                        })
            else:
                # Merge all rows into a single paragraph chunk
                all_phrases = [phrase for phrases in row_phrases for phrase in phrases]
                px0 = min(s["bbox"][0] for p in all_phrases for s in p)
                py0 = min(s["bbox"][1] for p in all_phrases for s in p)
                px1 = max(s["bbox"][2] for p in all_phrases for s in p)
                py1 = max(s["bbox"][3] for p in all_phrases for s in p)
                
                h = py1 - py0
                py0 = max(0, py0 - h * 0.1)
                py1 = min(page.rect.height, py1 + h * 0.1)
                
                chunks.append({
                    "phrases": all_phrases,
                    "bbox": [px0, py0, px1, py1]
                })
                    
            # 3. Create items from chunks
            for chunk in chunks:
                lines_text = []
                all_spans = []
                for phrase in chunk["phrases"]:
                    parts = []
                    for s in phrase:
                        parts.append(s["text"].strip())
                        all_spans.append(s)
                    line_str = " ".join(parts).strip()
                    if not line_str:
                        continue
                        
                    if not lines_text:
                        lines_text.append(line_str)
                    else:
                        first_word = line_str.split()[0]
                        if bool(re.match(r'^(\d+[\.\)]|[•\-\*>])$', first_word)):
                            lines_text.append(line_str)
                        else:
                            lines_text[-1] += " " + line_str
                        
                text = clean_text("\n".join(lines_text))
                if not text:
                    continue
                    
                sizes = [s.get("size", 12) for s in all_spans]
                size = float(statistics.median(sizes)) if sizes else 12.0
                color = all_spans[0].get("color", 0) if all_spans else 0
                bold = any("bold" in s.get("font", "").lower() for s in all_spans) or any(s.get("flags", 0) & 16 for s in all_spans)
                
                items.append({
                    "page": page_number,
                    "bbox": chunk["bbox"],
                    "text": text,
                    "size": size,
                    "color": color,
                    "bold": bold,
                })
    return items


# ---------------------------------------------------------------------------
# Translation engine (Google Translate, free tier)
# ---------------------------------------------------------------------------

def translate_payload(payload):
    url = (
        "https://translate.googleapis.com/translate_a/single"
        "?client=gtx&sl=auto&tl=th&dt=t&q="
        + urllib.parse.quote(payload)
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return clean_text("".join(part[0] for part in data[0] if part and part[0]))


def translate_batch(batch):
    marker_prefix = "ZXQ"
    payload_parts, markers = [], []
    for index, text in batch:
        marker = f"@@{marker_prefix}{index:04d}@@"
        markers.append((marker, index, text))
        payload_parts.append(marker)
        payload_parts.append(text)
    payload_parts.append(f"@@{marker_prefix}END@@")
    translated = translate_payload("\n".join(payload_parts))

    result = {}
    for pos, (marker, index, original) in enumerate(markers):
        next_marker = markers[pos + 1][0] if pos + 1 < len(markers) else f"@@{marker_prefix}END@@"
        pattern = re.escape(marker) + r"\s*(.*?)\s*" + re.escape(next_marker)
        match = re.search(pattern, translated, flags=re.S)
        if not match:
            raise RuntimeError(f"Cannot parse translated batch near {marker}")
        value = clean_text(match.group(1))
        result[original] = value
    return result


# ---------------------------------------------------------------------------
# PDF rendering helpers
# ---------------------------------------------------------------------------

def rgb_from_int(color):
    return ((color >> 16 & 255) / 255, (color >> 8 & 255) / 255, (color & 255) / 255)


def sample_background(page, rect, pix):
    width, height = pix.width, pix.height
    x0, y0, x1, y1 = [int(round(v)) for v in rect]
    pad, step, samples = 5, 6, []
    for x in range(max(0, x0 - pad), min(width, x1 + pad), step):
        for y in (max(0, y0 - pad), min(height - 1, y1 + pad)):
            samples.append(pix.pixel(x, y)[:3])
    for y in range(max(0, y0 - pad), min(height, y1 + pad), step):
        for x in (max(0, x0 - pad), min(width - 1, x1 + pad)):
            samples.append(pix.pixel(x, y)[:3])
    if not samples:
        return (1, 1, 1)
    return tuple(statistics.median(ch) / 255 for ch in zip(*samples))


def expanded_rect(rect, page_rect, amount=1.4):
    output = fitz.Rect(rect)
    output.x0 = max(page_rect.x0, output.x0 - amount)
    output.y0 = max(page_rect.y0, output.y0 - amount)
    output.x1 = min(page_rect.x1, output.x1 + amount)
    output.y1 = min(page_rect.y1, output.y1 + amount)
    return output


# ---------------------------------------------------------------------------
# Job state
# ---------------------------------------------------------------------------
jobs = {}  # job_id -> { status, progress, events, ... }
jobs_lock = threading.Lock()


def emit(job_id, event_type, data):
    """Push an SSE event into the job's event queue."""
    with jobs_lock:
        job = jobs.get(job_id)
        if job:
            job["events"].append({"event": event_type, "data": data})


# ---------------------------------------------------------------------------
# Translation pipeline (runs in background thread)
# ---------------------------------------------------------------------------

def run_translation(job_id, src_path, parsing_mode="auto"):
    """Full translation pipeline with progress events."""
    try:
        emit(job_id, "stage", {"stage": "extracting", "message": "กำลังอ่านไฟล์ PDF..."})

        doc = fitz.open(str(src_path))
        total_pages = len(doc)
        emit(job_id, "info", {"pages": total_pages, "filename": src_path.name})

        # Extract text blocks
        items = extract_items(doc, parsing_mode)
        emit(job_id, "stage", {"stage": "translating", "message": f"พบ {len(items)} ข้อความ กำลังแปล..."})

        # Load/build cache
        cache_path = CACHE_DIR / f"{job_id}_cache.json"
        cache = {}

        # Find unique texts to translate — skip already-Thai text
        unique, seen = [], set()
        thai_skipped = 0
        for item in items:
            text = item["text"]
            if is_mostly_thai(text):
                cache[text] = text  # Keep original Thai unchanged
                thai_skipped += 1
            elif text not in cache and text not in seen:
                seen.add(text)
                unique.append(text)

        if thai_skipped:
            emit(job_id, "info", {"thai_skipped": thai_skipped})

        # Build batches
        batches, current, current_chars = [], [], 0
        for idx, text in enumerate(unique):
            text_len = len(text)
            if current and (len(current) >= 24 or current_chars + text_len > 3500):
                batches.append(current)
                current, current_chars = [], 0
            current.append((idx, text))
            current_chars += text_len
        if current:
            batches.append(current)

        total_batches = len(batches)
        emit(job_id, "progress", {
            "step": "translate",
            "current": 0,
            "total": total_batches,
            "percent": 0,
        })

        # Translate in parallel
        if batches:
            completed = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_batch = {
                    executor.submit(translate_batch, batch): batch
                    for batch in batches
                }
                for future in concurrent.futures.as_completed(future_to_batch):
                    batch = future_to_batch[future]
                    try:
                        cache.update(future.result())
                    except Exception:
                        for entry in batch:
                            try:
                                cache.update(translate_batch([entry]))
                            except Exception as e:
                                # Skip untranslatable items
                                _, _, orig_text = entry if len(entry) == 3 else (None, None, entry[1])
                                cache[orig_text] = orig_text
                    completed += 1
                    pct = int(completed / total_batches * 100)
                    emit(job_id, "progress", {
                        "step": "translate",
                        "current": completed,
                        "total": total_batches,
                        "percent": pct,
                    })
                    time.sleep(0.05)

            # Save cache
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

        # Build PDF
        emit(job_id, "stage", {"stage": "building", "message": "กำลังสร้าง PDF ภาษาไทย..."})

        # Remove original text
        by_page = {}
        for item in items:
            by_page.setdefault(item["page"], []).append(item)

        for page_number, page_items in by_page.items():
            page = doc[page_number]
            pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
            for item in page_items:
                rect = fitz.Rect(item["bbox"])
                rect.x0 -= 1.0
                rect.y0 -= 1.0
                rect.x1 += 1.0
                rect.y1 += 1.0
                page.add_redact_annot(rect, fill=None)
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            pct = int((page_number + 1) / total_pages * 40)
            emit(job_id, "progress", {
                "step": "build_redact",
                "current": page_number + 1,
                "total": total_pages,
                "percent": pct,
            })

        # Insert Thai text
        shrunk, clipped = 0, 0
        for index, item in enumerate(items, 1):
            page = doc[item["page"]]
            original_size = item["size"]
            size = original_size * 0.9  # Use 90% of original size to fit Thai better
            rect = fitz.Rect(item["bbox"])
            
            # Clamp rectangle to page boundaries to avoid rendering off-page
            rect.x0 = max(page.rect.x0, rect.x0 - 0.5)
            rect.y0 = max(page.rect.y0, rect.y0 - 0.5)
            rect.x1 = min(page.rect.x1, rect.x1 + 1.0)
            rect.y1 = min(page.rect.y1, rect.y1 + 1.0)
            
            # Allow HTML text box to expand vertically slightly so it doesn't shrink the font too much
            text_rect = fitz.Rect(rect)
            text_rect.y1 += (text_rect.y1 - text_rect.y0) * 0.2

            raw_translated = sanitize_text(cache.get(item["text"], item["text"]))
            # Keep the spaces from Google Translate instead of stripping and using zero-width spaces.
            translated = raw_translated

            min_scale = 0.40

            color_hex = f"#{item['color']:06x}"
            font_weight = "bold" if item["bold"] else "normal"
            html_text = translated.replace('\n', '<br>')
            
            # Dynamic line-height calculation
            num_lines = html_text.count('<br>') + 1
            box_height = text_rect.y1 - text_rect.y0
            calculated_lineheight = (box_height / num_lines) / size if size > 0 else 1.05
            lineheight = max(1.0, min(calculated_lineheight, 1.5))

            html = f"""<div style="font-family: sans-serif; font-size: {size}pt; font-weight: {font_weight}; color: {color_hex}; line-height: {lineheight}; text-align: left; margin: 0; margin-top: -0.2em;">{html_text}</div>"""
            
            spare_height, scale = page.insert_htmlbox(
                text_rect, html,
                scale_low=min_scale
            )

            if scale < 1.0:
                shrunk += 1
            if spare_height < 0:
                clipped += 1

            if index % 50 == 0 or index == len(items):
                pct = 40 + int(index / len(items) * 60)
                emit(job_id, "progress", {
                    "step": "build_insert",
                    "current": index,
                    "total": len(items),
                    "percent": pct,
                })

        # Save output
        out_path = OUTPUT_DIR / f"{job_id}.pdf"
        doc.save(str(out_path), garbage=4, deflate=True)
        doc.close()

        with jobs_lock:
            jobs[job_id]["status"] = "complete"
            jobs[job_id]["output"] = str(out_path)
            jobs[job_id]["total_pages"] = total_pages

        emit(job_id, "complete", {
            "message": "แปลเสร็จสมบูรณ์! 🎉",
            "filename": src_path.stem + "_TH.pdf",
            "pages": total_pages,
            "shrunk": shrunk,
            "clipped": clipped,
        })

    except Exception as e:
        with jobs_lock:
            jobs[job_id]["status"] = "error"
        emit(job_id, "error", {"message": str(e)})


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "ไม่พบไฟล์"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "กรุณาอัปโหลดไฟล์ PDF เท่านั้น"}), 400

    job_id = uuid.uuid4().hex[:12]
    safe_name = re.sub(r'[^\w\-.]', '_', file.filename)
    src_path = UPLOAD_DIR / f"{job_id}_{safe_name}"
    file.save(str(src_path))
    
    parsing_mode = request.form.get("parsing_mode", "auto")

    # Get page count
    try:
        doc = fitz.open(str(src_path))
        page_count = len(doc)
        doc.close()
    except Exception as e:
        return jsonify({"error": f"ไม่สามารถเปิดไฟล์ PDF: {e}"}), 400

    with jobs_lock:
        jobs[job_id] = {
            "status": "processing",
            "progress": 0,
            "events": [],
            "source": str(src_path),
            "filename": file.filename,
            "pages": page_count,
        }

    # Start background translation
    thread = threading.Thread(target=run_translation, args=(job_id, src_path, parsing_mode), daemon=True)
    thread.start()

    return jsonify({
        "job_id": job_id,
        "filename": file.filename,
        "pages": page_count,
    })


@app.route("/progress/<job_id>")
def progress(job_id):
    """Server-Sent Events endpoint for real-time progress."""
    def generate():
        last_index = 0
        while True:
            with jobs_lock:
                job = jobs.get(job_id)
                if not job:
                    yield f"event: error\ndata: {json.dumps({'message': 'Job not found'})}\n\n"
                    return

                events = job["events"][last_index:]
                last_index = len(job["events"])
                status = job["status"]

            for ev in events:
                yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"

            if status in ("complete", "error"):
                return

            time.sleep(0.3)

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.route("/download/<job_id>/<filename>")
def download(job_id, filename):
    with jobs_lock:
        job = jobs.get(job_id)
        
    out_path = OUTPUT_DIR / f"{job_id}.pdf"
    if not job or job.get("status") != "complete":
        if not out_path.exists():
            return jsonify({"error": "ไฟล์ยังไม่พร้อม หรือไม่พบไฟล์"}), 404

    return send_file(
        str(out_path),
        as_attachment=False,
        download_name=filename,
        mimetype="application/pdf",
    )


@app.route("/download_original/<job_id>")
def download_original(job_id):
    """Serve the original PDF file."""
    matching_uploads = list(UPLOAD_DIR.glob(f"{job_id}_*"))
    if not matching_uploads:
        return jsonify({"error": "ไม่พบไฟล์ต้นฉบับ"}), 404
        
    orig_path = matching_uploads[0]
    return send_file(
        str(orig_path),
        as_attachment=False,
        download_name=orig_path.name,
        mimetype="application/pdf",
    )


@app.route("/preview/<job_id>/<int:page>")
def preview(job_id, page):
    """Render a page of the translated PDF as a PNG image."""
    with jobs_lock:
        job = jobs.get(job_id)
        
    out_path = OUTPUT_DIR / f"{job_id}.pdf"
    if not job or job.get("status") != "complete":
        if not out_path.exists():
            return jsonify({"error": "ยังไม่เสร็จ หรือไม่พบไฟล์"}), 404

    doc = fitz.open(str(out_path))
    if page < 0 or page >= len(doc):
        doc.close()
        return jsonify({"error": "หน้าไม่ถูกต้อง"}), 404

    pix = doc[page].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
    img_bytes = pix.tobytes("png")
    doc.close()

    return Response(img_bytes, mimetype="image/png", headers={
        "Cache-Control": "public, max-age=3600",
    })


@app.route("/preview_original/<job_id>/<int:page>")
def preview_original(job_id, page):
    """Render a page of the original PDF as a PNG image."""
    # Find original file in UPLOAD_DIR
    matching_uploads = list(UPLOAD_DIR.glob(f"{job_id}_*"))
    if not matching_uploads:
        return jsonify({"error": "ไม่พบไฟล์ต้นฉบับ"}), 404
        
    orig_path = matching_uploads[0]

    try:
        doc = fitz.open(str(orig_path))
        if page < 0 or page >= len(doc):
            doc.close()
            return jsonify({"error": "หน้าไม่ถูกต้อง"}), 404

        pix = doc[page].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        img_bytes = pix.tobytes("png")
        doc.close()

        return Response(img_bytes, mimetype="image/png", headers={
            "Cache-Control": "public, max-age=3600",
        })
    except Exception as e:
        return jsonify({"error": f"Error: {str(e)}"}), 500

@app.route("/history")
def get_history():
    history_list = []
    # Find all {job_id}.pdf in OUTPUT_DIR
    for out_file in OUTPUT_DIR.glob("*.pdf"):
        job_id = out_file.stem
        # Find corresponding original file in UPLOAD_DIR
        matching_uploads = list(UPLOAD_DIR.glob(f"{job_id}_*"))
        
        if matching_uploads:
            orig_path = matching_uploads[0]
            original_name = orig_path.name[len(job_id)+1:]
            
            try:
                doc = fitz.open(str(out_file))
                pages = len(doc)
                doc.close()
            except:
                pages = 0
                
            stat = out_file.stat()
            history_list.append({
                "job_id": job_id,
                "filename": original_name,
                "created_at": stat.st_mtime,
                "size": stat.st_size,
                "pages": pages
            })
            
    # Sort descending by date
    history_list.sort(key=lambda x: x["created_at"], reverse=True)
    return jsonify({"history": history_list})

@app.route("/delete/<job_id>", methods=["DELETE"])
def delete_history(job_id):
    # Security: Ensure job_id is alphanumeric (with underscores/hyphens)
    import re
    if not re.match(r"^[a-zA-Z0-9_-]+$", job_id):
        return jsonify({"error": "รูปแบบรหัสงานไม่ถูกต้อง"}), 400

    deleted_files = 0
    
    # 1. Delete translated file from OUTPUT_DIR
    out_file = OUTPUT_DIR / f"{job_id}.pdf"
    if out_file.exists():
        try:
            out_file.unlink()
            deleted_files += 1
        except Exception:
            pass

    # 2. Delete original file from UPLOAD_DIR
    for upload_file in UPLOAD_DIR.glob(f"{job_id}_*"):
        try:
            upload_file.unlink()
            deleted_files += 1
        except Exception:
            pass

    # 3. Delete cache JSON if it exists
    cache_file = CACHE_DIR / f"{job_id}.json"
    if cache_file.exists():
        try:
            cache_file.unlink()
            deleted_files += 1
        except Exception:
            pass
            
    # Remove from active jobs if somehow still there
    with jobs_lock:
        if job_id in jobs:
            del jobs[job_id]

    if deleted_files == 0:
        return jsonify({"error": "ไม่พบประวัติการแปลดังกล่าว"}), 404
        
    return jsonify({"success": True, "message": "ลบประวัติสำเร็จ"})


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"🌐 PDF Translator running at http://localhost:5000")
    print(f"📁 Thai font (regular): {FONT_REG}")
    print(f"📁 Thai font (bold):    {FONT_BOLD}")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
