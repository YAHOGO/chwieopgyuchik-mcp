# -*- coding: utf-8 -*-
"""국가법령정보 공동활용(open.law.go.kr) DRF API — 판례·법령해석례 검색/본문 조회."""
import json
import os
import re
import urllib.parse
import urllib.request

BASE = "https://www.law.go.kr/DRF"
OC = os.environ.get("LAW_OC", "")

_TARGET_NAMES = {"prec": "판례", "expc": "법령해석례"}


def _get(path: str, params: dict) -> dict:
    params = {"OC": OC, "type": "JSON", **params}
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "chwieopgyuchik-mcp"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        # OC 미승인 등일 때 HTML 오류 페이지가 돌아옴
        raise RuntimeError(f"API가 JSON 이 아닌 응답을 반환 — OC 승인 여부 확인 필요: {body[:200]}")


def search(target: str, query: str, display: int = 10, page: int = 1,
           scope: str = "title") -> dict:
    """target: prec(판례) | expc(법령해석례), scope: title(사건명·안건명) | body(본문)"""
    if not OC:
        return {"error": "LAW_OC 환경변수가 설정되지 않았습니다."}
    data = _get("lawSearch.do", {"target": target, "query": query,
                                 "search": 2 if scope == "body" else 1,
                                 "display": max(1, min(display, 50)), "page": page})
    root = next(iter(data.values())) if isinstance(data, dict) and data else {}
    items = root.get(target) or []
    if isinstance(items, dict):
        items = [items]
    rows = []
    for it in items:
        if target == "prec":
            rows.append({
                "판례일련번호": it.get("판례일련번호"), "사건번호": it.get("사건번호"),
                "사건명": it.get("사건명"), "법원명": it.get("법원명") or it.get("데이터출처명"),
                "선고일자": it.get("선고일자"), "사건종류": it.get("사건종류명"),
                "원문링크": "https://www.law.go.kr" + re.sub(r"OC=[^&]*", "OC=*", it.get("판례상세링크", "")),
            })
        else:
            rows.append({
                "법령해석례일련번호": it.get("법령해석례일련번호"), "안건번호": it.get("안건번호"),
                "안건명": it.get("안건명"), "질의기관": it.get("질의기관명"),
                "회신기관": it.get("회신기관명"), "회신일자": it.get("회신일자"),
                "원문링크": "https://www.law.go.kr" + re.sub(r"OC=[^&]*", "OC=*", it.get("법령해석례상세링크", "")),
            })
    return {"구분": _TARGET_NAMES.get(target, target), "검색어": query,
            "전체건수": root.get("totalCnt"), "page": root.get("page"), "결과": rows,
            "출처": "국가법령정보센터(law.go.kr) Open API"}


_STRIP_TAGS = re.compile(r"<br\s*/?>|<[^>]+>")


def _clean(text):
    if not isinstance(text, str):
        return text
    return _STRIP_TAGS.sub(lambda m: "\n" if m.group(0).lower().startswith("<br") else "", text).strip()


def detail(target: str, serial_id: str, max_chars: int = 6000) -> dict:
    """판례/해석례 본문 조회. serial_id: 판례일련번호 또는 법령해석례일련번호"""
    if not OC:
        return {"error": "LAW_OC 환경변수가 설정되지 않았습니다."}
    data = _get("lawService.do", {"target": target, "ID": serial_id})
    root = next(iter(data.values())) if isinstance(data, dict) and data else {}
    out = {"구분": _TARGET_NAMES.get(target, target), "출처": "국가법령정보센터(law.go.kr) Open API"}
    if target == "prec":
        for k in ("사건번호", "사건명", "법원명", "선고일자", "판시사항", "판결요지", "참조조문", "참조판례"):
            out[k] = _clean(root.get(k))
        body = _clean(root.get("판례내용") or "")
        out["판례내용"] = body[:max_chars] + ("…(이하 생략)" if len(body) > max_chars else "")
    else:
        for k in ("안건번호", "안건명", "회신기관명", "회신일자", "질의요지", "회답", "이유"):
            v = _clean(root.get(k))
            if isinstance(v, str) and len(v) > max_chars:
                v = v[:max_chars] + "…(이하 생략)"
            out[k] = v
    return out
