import fitz
import json

doc = fitz.open('test.pdf')
# Find a page with a table, maybe page 3 or 4 based on screenshots
page = doc[3] 
blocks = [b for b in page.get_text('dict')['blocks'] if b['type']==0]
with open('debug_dump.json', 'w', encoding='utf-8') as f:
    json.dump(blocks, f, indent=2, ensure_ascii=False)
