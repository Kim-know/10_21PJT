"""키 없는 공개 웹 검색. 실패와 검색 결과 없음은 구분한다."""
import ipaddress
import socket
from urllib.parse import urlparse, urljoin

import requests

from services import cache
from settings import limits
from services.throttle import wait_turn


def public_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username:
            return False
        if parsed.port not in (None, 80, 443):
            return False
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (ValueError, OSError):
        return False


def search_web(query, kind="text", limit=4):
    key = cache.digest(["ddgs-v1", query, kind, limit])
    stored = cache.get("web_search", key)
    if stored is not None:
        return stored
    from ddgs import DDGS
    wait_turn('ddgs')
    client = DDGS(timeout=12)
    if kind == "images":
        raw = client.images(query, region="kr-kr", safesearch="moderate", max_results=limit)
        result = [{"title": r.get("title", "")[:200], "url": r.get("url", ""),
                   "image": r.get("image", ""), "thumbnail": r.get("thumbnail", "")} for r in raw]
    else:
        raw = client.text(query, region="kr-kr", safesearch="moderate", max_results=limit)
        result = [{"title": r.get("title", "")[:200], "url": r.get("href", ""),
                   "text": r.get("body", "")[:800], "source_type": "웹 검색 요약(본문 미확인)"} for r in raw]
    # 임시 검색 실패나 빈 결과는 7일 동안 고정하지 않는다.
    if result:
        cache.put("web_search", key, result, limits()["cache_days"])
    return result


def fetch_public(url, max_bytes=2_000_000, respect_robots=True):
    current = url
    for _ in range(4):
        if not public_url(current):
            raise ValueError("공개 웹 주소가 아닙니다.")
        if respect_robots:
            from services.source_policy import allowed
            if not allowed(current):
                raise ValueError('원문 수집 정책을 확인할 수 없거나 수집이 허용되지 않는 주소입니다.')
        wait_turn(current)
        with requests.get(current, timeout=12, stream=True, allow_redirects=False,
                          headers={"User-Agent": "SceneFinder/0.1 (filming-location-research)"}) as response:
            if response.is_redirect:
                current = urljoin(current, response.headers["Location"])
                continue
            response.raise_for_status()
            data = bytearray()
            for piece in response.iter_content(16384):
                data.extend(piece)
                if len(data) > max_bytes:
                    raise ValueError("자료 크기 한도를 초과했습니다.")
            return bytes(data), response.headers.get("Content-Type", ""), response.encoding
    raise ValueError("웹 주소 이동이 너무 많습니다.")


def fetch_text(url):
    key = cache.digest(["page-v1", url])
    stored = cache.get("web_page", key)
    if stored is not None:
        return stored
    data, content_type, encoding = fetch_public(url)
    if "html" not in content_type.lower():
        return ""
    from lxml import html
    page = html.fromstring(data, parser=html.HTMLParser(encoding=encoding if encoding and encoding.lower() != "iso-8859-1" else None))
    for node in page.xpath("//script|//style|//nav|//header|//footer|//noscript|//form"):
        node.drop_tree()
    # 본문 컨테이너가 있으면 메뉴를 제외한다.
    main = page.xpath("//article|//main")
    text = " ".join((main[0] if main else page).text_content().split())[:16000]
    if text:
        cache.put("web_page", key, text, limits()["cache_days"])
    return text
