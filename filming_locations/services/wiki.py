"""step8_wiki_api.py의 검색/본문 수집을 서비스용으로 분리."""
import html
import os
import re
import time

import requests

from services import cache
from settings import limits
from services.throttle import wait_turn

API_URL = "https://ko.wikipedia.org/w/api.php"


def request_wikipedia(params: dict) -> dict:
    contact = os.getenv("WIKI_CONTACT", "").strip()
    if not contact:
        raise ValueError('위키백과 호출 전 .env의 WIKI_CONTACT에 영문 연락처를 설정해 주세요.')
    agent = f"FilmingLocations/0.1 ({contact}) python-requests" if contact else "FilmingLocations/0.1 python-requests"
    agent.encode("ascii")
    for attempt in range(3):
        wait_turn(API_URL)
        response = requests.get(API_URL, params=params, headers={"User-Agent": agent}, timeout=20)
        if response.status_code == 429:
            # UI가 오래 멈추지 않도록 60초를 넘는 제한은 재시도를 안내한다.
            delay = float(response.headers.get("Retry-After") or 2 ** (attempt + 1))
            if not 0 <= delay <= 60 or attempt == 2:
                raise RuntimeError("API 호출이 제한되었습니다. 잠시 후 다시 시도하세요.")
            time.sleep(delay)
            continue
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError("위키백과 API 오류")
        return data
    raise RuntimeError("위키백과 요청 실패")


def search(query: str, limit: int = 5) -> list[dict]:
    key = cache.digest([API_URL, query, limit])
    stored = cache.get("wiki_search", key)
    if stored is not None:
        return stored
    data = request_wikipedia({
        "action": "query", "list": "search", "srsearch": query,
        "srlimit": limit, "format": "json", "formatversion": 2,
    })
    results = [{"page_id": p["pageid"], "title": p["title"],
             "snippet": html.unescape(re.sub(r"<[^>]+>", "", p.get("snippet", "")))}
            for p in data.get("query", {}).get("search", [])]
    cache.put("wiki_search", key, results, limits()["cache_days"])
    return results


def fetch_page(title: str) -> dict | None:
    key = cache.digest([API_URL, title])
    stored = cache.get("wiki_page", key)
    if stored is not None:
        return stored
    data = request_wikipedia({
        "action": "query", "prop": "extracts|info", "titles": title,
        "explaintext": 1, "inprop": "url", "redirects": 1,
        "format": "json", "formatversion": 2,
    })
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    page = pages[0]
    result = {"page_id": page["pageid"], "title": page["title"],
            "url": page["fullurl"], "text": page.get("extract", ""), "source_type": "위키백과"}
    if result["text"].strip():
        cache.put("wiki_page", key, result, limits()["cache_days"])
    return result
