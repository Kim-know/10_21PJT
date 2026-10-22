# 장면에서 여행으로

**프로젝트 주제: 영상 제목과 캡처로 촬영지를 찾아 검수하고 지도에 축적하는 RAG 서비스**

주제 설명과 발표용 소개는 `PROJECT_OVERVIEW.md`에 정리했습니다.

영상 제목과 붙여넣은 캡처로 촬영지 후보를 찾고, 촬영지 자료실에서 문서 근거로 질문하는 Streamlit 서비스입니다.

## 현재 구현

- 영화·드라마·유튜브·기타 영상 제목 + Ctrl+V 캡처, 단서 분석·외부 검색·장소 후보와 근거·지도 표시.
- 촬영 장소 266곳 / 관련 영화 69편 / 설명 자료 연결 266곳 / 외부 자료 292건.
- 설명 자료는 공공 CSV의 원문 장소설명 269건과 별도 조사 요약 23건입니다. 문서를 새로 창작하거나 촬영 사실 검증 완료로 승격하지 않습니다.
- Chroma `location_meta` 266건, `location_documents` 292개 청크를 실제 생성했습니다.
- 로컬 다국어 MiniLM 의미 임베딩. GMS 임베딩 호출 없이 동작합니다.
- 유사도/MMR 검색 전환 및 설정별 실제 근거 비교 보고서.
- LangGraph `retrieve → generate`, 선택 장소 메타데이터 상시 포함, 장소별 외부 문서 검색·중복 제거·Top-k.
- 자료실의 자연어 조건 탐색: 의미 검색 후 LLM으로 조건 충족 항목 선별, 실제 문구 검증, 선택한 장소 채팅으로 이동.
- 질문별 외부 문서 수집: 검색어 추출 프롬프트 → 후보 선별 프롬프트 → 원문 수집·색인. 기존 장소 자체 문서는 선별과 관계없이 색인합니다.
- 근거 번호와 사용한 문서 제목·출처 유형·원문 링크 표시, 장소별 대화 격리.
- 진행 상태·키 누락·색인 없음·오류 안내, 비용 한도·캐시.

## 실행

Python 3.10 이상, 권장 3.12. 프로젝트 폴더에서 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe scripts/import_research.py
.\.venv\Scripts\python.exe scripts/build_index.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

`.env`에 `GMS_KEY`, 실제 계정의 텍스트 모델 `GMS_MODEL`, 이미지 지원 모델 `GMS_VISION_MODEL`을 설정합니다. 위키 수집을 쓰려면 `WIKI_CONTACT`에 영문 연락처를 입력합니다. 키는 소스에 넣거나 공유하지 않습니다.

최초 색인은 다국어 임베딩 모델을 인터넷에서 다운로드합니다. 이후 `.models`에 저장한 모델을 재사용합니다. 자료실의 `기본 자료 색인 / 갱신`으로도 색인할 수 있습니다. `.vectors`가 없는 다른 PC에서는 재색인해야 합니다.

키가 없으면 자료·지도·입력·색인을 확인할 수 있습니다. 실제 모델이 필요한 채팅·조건 선별·검색어 생성·캡처 판단은 키 연결이 필요합니다.

## 검색 결과 검수 후 추가 저장

검색 결과마다 **찾던 장소가 맞나요?**가 표시됩니다. `맞아요`를 선택하고 장소명·주소·지역을 검수한 뒤 저장 버튼을 눌러야 영구 저장됩니다. `검토 중` 또는 `다른 장소예요`는 저장하지 않습니다.

지도 위치는 Photon/OpenStreetMap 후보 검색 또는 직접 입력으로 확인합니다. 좌표 확인 체크 전에는 지도 저장을 진행할 수 없습니다. 좌표 없이 자료실에만 저장하는 선택지도 있습니다. 지오코더는 동명 장소를 반환할 수 있으므로 자동으로 정답 좌표로 승인하지 않습니다. 위치 후보 조회에는 GMS 토큰을 쓰지 않습니다.

저장은 `data/confirmed_locations.sqlite3`에 보관하며 기본 JSON 재생성과 분리됩니다. 같은 장소명·주소는 중복 추가하지 않고 작품·근거를 병합합니다. 사용자 확인 표시는 공식 촬영 사실 검증과 구분됩니다. 저장 후 로컬 벡터 색인을 갱신하고, 자료실·지도와 이후 캡처 검색에 사용합니다. 색인이 실패하면 DB 저장은 유지하고 자료실에서 재색인 안내를 표시합니다.

기존 기본 자료에 같은 장소가 있으면 기존 ID를 사용합니다. 기본 자료에 이미 있는 좌표는 조용히 교체하지 않습니다. 새로 받은 좌표는 기존 좌표가 비어 있을 때 반영합니다. 추가된 모든 사용자 데이터는 `confirmed_locations.sqlite3`를 별도로 백업해야 하며, 캐시 DB와 다릅니다. 외부 공개·제출 전 저장된 출처·주소·이용 조건을 검토하세요.

검증: `python check_confirmed.py`는 임시 DB에서 미승인 무저장, 좌표 확인, 저장 지속성, 중복 병합, 검수 UI, 자료실 이동을 검증합니다.

## 호출별 GMS 비용

| 작업 | GMS 사용 |
|---|---|
| 데이터 재생성·로컬 임베딩·색인·의미 검색 | 없음 |
| 기존 설명 자료 채팅 | 보통 1회 |
| 자연어 조건 탐색 | 후보 선별 1회 |
| 질문으로 외부 자료 추가 | 새 수집 보통 2회, 완료 수집 재사용 시 없음 |
| 캡처 장소 검색 | 새 검색 보통 2회 |

기본 하루 최대 30회 시도, 자동 모델 재시도 없음. 자료실 출력 600토큰, 청크 700자/겹침 100자, 전체 Top-k 3(메타데이터 1건 포함), 근거 본문 2,600자, 이력 최근 최대 2턴·1,000자입니다. `.env.example`에서 변경할 수 있습니다. 호출 실패도 일일 시도에 포함합니다.

웹/모델 단기 캐시는 `.cache`, 완료된 자료 수집과 검색어·원문은 `data/collected`, 벡터는 `.vectors`에 보관합니다. 수집 완료 상태는 TTL 없이 재사용하므로 최신 정보가 자동 반영되는 것은 아닙니다. 캐시는 계정 전체 금액 한도가 아닙니다.

## 설계·검증·출처

- `RAG_DESIGN.md`: 컬렉션·프롬프트·검색·제약과 출처 이용 조건.
- `REQUIREMENTS_CHECKLIST.md`: 최초 진단 기록과 현재 보완 상태 안내.
- `IMPLEMENTATION_STATUS.md`: 보완 후 요구사항별 결과 및 미확인 사항.
- `data/research/manifest.json`: 데이터 출처·이용 안내·건수·해시.
- `data/research/README.md`: 원본·촬영 관계 검증 범위.

```powershell
python check_rag.py
python check_scene.py
python check_app.py
python check_savings.py
python check_grounding.py
python check_confirmed.py
python scripts/verify_project.py
python scripts/run_checks.py
python scripts/package_project.py
python -m pip check
```

`check_rag.py`는 실제 로컬 모델·Chroma·그래프 연결을 검증하고, GMS와 외부 수집은 모의 응답을 사용합니다. 다른 테스트도 실제 GMS를 호출하지 않습니다. Windows Chroma가 임시 mmap 파일을 유지하면 테스트 임시 폴더 정리는 프로세스 종료 후 필요할 수 있습니다.

## 범위와 남은 확인

자료실 항목은 **장소**입니다. 266곳 전체가 촬영 사실 재검증 완료인 것은 아니며 별도 촬영 관계를 확인한 장소는 23곳입니다. 공공 원문은 짧거나 오래됐을 수 있고, 영업·출입·정밀 좌표를 보증하지 않습니다. 문서가 있어도 모든 질문에 답할 수 있는 것은 아닙니다.

실제 GMS 연결·지원 모델·답변 품질·전체 응답 시간은 아직 검증하지 않았습니다. 실제 실행 증거와 상호 점검은 별도 필요합니다. MMR은 구현·로컬 비교를 완료했고 독립 프론트/서버와 실제 RAG 전후 답변 품질 비교는 미구현/미실행입니다.

원본 `C:/Users/SSAFY/Desktop/streamlit_lab`의 소스는 변경하지 않았습니다. 실행용 venv에는 필수 라이브러리를 추가했습니다. 제출물에서 `.env`, `.models`, `.vectors`, `.cache`, 가상환경, 재배포 조건을 확인하지 않은 수집 원문은 제외하고 재생성 절차를 제공하세요.


## 독립 HTML/JS 화면과 API 서버

프로젝트 폴더에서 `python -m uvicorn api:app --host 127.0.0.1 --port 8000`을 실행하고 http://127.0.0.1:8000 으로 접속한다. 기존 Streamlit 화면은 `streamlit run app.py`로 유지된다. 두 화면은 동일한 카탈로그·확인 DB·벡터 저장소를 사용한다. `.env` 변경 후 서버를 재시작한다. 키는 브라우저에 전달하지 않는다.

독립 화면도 Ctrl+V 캡처, 매체 선택, 검수 후 DB 저장, 지도 핀과 상세 연결, 장소별 대화, MMR, 조건 탐색, 문서 수집을 제공한다. GMS 키가 없으면 자료실·지도·로컬 색인을 사용할 수 있다. 로컬 개발용이며 인터넷 공개용 인증·사용자별 저장 격리는 범위에 포함되지 않는다.

검사: `python scripts/run_checks.py`, `python scripts/verify_project.py`, `python scripts/compare_rag.py`. 마지막 명령의 기본 실행은 토큰을 쓰지 않는다. `--run-gms`는 실제 호출이므로 이번 검수에서는 실행하지 않았다.

최종 판정은 FINAL_CHECKLIST.md, 출처·권리 검토는 LICENSE_REVIEW.md, 교육생 상호 검수용 빈 양식은 PEER_REVIEW.md에 있다.
