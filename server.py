# -*- coding: utf-8 -*-
"""취업규칙 작성·검토 MCP 서버 (원격 HTTP).

도구
1. make_comparison_table   — 신구조문대비표 .docx 생성(법제처 양식), 다운로드 URL 반환
2. review_employment_rules — 필수기재사항(근기법 §93)·개정법 반영·일반 적법성 1차 스캔
3. get_amendment_checklist — 시행일별 개정 체크리스트 원본 데이터 조회
4. extract_articles        — 취업규칙 .docx(base64)에서 장·조문 구조 추출
5. edit_docx               — .docx 본문 정확 일치 치환(치환 횟수 검증), 결과 파일 URL 반환

실행:  PUBLIC_BASE_URL=https://내도메인 PORT=8000 python server.py
"""
import os
import re
import secrets
import time
from pathlib import Path

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse

from comparison_table import build_comparison_docx
from review import review_text
from rules_data import AMENDMENT_CHECKS, MANDATORY_ITEMS
import docx_tools
import nlrc

PORT = int(os.environ.get("PORT", "8000"))
BASE_URL = os.environ.get("PUBLIC_BASE_URL", f"http://localhost:{PORT}").rstrip("/")
FILES_DIR = Path(os.environ.get("FILES_DIR", "/tmp/chwieop-files"))
FILES_DIR.mkdir(parents=True, exist_ok=True)
FILE_TTL = 60 * 60 * 24  # 24시간 보관

mcp = FastMCP(
    name="취업규칙 작성·검토",
    instructions=(
        "공인노무사의 취업규칙 작성·검토 보조 도구. "
        "신구조문대비표 생성 시 마크업: **굵게**(조문 제목), ⟦밑줄⟧(변경 부분), "
        "<신  설>/<삭  제>(단독 셀, 가운데 정렬), 미변경 부분은 대시(-----) 그대로. "
        "검토 도구의 결과는 패턴 기반 1차 스캔이므로 근거 조문과 함께 제시하되 단정하지 말 것."
    ),
)


def _store(src_path: Path, filename: str) -> str:
    # 만료 파일 정리
    now = time.time()
    for p in FILES_DIR.glob("*"):
        if p.is_file() and now - p.stat().st_mtime > FILE_TTL:
            p.unlink(missing_ok=True)
    token = secrets.token_urlsafe(16)
    safe = re.sub(r"[^\w.\-가-힣 ()]", "_", filename) or "output.docx"
    dest = FILES_DIR / f"{token}__{safe}"
    dest.write_bytes(Path(src_path).read_bytes())
    return f"{BASE_URL}/download/{token}"


@mcp.custom_route("/download/{token}", methods=["GET"])
async def download(request: Request):
    token = request.path_params["token"]
    if not re.fullmatch(r"[\w\-]{10,64}", token):
        return PlainTextResponse("잘못된 요청", status_code=400)
    matches = list(FILES_DIR.glob(f"{token}__*"))
    if not matches:
        return PlainTextResponse("파일이 없거나 보관기간(24시간)이 지났습니다.", status_code=404)
    path = matches[0]
    filename = path.name.split("__", 1)[1]
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request):
    return PlainTextResponse("ok")


@mcp.tool
def make_comparison_table(
    rows: list[dict],
    title: str = "취업규칙 신ㆍ구조문대비표",
    filename: str = "취업규칙_신구조문대비표.docx",
) -> dict:
    """신구조문대비표 .docx(법제처 양식)를 생성하고 다운로드 URL을 반환합니다.

    rows: [{"old": "현행 셀 텍스트", "new": "개정안 셀 텍스트"}, ...]
      - 항·호 블록마다 행 1개 (가로 내부선은 자동으로 숨김)
      - 마크업: **굵게**(조문 제목), ⟦밑줄⟧(변경 부분)
      - 신설/삭제 셀은 "<신  설>" / "<삭  제>" 만 기재 (자동 가운데 정렬)
      - 셀 안 줄바꿈은 \\n
      - 미변경 구간은 대시(-----)와 "(현행과 같음)", "(생  략)" 표기 그대로 입력
    """
    if not rows:
        return {"error": "rows 가 비어 있습니다."}
    tmp = FILES_DIR / f"tmp_{secrets.token_hex(6)}.docx"
    build_comparison_docx(rows, title=title, out_path=str(tmp))
    url = _store(tmp, filename)
    tmp.unlink(missing_ok=True)
    return {"download_url": url, "filename": filename, "rows": len(rows),
            "비고": "다운로드 링크는 24시간 유효"}


@mcp.tool
def review_employment_rules(text: str, scope: list[str] | None = None) -> dict:
    """취업규칙 본문 텍스트를 1차 스캔 검토합니다.

    scope(생략 시 전체): "mandatory"(근기법 §93 필수기재사항),
    "amendments"(2025~2027 시행일별 개정 반영), "general"(수습급여·가산율 등 일반 적법성)
    결과는 키워드·정규식 기반 추정이며, 각 판정에 근거 조문과 적중 위치(조문·발췌)를 포함합니다.
    """
    if not text or len(text.strip()) < 50:
        return {"error": "검토할 본문 텍스트가 너무 짧습니다. extract_articles 결과의 전체 텍스트를 넣어 주세요."}
    return review_text(text, tuple(scope) if scope else ("mandatory", "amendments", "general"))


@mcp.tool
def get_amendment_checklist(effective_from: str = "") -> dict:
    """시행일별 개정법 체크리스트 원본을 반환합니다. effective_from(예: "2026-01-01") 이후 시행분만 걸러볼 수 있습니다."""
    items = [c for c in AMENDMENT_CHECKS if c["effective"] >= effective_from] if effective_from else AMENDMENT_CHECKS
    return {"기준": "근로기준법·남녀고용평등법 등 개정(시행일순)", "항목": [
        {"시행일": c["effective"], "근거": c["law"], "요지": c["summary"]} for c in items
    ], "필수기재사항_근거": "근로기준법 제93조", "필수기재사항": [
        {"호": m["no"], "내용": m["item"]} for m in MANDATORY_ITEMS
    ]}


@mcp.tool
def extract_articles(docx_base64: str) -> dict:
    """취업규칙 .docx(base64)에서 장(章)·조문 구조를 추출합니다.

    반환: chapters, preamble, articles[{article, title, chapter, text}].
    내부적으로 run 병합을 수행하므로, 이후 edit_docx 의 find 문자열은
    이 결과의 text 원문을 그대로 사용해야 정확히 일치합니다.
    """
    try:
        data = docx_tools.b64_to_bytes(docx_base64)
        return docx_tools.extract_articles(data)
    except Exception as e:
        return {"error": f"추출 실패: {e}"}


@mcp.tool
def edit_docx(docx_base64: str, replacements: list[dict],
              filename: str = "취업규칙_수정본.docx") -> dict:
    """취업규칙 .docx 본문을 정확 일치 치환으로 편집하고 결과 파일 URL을 반환합니다.

    replacements: [{"find": "바꿀 원문", "replace": "새 문구", "expect_count": 1}, ...]
    - find 는 extract_articles 가 돌려준 본문 텍스트를 그대로 사용(띄어쓰기 포함)
    - 일치 횟수가 expect_count 와 다르면 그 항목은 적용하지 않고 사유를 보고
    - 서식(굵게·밑줄 등)은 원본 run 서식을 따르며 새로 지정하지 않음
    """
    try:
        data = docx_tools.b64_to_bytes(docx_base64)
        edited, results = docx_tools.edit_document_text(data, replacements)
    except Exception as e:
        return {"error": f"편집 실패: {e}"}
    tmp = FILES_DIR / f"tmp_{secrets.token_hex(6)}.docx"
    tmp.write_bytes(edited)
    url = _store(tmp, filename)
    tmp.unlink(missing_ok=True)
    applied = sum(1 for r in results if r["status"] == "적용")
    return {"download_url": url, "filename": filename,
            "적용": applied, "미적용": len(results) - applied, "상세": results,
            "비고": "다운로드 링크는 24시간 유효"}


@mcp.tool
def search_nlrc_cases(query: str = "", category: str = "", limit: int = 10) -> dict:
    """중앙노동위원회 주요판정사례(공공데이터포털, 2014.11~ 선별 사례 약 400건)를 검색합니다.

    query: 제목에서 찾을 키워드(예: "갱신기대권", "본채용 거부", "공정대표").
    category: 자료구분 필터(예: "징계해고", "부당노동행위", "기간만료", "차별시정") — 결과의 '자료구분 목록' 참고.
    목록(제목·자료구분·작성일자)만 제공되며, 판정서 원문은 중앙노동위원회 홈페이지(nlrc.go.kr)
    '주요사례' 메뉴에서 제목으로 찾아야 합니다. 전체 판정례 DB가 아니므로 망라적 검색에는 부적합합니다.
    """
    try:
        return nlrc.search(query, category, limit)
    except Exception as e:
        return {"error": f"판정사례 조회 실패: {e}"}


if __name__ == "__main__":
    # 인증을 두지 않는 대신 MCP_PATH 를 추측하기 어려운 문자열로 바꿔 비공개로 유지할 것
    mcp.run(transport="http", host="0.0.0.0", port=PORT,
            path=os.environ.get("MCP_PATH", "/mcp"))
