import concurrent.futures
import json
import re
import statistics
import time
import urllib.parse
import urllib.request
from pathlib import Path

import fitz
import pythainlp


SRC = Path("C:/Project/computer-network-&-Internet/Chapter_1_Introduction.pdf")
WORK = Path("D:/Trade/BlackTest/tmp/pdfs")
OUTDIR = Path("D:/Trade/BlackTest/output/pdf")
CACHE = WORK / "chapter1_translation_cache.json"
OUT = OUTDIR / "Chapter_1_Introduction_TH.pdf"
FONT_REG = "C:/Windows/Fonts/LeelawUI.ttf"
FONT_BOLD = "C:/Windows/Fonts/LeelaUIb.ttf"

OUTDIR.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)

SPECIAL = {
    "Chapter 1": "บทที่ 1",
    "Introduction": "บทนำ",
}

BULLETS = {
    "\uf0a7": "▪",
    "\uf0b7": "•",
    "\uf0d8": "◦",
    "\uf0fc": "✓",
    "": "▪",
    "": "•",
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


def block_text_info(block):
    lines = []
    sizes = []
    colors = []
    fonts = []
    flags = []
    for line in block.get("lines", []):
        parts = []
        for span in line.get("spans", []):
            value = span.get("text", "")
            if value:
                parts.append(value)
                sizes.append(span.get("size", 12))
                colors.append(span.get("color", 0))
                fonts.append(span.get("font", ""))
                flags.append(span.get("flags", 0))
        joined = "".join(parts).strip()
        if joined:
            lines.append(joined)

    text = clean_text("\n".join(lines))
    size = float(statistics.median(sizes)) if sizes else 12.0
    color = colors[0] if colors else 0
    bold = any("bold" in font.lower() for font in fonts) or any(flag & 16 for flag in flags)
    return text, size, color, bold


def extract_items(doc):
    items = []
    for page_number, page in enumerate(doc):
        page_dict = page.get_text("dict")
        for block in page_dict["blocks"]:
            if block.get("type") != 0:
                continue
            text, size, color, bold = block_text_info(block)
            if text:
                items.append(
                    {
                        "page": page_number,
                        "bbox": list(block["bbox"]),
                        "text": text,
                        "size": size,
                        "color": color,
                        "bold": bold,
                    }
                )
    return items


def load_cache():
    if not CACHE.exists():
        return {}
    return json.loads(CACHE.read_text(encoding="utf-8"))


def save_cache(cache):
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def translate_payload(payload):
    url = (
        "https://translate.googleapis.com/translate_a/single"
        "?client=gtx&sl=en&tl=th&dt=t&q="
        + urllib.parse.quote(payload)
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = json.loads(response.read().decode("utf-8"))
    return clean_text("".join(part[0] for part in data[0] if part and part[0]))


def translate_batch(batch):
    marker_prefix = "ZXQ"
    payload_parts = []
    markers = []
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


def translate_missing(items, cache):
    unique = []
    seen = set()
    for item in items:
        text = item["text"]
        if text in SPECIAL:
            cache[text] = SPECIAL[text]
        if text not in cache and text not in seen:
            seen.add(text)
            unique.append(text)

    batches = []
    current = []
    current_chars = 0
    for idx, text in enumerate(unique):
        text_len = len(text)
        if current and (len(current) >= 24 or current_chars + text_len > 3500):
            batches.append(current)
            current = []
            current_chars = 0
        current.append((idx, text))
        current_chars += text_len
    if current:
        batches.append(current)

    print(f"items={len(items)} unique_missing={len(unique)} batches={len(batches)} cached={len(cache)}", flush=True)
    if not batches:
        return cache

    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_batch = {executor.submit(translate_batch, batch): batch for batch in batches}
        for future in concurrent.futures.as_completed(future_to_batch):
            batch = future_to_batch[future]
            try:
                cache.update(future.result())
            except Exception:
                # Retry once serially with a smaller split; this handles occasional marker oddities.
                for entry in batch:
                    cache.update(translate_batch([entry]))
            completed += 1
            if completed % 5 == 0 or completed == len(batches):
                save_cache(cache)
                print(f"translated_batches={completed}/{len(batches)} cache={len(cache)}", flush=True)
            time.sleep(0.05)
    save_cache(cache)
    return cache


def rgb_from_int(color):
    return ((color >> 16 & 255) / 255, (color >> 8 & 255) / 255, (color & 255) / 255)


def sample_background(page, rect, pix):
    width, height = pix.width, pix.height
    x0, y0, x1, y1 = [int(round(value)) for value in rect]
    pad = 5
    samples = []
    step = 6
    for x in range(max(0, x0 - pad), min(width, x1 + pad), step):
        for y in (max(0, y0 - pad), min(height - 1, y1 + pad)):
            samples.append(pix.pixel(x, y)[:3])
    for y in range(max(0, y0 - pad), min(height, y1 + pad), step):
        for x in (max(0, x0 - pad), min(width - 1, x1 + pad)):
            samples.append(pix.pixel(x, y)[:3])
    if not samples:
        return (1, 1, 1)
    return tuple(statistics.median(channel) / 255 for channel in zip(*samples))


def expanded_rect(rect, page_rect, amount=1.4):
    output = fitz.Rect(rect)
    output.x0 = max(page_rect.x0, output.x0 - amount)
    output.y0 = max(page_rect.y0, output.y0 - amount)
    output.x1 = min(page_rect.x1, output.x1 + amount)
    output.y1 = min(page_rect.y1, output.y1 + amount)
    return output


def remove_original_text(doc, items):
    by_page = {}
    for item in items:
        by_page.setdefault(item["page"], []).append(item)

    for page_number, page_items in by_page.items():
        page = doc[page_number]
        pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        for item in page_items:
            rect = expanded_rect(item["bbox"], page.rect)
            fill = sample_background(page, rect, pix)
            page.add_redact_annot(rect, fill=fill)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        if (page_number + 1) % 20 == 0:
            print(f"redacted_page={page_number + 1}", flush=True)


def insert_thai_text(doc, items, cache):
    shrunk = 0
    clipped = 0
    for index, item in enumerate(items, 1):
        page = doc[item["page"]]
        original_size = item["size"]
        # Reduce starting font size slightly to account for Thai tone marks
        size = original_size * 0.85
        rect = fitz.Rect(item["bbox"])
        
        # Minimal padding to avoid crossing table boundaries or adjacent blocks
        rect.x0 = max(page.rect.x0, rect.x0 - 0.5)
        rect.y0 = max(page.rect.y0, rect.y0 - 0.5)
        rect.x1 = min(page.rect.x1, rect.x1 + 0.5)
        rect.y1 = min(page.rect.y1, rect.y1 + 1.0)
        
        fontfile = FONT_BOLD if item["bold"] and Path(FONT_BOLD).exists() else FONT_REG
        fontname = "ThaiFontB" if item["bold"] else "ThaiFont"
        
        raw_translated = cache[item["text"]].replace("▪", "•").replace("□", "•")
        # Tokenize Thai words and join with space to allow PyMuPDF to wrap text in tight table cells
        words = pythainlp.word_tokenize(raw_translated, engine="newmm")
        translated = " ".join(words)

        # Remove multiple spaces
        translated = re.sub(r" +", " ", translated).strip()

        min_size = max(4.0, original_size * 0.40)
        lineheight = 1.15
        
        rc = -1
        while size >= min_size:
            rc = page.insert_textbox(
                rect,
                translated,
                fontsize=size,
                fontname=fontname,
                fontfile=fontfile,
                color=rgb_from_int(item["color"]),
                align=fitz.TEXT_ALIGN_LEFT,
                lineheight=lineheight,
            )
            if rc >= 0:
                break
            size -= 0.5

        if size < original_size * 0.85:
            shrunk += 1
        if rc < 0:
            clipped += 1
            # Force insert at min size if it still doesn't fit
            page.insert_textbox(
                rect,
                translated,
                fontsize=min_size,
                fontname=fontname,
                fontfile=fontfile,
                color=rgb_from_int(item["color"]),
                align=fitz.TEXT_ALIGN_LEFT,
                lineheight=lineheight,
            )
        if index % 150 == 0:
            print(f"inserted={index}/{len(items)}", flush=True)
    print(f"fit_adjusted={shrunk} clipped={clipped}", flush=True)


def main():
    print(f"source={SRC}", flush=True)
    doc = fitz.open(str(SRC))
    items = extract_items(doc)
    cache = translate_missing(items, load_cache())
    print("building_pdf=1", flush=True)
    remove_original_text(doc, items)
    insert_thai_text(doc, items, cache)
    doc.save(str(OUT), garbage=4, deflate=True)
    print(f"saved={OUT}", flush=True)


if __name__ == "__main__":
    main()
