"""사용자가 요청할 때만 공개 지오코더의 위치 후보를 조회한다."""
import requests
from services import cache
from services.throttle import wait_turn


def _lookup_one(query):
    query = query.strip()[:400]
    if not query:
        return []
    key = cache.digest(['photon-v2', query])
    previous = cache.get('geocode', key)
    if previous is not None:
        return previous
    endpoint = 'https://photon.komoot.io/api/'
    wait_turn(endpoint, interval=1.1)
    response = requests.get(endpoint, params={'q': query, 'limit': 5},
                            headers={'User-Agent': 'SceneFinder/0.1 (user-requested-location-review)'}, timeout=15)
    response.raise_for_status()
    output = []
    for feature in response.json().get('features', []):
        coordinates = feature.get('geometry', {}).get('coordinates', [])
        properties = feature.get('properties', {})
        if len(coordinates) != 2:
            continue
        lon, lat = coordinates
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            continue
        label = ' · '.join(str(properties.get(k, '')) for k in ('name', 'street', 'city', 'state', 'country') if properties.get(k))
        output.append(dict(label=label, latitude=lat, longitude=lon,
                           source=f'https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}'))
    if output:
        cache.put('geocode', key, output, 7)
    return output


def lookup(query, *, name="", address=""):
    """전체 검색 실패 시 주소와 장소명을 분리한다. 실패를 결과 없음으로 숨기지 않는다."""
    variants = [query.strip()[:400]]
    if address.strip():
        expanded = address.strip()
        for short, full in [('경기 ', '경기도 '), ('서울 ', '서울특별시 '), ('부산 ', '부산광역시 ')]:
            if expanded.startswith(short):
                expanded = full + expanded[len(short):]
                break
        variants.extend([expanded, address.strip()])
    if name.strip():
        variants.append(name.strip())
    variants = list(dict.fromkeys(v for v in variants if v))[:4]
    if not variants:
        return []
    for variant in variants:
        # 통신/서비스 오류는 같은 서버에 연속 재시도하지 않는다.
        points = _lookup_one(variant)
        if points:
            return [dict(point, query_used=variant) for point in points]
    return []
