# -*- coding: utf-8 -*-
"""취업규칙 본문 텍스트 검토 로직."""
import re
from rules_data import MANDATORY_ITEMS, AMENDMENT_CHECKS, GENERAL_CHECKS

_ARTICLE_SPLIT = re.compile(r"(?=^제\s*\d+\s*조(?:의\s*\d+)?\s*[(（])", re.M)


def _locate(text: str, span_start: int) -> str:
    """적중 위치가 속한 조문 번호를 찾아 근거로 제시."""
    head = text[:span_start]
    matches = re.findall(r"제\s*\d+\s*조(?:의\s*\d+)?\s*[(（][^)）]*[)）]", head)
    return matches[-1].replace(" ", "") if matches else "조문 식별 불가(서두 부분)"


def _scan(text: str, patterns):
    hits = []
    for pat in patterns:
        for m in re.finditer(pat, text):
            snippet = text[max(0, m.start() - 15): m.end() + 15].replace("\n", " ")
            hits.append({"위치": _locate(text, m.end()), "발췌": f"…{snippet}…"})
    return hits


def review_text(text: str, scope=("mandatory", "amendments", "general")):
    report = {"주의": "키워드·패턴 기반 1차 스캔 결과입니다. 최종 판단은 법령 원문 대조로 확정하십시오."}

    if "mandatory" in scope:
        rows = []
        for item in MANDATORY_ITEMS:
            found = [kw for kw in item["keywords"] if kw in text]
            rows.append({
                "근거": f"근로기준법 제93조 {item['no']}",
                "기재사항": item["item"],
                "판정": "기재 추정" if found else ("판단 보류(키워드 없음)" if item["keywords"] else "개별 확인 필요"),
                "탐지 키워드": found,
            })
        report["필수기재사항"] = rows

    if "amendments" in scope:
        rows = []
        for chk in AMENDMENT_CHECKS:
            old_hits = _scan(text, chk["old_patterns"])
            new_hits = _scan(text, chk["new_patterns"])
            if old_hits and not new_hits:
                status = "구법 조항 잔존 의심"
            elif new_hits:
                status = "개정 반영 추정" + (" (구법 표현 병존 — 확인 필요)" if old_hits else "")
            else:
                status = "관련 조항 미발견 — 기재 여부 확인 필요"
            rows.append({
                "시행일": chk["effective"], "근거": chk["law"], "개정 요지": chk["summary"],
                "판정": status, "구법 패턴 적중": old_hits, "신법 패턴 적중": new_hits,
            })
        report["개정법 반영"] = rows

    if "general" in scope:
        rows = []
        for chk in GENERAL_CHECKS:
            risk = _scan(text, chk["risk_patterns"])
            ok = _scan(text, chk["ok_patterns"])
            rows.append({
                "근거": chk["law"], "점검사항": chk["summary"],
                "판정": "위험 패턴 적중 — 검토 필요" if risk and not ok else ("적정 기재 추정" if ok else "해당 없음/미발견"),
                "위험 패턴 적중": risk, "적정 패턴 적중": ok,
            })
        report["일반 적법성"] = rows

    return report
