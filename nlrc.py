# -*- coding: utf-8 -*-
"""중앙노동위원회 주요판정사례 검색.

데이터: 공공데이터포털 '고용노동부 중앙노동위원회_주요판정사례'(약 399건, 2014.11~)
- 목록(메타데이터)만 제공되며 판정서 원문은 중앙노동위원회 홈페이지 '주요사례' 메뉴에 있음
- 서버 기동 후 첫 호출 시 CSV를 내려받아 로컬에 캐시(기본 30일)
"""
import csv
import io
import os
import time
import urllib.parse
import urllib.request

# 공공데이터포털 파일 직접 다운로드 (데이터셋 갱신 시 atchFileId가 바뀔 수 있어 env 로 교체 가능)
ATCH_FILE_ID = os.environ.get("NLRC_ATCH_FILE_ID", "FILE_000000003638706")
DOWNLOAD_URL = ("https://www.data.go.kr/cmm/cmm/fileDownload.do?"
                + urllib.parse.urlencode({"atchFileId": ATCH_FILE_ID, "fileDetailSn": "1",
                                          "dataNm": "중앙노동위원회_주요판정사례"}))
CACHE_PATH = os.environ.get("NLRC_CACHE", "/tmp/nlrc_cases.csv")
CACHE_TTL = 60 * 60 * 24 * 30  # 30일

_rows_cache = None


def _download() -> bytes:
    req = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "Mozilla/5.0 chwieopgyuchik-mcp"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _load_rows():
    global _rows_cache
    if _rows_cache is not None:
        return _rows_cache
    text = None
    try:
        if os.path.exists(CACHE_PATH) and time.time() - os.path.getmtime(CACHE_PATH) < CACHE_TTL:
            with open(CACHE_PATH, "rb") as f:
                text = _decode(f.read())
    except OSError:
        pass
    if text is None:
        raw = _download()
        if not raw.lstrip()[:20].count(b","):  # HTML 오류 페이지 방어
            if raw.lstrip().startswith(b"<"):
                raise RuntimeError("공공데이터포털이 CSV 대신 오류 페이지를 반환 — atchFileId 갱신 필요(NLRC_ATCH_FILE_ID)")
        try:
            with open(CACHE_PATH, "wb") as f:
                f.write(raw)
        except OSError:
            pass
        text = _decode(raw)
    reader = csv.DictReader(io.StringIO(text))
    rows = [r for r in reader if r.get("제목")]
    if not rows:
        raise RuntimeError("판정사례 CSV 파싱 결과가 비어 있음")
    _rows_cache = rows
    return rows


def search(query: str = "", category: str = "", limit: int = 10) -> dict:
    rows = _load_rows()
    q = (query or "").strip()
    cat = (category or "").strip()
    out = []
    for r in rows:
        if cat and cat not in (r.get("자료구분") or ""):
            continue
        if q and q not in (r.get("제목") or "") and q not in (r.get("자료구분") or ""):
            continue
        out.append({"자료구분": r.get("자료구분"), "제목": r.get("제목"),
                    "위원회": r.get("위원회명"), "작성일자": r.get("작성일자")})
    categories = sorted({r.get("자료구분") for r in rows if r.get("자료구분")})
    return {
        "데이터": "중앙노동위원회 주요판정사례 (공공데이터포털, 수록 2014.11~, 선별 사례 목록)",
        "주의": "목록(메타데이터)이며 판정서 원문은 중앙노동위원회 홈페이지(nlrc.go.kr) '주요사례' 메뉴에서 제목으로 검색해 확인",
        "검색어": q or "(전체)", "자료구분 필터": cat or "(전체)",
        "일치": len(out), "결과": out[:max(1, min(limit, 50))],
        "자료구분 목록": categories,
    }
