# 출처·라이선스 검토 기록 (2026-10-21)

## 데이터와 화면 자료

|자료|확인 내용|처리·남은 범위|
|---|---|---|
|한국문화정보원 영화 촬영지 CSV|공공데이터포털 무료·이용허락범위 제한 없음|원문 URL·행 번호·출처 보존, 266곳/269개 설명. 다른 웹 자료 권리까지 허가하는 것은 아님|
|기관·운영사 촬영 안내 23개 요약|사실 요약과 링크를 저장|원문 전문 재배포 권한 주장 없음|
|영화 예시 이미지 3개|제공 페이지와 위치 근거 표시|권리자의 재배포 허가 확인 못함. 공개 배포 전 허락 확보 또는 사용 가능한 이미지로 교체 필요|
|추가 수집 원문·사용자 캡처|개별 권리와 개인정보 확인 필요|원문 캐시·스크린샷 원본은 검토 ZIP에서 제외. 검색 결과는 사용자 검수 전 DB에 저장하지 않음|

CSV 출처: https://www.data.go.kr/data/15111405/fileData.do

## 소프트웨어와 모델

|구성요소|라이선스|기록|
|---|---|---|
|Leaflet 1.9.4|BSD-2-Clause|THIRD_PARTY_LICENSES/Leaflet-BSD-2-Clause.txt|
|Leaflet.markercluster 1.5.3|MIT|THIRD_PARTY_LICENSES/Leaflet-markercluster-MIT.txt|
|Leaflet.heat 0.2.0|BSD-2-Clause|THIRD_PARTY_LICENSES/Leaflet-heat-BSD-2-Clause.txt|
|Gowun Dodum|SIL OFL 1.1|THIRD_PARTY_LICENSES/Gowun-Dodum-OFL.txt|
|paraphrase-multilingual-MiniLM-L12-v2|Apache-2.0|THIRD_PARTY_LICENSES/Apache-2.0.txt 및 모델 카드|

원문 URL·다운로드 기록은 THIRD_PARTY_LICENSES/manifest.json에 보존했다. Python 의존성은 requirements.txt로 설치하며 라이브러리·모델 바이너리를 ZIP에 묶지 않는다.

## 외부 서비스

- OpenStreetMap 표준 타일 URL과 지도 내 저작자 표기를 유지한다. 대량/오프라인 다운로드 기능 없음. 로컬 개발용이며 서비스 트래픽이 늘면 정책에 맞는 타일 제공자를 선택해야 한다. https://operations.osmfoundation.org/policies/tiles/
- Photon 공개 데모는 주소를 요청할 때만 호출하고 요청 간격·캐시를 사용한다. 운영 규모에서 별도 서버/제공자 검토 필요. https://github.com/komoot/photon
- 새 웹 수집은 공개 URL 검사, robots.txt 허용 여부, 호스트별 간격을 적용한다. 정책을 확인하지 못하면 수집하지 않는다. robots 허용은 본문 재배포 허가와 별개다.
- 위키는 연락처 설정과 출처·라이선스 표시가 필요하다. 현재 데이터 준비에 위키 호출은 필요하지 않다.

권리자 허락이나 외부 교육생 검수를 임의로 완료 처리하지 않았다. 이 문서는 구현에 사용한 출처 확인 기록이며 법률상 이용 허가서가 아니다.
