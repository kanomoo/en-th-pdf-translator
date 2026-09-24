# Academic Formatting Standards & Word COM Automation Reference

คู่มืออ้างอิงเชิงลึกสำหรับการตั้งค่า `python-docx`, XML Elements และ Microsoft Word COM API เพื่อให้เอกสารเป็นไปตามระเบียบงานสารบรรณวิชาการ

---

## 1. การตั้งค่าระยะขอบและส่วนต่างๆ (Page Setup in twips)

1 นิ้ว = 1440 twips = 72 pt = 2.54 ซม.

```python
from docx.shared import Inches, Pt

# หน้าเนื้อหาทั่วไป (Body Sections)
section.top_margin = Inches(1.5)      # 2160 twips
section.bottom_margin = Inches(1.0)   # 1440 twips
section.left_margin = Inches(1.5)     # 2160 twips (สำหรับเย็บเล่ม)
section.right_margin = Inches(1.0)    # 1440 twips
section.header_distance = Inches(0.75)
section.footer_distance = Inches(0.5)

# หน้าปก (Cover Section)
cover_section.top_margin = Inches(1.5)
cover_section.bottom_margin = Inches(1.0)
cover_section.left_margin = Inches(1.0)  # ซ้าย-ขวาเท่ากัน 1.0 นิ้วเพื่อความสมดุล
cover_section.right_margin = Inches(1.0)
```

---

## 2. การสร้างแท็บและจุดไข่ปลาในสารบัญ (Tab Stops & Dot Leaders)

ใน `python-docx` การสร้างจุดไข่ปลาที่ชิดขอบขวาอย่างสมบูรณ์แบบ ต้องใช้ OpenXML เพื่อระบุ `w:leader="dot"`:

```python
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.enum.text import WD_TAB_ALIGNMENT

def add_toc_line(p, title_text, page_num_str, font_name="TH Sarabun PSK", font_size_pt=16, is_bold=False):
    """
    เพิ่มบรรทัดสารบัญพร้อมจุดไข่ปลาและเลขหน้าชิดขอบขวาอย่างถูกต้อง
    ระยะขอบกระดาษเนื้อหา: กว้าง 8.27" - ซ้าย 1.5" - ขวา 1.0" = เนื้อที่พิมพ์ 5.77"
    """
    p.paragraph_format.tab_stops.add_tab_stop(Inches(5.77), WD_TAB_ALIGNMENT.RIGHT)
    
    # เพิ่มชื่อหัวข้อ
    run_title = p.add_run(title_text)
    run_title.font.name = font_name
    run_title.font.size = Pt(font_size_pt)
    run_title.font.bold = is_bold
    
    # เพิ่มแท็บพร้อมจุดไข่ปลา
    run_tab = p.add_run()
    tab_elem = parse_xml(f'<w:tab {nsdecls("w")} w:leader="dot"/>')
    run_tab._r.append(tab_elem)
    
    # เพิ่มเลขหน้า
    run_page = p.add_run(str(page_num_str))
    run_page.font.name = font_name
    run_page.font.size = Pt(font_size_pt)
    run_page.font.bold = is_bold
```

---

## 3. การควบคุมตารางวิชาการ (Academic Table XML Styling)

### 3.1 การป้องกันแถวขาดหน้า (`cantSplit`) และทำซ้ำหัวตาราง (`tblHeader`)
```python
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def protect_table(table):
    for i, row in enumerate(table.rows):
        trPr = row._tr.get_or_add_trPr()
        # ป้องกันไม่ให้แถวแยกขาดข้ามหน้ากระดาษ
        trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
        # กำหนดแถวแรกเป็นหัวตารางที่ทำซ้ำหากมีหลายหน้า
        if i == 0:
            trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
```

### 3.2 การกำหนดเส้นขอบมาตรฐาน APA (เฉพาะแนวนอน ไม่มีแนวตั้ง)
```python
def apply_academic_borders(table):
    tblPr = table._tbl.tblPr
    tblBorders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="single" w:sz="12" w:space="0" w:color="1A365D"/>'      # 1.5 pt
        f'  <w:bottom w:val="single" w:sz="12" w:space="0" w:color="1A365D"/>'   # 1.5 pt
        f'  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'   # 0.5 pt บางๆ
        f'  <w:insideV w:val="none"/>'                                            # ไม่มีเส้นตั้ง
        f'  <w:left w:val="none"/>'
        f'  <w:right w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(tblBorders)
```

### 3.3 การปรับระยะขอบภายในเซลล์ (Cell Padding) เพื่อคุมความสูงหน้า
```python
def set_cell_margins(cell, top=50, bottom=50, left=100, right=100):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'  <w:top w:w="{top}" w:type="dxa"/>'
        f'  <w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'  <w:left w:w="{left}" w:type="dxa"/>'
        f'  <w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)
```

---

## 4. กลไกการแปลงไฟล์ผ่าน Microsoft Word COM (Headless & Clean)

```python
import os
import win32com.client

def export_to_pdf_word_com(docx_path, pdf_path):
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        abs_docx = os.path.abspath(docx_path)
        abs_pdf = os.path.abspath(pdf_path)
        doc = word.Documents.Open(abs_docx)
        # 17 = wdExportFormatPDF
        doc.SaveAs(abs_pdf, FileFormat=17)
        doc.Close(False)
    finally:
        word.Quit()
```

---

## 5. การสแกนเลขหน้าจริงผ่าน PyMuPDF (fitz)

```python
import fitz
import re

def scan_pdf_page_locations(pdf_path, heading_patterns):
    """
    heading_patterns: dict ของ {key: regex_pattern}
    เช่น {'ch1': r'บทที่\s*1\b', 'ch2': r'บทที่\s*2\b', 'tab_2_1': r'ตารางที่\s*2\.1'}
    """
    doc = fitz.open(pdf_path)
    page_map = {}
    
    for page_idx, page in enumerate(doc):
        text = page.get_text()
        actual_page_num = page_idx + 1 # หรือคำนวณตามหน้าเนื้อหาเริ่มนับ 1 ที่บทที่ 1
        
        for key, pattern in heading_patterns.items():
            if key not in page_map and re.search(pattern, text):
                page_map[key] = actual_page_num
                
    doc.close()
    return page_map
```
