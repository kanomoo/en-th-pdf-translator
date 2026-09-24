---
name: academic-project-report
description: >-
  Standardized runbook and automation framework for creating, compiling, and formatting
  official Thai academic project reports (.docx, .pdf) and pitching presentations (.pptx, .pdf)
  strictly adhering to university/ministry/KMUTNB thesis and project standards.
  Enforces TH Sarabun PSK typography, exact margins (Left 1.5", Top 1.5", Right 1.0", Bottom 1.0"),
  anti-orphan page budgeting, APA table styling, and two-pass dynamic TOC/LOT/LOF page synchronization.
  Activate whenever the user requests generating, formatting, or refining academic reports, project documents, or pitch decks.
---

# Academic Project Report & Presentation Skill (Thai Standard)

ทักษะสำหรับการจัดทำรูปเล่มรายงานโครงงานทางวิชาการ (Academic Project Report) และสไลด์นำเสนอ (Pitching Presentation) ตามมาตรฐานบัณฑิตวิทยาลัยและระเบียบงานสารบรรณ/โครงงานมหาวิทยาลัย (เช่น มจพ. / สถาบันอุดมศึกษาไทย) อย่างประณีต ถูกต้องตามแบบแผน และไม่มีข้อผิดพลาดเรื่องการตัดหน้าหรือกั้นหน้า

---

## 1. ข้อกำหนดมาตรฐานรูปเล่ม (Academic Formatting Specifications)

### 1.1 ระยะขอบกระดาษ (Page Margins)
*   **หน้าเนื้อหาทั่วไป:**
    *   ขอบบน (Top): **1.5 นิ้ว** (3.81 ซม.)
    *   ขอบซ้าย (Left): **1.5 นิ้ว** (3.81 ซม.) — เว้นสำหรับเย็บเล่ม/เข้าเล่ม
    *   ขอบขวา (Right): **1.0 นิ้ว** (2.54 ซม.)
    *   ขอบล่าง (Bottom): **1.0 นิ้ว** (2.54 ซม.)
*   **หน้าปก (Cover Page):**
    *   ขอบบน 1.5 นิ้ว, ขอบล่าง 1.0 นิ้ว, ขอบซ้าย 1.0 นิ้ว, ขอบขวา 1.0 นิ้ว (กึ่งกลางสมดุล)

### 1.2 ตัวพิมพ์และการจัดวรรคตอน (Typography & Hierarchy)
*   **ฟอนต์หลัก:** `TH Sarabun PSK` (หรือ `TH Sarabun New`) ตลอดทั้งเล่ม รวมทั้งในตารางและเชิงอรรถ
*   **ลำดับชั้นขนาดตัวอักษร:**
    *   **ชื่อบท (Chapter Title):** 20pt หนา (Bold) กึ่งกลางหน้ากระดาษ (Centered), Space Before 0pt, Space After 12pt
    *   **หัวข้อหลัก (Heading 1 - X.X):** 16pt หนา (Bold) ชิดซ้าย ไม่ย่อหน้า (Flush Left), Space Before 6pt, Space After 4pt
    *   **หัวข้อย่อย (Heading 2 - X.X.X):** 16pt หนา (Bold) ย่อหน้า 0.5 นิ้ว (1.27 ซม.)
    *   **เนื้อความทั่วไป (Body Text):** 16pt ปกติ (Regular), จัดแนวแบบกระจายข้อความ (Thai Distributed / Justified)
    *   **ย่อหน้าแรกของเนื้อความ (First-line Indent):** **0.5 นิ้ว** (36pt / 720 twips) สม่ำเสมอทุกย่อหน้า
    *   **รายการข้อย่อย (Bullets / Numbering):** Left Indent 0.5 นิ้ว, Hanging Indent 0.25–0.5 นิ้ว ป้องกันตัวอักษรกระโดดข้ามแนว
    *   **ระยะบรรทัด (Line Spacing):** 1.15 เท่า หรือ Multiple 1.15

### 1.3 กฎเหล็กป้องกันหน้าแหว่ง (Zero Orphan / Spillover Page Rule)
*   **ห้ามมีหน้าตกหล่นที่มีเนื้อหาเพียง 1–5 บรรทัดเด็ดขาด (No Orphan Spillover Pages)**
*   **Page Budgeting:** กำหนดจำนวนหน้าต่อบทอย่างเคร่งครัด (เช่น บทที่ 1 = 3 หน้าพอดี, บทที่ 2 = 2 หน้าพอดี)
*   ใช้คำสั่งขึ้นหน้าใหม่ (`add_page_break`) **เฉพาะจุดเริ่มต้นของบทใหม่เท่านั้น** (ห้ามใส่สุ่มสี่สุ่มห้ากลางบท)
*   หากเนื้อหาหรือตารางล้นไปหน้าใหม่อย่างไม่สมดุล ให้ปรับความกระชับของข้อความ, ปรับขนาดความกว้างภาพ (2.2"–3.5"), หรือปรับ Padding ในเซลล์ตาราง (`font_size_pt=12.5`, `padding_twips=35`) เพื่อให้เนื้อหาดึงกลับมาจบเต็มหน้าได้อย่างลงตัว

---

## 2. มาตรฐานตารางและภาพประกอบ (Tables & Figures)

### 2.1 ตารางวิชาการ (Academic APA Table Style)
*   **เส้นขอบ:** ใช้เฉพาะเส้นแนวนอน (Horizontal borders) — เส้นบนสุดหนา 1.5pt, เส้นใต้หัวตาราง 1.0pt, เส้นล่างสุดหนา 1.5pt
*   **ห้ามมีเส้นแบ่งแนวตั้ง (No Vertical Lines)**
*   **การตั้งค่าป้องกันตารางขาดหน้า:**
    *   ใส่ `cantSplit` บนทุกแถว (`w:trPr`) เพื่อไม่ให้แถวขาดครึ่ง
    *   ใส่ `tblHeader` บนแถวหัวตาราง
*   **ขนาดฟอนต์ในตาราง:** 12–14pt ตามความหนาแน่นของข้อมูล
*   **คำบรรยายหัวตาราง:** อยู่ **เหนือตาราง** ชิดซ้าย เช่น `ตารางที่ 2.1: การวิเคราะห์เป้าหมายเชิงกลยุทธ์ (SMART Goals)`

### 2.2 ภาพประกอบ (Academic Figure Style)
*   ภาพวาง **กึ่งกลางหน้ากระดาษ** ความกว้างเหมาะสม (2.2 – 3.8 นิ้ว ไม่ดันข้อความล้นหน้า)
*   **คำบรรยายใต้ภาพ:** อยู่ **ใต้ภาพ กึ่งกลาง** เช่น `ภาพที่ 4.1: แผนภาพสถาปัตยกรรมระบบ (System Architecture)` (14pt หนา)
*   **แหล่งที่มา:** บรรทัดถัดไปกึ่งกลาง เช่น `(ที่มา: คณะผู้จัดทำ, 2569)` (12pt เอียง)

---

## 3. ระบบสารบัญซิงค์พิกัดหน้าจริงแบบ 2 รอบ (Two-Pass Dynamic TOC Engine)

เพื่อให้เลขหน้าในหน้าสารบัญ (สารบัญเนื้อหา, สารบัญตาราง, สารบัญภาพ) ตรงกับตำแหน่งหน้าจริงในไฟล์ PDF 100%:

1.  **Pass 1 (Draft Generation):** สร้างไฟล์ `.docx` รอบแรกโดยใส่เลขหน้าชั่วคราว
2.  **PDF Conversion:** แปลง `.docx` เป็น `.pdf` ผ่าน Microsoft Word COM API (`win32com.client.Dispatch("Word.Application")`)
3.  **Page Number Scanning:** ใช้ PyMuPDF (`import fitz`) อ่านไฟล์ PDF และค้นหาหัวข้อ/ชื่อตาราง/ชื่อภาพ ด้วย Regex เพื่อดึงพิกัดเลขหน้าที่แท้จริง
4.  **Pass 2 (Final TOC Injection):** นำพิกัดเลขหน้าที่สแกนได้มาเขียนลงในหน้าสารบัญของ `.docx` อีกครั้ง โดยใช้ **Right Tab Stop ที่ระยะ 5.77 นิ้ว พร้อมจุดไข่ปลา (Leader Dots: `w:leader="dot"`)**
5.  **Final PDF Generation:** แปลงไฟล์รอบสุดท้าย จะได้เล่มรายงานที่เลขหน้า สารบัญเนื้อหา สารบัญตาราง และสารบัญภาพ ตรงเป๊ะ 100%

---

## 4. โครงสร้างโฟลเดอร์ส่งงานมาตรฐาน (Delivery Folder Architecture)

เมื่อทำงานเสร็จสิ้น ให้จัดเตรียมโฟลเดอร์ส่งงานแบบสำเร็จรูป (Clean Delivery Folder) โดยแยกขาดจากโฟลเดอร์พัฒนา:

```text
C:/Project/<workspace>/
├── 00_ไฟล์ส่งงาน_<ProjectName>/           # [โฟลเดอร์ส่งงานหลักสำหรับผู้ใช้]
│   ├── 01_เล่มรายงาน_<ProjectName>_ฉบับสมบูรณ์.docx
│   ├── 01_เล่มรายงาน_<ProjectName>_ฉบับสมบูรณ์.pdf
│   ├── 02_สไลด์นำเสนอ_<ProjectName>_Pitching.pptx
│   ├── 02_สไลด์นำเสนอ_<ProjectName>_Pitching.pdf
│   └── README_คำอธิบายไฟล์ส่งงาน.txt
└── Project_<ProjectName>/                  # [โฟลเดอร์ซอร์สโค้ดและสคริปต์ตัวสร้าง]
    ├── scripts/
    │   ├── build_report.py
    │   └── report_helpers.py
    └── assets/
        └── images/
```

---

## 5. การสร้างสไลด์นำเสนอแบบมืออาชีพ (Pitching Deck)

*   อัตราส่วนสไลด์: **16:9 Widescreen**
*   โทนสี: สุภาพ น่าเชื่อถือ ทันสมัย (Navy Blue `#1E3A8A`, Deep Cyan `#0D9488`, Slate Gray `#475569`, Warm Amber `#D97706`)
*   โครงสร้างสไลด์ Pitching 10 แผ่นมาตรฐาน:
    1. Title & Team Overview
    2. Problem Statement & Pain Points
    3. Solution & Value Proposition (UVP)
    4. Business Model Canvas (BMC)
    5. Target Market & TAM / SAM / SOM
    6. Competitive Advantage & Differentiation
    7. Go-to-Market (GTM) Strategy & 4Ps
    8. Technical Architecture & Innovation Tactics
    9. Risk Management & Business Continuity (BCP)
    10. Financial Projections, Milestones & Call to Action (Q&A)
*   แปลงสไลด์เป็น PDF ผ่าน PowerPoint COM API เพื่อความคมชัดสูงสุด
