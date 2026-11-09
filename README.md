# 취업규칙 작성·검토 MCP 서버

공인노무사용 취업규칙 작성·검토 보조 원격 MCP 서버입니다. claude.ai(웹·앱)에 커스텀 커넥터로 등록하면 어느 대화에서든 아래 도구를 쓸 수 있습니다.

## 도구

1. make_comparison_table — 신구조문대비표 .docx 생성(법제처 양식: 현 행/개 정 안 2열, 조문 제목 굵게, 변경 부분 밑줄, <신  설>/<삭  제> 가운데 정렬, 내부 가로선 숨김). 다운로드 URL 반환(24시간 유효)
2. review_employment_rules — 본문 텍스트 1차 스캔: 근로기준법 제93조 필수기재사항, 2025~2027 시행일별 개정 반영 여부, 수습급여·가산율 등 일반 적법성. 판정마다 근거 조문·적중 위치(조문·발췌) 포함
3. get_amendment_checklist — 시행일별 개정 체크리스트 원본 조회(2025.2.23. / 2026.8.20. / 9.18. / 11.27. / 12.10. / 2027.6.10.)
4. extract_articles — 취업규칙 .docx(base64)에서 장·조문 구조 추출(run 병합 적용)
5. edit_docx — .docx 본문 정확 일치 치환(치환 횟수 검증, 불일치 시 미적용·사유 보고), 결과 파일 URL 반환

## 파일 구성

- server.py — FastMCP 서버 본체, 다운로드 라우트(/download/{token}, /health)
- comparison_table.py — 대비표 docx 생성
- review.py / rules_data.py — 검토 로직·기준 데이터(법령 개정 시 rules_data.py만 수정)
- docx_tools.py — 조문 추출·편집(run 병합 포함)
- test_client.py — 로컬 검증 스크립트

## 로컬 실행·테스트

    pip install -r requirements.txt
    python server.py                 # http://localhost:8000/mcp
    python test_client.py            # 다른 터미널에서 5개 도구 동작 확인

## 배포 (둘 중 택1)

### A. Render (GitHub 연동)

1. 이 폴더를 GitHub 저장소로 올림
2. render.com → New → Web Service → 저장소 선택
3. Build Command: `pip install -r requirements.txt` / Start Command: `python server.py`
4. 환경변수: `PUBLIC_BASE_URL` = 배포 후 받은 주소(예: https://xxx.onrender.com), `MCP_PATH` = `/mcp-임의긴문자열`
5. 배포 완료 후 `https://xxx.onrender.com/health` 가 ok 면 정상

### B. Fly.io (CLI, 저장소 불필요)

    fly launch --no-deploy           # 폴더에서 실행, Python 자동 감지
    fly secrets set PUBLIC_BASE_URL=https://앱이름.fly.dev MCP_PATH=/mcp-임의긴문자열
    fly deploy

## claude.ai 등록

1. claude.ai → 설정 → 커넥터 → 커스텀 커넥터 추가
2. URL: `https://배포주소` + MCP_PATH (예: https://xxx.onrender.com/mcp-임의긴문자열)
3. 인증: 없음 → 추가

## 보안 주의

- 인증(OAuth)을 붙이지 않은 구성이므로, MCP_PATH 를 추측하기 어려운 긴 문자열로 설정해 사실상의 비밀키로 사용하십시오. 기본값 /mcp 그대로 공개 배포하면 누구나 접근할 수 있습니다.
- 생성·편집된 파일은 서버의 임시 저장소에 24시간 보관 후 자동 삭제됩니다. 고객사 규칙 원문이 서버를 거치므로, 필요하면 FILE_TTL(server.py)을 줄이십시오.

## 사용 예 (claude.ai 대화에서)

- "첨부한 취업규칙을 검토해줘" → extract_articles → review_employment_rules → 근거 조문별 결과
- "제38조 개정 신구조문대비표 만들어줘" → make_comparison_table → 다운로드 링크
- "2026년 하반기 시행분 뭐 남았지" → get_amendment_checklist(effective_from="2026-07-01")

## 유지보수

새 개정법은 rules_data.py 의 AMENDMENT_CHECKS 에 항목(시행일·근거·요지·구법/신법 패턴)만 추가하면 됩니다. 2026.9.18. / 12.10. / 2027.6.10. 시행분은 요지만 수록되어 있으므로 법령 원문 확정 후 패턴을 보강하십시오.
