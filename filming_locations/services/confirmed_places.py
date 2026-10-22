"""사용자가 검수한 장소만 영구 저장. 기본 JSON과 별도 DB로 보존한다."""
import copy
import json
import math
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from contextlib import contextmanager

from services.cache import digest

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def connection(path):
    db = sqlite3.connect(path, timeout=10)
    try:
        with db:
            yield db
    finally:
        db.close()


def db_path():
    return Path(os.getenv('CONFIRMED_DB_PATH', str(ROOT / 'data/confirmed_locations.sqlite3')))


def normalized(value):
    return re.sub(r'\s+', '', value).casefold()


def saved_records(include_inactive=False):
    path = db_path()
    if not path.exists():
        return []
    with connection(path) as db:
        records = [json.loads(row[0]) for row in db.execute('SELECT payload FROM confirmed_places ORDER BY id')]
        return records if include_inactive else [r for r in records if not r.get('withdrawn')]


def merge_records(base, saved):
    records = {p['id']: copy.deepcopy(p) for p in base}
    for addition in saved:
        if addition['id'] not in records:
            records[addition['id']] = copy.deepcopy(addition)
            continue
        current = records[addition['id']]
        current['works'] = list(dict.fromkeys(current['works'] + addition['works']))
        docs = current.setdefault('research_documents', [])
        known = {(d.get('document_id'), d['url'], d['text']) for d in docs}
        docs.extend(copy.deepcopy(d) for d in addition['research_documents']
                    if (d.get('document_id'), d['url'], d['text']) not in known)
        current['scenes'] = copy.deepcopy(addition.get('scenes', []))
        for field in addition.get('corrected_fields', []):
            current[field] = copy.deepcopy(addition[field])
        current['user_confirmed'] = True
        current['user_confirmed_at'] = addition['user_confirmed_at']
        # 기본 데이터 좌표를 사용자 입력으로 조용히 덮어쓰지 않는다.
        if not set(addition.get('corrected_fields', [])) & {'latitude','longitude'} and current.get('latitude') is None and addition.get('latitude') is not None:
            for field in ('latitude', 'longitude', 'coordinate_status', 'coordinate_source'):
                current[field] = addition.get(field)
    return list(records.values())


def load_catalog(base=None):
    if base is None:
        base = json.loads((ROOT / 'data/locations.json').read_text(encoding='utf-8-sig'))
    from services.enrichment import attach
    return attach(merge_records(base, saved_records()))


def save_confirmed(*, candidate, sources, work, media_type, name, address, region,
                   confirmed=False, latitude=None, longitude=None,
                   coordinates_confirmed=False, coordinate_source='', episode='', scene_description=''):
    if confirmed is not True:
        raise ValueError('찾던 장소가 맞는지 확인한 뒤 저장해 주세요.')
    if not all(isinstance(v, str) and v.strip() for v in (name, address, region, work)):
        raise ValueError('장소명·주소·지역·영상 제목을 확인해 주세요.')
    if len(name) > 150 or len(address) > 300 or len(region) > 100 or len(work) > 100:
        raise ValueError('입력 내용이 너무 깁니다.')
    if (latitude is None) != (longitude is None):
        raise ValueError('위도와 경도는 함께 입력해 주세요.')
    if latitude is not None:
        if (coordinates_confirmed is not True or isinstance(latitude, bool) or isinstance(longitude, bool)
                or not math.isfinite(latitude) or not math.isfinite(longitude)
                or not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
            raise ValueError('지도 위치 확인과 올바른 위도·경도가 필요합니다.')
    if len(episode) > 80 or len(scene_description) > 500:
        raise ValueError('회차 80자·장면 설명 500자 이내로 입력해 주세요.')
    documents = []
    for evidence in candidate.get('evidence', []):
        source_id = evidence.get('source_id')
        if not isinstance(source_id, int) or not 1 <= source_id <= len(sources):
            continue
        source = sources[source_id - 1]
        quote = evidence.get('quote', '').strip()
        url = source.get('url', '')
        if (urlparse(url).scheme not in ('http', 'https') or not urlparse(url).netloc
                or len(normalized(quote)) < 6
                or normalized(quote) not in normalized(source.get('title', '') + ' ' + source.get('text', ''))):
            continue
        documents.append(dict(document_id='confirmed-' + digest([url, quote])[:24],
                              title=source.get('title') or '검색 근거', url=url, text=quote,
                              source_type='검색 근거 인용 · 사용자 장면 확인',
                              collected_at=datetime.now(timezone.utc).isoformat(),
                              license='원문 권리자 조건 적용. 출처와 짧은 근거 인용 보존'))
    if not documents:
        raise ValueError('저장할 수 있는 원문 근거가 없습니다. 근거가 있는 후보를 확인해 주세요.')
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with connection(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS confirmed_places (id TEXT PRIMARY KEY, identity TEXT UNIQUE, payload TEXT NOT NULL, indexed INTEGER NOT NULL DEFAULT 0)')
        db.execute('BEGIN IMMEDIATE')
        identity = digest([normalized(name), normalized(address)])
        stored = db.execute('SELECT payload FROM confirmed_places WHERE identity=?', (identity,)).fetchone()
        baseline = json.loads((ROOT / 'data/locations.json').read_text(encoding='utf-8-sig'))
        existing = next((p for p in baseline if normalized(p['name']) == normalized(name)
                         and normalized(p['address']) == normalized(address)), None)
        if existing and not stored and db.execute('SELECT id FROM confirmed_places WHERE id=?',(existing['id'],)).fetchone():
            raise ValueError('이 기본 장소의 정정 기록이 이미 있습니다. 자료실에서 기존 기록을 정정하거나 복원해 주세요.')
        if stored:
            record = json.loads(stored[0])
        else:
            record = dict(id=existing['id'] if existing else 'user-' + identity[:24], name=name.strip(),
                          address=address.strip(), region=region.strip(), works=[], verified_works=[],
                          wiki_title=name.strip(), source_url=documents[0]['url'],
                          verification_status='사용자가 장면 일치 확인 · 외부 기관 검증 아님',
                          latitude=None, longitude=None, research_documents=[], research_notes=[],
                          visit_status='현재 운영·출입 여부 미확인')
        scene = dict(work=work.strip(), media_type=media_type, episode=episode.strip(),
                     description=scene_description.strip(), evidence_ids=[d['document_id'] for d in documents],
                     visual_match=candidate.get('visual_match', 'unconfirmed'), review_status='user_confirmed')
        scene['id'] = 'scene-' + digest(scene)[:24]
        scenes = record.setdefault('scenes', [])
        if not any(x['id'] == scene['id'] for x in scenes):
            scenes.append(scene)
        record['withdrawn'] = False
        record['schema_version'] = 2
        record['works'] = list(dict.fromkeys(record['works'] + [work.strip()]))
        known = {d['document_id'] for d in record['research_documents']}
        record['research_documents'].extend(d for d in documents if d['document_id'] not in known)
        record.update(user_confirmed=True, user_confirmed_at=datetime.now(timezone.utc).isoformat(),
                      media_type=media_type,
                      review_original_name=candidate.get('place', ''),
                      review_original_address=candidate.get('address', ''))
        if latitude is not None:
            record.update(latitude=float(latitude), longitude=float(longitude),
                          coordinate_status='사용자가 지도 위치 확인 · 현장 정밀도 미검증',
                          coordinate_source=coordinate_source)
        db.execute('INSERT INTO confirmed_places(id,identity,payload,indexed) VALUES (?,?,?,0) '
                   'ON CONFLICT(identity) DO UPDATE SET payload=excluded.payload,indexed=0',
                   (record['id'], identity, json.dumps(record, ensure_ascii=False)))
    return next(p for p in load_catalog() if p['id'] == record['id'])


def mark_indexed(place_id):
    with connection(db_path()) as db:
        db.execute('UPDATE confirmed_places SET indexed=1 WHERE id=?', (place_id,))


def pending_index_count():
    if not db_path().exists():
        return 0
    with connection(db_path()) as db:
        return db.execute('SELECT COUNT(*) FROM confirmed_places WHERE indexed=0').fetchone()[0]


def revise_record(place_id, *, action, changes=None, reason=''):
    """사용자 기록만 정정·취소·복원하며 원본과 이력을 보존한다."""
    if action not in {'correct', 'withdraw', 'restore'}:
        raise ValueError('지원하지 않는 정정 작업입니다.')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise ValueError('정정·취소 이유를 500자 이내로 입력해 주세요.')
    if not db_path().exists():
        raise ValueError('사용자 저장 기록이 없습니다.')
    with connection(db_path()) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT payload FROM confirmed_places WHERE id=?', (place_id,)).fetchone()
        if not row:
            raise ValueError('사용자가 저장한 장소만 정정할 수 있습니다.')
        record = json.loads(row[0])
        previous = copy.deepcopy(record)
        if action == 'correct':
            changes = changes or {}
            if not changes or set(changes) - {'name','address','region','latitude','longitude','coordinates_confirmed'}:
                raise ValueError('수정할 필드를 확인해 주세요.')
            for key, maximum in [('name',150),('address',300),('region',100)]:
                if key in changes and (not isinstance(changes[key], str) or not changes[key].strip() or len(changes[key]) > maximum):
                    raise ValueError('장소명·주소·지역 입력을 확인해 주세요.')
            if any(k in changes for k in ('latitude','longitude')):
                lat, lon = changes.get('latitude'), changes.get('longitude')
                if (lat is None) != (lon is None):
                    raise ValueError('위도와 경도는 함께 입력해 주세요.')
                if lat is not None and (changes.get('coordinates_confirmed') is not True or
                    isinstance(lat, bool) or isinstance(lon, bool) or not isinstance(lat,(int,float)) or
                    not isinstance(lon,(int,float)) or not math.isfinite(lat) or not math.isfinite(lon) or
                    not -90 <= lat <= 90 or not -180 <= lon <= 180):
                    raise ValueError('좌표 범위와 지도 확인을 점검해 주세요.')
            elif any(k in changes and changes[k].strip() != record[k] for k in ('name','address')):
                # 주소 변경 후 기존 좌표를 새 주소의 확정 위치로 재사용하지 않는다.
                changes = dict(changes, latitude=None, longitude=None)
            fields = [k for k in changes if k != 'coordinates_confirmed']
            record.update({k: changes[k].strip() if isinstance(changes[k],str) else changes[k] for k in fields})
            record['corrected_fields'] = sorted(set(record.get('corrected_fields', []) + fields))
        else:
            record['withdrawn'] = action == 'withdraw'
        record['updated_at'] = datetime.now(timezone.utc).isoformat()
        identity = digest([normalized(record['name']), normalized(record['address'])])
        duplicate = db.execute('SELECT id FROM confirmed_places WHERE identity=? AND id<>?', (identity,place_id)).fetchone()
        if duplicate:
            raise ValueError('같은 장소명·주소의 저장 기록이 있습니다. 중복 기록을 확인해 주세요.')
        db.execute('CREATE TABLE IF NOT EXISTS review_revisions (id INTEGER PRIMARY KEY, place_id TEXT, action TEXT, reason TEXT, before_payload TEXT, changed_at TEXT)')
        db.execute('INSERT INTO review_revisions(place_id,action,reason,before_payload,changed_at) VALUES (?,?,?,?,?)',
                   (place_id, action, reason.strip(), json.dumps(previous,ensure_ascii=False), record['updated_at']))
        db.execute('UPDATE confirmed_places SET identity=?,payload=?,indexed=0 WHERE id=?',
                   (identity,json.dumps(record,ensure_ascii=False),place_id))
    return record


def revision_history(place_id):
    if not db_path().exists():
        return []
    with connection(db_path()) as db:
        if not db.execute("SELECT name FROM sqlite_master WHERE name='review_revisions'").fetchone():
            return []
        return [dict(action=r[0],reason=r[1],changed_at=r[2]) for r in db.execute(
            'SELECT action,reason,changed_at FROM review_revisions WHERE place_id=? ORDER BY id DESC', (place_id,))]
