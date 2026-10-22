"""원문 수집 전 공개 robots 규칙 확인. 수집 허용과 재배포 허가는 별개다."""
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from services import cache

AGENT = 'SceneFinder/0.1'


def allowed(url):
    parsed = urlparse(url)
    origin = f'{parsed.scheme}://{parsed.netloc}'
    stored = cache.get('robots_policy_v1', origin)
    if stored is None:
        from services.web_search import fetch_public
        try:
            body, _, _ = fetch_public(urljoin(origin, '/robots.txt'), max_bytes=128_000, respect_robots=False)
            stored = {'rules': body.decode('utf-8', errors='replace')}
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code in (404, 410):
                stored = {'rules': ''}
            else:
                stored = {'blocked': True}
        except Exception:
            stored = {'blocked': True}
        cache.put('robots_policy_v1', origin, stored, 10/1440 if stored.get('blocked') else 1)
    if stored.get('blocked'):
        return False
    parser = RobotFileParser()
    parser.parse(stored['rules'].splitlines())
    delay = parser.crawl_delay(AGENT) or parser.crawl_delay('*') or 1
    if delay > 10:
        return False
    if parser.can_fetch(AGENT, url):
        from services.throttle import wait_turn
        wait_turn(origin, interval=max(1, delay))
        return True
    return False
