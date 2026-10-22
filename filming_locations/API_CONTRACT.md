# 독립 프론트엔드·API 규격 (F2013)

실행: `python -m uvicorn api:app --host 127.0.0.1 --port 8000`

프론트는 `frontend/index.html`, `style.css`, `app.js`, `map.html`이다. 서버 로직은 `api.py`가 공통 서비스 모듈에 위임한다. 브라우저에 GMS 키·프롬프트·스택 추적을 보내지 않는다. 현재는 로컬 개발용이며 공개 다중 사용자 서버 인증을 구현한 서비스는 아니다.

|메서드·경로|입력|출력|
|---|---|---|
|GET /|없음|독립 HTML 화면|
|GET /api/status|없음|장소 수·색인 수·AI 연결 여부·호출 수 (키 값 없음)|
|GET /api/places|없음|기본+사용자 확인 장소와 설명 문서|
|POST /api/index|빈 JSON|메타데이터/문서 색인 건수|
|POST /api/explore|condition, 최대 300자|조건을 충족한다고 선별한 matches와 실제 인용문|
|POST /api/scene|multipart image(8MB 이하), work, media_type, hint, channel, compare_photos|result, review_token, seconds|
|POST /api/chat|place_id, question(600자 이하), history(최근 최대 4메시지), mode(similarity/mmr)|answer, 실제 사용 sources(번호/제목/URL/유형), no_citations, usage, cache_hit, seconds|
|POST /api/research|place_id, question|검색어, 선택/제외 URL, 수집 문서, 실패 URL, 재사용 여부|
|POST /api/geocode|query, 최대 400자|위치 후보의 이름·좌표·OSM 링크|
|POST /api/confirm|review_token, candidate_index, confirmed, name, address, region, 선택 좌표와 좌표 확인|저장한 place, indexed 여부|

정확한 필드 형식은 실행한 서버의 `/docs`와 `/openapi.json`으로 확인할 수 있다. 검색 원문과 후보는 서버에 최대 30분/100건 보존하고 캡처 원본은 영구 저장하지 않는다. 검수 API는 클라이언트가 보내는 임의 근거 대신 서버가 반환했던 검색 결과 토큰으로 원래 근거를 찾는다. 토큰 만료 시 재검색을 요구한다.

확인 전 저장은 HTTP 400, 만료된 토큰은 410, 입력 오류는 422, 키 누락은 503, 예상하지 못한 오류는 내용이 가려진 500을 반환한다. 같은 출처/주소 중복은 새 장소를 생성하지 않고 병합한다. 지도 좌표는 별도 확인해야 한다. 다른 웹사이트 Origin의 변경 요청과 허용하지 않은 Host는 차단한다.

브라우저 채팅은 장소 ID별 메모리에 분리하며 새로고침하면 지워진다. 영구 보존은 확인한 장소 DB에만 적용한다. GMS가 없으면 자료실·필터·지도·좌표 조회·색인은 사용 가능하며 모델이 필요한 기능은 연결 전 안내를 표시한다.


추가 API (2026-10-22):

|메서드·경로|입력|출력|
|---|---|---|
|GET /api/reviews|없음|사용자 저장·취소 기록과 정정 이력|
|POST /api/revise|place_id, action(correct/withdraw/restore), changes, reason|record, indexed|
|GET /api/enrichment|없음|수집 본문 대기/승인/제외 목록|
|POST /api/enrichment/collect|빈 JSON|기존 공식 출처 최대 5개 수집 결과|
|POST /api/enrichment/review|document_id, approved|승인 후 색인 또는 제외|
|POST /api/refine|multipart review_token, image, additional_hint, compare_photos|기존 단서를 재사용한 result, 새 review_token|

/api/chat의 mode는 hybrid도 허용한다. /api/confirm은 episode(80자), scene_description(500자)를 추가로 받는다. /api/geocode는 query 외에 name/address를 받아 분리 검색한다. 정정은 사용자 저장 기록에만 적용하며 취소는 복원 가능하다. 주소 변경 시 좌표 재확인이 필요하다. 본문 대기 DB는 원문 캐시로 검토 패키지에 포함하지 않는다.
