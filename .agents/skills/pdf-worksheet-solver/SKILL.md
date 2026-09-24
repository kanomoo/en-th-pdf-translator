---
name: pdf-worksheet-solver
description: >-
  Specialized skill and automated engine for accurately solving, filling, and annotating
  academic PDF worksheets, lecture exercises, and exam sheets. Enforces strict in-place
  filling into blanks/tables, zero-overflow bounded cards, zero occlusion of original content,
  exact page budgeting, sub-pixel typography alignment (Thai & English), and automated
  multi-pass visual PNG verification. Activate whenever the user requests solving, filling,
  or annotating academic PDF/image worksheets or exercise sheets.
---

# PDF Worksheet & Exam Solver Skill (In-Place & Zero-Overflow Standards)

ทักษะระดับสูงสำหรับการทำเฉลย, เติมคำตอบ, และเขียนคำอธิบายลงในใบงานวิชาการ (Academic Worksheets), สไลด์แบบฝึกหัดในชั้นเรียน (Lecture Exercises), และข้อสอบ (Exam Papers) ในรูปแบบ PDF และรูปภาพ โดยยึดมาตรฐานความประณีตระดับเดียวกับ `Topological sort_solved.pdf` และ `For Example Graph_solved.pdf`

---

## 🏛️ กฎเหล็ก 6 ประการ (The 6 Golden Rules)

### 1. 🎯 ใส่ในกรอบ/ช่องว่าง/ที่เว้นว่างให้ครบก่อนเสมอ (In-Place Filling First)
* **เติมลงในตำแหน่งที่เว้นว่างเดิมเป็นอันดับแรก**:
  * หากโจทย์มีช่องว่าง เช่น `Answer: [  ]` หรือเส้นประ `____` ให้หยอดคำตอบลงในตำแหน่งนั้นโดยตรง
  * หากเป็นตาราง (Table / Matrix / Grid) ให้วางตัวเลขลงใน **กึ่งกลางช่องตารางจริง** (`fill_cell`)
  * หากเป็นโหนดแผนภาพ (เช่น วงกลม Binary Tree หรือ Heap) ให้วางตัวเลขลงในใจกลางวงกลมเดิม ไม่สร้างวงกลมใหม่มาซ้อน
* **คงโครงสร้างเดิมของเอกสาร 100%**: ไม่ลบ ไม่บัง และไม่แทนที่โครงเดิมโดยไม่จำเป็น

### 2. 🛡️ กรอบข้อความต้องไม่ล้นขอบเด็ดขาด (Zero-Overflow Bounded Cards)
* **กฎความปลอดภัยของกรอบ (Boundary Containment Rule)**:
  * หากจำเป็นต้องสร้างการ์ดสรุป (Summary Card) หรือกล่องเฉลย (Solution Box) **ข้อความต้องอยู่ภายในกรอบเสมอ 100%**
  * ห้ามตัวหนังสือแตะขอบกล่อง, หลุดล้นขอบขวา, หรือทะลุขอบล่างเด็ดขาด
  * ต้องมีระยะขอบความปลอดภัย (Safety Padding) อย่างน้อย `8–10 pt` โดยรอบ
* **การตัดคำภาษาไทยและการคำนวณขนาดฟอนต์อัตโนมัติ (Dynamic Sub-Pixel Fitting)**:
  * ใช้ `ThaiTextFitter` ในการตัดคำตามหลักไวยากรณ์ด้วย `pythainlp` ป้องกันการตัดกลางสระหรือพยัญชนะ
  * ทำการคำนวณความกว้างจริงของตัวอักษรระดับ Sub-pixel (`font.text_length`) ก่อนวาด
  * หากเนื้อหาบรรทัดรวมยาวเกินความสูงกล่อง ให้ลดขนาดฟอนต์แบบลดหลั่นอัตโนมัติ (เช่น 11pt -> 10pt -> 9pt -> 8pt) จนกระทั่งบรรจุลงได้พอดี

### 3. 🚫 กฎการไม่บดบังเนื้อหาเดิมเด็ดขาด (Zero Occlusion Rule)
* **ห้ามวางข้อความทับเนื้อหาเดิม**: ตัวหนังสือ, กรอบเฉลย, หรือลูกศรชี้ **ต้องไม่ทับเส้น, ตัวหนังสือโจทย์, ไดอะแกรม, หรือลูกศรเดิมของอาจารย์**
* **ตรวจหาพิกัดปลอดภัย (Safe White Space Detection)**:
  * สแกนหาพิกัดกล่องข้อความเดิมด้วย `page.get_text('blocks')` และภาพวาดด้วย `page.get_drawings()`
  * ใช้เฉพาะพื้นที่ว่างสีขาวที่ไม่มีวัตถุใดๆ วางอยู่เท่านั้น

### 4. 📐 การจัดกึ่งกลางและการวางแนวพิกัดแม่นยำ (Sub-pixel Grid Alignment)
* ในการเติมค่าลงตาราง: คำนวณจุดกึ่งกลาง $(cx, cy)$ ของแต่ละเซลล์:
  $$cx = x_0 + \frac{w - \text{text\_w}}{2}, \quad cy = y_0 + \frac{h + \text{text\_h}}{2} - \text{baseline\_offset}$$
* ในการทำ Highlight Badge (เช่น ตัวเลข 1 ในตาราง Matrix) ให้วาดกล่องขอบมนสีฟ้าอ่อน `#f0f7ff` ขนาดพอดีกับตัวเลขและมีขอบมน `radius=0.2`

### 5. 📄 การเพิ่มหน้าใหม่เป็นทางเลือกสุดท้าย (New Page as Strict Last Resort)
* **"การเขียนหน้าใหม่เป็นลำดับสุดท้ายถ้ามันไม่เหลือที่ว่างเลยจริง"**
* ต้องรักษาจำนวนหน้าให้ตรงกับเอกสารต้นฉบับเสมอ (เช่น ต้นฉบับมี 2 หน้า เอกสารเฉลยต้องมี 2 หน้าเท่ากัน)
* หากมีเนื้อหาอธิบายเพิ่มเติม ให้จัดลงในการ์ดสรุปท้ายหน้าที่มีพื้นที่ว่าง โดยใช้ฟอนต์และระยะบรรทัดที่กะทัดรัดแต่สบายตา

### 6. 👁️ การตรวจสอบด้วยสายตาทุกหน้าอย่างเคร่งครัด (Mandatory Visual Verification via PNG)
* หลังสร้างไฟล์ PDF เสร็จเรียบร้อย **ต้องเรนเดอร์ทุกหน้าเป็นภาพ PNG ความละเอียดสูง (150–200 DPI)**
* ใช้เครื่องมือ `view_file` เปิดดูภาพ PNG ที่เรนเดอร์ออกมาทุกหน้า เพื่อตรวจทาน:
  1. ตัวอักษรอยู่ในช่องว่าง/ตารางอย่างแม่นยำหรือไม่
  2. กรอบข้อความมีตัวหนังสือล้นหรือเบียดขอบหรือไม่
  3. มีส่วนใดบดบังเนื้อหาหรือโจทย์เดิมหรือไม่
  4. หากพบจุดที่ไม่สมบูรณ์ ให้ปรับแก้พิกัดหรือขนาดฟอนต์ และเรนเดอร์ตรวจซ้ำจนกว่าจะสมบูรณ์แบบที่สุด

---

## 🛠️ โครงสร้างเครื่องมือและการใช้งาน (`worksheet_engine.py`)

เครื่องมืออัตโนมัติถูกจัดเตรียมไว้ในโฟลเดอร์ `scripts/worksheet_engine.py`:

```python
from worksheet_engine import WorksheetSolverCanvas, CardStyle, render_pdf_to_images
import fitz

# 1. โหลดเอกสารต้นฉบับ
doc = fitz.open("assignment.pdf")
page = doc[0]
canvas = WorksheetSolverCanvas(page)

# 2. เติมคำตอบลงในช่องว่างเดิม (In-Place Filling)
canvas.fill_text(point=(150, 240), text="42", fontsize=11, bold=True, color=(0.0, 0.25, 0.65))

# 3. เติมลงในช่องตารางพร้อม Badge สวยงาม
canvas.fill_cell(
    rect=fitz.Rect(100, 300, 140, 325),
    text="1",
    fontsize=10,
    badge_fill=(0.89, 0.95, 1.0),
    badge_stroke=(0.56, 0.79, 0.98)
)

# 4. สร้างการ์ดอธิบายที่ไม่ล้นกรอบ 100%
canvas.draw_card(
    rect=fitz.Rect(50, 600, 550, 720),
    title="💡 สรุปขั้นตอนการคำนวณ (Solution Steps):",
    body_lines=[
        "• ขั้นตอนที่ 1: ตรวจสอบความถูกต้องของ Input ลำดับแรก",
        "• ขั้นตอนที่ 2: ดำเนินการคำนวณตามขั้นตอนอัลกอริทึม",
        "✓ สรุปคำตอบสุดท้าย: ได้ผลลัพธ์ที่ถูกต้องและสมบูรณ์"
    ],
    style=CardStyle.INFO,
    base_fontsize=10.0,
    padding=8.0
)

# 5. บันทึกและเรนเดอร์ภาพตรวจทานสายตา
doc.save("assignment_solved.pdf")
doc.close()
images = render_pdf_to_images("assignment_solved.pdf", "output_qa", dpi=150)
```

---

## 🎨 จานสีมาตรฐานการออกแบบ (Design Palette)

* **สีตัวอักษรคำตอบทั่วไป:** Navy Blue `RGB(0.0, 0.25, 0.65)` หรือ `#004085` (ดูเป็นระเบียบ แตกต่างจากโจทย์เดิมอย่างชัดเจน)
* **สีคำตอบทางการ (Official Answer):** Forest Green `RGB(0.08, 0.45, 0.20)` หรือ Deep Blue `RGB(0.05, 0.30, 0.70)`
* **สีข้อควรระวัง/คำเตือน (Warning):** Amber/Red `RGB(0.75, 0.15, 0.10)`
* **สีกรอบการ์ด (Card Backgrounds):**
  * ข้อมูลทั่วไป: `#f0f7ff` ขอบ `#b3d1fa`
  * ผลลัพธ์ถูกต้อง: `#f0fff4` ขอบ `#bbf7d0`
  * ข้อควรระวัง: `#fffbeb` ขอบ `#fde68a`
  * โค้ด/เทคนิคัล: `#f8f9fa` ขอบ `#dee2e6`
