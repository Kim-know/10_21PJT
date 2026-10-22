"""기존 공식 출처의 본문을 검토 대기함에 보관. 승인 전 서비스 색인에 넣지 않는다."""
import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from services.cache import digest
from services.web_search import fetch_text

ROOT=Path(__file__).resolve().parents[1]

def path():
    return Path(os.getenv('RESEARCH_DB_PATH',str(ROOT/'data/research_documents.sqlite3')))

def connection():
    target=path();target.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(target,timeout=10)
    db.execute('CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY,item_id TEXT,payload TEXT,status TEXT)')
    return db

def records(status=None):
    if not path().exists():return []
    db=connection()
    try:
        rows=db.execute('SELECT id,item_id,payload,status FROM documents'+(' WHERE status=?' if status else ''),(status,) if status else ()).fetchall()
        return [dict(id=r[0],item_id=r[1],document=json.loads(r[2]),status=r[3]) for r in rows]
    finally:db.close()

def stage(item,source,text):
    if len(text.strip())<150:raise ValueError('본문이 짧아 자료 보강 대상으로 저장하지 않았습니다.')
    document=dict(document_id='enriched-'+digest([item['id'],source['url']])[:24],title=source['title'],url=source['url'],text=text,
       source_type='공식 출처 웹 본문 · 사용자 검토',collected_at=datetime.now(timezone.utc).isoformat(),
       license='원문 권리자 조건 적용. 로컬 조사 보관·원문 재배포 제외')
    db=connection()
    try:
        with db:
            old=db.execute('SELECT payload,status FROM documents WHERE id=?',(document['document_id'],)).fetchone()
            status=old[1] if old and json.loads(old[0])['text']==text else 'pending'
            db.execute('INSERT INTO documents VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,status=excluded.status',
              (document['document_id'],item['id'],json.dumps(document,ensure_ascii=False),status))
    finally:db.close()
    return document

def collect_official(catalog,limit=5):
    report={'collected':[],'failed':[],'skipped':[],'real_gms_used':False}
    seen=set();known={(r['item_id'],r['document']['url']) for r in records()}
    for item in catalog:
        for source in item.get('research_documents',[]):
            if source.get('source_type')!='공식 문서의 사실 요약(조사자 작성)':continue
            key=(item['id'],source['url'])
            if key in known or key in seen:continue
            if len(seen)>=limit:return report
            seen.add(key)
            try:
                text=fetch_text(source['url'])
                if len(text.strip())<150:
                    report['skipped'].append(dict(item_id=item['id'],url=source['url'],reason='본문 없음 또는 150자 미만'));continue
                doc=stage(item,source,text)
                report['collected'].append(dict(item_id=item['id'],name=item['name'],document_id=doc['document_id'],chars=len(text)))
            except Exception:
                report['failed'].append(dict(item_id=item['id'],url=source['url'],reason='정책·접근·네트워크 확인 필요'))
    return report

def review(document_id,approve):
    db=connection()
    try:
        with db:
            row=db.execute('SELECT item_id FROM documents WHERE id=?',(document_id,)).fetchone()
            if not row:raise ValueError('수집 문서가 없습니다.')
            db.execute('UPDATE documents SET status=? WHERE id=?',('approved' if approve else 'rejected',document_id))
        return row[0]
    finally:db.close()

def attach(catalog):
    items={p['id']:p for p in catalog}
    for row in records('approved'):
        if row['item_id'] in items:items[row['item_id']].setdefault('research_documents',[]).append(row['document'])
    return catalog
