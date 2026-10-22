"""문서·응답 영구 캐시와 한국 날짜별 호출 제한. 키/프롬프트는 저장하지 않는다."""
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


@contextmanager
def connect():
    directory = Path(os.getenv("APP_CACHE_DIR", str(ROOT / ".cache")))
    directory.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(directory / "service.sqlite3", timeout=10)
    db.execute("CREATE TABLE IF NOT EXISTS cache (kind TEXT, key TEXT, value TEXT, expires REAL, PRIMARY KEY(kind,key))")
    db.execute("CREATE TABLE IF NOT EXISTS calls (id INTEGER PRIMARY KEY, day TEXT, usage TEXT)")
    try:
        with db:
            yield db
    finally:
        db.close()


def get(kind, key):
    with connect() as db:
        row = db.execute("SELECT value FROM cache WHERE kind=? AND key=? AND expires>?", (kind, key, time.time())).fetchone()
    return json.loads(row[0]) if row else None


def put(kind, key, value, days):
    with connect() as db:
        db.execute("DELETE FROM cache WHERE expires<=?", (time.time(),))
        db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?)",
                   (kind, key, json.dumps(value, ensure_ascii=False), time.time() + days * 86400))


def today():
    return datetime.now(timezone(timedelta(hours=9))).date().isoformat()


def call_count():
    with connect() as db:
        return db.execute("SELECT COUNT(*) FROM calls WHERE day=?", (today(),)).fetchone()[0]


def reserve_call(limit):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        count = db.execute("SELECT COUNT(*) FROM calls WHERE day=?", (today(),)).fetchone()[0]
        if count >= limit:
            raise ValueError("오늘의 LLM 호출 제한에 도달했습니다. 내일 이용하거나 설정을 조정하세요.")
        return db.execute("INSERT INTO calls(day,usage) VALUES (?,?)", (today(), "{}")).lastrowid


def record_usage(call_id, usage):
    with connect() as db:
        db.execute("UPDATE calls SET usage=? WHERE id=?", (json.dumps(usage), call_id))
