"""
Academic Project Report Template Engine
Standard library of helper functions for generating publication-grade academic project reports (.docx & .pdf)
following Thai Ministry/University (KMUTNB) formatting standards.
"""

import os
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def create_academic_document():
    """Initializes Document with standard Thai academic margins and styles."""
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(1.5)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.5)
    section.right_margin = Inches(1.0)
    section.header_distance = Inches(0.75)
    section.footer_distance = Inches(0.5)

    # Set normal style font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'TH Sarabun PSK'
    font.size = Pt(16)
    font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
    style.paragraph_format.line_spacing = 1.15
    style.paragraph_format.space_after = Pt(0)
    style.paragraph_format.space_before = Pt(0)

    # Ensure EastAsia font is set to TH Sarabun PSK
    rPr = style._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), 'TH Sarabun PSK')
    rFonts.set(qn('w:cs'), 'TH Sarabun PSK')

    return doc

def add_chapter_title(doc, chapter_num, title_th, title_en=""):
    """Adds formal centered chapter header."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    r1 = p.add_run(f"บทที่ {chapter_num}\n")
    r1.font.name = "TH Sarabun PSK"
    r1.font.size = Pt(20)
    r1.font.bold = True
    r1.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

    r2 = p.add_run(title_th)
    r2.font.name = "TH Sarabun PSK"
    r2.font.size = Pt(20)
    r2.font.bold = True
    r2.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

    if title_en:
        p2 = doc.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p2.paragraph_format.space_before = Pt(0)
        p2.paragraph_format.space_after = Pt(12)
        r_en = p2.add_run(f"({title_en})")
        r_en.font.name = "TH Sarabun PSK"
        r_en.font.size = Pt(16)
        r_en.font.bold = True
        r_en.font.color.rgb = RGBColor(0x3B, 0x82, 0xF6)
    else:
        p.paragraph_format.space_after = Pt(12)

def add_heading_1(doc, heading_text):
    """Level 1 heading: 16pt Bold, flush left."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Inches(0)
    r = p.add_run(heading_text)
    r.font.name = "TH Sarabun PSK"
    r.font.size = Pt(16)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    return p

def add_heading_2(doc, heading_text):
    """Level 2 heading: 16pt Bold, indented 0.5"."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.left_indent = Inches(0.5)
    r = p.add_run(heading_text)
    r.font.name = "TH Sarabun PSK"
    r.font.size = Pt(16)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
    return p

def add_body_paragraph(doc, text):
    """Body paragraph with standard 0.5" first-line indent and justified text."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.first_line_indent = Inches(0.5)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    r = p.add_run(text)
    r.font.name = "TH Sarabun PSK"
    r.font.size = Pt(16)
    r.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
    return p

def add_list_item(doc, label_text, content_text, indent_inches=0.5):
    """Clean list item with label bold and hanging text."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent = Inches(indent_inches)
    p.paragraph_format.first_line_indent = Inches(0)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    
    r_label = p.add_run(label_text + " ")
    r_label.font.name = "TH Sarabun PSK"
    r_label.font.size = Pt(16)
    r_label.font.bold = True
    r_label.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

    r_content = p.add_run(content_text)
    r_content.font.name = "TH Sarabun PSK"
    r_content.font.size = Pt(16)
    r_content.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
    return p

def add_styled_table(doc, headers, data, col_widths=None, font_size_pt=13, padding_twips=40):
    """Adds APA-styled cohesive table with cantSplit and tblHeader."""
    table = doc.add_table(rows=len(data) + 1, cols=len(headers))
    table.autofit = False

    # Header Row
    hdr_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        hdr_cells[i].text = header
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        for run in p.runs:
            run.font.name = 'TH Sarabun PSK'
            run.font.size = Pt(font_size_pt + 1)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="1E3A8A"/>')
        hdr_cells[i]._tc.get_or_add_tcPr().append(shd)

    # Data Rows
    for r_idx, row_data in enumerate(data):
        row_cells = table.rows[r_idx + 1].cells
        bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, cell_value in enumerate(row_data):
            row_cells[c_idx].text = str(cell_value)
            p = row_cells[c_idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if c_idx > 0 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.line_spacing = 1.05
            for run in p.runs:
                run.font.name = 'TH Sarabun PSK'
                run.font.size = Pt(font_size_pt)
                run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_color}"/>')
            row_cells[c_idx]._tc.get_or_add_tcPr().append(shd)

    # Border and row protection
    for i, row in enumerate(table.rows):
        trPr = row._tr.get_or_add_trPr()
        trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
        if i == 0:
            trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
        for c_idx, cell in enumerate(row.cells):
            tcPr = cell._tc.get_or_add_tcPr()
            tcMar = parse_xml(
                f'<w:tcMar {nsdecls("w")}>'
                f'<w:top w:w="{padding_twips}" w:type="dxa"/>'
                f'<w:bottom w:w="{padding_twips}" w:type="dxa"/>'
                f'<w:left w:w="80" w:type="dxa"/>'
                f'<w:right w:w="80" w:type="dxa"/>'
                f'</w:tcMar>'
            )
            tcPr.append(tcMar)
            if col_widths and c_idx < len(col_widths):
                cell.width = col_widths[c_idx]

    tblPr = table._tbl.tblPr
    tblBorders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="12" w:space="0" w:color="1E3A8A"/>'
        f'<w:bottom w:val="single" w:sz="12" w:space="0" w:color="1E3A8A"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
        f'<w:insideV w:val="none"/>'
        f'<w:left w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(tblBorders)
    return table

def add_figure_with_caption(doc, image_path, caption_text, width_inches=3.0, source_text="คณะผู้จัดทำ, 2569"):
    """Adds figure centered with proper academic caption and citation."""
    if os.path.exists(image_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(2)
        run_img = p_img.add_run()
        run_img.add_picture(image_path, width=Inches(width_inches))

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(0)
        p_cap.paragraph_format.space_after = Pt(1)
        r_cap = p_cap.add_run(caption_text)
        r_cap.font.name = "TH Sarabun PSK"
        r_cap.font.size = Pt(14)
        r_cap.font.bold = True
        r_cap.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

        p_src = doc.add_paragraph()
        p_src.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_src.paragraph_format.space_before = Pt(0)
        p_src.paragraph_format.space_after = Pt(6)
        r_src = p_src.add_run(f"(ที่มา: {source_text})")
        r_src.font.name = "TH Sarabun PSK"
        r_src.font.size = Pt(12)
        r_src.font.italic = True
        r_src.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
