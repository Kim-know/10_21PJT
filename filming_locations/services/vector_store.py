"""로컬 다국어 임베딩과 영구 Chroma 두 컬렉션. GMS 호출 없음."""
import json
import os
from functools import lru_cache
from pathlib import Path

from services.cache import digest
from settings import limits

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'


def metadata_text(item):
    scenes = ' '.join(f"{x['work']} {x.get('episode','')} {x.get('description','')}" for x in item.get('scenes', []))
    descriptions = ' '.join(r.get('description', '') for r in item.get('relations', []))
    if scenes:
        descriptions = scenes + ' ' + descriptions
    return (f"장소: {item['name']}\n지역: {item['region']}\n주소: {item['address']}\n"
            f"관련 작품: {', '.join(item['works'])}\n장소 유형: {item.get('location_type', '')}\n"
            f"장면 설명: {descriptions}\n검증 상태: {item.get('verification_status', '등록 정보')}\n"
            '현재 운영시간과 출입 가능 여부는 별도 확인이 필요합니다.')


@lru_cache(maxsize=1)
def encoder():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=MODEL, cache_dir=str(ROOT / '.models'), threads=2)


def embed(texts, query=False):
    return [v.tolist() for v in encoder().embed(texts, batch_size=16)]


@lru_cache(maxsize=4)
def collections(path=None):
    import chromadb
    from chromadb.config import Settings
    client = chromadb.PersistentClient(path=path or os.getenv('VECTOR_DB_DIR', str(ROOT / '.vectors')),
                                      settings=Settings(anonymized_telemetry=False))
    stores = tuple(client.get_or_create_collection(name, embedding_function=None,
                metadata={'hnsw:space': 'cosine', 'embedding_model': MODEL})
                for name in ('location_meta', 'location_documents'))
    if any(c.metadata.get('embedding_model') != MODEL for c in stores):
        raise ValueError('기존 색인의 임베딩 모델이 다릅니다. 별도 VECTOR_DB_DIR 경로로 재색인해 주세요.')
    return stores


def counts():
    a, b = collections()
    return {'metadata': a.count(), 'documents': b.count()}


def split_text(text):
    c = limits()
    return [text[i:i+c['chunk_size']] for i in range(0, len(text), c['chunk_size']-c['chunk_overlap'])
            if text[i:i+c['chunk_size']].strip()]


def upsert_rows(collection, rows):
    if not rows:
        return
    existing = collection.get(ids=[r[0] for r in rows], include=['metadatas'])
    known = {key: m.get('hash') for key, m in zip(existing['ids'], existing['metadatas'])}
    changed = [r for r in rows if known.get(r[0]) != r[2]['hash']]
    for offset in range(0, len(changed), 32):
        batch = changed[offset:offset+32]
        collection.upsert(ids=[r[0] for r in batch], documents=[r[1] for r in batch],
                          metadatas=[r[2] for r in batch], embeddings=embed([r[1] for r in batch]))


def index_documents(item, documents):
    _, store = collections()
    for doc in documents:
        document_id = doc.get('document_id') or digest([doc['url'], doc['title']])[:24]
        base = item['id'] + ':' + document_id
        rows = []
        for i, text in enumerate(split_text(doc['text'])):
            metadata = dict(item_id=item['id'], document_id=document_id, title=doc['title'],
                            url=doc['url'], source_type=doc.get('source_type', '외부 문서'),
                            collected_at=doc.get('collected_at', doc.get('checked_at', '2026-10-21')),
                            license=doc.get('license', '원문 이용 조건 별도 확인'), chunk=i,
                            hash=digest([text, MODEL, doc['url'], doc.get('source_type')]))
            rows.append((f'{base}:{i}', text, metadata))
        upsert_rows(store, rows)
        # 같은 문서가 짧아졌을 때 이전 뒤쪽 청크를 남기지 않는다.
        previous = store.get(where={'$and': [{'item_id': item['id']}, {'document_id': document_id}]}, include=[])
        keep = {r[0] for r in rows}
        stale = [key for key in previous['ids'] if key not in keep]
        if stale:
            store.delete(ids=stale)


def build_index(catalog):
    meta, _ = collections()
    rows = []
    for item in catalog:
        text = metadata_text(item)
        rows.append((item['id'], text, dict(item_id=item['id'], title=item['name'],
                     url=item['source_url'], source_type='항목 메타데이터', hash=digest([text, MODEL]))))
    upsert_rows(meta, rows)
    for item in catalog:
        index_documents(item, item.get('research_documents', []))
    return counts()


def result_sources(result):
    return [dict(m, text=text) for text, m in zip(result['documents'][0], result['metadatas'][0])]


def mmr_indices(query, vectors, k, weight=0.5):
    import numpy as np
    matrix = np.asarray(vectors, dtype=float)
    query = np.asarray(query, dtype=float)
    norms = np.maximum(np.linalg.norm(matrix, axis=1), 1e-12)
    matrix = matrix / norms[:, None]
    query = query / max(float(np.linalg.norm(query)), 1e-12)
    relevance = matrix @ query
    selected = []
    while len(selected) < min(k, len(matrix)):
        best, score = None, float('-inf')
        for i in range(len(matrix)):
            if i in selected:
                continue
            redundancy = max(float(matrix[i] @ matrix[j]) for j in selected) if selected else 0.0
            value = weight * relevance[i] - (1-weight) * redundancy
            if value > score:
                best, score = i, value
        selected.append(best)
    return selected


def retrieve_vectors(item, question, mode='similarity'):
    if mode not in ('similarity', 'mmr', 'hybrid'):
        raise ValueError('지원하지 않는 검색 방식입니다.')
    meta, docs = collections()
    selected = meta.get(ids=[item['id']], include=['documents', 'metadatas'])
    if not selected['ids']:
        raise ValueError('선택 장소의 색인이 없습니다. 자료실에서 기본 자료 색인을 실행해 주세요.')
    if selected['documents'][0] != metadata_text(item):
        raise ValueError('장소 정보가 변경돼 검색 색인 갱신이 필요합니다. 기본 자료 색인 / 갱신을 실행해 주세요.')
    evidence = [dict(selected['metadatas'][0], text=selected['documents'][0])]
    subset = docs.get(where={'item_id': item['id']}, include=[])
    k = min(max(0, limits()['top_k'] - 1), len(subset['ids']))
    if k:
        query = embed([question], query=True)
        fetch_k = min(len(subset['ids']), max(k*4, 20)) if mode in ('mmr','hybrid') else k
        include = ['documents', 'metadatas', 'embeddings'] if mode == 'mmr' else ['documents', 'metadatas']
        found = docs.query(query_embeddings=query, n_results=fetch_k,
                           where={'item_id': item['id']}, include=include)
        candidates = result_sources(found)
        if mode == 'mmr':
            chosen = mmr_indices(query[0], found['embeddings'][0], k)
            candidates = [candidates[i] for i in chosen]
        if mode == 'hybrid':
            from services.hybrid_search import lexical_rank, fuse
            all_rows = docs.get(where={'item_id':item['id']},include=['documents','metadatas'])
            pool = [dict(m,text=t) for m,t in zip(all_rows['metadatas'],all_rows['documents'])]
            by_id = dict(zip(all_rows['ids'],pool))
            lexical = [all_rows['ids'][i] for i in lexical_rank(question,pool)[:max(20,k*4)]]
            keys = fuse(found['ids'][0],lexical,k)
            candidates = [by_id[key] for key in keys]
        evidence += candidates
    seen, output = set(), []
    allowed_review_docs = {d.get('document_id') for d in item.get('research_documents', [])}
    for source in evidence:
        document_id = source.get('document_id','')
        if document_id.startswith(('confirmed-','enriched-')) and document_id not in allowed_review_docs:
            continue
        identity = digest([source['text'], source['url']])
        if identity not in seen:
            output.append(source)
            seen.add(identity)
    return output


def search_items(condition, limit=12):
    meta, _ = collections()
    if not meta.count():
        raise ValueError('색인이 없습니다. 기본 자료 색인을 먼저 실행해 주세요.')
    result = meta.query(query_embeddings=embed([condition], query=True), n_results=min(limit, meta.count()),
                        include=['documents', 'metadatas'])
    from services.confirmed_places import load_catalog
    active = {p['id']:p for p in load_catalog()}
    return [r for r in result_sources(result) if r['item_id'] in active
            and r['text']==metadata_text(active[r['item_id']])]


def sync_review_index(place_id):
    """취소한 사용자 근거를 제거하고 기본 기록이 있으면 되돌린다."""
    from services.confirmed_places import load_catalog, mark_indexed
    meta, docs = collections()
    rows = docs.get(where={'item_id':place_id}, include=['metadatas'])
    remove = [key for key,m in zip(rows['ids'],rows['metadatas']) if m.get('document_id','').startswith('confirmed-')]
    if remove:
        docs.delete(ids=remove)
    current = next((p for p in load_catalog() if p['id']==place_id), None)
    if current:
        build_index([current])
    else:
        meta.delete(ids=[place_id])
        leftovers = docs.get(where={'item_id':place_id}, include=[])
        if leftovers['ids']:
            docs.delete(ids=leftovers['ids'])
    mark_indexed(place_id)
