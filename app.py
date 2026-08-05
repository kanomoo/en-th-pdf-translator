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

import sqlite3
# pyrefly: ignore [missing-import]
from werkzeug.security import generate_password_hash, check_password_hash

try:
    # pyrefly: ignore [missing-import]
    import psycopg
    # pyrefly: ignore [missing-import]
    from psycopg.rows import dict_row
except ImportError:  # Optional locally; required when DATABASE_URL is configured.
    psycopg = None
    dict_row = None

POSTGRES_INTEGRITY_ERROR = psycopg.IntegrityError if psycopg else type(None)

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
    session,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "pdf-translator-secret-key-2026")

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL and psycopg is None:
    raise RuntimeError("DATABASE_URL is set but psycopg is not installed")

# Render's local filesystem is ephemeral. Set DATA_DIR to a mounted persistent
# disk (Render commonly exposes it as /var/data) so accounts and translations
# survive restarts and deploys.
_storage_root = os.environ.get("DATA_DIR") or os.environ.get("RENDER_DISK_MOUNT_PATH")
DATA_DIR = Path(_storage_root).expanduser() if _storage_root else BASE_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "database.db"

def init_db():
    if DATABASE_URL:
        conn = psycopg.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translation_history (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                project_id BIGINT REFERENCES projects(id) ON DELETE SET NULL,
                job_id TEXT UNIQUE NOT NULL,
                original_filename TEXT NOT NULL,
                file_size BIGINT DEFAULT 0,
                pages INTEGER DEFAULT 0,
                position INTEGER DEFAULT 0,
                original_pdf BYTEA,
                translated_pdf BYTEA,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("ALTER TABLE translation_history ADD COLUMN IF NOT EXISTS project_id BIGINT")
        cursor.execute("ALTER TABLE translation_history ADD COLUMN IF NOT EXISTS position INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE translation_history ADD COLUMN IF NOT EXISTS original_pdf BYTEA")
        cursor.execute("ALTER TABLE translation_history ADD COLUMN IF NOT EXISTS translated_pdf BYTEA")
        cursor.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS position INTEGER DEFAULT 0")
        conn.commit()
        conn.close()
        return

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS translation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            project_id INTEGER,
            job_id TEXT UNIQUE NOT NULL,
            original_filename TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            pages INTEGER DEFAULT 0,
            position INTEGER DEFAULT 0,
            original_pdf BLOB,
            translated_pdf BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            position INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("PRAGMA table_info(translation_history)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if "project_id" not in existing_columns:
        cursor.execute("ALTER TABLE translation_history ADD COLUMN project_id INTEGER")
    if "position" not in existing_columns:
        cursor.execute("ALTER TABLE translation_history ADD COLUMN position INTEGER DEFAULT 0")
    if "original_pdf" not in existing_columns:
        cursor.execute("ALTER TABLE translation_history ADD COLUMN original_pdf BLOB")
    if "translated_pdf" not in existing_columns:
        cursor.execute("ALTER TABLE translation_history ADD COLUMN translated_pdf BLOB")
    
    cursor.execute("PRAGMA table_info(projects)")
    existing_proj_columns = {row[1] for row in cursor.fetchall()}
    if "position" not in existing_proj_columns:
        cursor.execute("ALTER TABLE projects ADD COLUMN position INTEGER DEFAULT 0")
    conn.commit()
    conn.close()

init_db()

def get_db():
    if DATABASE_URL:
        return PostgresConnection(psycopg.connect(DATABASE_URL, row_factory=dict_row))
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


class PostgresCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=()):
        return self._cursor.execute(query.replace("?", "%s"), params)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class PostgresConnection:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return PostgresCursor(self._connection.cursor())

    def __getattr__(self, name):
        return getattr(self._connection, name)


def insert_and_get_id(cursor, query, params):
    if DATABASE_URL:
        cursor.execute(query + " RETURNING id", params)
        return cursor.fetchone()["id"]
    cursor.execute(query, params)
    return cursor.lastrowid


def _request_owner_clause(user_id, column="user_id"):
    if user_id:
        return f"{column} = ?", (user_id,)
    return f"{column} IS NULL", ()


def _get_owned_project(cursor, project_id, user_id):
    owner_clause, owner_params = _request_owner_clause(user_id)
    cursor.execute(
        f"SELECT id, name FROM projects WHERE id = ? AND {owner_clause}",
        (project_id, *owner_params),
    )
    return cursor.fetchone()


def get_or_create_project(cursor, user_id, project_id=None, project_name=None):
    owner_clause, owner_params = _request_owner_clause(user_id)

    if project_id:
        cursor.execute(
            f"SELECT id, name FROM projects WHERE id = ? AND {owner_clause}",
            (project_id, *owner_params),
        )
        row = cursor.fetchone()
        if row:
            return row["id"], row["name"]

    name = (project_name or "").strip()
    if not name:
        name = time.strftime("Uploads %Y-%m-%d %H:%M")

    cursor.execute(
        f"SELECT id, name FROM projects WHERE name = ? AND {owner_clause}",
        (name, *owner_params),
    )
    row = cursor.fetchone()
    if row:
        return row["id"], row["name"]

    return insert_and_get_id(
        cursor,
        "INSERT INTO projects (user_id, name) VALUES (?, ?)",
        (user_id, name),
    ), name


def default_project_name():
    return time.strftime("New Folder %Y-%m-%d %H:%M")

UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "output"
CACHE_DIR = DATA_DIR / "cache"
DOCS_DIR = BASE_DIR / "docs"

SCRIPTS_DIR = BASE_DIR / "scripts"
EXAMPLES_DIR = BASE_DIR / "examples"
DESIGN_DIR = BASE_DIR / "design"

for d in (UPLOAD_DIR, OUTPUT_DIR, CACHE_DIR, DOCS_DIR, SCRIPTS_DIR, EXAMPLES_DIR, DESIGN_DIR):
    d.mkdir(parents=True, exist_ok=True)


def get_pdf_file_path(job_id, is_original=False):
    """Retrieve PDF path from disk, or restore it from DB BLOB if missing."""
    if is_original:
        matching = list(UPLOAD_DIR.glob(f"{job_id}_*"))
        if matching and matching[0].exists():
            return matching[0]
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT original_filename, original_pdf FROM translation_history WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            conn.close()
            if row and row["original_pdf"]:
                orig_name = row["original_filename"] or "document.pdf"
                safe_name = re.sub(r'[^\w\-.]', '_', orig_name)
                target_path = UPLOAD_DIR / f"{job_id}_{safe_name}"
                target_path.parent.mkdir(parents=True, exist_ok=True)
                raw_data = row["original_pdf"]
                pdf_data = bytes(raw_data) if not isinstance(raw_data, bytes) else raw_data
                target_path.write_bytes(pdf_data)
                return target_path
        except Exception as e:
            print(f"Error restoring original PDF from DB: {e}")
        return None
    else:
        out_path = OUTPUT_DIR / f"{job_id}.pdf"
        if out_path.exists():
            return out_path
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT translated_pdf FROM translation_history WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            conn.close()
            if row and row["translated_pdf"]:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                raw_data = row["translated_pdf"]
                pdf_data = bytes(raw_data) if not isinstance(raw_data, bytes) else raw_data
                out_path.write_bytes(pdf_data)
                return out_path
        except Exception as e:
            print(f"Error restoring translated PDF from DB: {e}")
        return None

# Clean up legacy root files if they exist (moved to subdirectories)
for _legacy_file in ["debug.py", "extract.py", "test_extract.py", "translate_pdf.py", "GETTING_STARTED.md", "DEPLOY_TO_GITHUB.md", "organize.py", "organize_cleanup.py"]:
    _p = BASE_DIR / _legacy_file
    if _p.exists():
        try:
            _p.unlink()
        except Exception:
            pass

for _legacy_pdf in ["1_6 - Cover.pdf", "Ch1 Introduction.pdf"]:
    _p = BASE_DIR / _legacy_pdf
    if _p.exists():
        try:
            _p.rename(EXAMPLES_DIR / _legacy_pdf)
        except Exception:
            pass

_old_design_dir = BASE_DIR / "ดีไซน์เว็บแปลภาษา-Translator-PDF"
if _old_design_dir.exists():
    try:
        import shutil
        shutil.rmtree(_old_design_dir, ignore_errors=True)
    except Exception:
        pass

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
    # Linux — Thai TLWG fonts
    "/usr/share/fonts/truetype/tlwg/Waree.ttf",
    "/usr/share/fonts/truetype/tlwg/Loma.ttf",
    "/usr/share/fonts/truetype/tlwg/Garuda.ttf",
    "/usr/share/fonts/truetype/tlwg/Kinnari.ttf",
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
    "/usr/share/fonts/truetype/tlwg/Waree-Bold.ttf",
    "/usr/share/fonts/truetype/tlwg/Loma-Bold.ttf",
    "/usr/share/fonts/truetype/tlwg/Garuda-Bold.ttf",
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
        emit(job_id, "stage", {"stage": "extracting", "message": "Reading PDF..."})

        doc = fitz.open(str(src_path))
        total_pages = len(doc)
        emit(job_id, "info", {"pages": total_pages, "filename": src_path.name})

        # Extract text blocks
        items = extract_items(doc, parsing_mode)
        emit(job_id, "stage", {"stage": "translating", "message": f"Found {len(items)} text blocks. Translating..."})

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
        emit(job_id, "stage", {"stage": "building", "message": "Building Thai PDF..."})

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

        try:
            translated_bytes = out_path.read_bytes()
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE translation_history SET translated_pdf = ? WHERE job_id = ?", (translated_bytes, job_id))
            conn.commit()
            conn.close()
        except Exception as err:
            print(f"Error saving translated PDF BLOB to DB: {err}")

        with jobs_lock:
            jobs[job_id]["status"] = "complete"
            jobs[job_id]["output"] = str(out_path)
            jobs[job_id]["total_pages"] = total_pages

        emit(job_id, "complete", {
            "message": "Translation complete.",
            "filename": src_path.stem + "_TH.pdf",
            "pages": total_pages,
            "shrunk": shrunk,
            "clipped": clipped,
        })

    except Exception as e:
        with jobs_lock:
            jobs[job_id]["status"] = "error"
        emit(job_id, "error", {"message": str(e)})


import base64

def decode_google_id_token(token):
    """Helper to decode Google OAuth JWT credential payload."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        decoded_bytes = base64.urlsafe_b64decode(padded)
        payload = json.loads(decoded_bytes.decode("utf-8"))
        return payload
    except Exception as e:
        print(f"Error decoding Google ID token: {e}")
        return None


# ---------------------------------------------------------------------------
# Auth Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "199187564058-r2jnh8frc0u2o0cp1cte4kc25050g06g.apps.googleusercontent.com")
    return render_template("index.html", google_client_id=google_client_id)



@app.route("/api/google-login", methods=["POST"])
def google_login():
    data = request.get_json() or {}
    token = data.get("credential") or ""

    if not token:
        return jsonify({"error": "Missing Google token"}), 400

    payload = decode_google_id_token(token)
    if not payload:
        return jsonify({"error": "Invalid Google token"}), 400

    email = (payload.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Could not read email from Google account"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()

    if not user:
        # Auto-register Google user
        dummy_hash = generate_password_hash(f"google_oauth_{uuid.uuid4().hex}")
        user_id = insert_and_get_id(
            cursor,
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, dummy_hash),
        )
        conn.commit()
    else:
        user_id = user["id"]

    conn.close()

    session["user_id"] = user_id
    session["email"] = email
    return jsonify({
        "success": True,
        "user": {
            "id": user_id,
            "email": email,
            "name": payload.get("name", ""),
            "picture": payload.get("picture", "")
        }
    })


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or "@" not in email:
        return jsonify({"error": "Enter a valid email"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        password_hash = generate_password_hash(password)
        user_id = insert_and_get_id(
            cursor,
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash),
        )
        conn.commit()
        conn.close()

        session["user_id"] = user_id
        session["email"] = email
        return jsonify({"success": True, "user": {"id": user_id, "email": email}})
    except (sqlite3.IntegrityError, POSTGRES_INTEGRITY_ERROR):
        conn.close()
        return jsonify({"error": "This email is already registered"}), 400
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 400

    session["user_id"] = user["id"]
    session["email"] = user["email"]
    return jsonify({"success": True, "user": {"id": user["id"], "email": user["email"]}})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    session.pop("email", None)
    return jsonify({"success": True})


@app.route("/api/me", methods=["GET"])
def me():
    if "user_id" in session:
        return jsonify({
            "logged_in": True,
            "user": {
                "id": session["user_id"],
                "email": session.get("email", "")
            }
        })
    return jsonify({"logged_in": False})


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file found"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Please upload PDF files only"}), 400

    job_id = uuid.uuid4().hex[:12]
    safe_name = re.sub(r'[^\w\-.]', '_', file.filename)
    src_path = UPLOAD_DIR / f"{job_id}_{safe_name}"
    file.save(str(src_path))
    
    parsing_mode = request.form.get("parsing_mode", "auto")
    project_id = request.form.get("project_id")
    project_name = request.form.get("project_name")
    try:
        project_id = int(project_id) if project_id else None
    except ValueError:
        project_id = None

    # Get page count
    try:
        doc = fitz.open(str(src_path))
        page_count = len(doc)
        doc.close()
    except Exception as e:
        return jsonify({"error": f"Could not open PDF: {e}"}), 400

    # Save translation history to database
    user_id = session.get("user_id")
    project = {"id": None, "name": ""}
    try:
        original_bytes = src_path.read_bytes()
        conn = get_db()
        cursor = conn.cursor()
        resolved_project_id, resolved_project_name = get_or_create_project(
            cursor,
            user_id,
            project_id=project_id,
            project_name=project_name,
        )
        history_params = (user_id, resolved_project_id, job_id, file.filename, src_path.stat().st_size, page_count, original_bytes)
        if DATABASE_URL:
            cursor.execute(
                """
                INSERT INTO translation_history
                    (user_id, project_id, job_id, original_filename, file_size, pages, original_pdf)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (job_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    project_id = EXCLUDED.project_id,
                    original_filename = EXCLUDED.original_filename,
                    file_size = EXCLUDED.file_size,
                    pages = EXCLUDED.pages,
                    original_pdf = EXCLUDED.original_pdf
                """,
                history_params,
            )
        else:
            cursor.execute(
                """
                INSERT OR REPLACE INTO translation_history
                    (user_id, project_id, job_id, original_filename, file_size, pages, original_pdf)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                history_params,
            )
        cursor.execute(
            "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (resolved_project_id,)
        )
        conn.commit()
        conn.close()
        project = {"id": resolved_project_id, "name": resolved_project_name}
    except Exception as e:
        print(f"Error saving history to DB: {e}")

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
        "project": project,
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
    out_path = get_pdf_file_path(job_id, is_original=False)
    if not out_path:
        return jsonify({"error": "File is not ready or was not found"}), 404

    response = send_file(
        str(out_path),
        as_attachment=False,
        download_name=filename,
        mimetype="application/pdf",
        conditional=True,
        max_age=86400,
    )
    response.headers["Cache-Control"] = "private, max-age=86400"
    return response


@app.route("/download_original/<job_id>")
def download_original(job_id):
    """Serve the original PDF file."""
    orig_path = get_pdf_file_path(job_id, is_original=True)
    if not orig_path:
        return jsonify({"error": "Original file not found"}), 404

    response = send_file(
        str(orig_path),
        as_attachment=False,
        download_name=orig_path.name,
        mimetype="application/pdf",
        conditional=True,
        max_age=86400,
    )
    response.headers["Cache-Control"] = "private, max-age=86400"
    return response


@app.route("/preview/<job_id>/<int:page>")
def preview(job_id, page):
    """Render a page of the translated PDF as a PNG image."""
    out_path = get_pdf_file_path(job_id, is_original=False)
    if not out_path:
        return jsonify({"error": "File is not ready or was not found"}), 404

    doc = fitz.open(str(out_path))
    if page < 0 or page >= len(doc):
        doc.close()
        return jsonify({"error": "Invalid page"}), 404

    pix = doc[page].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
    img_bytes = pix.tobytes("png")
    doc.close()

    return Response(img_bytes, mimetype="image/png", headers={
        "Cache-Control": "public, max-age=3600",
    })


@app.route("/preview_original/<job_id>/<int:page>")
def preview_original(job_id, page):
    """Render a page of the original PDF as a PNG image."""
    orig_path = get_pdf_file_path(job_id, is_original=True)
    if not orig_path:
        return jsonify({"error": "Original file not found"}), 404

    try:
        doc = fitz.open(str(orig_path))
        if page < 0 or page >= len(doc):
            doc.close()
            return jsonify({"error": "Invalid page"}), 404

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
    user_id = session.get("user_id")
    history_list = []
    projects_map = {}
    
    conn = get_db()
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute(
            """
            SELECT
                h.id, h.user_id, h.project_id, h.job_id, h.original_filename, h.file_size, h.pages, h.position, h.created_at,
                (CASE WHEN h.translated_pdf IS NOT NULL THEN 1 ELSE 0 END) AS has_db_pdf,
                COALESCE(p.name, 'Unfiled') AS project_name,
                p.created_at AS project_created_at,
                p.updated_at AS project_updated_at,
                COALESCE(p.position, 0) AS project_position
            FROM translation_history h
            LEFT JOIN projects p ON p.id = h.project_id
            WHERE h.user_id = ?
            ORDER BY COALESCE(p.position, 0) ASC, COALESCE(p.updated_at, h.created_at) DESC, COALESCE(h.position, 0) ASC, h.created_at DESC
            """,
            (user_id,),
        )
    else:
        cursor.execute(
            """
            SELECT
                h.id, h.user_id, h.project_id, h.job_id, h.original_filename, h.file_size, h.pages, h.position, h.created_at,
                (CASE WHEN h.translated_pdf IS NOT NULL THEN 1 ELSE 0 END) AS has_db_pdf,
                COALESCE(p.name, 'Unfiled') AS project_name,
                p.created_at AS project_created_at,
                p.updated_at AS project_updated_at,
                COALESCE(p.position, 0) AS project_position
            FROM translation_history h
            LEFT JOIN projects p ON p.id = h.project_id
            WHERE h.user_id IS NULL
            ORDER BY COALESCE(p.position, 0) ASC, COALESCE(p.updated_at, h.created_at) DESC, COALESCE(h.position, 0) ASC, h.created_at DESC
            LIMIT 80
            """
        )
        
    rows = cursor.fetchall()
    owner_clause, owner_params = _request_owner_clause(user_id, "user_id")
    cursor.execute(
        f"SELECT id, name, position, created_at, updated_at FROM projects WHERE {owner_clause} ORDER BY COALESCE(position, 0) ASC, updated_at DESC",
        owner_params,
    )
    project_rows = cursor.fetchall()
    conn.close()

    for row in project_rows:
        projects_map[row["id"]] = {
            "id": row["id"],
            "name": row["name"],
            "position": row["position"] if row["position"] is not None else 0,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "files": [],
        }
    
    for row in rows:
        job_id = row["job_id"]
        out_file = OUTPUT_DIR / f"{job_id}.pdf"
        has_db_pdf = bool(row["has_db_pdf"]) if ("has_db_pdf" in row.keys() and row["has_db_pdf"]) else False
        if out_file.exists() or has_db_pdf:
            history_list.append({
                "job_id": job_id,
                "filename": row["original_filename"],
                "created_at": row["created_at"],
                "size": row["file_size"],
                "pages": row["pages"],
                "position": row["position"] if row["position"] is not None else 0,
                "project_id": row["project_id"],
                "project_name": row["project_name"],
            })
            project_key = row["project_id"] or "unfiled"
            if project_key not in projects_map:
                projects_map[project_key] = {
                    "id": row["project_id"],
                    "name": row["project_name"],
                    "position": row["project_position"] if ("project_position" in row.keys() and row["project_position"] is not None) else 0,
                    "created_at": row["project_created_at"] or row["created_at"],
                    "updated_at": row["project_updated_at"] or row["created_at"],
                    "files": [],
                }
            projects_map[project_key]["files"].append(history_list[-1])
            
    projects_list = sorted(
        projects_map.values(),
        key=lambda item: (
            item.get("position") if item.get("position") is not None else 0,
            item.get("updated_at") or item.get("created_at") or ""
        ),
    )
    response = jsonify({"history": history_list, "projects": projects_list})
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/projects", methods=["GET", "POST"])
def projects():
    user_id = session.get("user_id")

    if request.method == "POST":
        data = request.get_json() or {}
        name = (data.get("name") or "").strip() or default_project_name()
        if not name:
            return jsonify({"error": "Folder name is required"}), 400

        conn = get_db()
        cursor = conn.cursor()
        project_id, project_name = get_or_create_project(cursor, user_id, project_name=name)
        cursor.execute("UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
        conn.commit()
        conn.close()
        return jsonify({"project": {"id": project_id, "name": project_name}})

    owner_clause, owner_params = _request_owner_clause(user_id, "p.user_id")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT
            p.id,
            p.name,
            p.position,
            p.created_at,
            p.updated_at,
            COUNT(h.id) AS file_count,
            COALESCE(SUM(h.pages), 0) AS page_count
        FROM projects p
        LEFT JOIN translation_history h ON h.project_id = p.id
        WHERE {owner_clause}
        GROUP BY p.id
        ORDER BY COALESCE(p.position, 0) ASC, p.updated_at DESC
        """,
        owner_params,
    )
    rows = cursor.fetchall()
    conn.close()
    return jsonify({"projects": [dict(row) for row in rows]})


@app.route("/projects/<int:project_id>", methods=["PATCH"])
def rename_project(project_id):
    user_id = session.get("user_id")
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Folder name is required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    if not _get_owned_project(cursor, project_id, user_id):
        conn.close()
        return jsonify({"error": "Folder not found"}), 404

    cursor.execute(
        "UPDATE projects SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (name, project_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "project": {"id": project_id, "name": name}})


@app.route("/files/<job_id>/move", methods=["PATCH"])
def move_file(job_id):
    if not re.match(r"^[a-zA-Z0-9_-]+$", job_id):
        return jsonify({"error": "Invalid job_id"}), 400

    user_id = session.get("user_id")
    data = request.get_json() or {}
    project_id = data.get("project_id")

    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Target folder is required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    target_project = _get_owned_project(cursor, project_id, user_id)
    if not target_project:
        conn.close()
        return jsonify({"error": "Target folder not found"}), 404

    owner_clause, owner_params = _request_owner_clause(user_id)
    cursor.execute(
        f"""
        UPDATE translation_history
        SET project_id = ?
        WHERE job_id = ? AND {owner_clause}
        """,
        (project_id, job_id, *owner_params),
    )
    moved = cursor.rowcount
    if moved:
        cursor.execute(
            "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (project_id,),
        )
    conn.commit()
    conn.close()

    if not moved:
        return jsonify({"error": "File not found"}), 404
    return jsonify({"success": True, "project": dict(target_project)})


@app.route("/files/reorder", methods=["POST"])
def reorder_files():
    user_id = session.get("user_id")
    data = request.get_json() or {}
    job_ids = data.get("job_ids") or []
    project_id = data.get("project_id")

    if not isinstance(job_ids, list):
        return jsonify({"error": "job_ids must be a list"}), 400

    conn = get_db()
    cursor = conn.cursor()
    owner_clause, owner_params = _request_owner_clause(user_id)

    for idx, job_id in enumerate(job_ids):
        if not re.match(r"^[a-zA-Z0-9_-]+$", str(job_id)):
            continue
        if project_id is not None:
            try:
                p_id = int(project_id)
            except (ValueError, TypeError):
                p_id = None
            cursor.execute(
                f"UPDATE translation_history SET position = ?, project_id = ? WHERE job_id = ? AND {owner_clause}",
                (idx, p_id, job_id, *owner_params),
            )
        else:
            cursor.execute(
                f"UPDATE translation_history SET position = ? WHERE job_id = ? AND {owner_clause}",
                (idx, job_id, *owner_params),
            )

    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/projects/reorder", methods=["POST"])
def reorder_projects():
    user_id = session.get("user_id")
    data = request.get_json() or {}
    project_ids = data.get("project_ids") or []

    if not isinstance(project_ids, list):
        return jsonify({"error": "project_ids must be a list"}), 400

    conn = get_db()
    cursor = conn.cursor()
    owner_clause, owner_params = _request_owner_clause(user_id)

    for idx, p_id in enumerate(project_ids):
        try:
            pid = int(p_id)
            cursor.execute(
                f"UPDATE projects SET position = ? WHERE id = ? AND {owner_clause}",
                (idx, pid, *owner_params),
            )
        except (ValueError, TypeError):
            continue

    conn.commit()
    conn.close()
    return jsonify({"success": True})


def delete_translation_files(job_id):
    deleted_files = 0

    out_file = OUTPUT_DIR / f"{job_id}.pdf"
    if out_file.exists():
        try:
            out_file.unlink()
            deleted_files += 1
        except Exception:
            pass

    matching_uploads = list(UPLOAD_DIR.glob(f"{job_id}_*"))
    for f in matching_uploads:
        try:
            f.unlink()
            deleted_files += 1
        except Exception:
            pass

    cache_file = CACHE_DIR / f"{job_id}_cache.json"
    if cache_file.exists():
        try:
            cache_file.unlink()
            deleted_files += 1
        except Exception:
            pass

    with jobs_lock:
        if job_id in jobs:
            del jobs[job_id]

    return deleted_files


@app.route("/projects/<int:project_id>", methods=["DELETE"])
def delete_project(project_id):
    user_id = session.get("user_id")
    mode = request.args.get("mode", "keep_files")
    if mode not in ("keep_files", "delete_files"):
        return jsonify({"error": "Invalid delete mode"}), 400

    conn = get_db()
    cursor = conn.cursor()
    if not _get_owned_project(cursor, project_id, user_id):
        conn.close()
        return jsonify({"error": "Folder not found"}), 404

    owner_clause, owner_params = _request_owner_clause(user_id, "user_id")
    cursor.execute(
        f"SELECT job_id FROM translation_history WHERE project_id = ? AND {owner_clause}",
        (project_id, *owner_params),
    )
    job_ids = [row["job_id"] for row in cursor.fetchall()]

    if mode == "delete_files":
        cursor.execute(
            f"DELETE FROM translation_history WHERE project_id = ? AND {owner_clause}",
            (project_id, *owner_params),
        )
    else:
        cursor.execute(
            f"UPDATE translation_history SET project_id = NULL WHERE project_id = ? AND {owner_clause}",
            (project_id, *owner_params),
        )

    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()

    deleted_files = 0
    if mode == "delete_files":
        for job_id in job_ids:
            deleted_files += delete_translation_files(job_id)

    return jsonify({
        "success": True,
        "mode": mode,
        "affected_files": len(job_ids),
        "deleted_files": deleted_files,
    })


@app.route("/delete/<job_id>", methods=["DELETE"])
def delete_history(job_id):
    if not re.match(r"^[a-zA-Z0-9_-]+$", job_id):
        return jsonify({"error": "Invalid job_id"}), 400

    user_id = session.get("user_id")

    conn = get_db()
    cursor = conn.cursor()
    if user_id:
        cursor.execute("DELETE FROM translation_history WHERE job_id = ? AND user_id = ?", (job_id, user_id))
    else:
        cursor.execute("DELETE FROM translation_history WHERE job_id = ? AND user_id IS NULL", (job_id,))
    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()

    deleted_files = delete_translation_files(job_id)

    if deleted_rows == 0 and deleted_files == 0:
        return jsonify({"error": "Translation record not found"}), 404
        
    return jsonify({"success": True, "message": "Translation record deleted"})


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("[server] PDF Translator running at http://localhost:5000")
    print(f"[font] Thai regular: {FONT_REG}")
    print(f"[font] Thai bold:    {FONT_BOLD}")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
