"""한국문화정보원 원본에서 영화만 추출하고 확인한 공식 문서 요약을 결합한다.

실행: python scripts/import_research.py
네트워크·GMS 호출 없음. 수집한 원본과 curated_sources.json으로 재현한다.
"""
import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.catalog import validate_locations

DATA = ROOT / "data"
RESEARCH = DATA / "research"
SOURCE = "https://www.data.go.kr/data/15111405/fileData.do"
CHECKED = "2026-10-21"
ALIASES = {"광해": "광해, 왕이 된 남자", "리틀포레스트": "리틀 포레스트",
           "공동경비구역JSA": "공동경비구역 JSA", "아이캔스피크": "아이 캔 스피크"}
QUARANTINE = {
    "1234": "여의도공원과 여의도한강공원 혼동. 서울시 자료 기준 한강공원을 별도 등록.",
    "1372": "원본 설명이 배우들의 식사 장소이며 촬영 사실이 아님.",
    "1373": "원본 설명이 배우들의 휴식 장소이며 촬영 사실이 아님.",
    "4600": "명량대첩 역사 현장 설명만 있음. 실제 촬영 관계 미확인.",
}
PRIORITY = ["명량", "극한직업", "신과함께-죄와 벌", "국제시장", "베테랑", "도둑들",
            "7번방의 선물", "암살", "범죄도시2", "광해, 왕이 된 남자", "왕의 남자",
            "신과함께-인과 연", "택시운전사", "태극기 휘날리며", "부산행", "해운대",
            "변호인", "실미도", "기생충", "괴물", "서울의 봄", "파묘", "범죄도시3", "범죄도시4"]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize(value):
    return re.sub(r"\s+", "", value).casefold()


def run():
    original = (RESEARCH / "kcisa_filming_20221125.csv").read_bytes()
    text = original.decode("utf-8-sig") if original.startswith(b"\xef\xbb\xbf") else original.decode("cp949")
    all_rows = list(csv.DictReader(io.StringIO(text)))
    films = [r for r in all_rows if r["미디어타입"] == "movie"]
    # 원본 영화 관계는 탈락 항목까지 모두 보존한다.
    write_json(RESEARCH / "movie_rows_original.json", films)
    by_key, by_row, quarantine = {}, {}, []
    for row in films:
        if row["연번"] in QUARANTINE:
            quarantine.append({"row": row, "reason": QUARANTINE[row["연번"]]})
            continue
        address, name = row["주소"].strip(), row["장소명"].strip()
        key = normalize(name) + "|" + normalize(address)
        work = ALIASES.get(row["제목"], row["제목"])
        item = by_key.setdefault(key, {
            "id": "kcisa-" + row["연번"], "name": name, "address": address,
            "region": address.split()[0], "works": [], "verified_works": [],
            "wiki_title": name, "wiki_title_status": "미확인 검색 후보",
            "source_url": SOURCE, "source_provider": "한국문화정보원",
            "source_basis_date": row["최종작성일"], "collected_at": CHECKED,
            "verification_status": "공공데이터 수록·촬영 관계 재검증 전",
            "visit_status": "현재 운영·개방 여부 미확인", "latitude": None, "longitude": None,
            "coordinate_status": "원본 좌표·현장 정밀도 미검증", "relations": [],
            "research_documents": [], "research_notes": [],
        })
        if work not in item["works"]:
            item["works"].append(work)
        item["relations"].append({"work": work, "source_row_id": row["연번"],
                                   "description": row["장소설명"], "source_url": SOURCE,
                                   "status": "dataset_only", "basis_date": row["최종작성일"]})
        try:
            lat, lon = float(row["위도"]), float(row["경도"])
            if 32 <= lat <= 39 and 124 <= lon <= 132:
                item["latitude"], item["longitude"] = lat, lon
        except ValueError:
            pass
        by_row[row["연번"]] = item

    curated = json.loads((RESEARCH / "curated_sources.json").read_text(encoding="utf-8"))
    for entry in curated:
        if "match_row" in entry:
            item = by_row[entry["match_row"]]
        else:
            key = "curated|" + entry["key"]
            item = by_key.setdefault(key, {
                "id": "curated-" + entry["key"], "name": entry["name"],
                "region": entry["region"], "address": entry["address"],
                "works": [], "verified_works": [], "wiki_title": entry["name"],
                "wiki_title_status": "미확인 검색 후보", "source_basis_date": "개별 문서 참조",
                "collected_at": CHECKED, "latitude": None, "longitude": None,
                "coordinate_status": "미확보", "relations": [], "research_documents": [],
                "research_notes": [], "visit_status": "현재 운영·개방 여부 미확인",
            })
        for field in ("name", "address", "region", "location_type", "address_precision"):
            if field in entry:
                item[field] = entry[field]
        for work in entry["works"]:
            if work not in item["works"]:
                item["works"].append(work)
            if work not in item["verified_works"]:
                item["verified_works"].append(work)
            item["relations"].append({"work": work, "source_url": entry["url"],
                                       "status": "official_document_checked", "checked_at": CHECKED})
        item.update(source_url=entry["url"], source_provider=entry["publisher"],
                    verification_status="일부 또는 전체 작품의 촬영 관계 문서 확인")
        item["research_documents"].append({
            "title": entry["title"], "url": entry["url"], "text": entry["summary"],
            "source_type": "공식 문서의 사실 요약(조사자 작성)", "publisher": entry["publisher"],
            "checked_at": CHECKED, "is_summary": True,
            "additional_urls": entry.get("additional_urls", []),
        })
        if entry.get("note"):
            item["research_notes"].append(entry["note"])

    catalog = list(by_key.values())
    # 공공데이터의 원문 '장소설명'을 별도 외부 문서로 보존한다.
    # 메타데이터를 재서술하거나 독립 검증된 설명으로 승격하지 않는다.
    for item in catalog:
        for relation in item['relations']:
            if relation.get('source_row_id') and relation.get('description', '').strip():
                item['research_documents'].append({
                    'document_id': 'kcisa-row-' + relation['source_row_id'],
                    'title': item['name'] + ' · ' + relation['work'] + ' 원문 장소설명',
                    'url': SOURCE, 'text': relation['description'].strip(),
                    'source_type': '공공데이터 원문(촬영 관계 재검증 전)',
                    'publisher': '한국문화정보원', 'collected_at': CHECKED,
                    'basis_date': relation.get('basis_date', ''),
                    'license': '공공데이터포털 표기: 이용허락범위 제한 없음',
                    'source_row_id': relation['source_row_id'], 'is_summary': False,
                })
    catalog.sort(key=lambda p: (not bool(p["verified_works"]),
                  not bool(set(p["works"]) & set(PRIORITY)), p["region"], p["name"]))
    validate_locations(catalog)
    write_json(DATA / "locations.json", catalog)
    write_json(RESEARCH / "quarantine.json", quarantine)
    coverage = [{"work": work,
                 "locations": sum(work in p["works"] for p in catalog),
                 "separately_checked_locations": sum(work in p["verified_works"] for p in catalog),
                 "status": "수집됨" if any(work in p["works"] for p in catalog) else "추가 수집 필요"}
                for work in PRIORITY]
    write_json(RESEARCH / "priority_coverage.json", coverage)
    manifest = {
        "collected_at": CHECKED, "provider": "한국문화정보원", "source_url": SOURCE,
        "download_url": "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003000299&fileDetailSn=1&insertDataPrcus=N",
        "license": "공공데이터포털 표기: 이용허락범위 제한 없음, 무료",
        "license_scope": "원본 CSV. 추가 조사한 웹 문서의 본문·사진에 일괄 적용되지 않음.",
        "sha256": hashlib.sha256(original).hexdigest(), "bytes": len(original),
        "raw_rows": len(all_rows), "media_types": dict(Counter(r["미디어타입"] for r in all_rows)),
        "movie_rows": len(films), "original_movies": len({r["제목"] for r in films}),
        "quarantined_rows": len(quarantine), "catalog_locations": len(catalog),
        "catalog_movies": len({w for p in catalog for w in p["works"]}),
        "separately_checked_locations": sum(bool(p["verified_works"]) for p in catalog),
        "separately_checked_relations": sum(len(p["verified_works"]) for p in catalog),
        "locations_with_documents": sum(bool(p['research_documents']) for p in catalog),
        "description_documents": sum(len(p['research_documents']) for p in catalog),
        "scope": "국내 영화 촬영 장소. 드라마·예능·가수 항목 제외. 세계 모든 영화 촬영지를 망라한 목록은 아님.",
    }
    write_json(RESEARCH / "manifest.json", manifest)
    lines = ["# 영화 촬영지 수집 결과", "", f"조사일: {CHECKED}", "",
             f"원본 {len(all_rows):,}행 → 영화 {len(films)}행 → 장소 {len(catalog)}곳.",
             f"별도 문서 확인: {manifest['separately_checked_locations']}곳 / {manifest['separately_checked_relations']}개 작품·장소 관계.", "",
             "|작품|수집 장소|별도 문서 확인 장소|", "|---|---:|---:|"]
    lines += [f"|{c['work']}|{c['locations']}|{c['separately_checked_locations']}|" for c in coverage]
    (RESEARCH / "collection_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
