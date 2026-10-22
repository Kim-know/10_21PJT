"""사용자가 요청할 때만 공개 지오코더의 위치 후보를 조회한다."""
import requests
from services import cache
from services.throttle import wait_turn


def lookup(query):
    query = query.strip()[:400]
    if not query:
        return []
    key = cache.digest(['photon-v1', query])
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
