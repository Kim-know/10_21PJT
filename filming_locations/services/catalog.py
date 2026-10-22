"""촬영지 데이터 입력 경계. 실제 확인한 데이터만 목록에 등록한다."""
from math import isfinite
from urllib.parse import urlparse


def validate_locations(records: object) -> list[dict]:
    if not isinstance(records, list):
        raise ValueError("JSON 최상위는 촬영지 목록([])이어야 합니다.")
    ids = set()
    for item in records:
        if not isinstance(item, dict):
            raise ValueError("각 촬영지는 객체여야 합니다.")
        for field in ("id", "name", "region", "address", "wiki_title"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"필수 문자열 누락: {field}")
        if item["id"] in ids:
            raise ValueError("촬영지 ID가 중복되었습니다.")
        ids.add(item["id"])
        if not isinstance(item.get("works"), list) or not all(
            isinstance(work, str) and work.strip() for work in item["works"]
        ) or not item["works"]:
            raise ValueError("works에는 관련 작품 이름을 하나 이상 넣으세요.")
        url = urlparse(item.get("source_url", ""))
        if url.scheme not in ("https", "http") or not url.netloc:
            raise ValueError("source_url에는 촬영 관계를 확인한 원문 URL을 넣으세요.")
        for field, limit in (("latitude", 90), ("longitude", 180)):
            value = item.get(field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
                or not isfinite(value) or abs(value) > limit
            ):
                raise ValueError(f"좌표 범위 오류: {field}")
        if (item.get("latitude") is None) != (item.get("longitude") is None):
            raise ValueError("위도와 경도는 함께 입력하세요.")
    return records
