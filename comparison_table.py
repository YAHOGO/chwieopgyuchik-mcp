# -*- coding: utf-8 -*-
"""신구조문대비표 .docx 생성 (법제처 양식).

양식 규칙
- 표 2열, 머리행 "현        행" / "개   정   안" (굵게, 가운데)
- 조문 제목(제N조(...)) 굵게 — 입력에서 **...** 로 표시
- 변경 부분 밑줄 — 입력에서 ⟦...⟧ 로 표시 (출력에는 괄호 제거, 밑줄만)
- 미변경 부분은 대시(-----) 또는 "(현행과 같음)"/"(생  략)" 그대로 기재
- 신설/삭제는 <신  설> / <삭  제> — 셀 가운데 정렬
- 항·호 블록마다 행을 분리, 행 사이 가로 내부선 숨김(외곽선·중앙 세로선·머리행 밑선만 표시)
- 전체 흑백, 바탕 글꼴
"""
import re
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

FONT = "바탕"
BODY_PT = 11

_CENTER_ONLY = re.compile(r"^\s*<\s*신\s*설\s*>\s*$|^\s*<\s*삭\s*제\s*>\s*$")


def _set_font(run, bold=False, underline=False, size=BODY_PT):
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    run.font.size = Pt(size)
    run.bold = bold
    run.underline = underline


def _add_runs(paragraph, text):
    """**굵게**, ⟦밑줄⟧ 마크업을 해석해 run 으로 분해."""
    tokens = re.split(r"(\*\*.*?\*\*|⟦.*?⟧)", text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            inner = tok[2:-2]
            # 굵은 구간 안의 밑줄 구간 처리
            for sub in re.split(r"(⟦.*?⟧)", inner):
                if not sub:
                    continue
                if sub.startswith("⟦") and sub.endswith("⟧"):
                    _set_font(paragraph.add_run(sub[1:-1]), bold=True, underline=True)
                else:
                    _set_font(paragraph.add_run(sub), bold=True)
        elif tok.startswith("⟦") and tok.endswith("⟧"):
            _set_font(paragraph.add_run(tok[1:-1]), underline=True)
        else:
            _set_font(paragraph.add_run(tok))


def _cell_write(cell, text):
    text = (text or "").strip()
    first = True
    for line in text.split("\n"):
        p = cell.paragraphs[0] if first else cell.add_paragraph()
        first = False
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.15
        if _CENTER_ONLY.match(line):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _set_font(p.add_run(re.sub(r"\s+", " ", line.strip()).replace("< ", "<").replace(" >", ">")
                                .replace("<신 설>", "<신  설>").replace("<삭 제>", "<삭  제>")))
        else:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            _add_runs(p, line)


def _borders(tbl_el, header_rows=1):
    """외곽선 + 중앙 세로선만 표시, 내부 가로선 숨김."""
    tblPr = tbl_el.tblPr
    borders = OxmlElement("w:tblBorders")
    for tag, val in (("top", "single"), ("left", "single"), ("bottom", "single"),
                     ("right", "single"), ("insideH", "none"), ("insideV", "single")):
        el = OxmlElement(f"w:{tag}")
        el.set(qn("w:val"), val)
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tblPr.append(borders)


def _header_bottom_border(row):
    for cell in row.cells:
        tcPr = cell._tc.get_or_add_tcPr()
        tcB = OxmlElement("w:tcBorders")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "4")
        bottom.set(qn("w:color"), "000000")
        tcB.append(bottom)
        tcPr.append(tcB)


def build_comparison_docx(rows, title="취업규칙 신ㆍ구조문대비표", out_path="대비표.docx"):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(2.0)
    sec.left_margin = sec.right_margin = Cm(2.0)

    tp = doc.add_paragraph()
    tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tp.paragraph_format.space_after = Pt(16)
    _set_font(tp.add_run(title), bold=True, size=16)

    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    width = Cm(8.5)
    for cell in table.rows[0].cells:
        cell.width = width

    hdr = table.rows[0]
    for cell, label in zip(hdr.cells, ("현        행", "개   정   안")):
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(3)
        _set_font(p.add_run(label), bold=True)
    _header_bottom_border(hdr)

    for r in rows:
        row = table.add_row()
        row.cells[0].width = width
        row.cells[1].width = width
        _cell_write(row.cells[0], r.get("old", ""))
        _cell_write(row.cells[1], r.get("new", ""))

    _borders(table._tbl)
    doc.save(out_path)
    return out_path
