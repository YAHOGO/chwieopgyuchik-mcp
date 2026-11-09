# -*- coding: utf-8 -*-
"""로컬 동작 검증 스크립트."""
import asyncio
import base64
import json
import urllib.request

from docx import Document
from fastmcp import Client

ROWS = [
    {"old": "**제20조(근로시간)** ① (생  략)",
     "new": "**제20조(⟦근로일 및 근로시간⟧)** ① (현행과 같음)"},
    {"old": "② 회사의 시업시간 및 종업시각은 08:00-17:00로 한다. 다만, 업무상 필요하다고 인정되는 경우에는 대표이사와 직원이 합의하여 시업 및 종업시각을 달리 정할 수 있다.",
     "new": "② 회사의 ⟦근로일 및 시업시각과 종업시각은 월∼금 09:00-18:00⟧-----. 다만, ------------------------------ 대표이사는 ⟦직원과 협의하여 근로일 및 시업시각과 종업시각을 변경⟧--------."},
    {"old": "② 근로자의 날(5.1)은 유급휴일로 부여한다.",
     "new": "<삭  제>"},
    {"old": "<신  설>",
     "new": "4. 육아기 근로시간 단축을 사용하여 단축된 근로시간"},
    {"old": "**제38조(배우자출산휴가)** ① 회사는 직원이 배우자의 출산을 이유로 휴가를 청구하는 경우에 10일의 휴가를 주어야 하며 이 기간은 유급으로 한다.",
     "new": "**제38조(배우자출산휴가)** ① ------------------------------------------- ⟦고지⟧---------- ⟦20일⟧----------------------------------------."},
]


def make_sample_rules_docx(path: str):
    doc = Document()
    doc.add_paragraph("취업규칙")
    doc.add_paragraph("제1장 총칙")
    doc.add_paragraph("제1조(목적) 이 규칙은 주식회사 OO의 직원의 근로조건을 정함을 목적으로 한다.")
    doc.add_paragraph("제5장 모성보호")
    doc.add_paragraph("제38조(배우자출산휴가) ① 회사는 직원이 배우자의 출산을 이유로 휴가를 청구하는 경우에 10일의 휴가를 주어야 하며 이 기간은 유급으로 한다.")
    doc.add_paragraph("② 배우자출산휴가는 직원의 배우자가 출산한 날로부터 90일이 지나면 청구할 수 없다.")
    doc.add_paragraph("제42조(육아기 근로시간 단축) ① 회사는 직원이 만 8세 이하 또는 초등학교 2학년 이하의 자녀를 양육하기 위하여 근로시간의 단축을 신청하는 경우에 이를 허용해야 한다.")
    doc.add_paragraph("제51조(수습기간 중의 급여) 수습기간을 두는 경우 당해 직원의 임금은 최저임금법에 따른 최저시급의 90%를 하한선으로 산정한다.")
    doc.add_paragraph("제55조(임금) 임금은 매월 1일부터 말일까지 산정하여 25일에 지급하며, 승급은 연 1회 실시한다. 직장 내 괴롭힘, 표창과 징계, 안전과 보건, 퇴직금, 재해 부조에 관한 사항은 별도 장에서 정한다.")
    doc.save(path)


async def main():
    async with Client("http://localhost:8000/mcp") as c:
        tools = await c.list_tools()
        print("TOOLS:", [t.name for t in tools])

        # 1) 대비표 생성
        r1 = await c.call_tool("make_comparison_table", {"rows": ROWS})
        print("TABLE:", json.dumps(r1.data, ensure_ascii=False))
        urllib.request.urlretrieve(r1.data["download_url"], "/home/claude/chwieopgyuchik-mcp/out_table.docx")

        # 2) 샘플 취업규칙 추출
        make_sample_rules_docx("/home/claude/chwieopgyuchik-mcp/sample_rules.docx")
        b64 = base64.b64encode(open("/home/claude/chwieopgyuchik-mcp/sample_rules.docx", "rb").read()).decode()
        r2 = await c.call_tool("extract_articles", {"docx_base64": b64})
        print("EXTRACT:", json.dumps(r2.data, ensure_ascii=False)[:600])

        # 3) 검토
        full_text = "\n".join(a["text"] for a in r2.data["articles"])
        r3 = await c.call_tool("review_employment_rules", {"text": full_text})
        print("REVIEW(발췌):")
        for row in r3.data["개정법 반영"]:
            if row["판정"] != "관련 조항 미발견 — 기재 여부 확인 필요":
                print(" -", row["시행일"], row["근거"], "→", row["판정"], row["구법 패턴 적중"][:1] or row["신법 패턴 적중"][:1])
        for row in r3.data["일반 적법성"]:
            print(" *", row["근거"], "→", row["판정"])

        # 4) 편집 (배우자출산휴가 10일→20일)
        r4 = await c.call_tool("edit_docx", {
            "docx_base64": b64,
            "replacements": [
                {"find": "휴가를 청구하는 경우에 10일의 휴가", "replace": "휴가를 고지하는 경우에 20일의 휴가", "expect_count": 1},
                {"find": "존재하지 않는 문구", "replace": "x", "expect_count": 1},
            ],
        })
        print("EDIT:", json.dumps({k: r4.data[k] for k in ("적용", "미적용", "상세")}, ensure_ascii=False))
        urllib.request.urlretrieve(r4.data["download_url"], "/home/claude/chwieopgyuchik-mcp/out_edited.docx")

        # 5) 체크리스트 조회
        r5 = await c.call_tool("get_amendment_checklist", {"effective_from": "2026-01-01"})
        print("CHECKLIST 2026+:", json.dumps(r5.data["항목"], ensure_ascii=False))


asyncio.run(main())
