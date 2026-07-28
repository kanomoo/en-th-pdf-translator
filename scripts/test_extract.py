import fitz

doc = fitz.open('uploads/d949d69f7b5d_Ch1_Introduction.pdf')
items = []
for page_number, page in enumerate(doc):
    if page_number != 6: continue
    page_dict = page.get_text("dict")
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0: continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                value = span.get("text", "")
                if value:
                    print(f"Span: '{value}', bbox: {span['bbox']}, font: {span['font']}")
