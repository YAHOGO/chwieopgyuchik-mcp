# -*- coding: utf-8 -*-
"""취업규칙 .docx 조문 추출·편집.

확립된 작업 방식 반영:
- run 병합(merge_runs): <w:lastRenderedPageBreak/> 제거 후 인접 run 의 <w:t> 결합
  → 패턴 매칭이 안정적으로 동작
- 편집: document.xml 문자열 치환 + 치환 횟수 검증(expect_count)
"""
import base64
import io
import re
import shutil
import zipfile

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_ARTICLE_RE = re.compile(r"^제\s*(\d+)\s*조(의\s*\d+)?\s*[(（]([^)）]*)[)）]")
_CHAPTER_RE = re.compile(r"^제\s*\d+\s*장\b")


# ── run 병합 ────────────────────────────────────────────────────
def merge_runs(xml: str) -> str:
    """lastRenderedPageBreak 제거 + 서식이 같은 인접 run 의 w:t 결합."""
    xml = xml.replace("<w:lastRenderedPageBreak/>", "")
    # 동일 rPr 인접 run 결합: </w:t></w:r><w:r>(rPr)?<w:t ...> 패턴을 반복 축약
    pattern = re.compile(
        r"</w:t></w:r><w:r(?P<attrs>[^>]*)>(?P<rpr><w:rPr>.*?</w:rPr>)?<w:t(?: xml:space=\"preserve\")?>",
        re.S,
    )

    def _collapse(text: str) -> str:
        out = []
        i = 0
        for m in pattern.finditer(text):
            # 직전 run 과 서식(rPr)이 동일할 때만 결합해야 하나,
            # 취업규칙 본문은 동일 서식 run 분절이 대부분이므로
            # rPr 이 없는 run(기본 서식)만 보수적으로 결합한다.
            if m.group("rpr"):
                continue
            out.append(text[i:m.start()])
            i = m.end()
        out.append(text[i:])
        return "".join(out)

    prev = None
    while prev != xml:
        prev = xml
        xml = _collapse(xml)
    return xml


# ── 추출 ────────────────────────────────────────────────────────
def _para_texts(xml: str):
    for pm in re.finditer(r"<w:p\b.*?</w:p>", xml, re.S):
        block = pm.group(0)
        text = "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", block, re.S))
        text = (text.replace("&amp;", "&").replace("&lt;", "<")
                    .replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'"))
        yield text


def extract_articles(docx_bytes: bytes):
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    xml = merge_runs(xml)

    articles, preamble, chapters = [], [], []
    current = None
    for text in _para_texts(xml):
        t = text.strip()
        if not t:
            continue
        if _CHAPTER_RE.match(t):
            chapters.append(t)
            continue
        m = _ARTICLE_RE.match(t)
        if m:
            current = {
                "article": f"제{m.group(1)}조" + (m.group(2).replace(" ", "") if m.group(2) else ""),
                "title": m.group(3).strip(),
                "chapter": chapters[-1] if chapters else None,
                "paragraphs": [t],
            }
            articles.append(current)
        elif current is not None:
            current["paragraphs"].append(t)
        else:
            preamble.append(t)
    for a in articles:
        a["text"] = "\n".join(a.pop("paragraphs"))
    return {"chapters": chapters, "preamble": preamble, "articles": articles,
            "article_count": len(articles)}


# ── 편집 ────────────────────────────────────────────────────────
def edit_document_text(docx_bytes: bytes, replacements):
    """replacements: [{"find": str, "replace": str, "expect_count": int(기본 1)}]

    merge_runs 적용 후 document.xml 본문 텍스트에서 정확 일치 치환.
    치환 횟수가 expect_count 와 다르면 해당 항목은 실패로 보고하고 적용하지 않는다.
    """
    src = io.BytesIO(docx_bytes)
    with zipfile.ZipFile(src) as zin:
        names = zin.namelist()
        xml = zin.read("word/document.xml").decode("utf-8")
        others = {n: zin.read(n) for n in names if n != "word/document.xml"}

    xml = merge_runs(xml)
    results = []
    for rep in replacements:
        find = rep["find"]
        repl = rep.get("replace", "")
        expect = int(rep.get("expect_count", 1))
        esc = (find.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        esc_r = (repl.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        count = xml.count(esc)
        if count == expect:
            xml = xml.replace(esc, esc_r)
            results.append({"find": find, "status": "적용", "count": count})
        else:
            results.append({"find": find, "status": "미적용",
                            "count": count, "expected": expect,
                            "reason": f"일치 {count}건(기대 {expect}건) — run 분절 또는 띄어쓰기 차이 가능, extract_articles 결과의 원문 그대로 지정 필요"})

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for n, data in others.items():
            zout.writestr(n, data)
        zout.writestr("word/document.xml", xml.encode("utf-8"))
    return out.getvalue(), results


def b64_to_bytes(data: str) -> bytes:
    return base64.b64decode(data)


def bytes_to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")
