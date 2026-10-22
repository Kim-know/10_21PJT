"""키 없이 실행하는 실측 검증 보고서. 실제 GMS 품질 통과를 주장하지 않는다."""
import json
import os
import sys
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
from services.confirmed_places import load_catalog
from services.vector_store import counts, retrieve_vectors, split_text, metadata_text
from services.rag_graph import graph


def run():
    catalog = load_catalog()
    target = max(catalog, key=lambda p: len(p.get('research_documents', [])))
    question = '이 장소에서 어떤 영화의 장면을 촬영했나요?'
    variants = []
    for mode in ('similarity', 'mmr'):
        for k in (1, 3, 5):
            with patch.dict(os.environ, {'RETRIEVAL_TOP_K': str(k)}):
                start = perf_counter()
                sources = retrieve_vectors(target, question, mode=mode)
                elapsed = perf_counter()-start
            variants.append(dict(mode=mode, top_k=k, seconds=round(elapsed, 4),
                                 item_id=target['id'], titles=[s['title'] for s in sources],
                                 source_types=[s['source_type'] for s in sources]))
    chunk_variants = []
    for size, overlap in ((300, 50), (700, 100)):
        with patch.dict(os.environ, {'CHUNK_SIZE': str(size), 'CHUNK_OVERLAP': str(overlap)}):
            actual = sum(len(split_text(doc['text'])) for p in catalog for doc in p.get('research_documents', []))
            fixture = len(split_text('청킹 설정 변화 검증용 합성 문장입니다. ' * 100))
        chunk_variants.append(dict(chunk_size=size, overlap=overlap, actual_corpus_chunks=actual,
                                   synthetic_fixture_chunks=fixture))
    licenses = {}
    for place in catalog:
        for doc in place.get('research_documents', []):
            key = (doc['url'], doc.get('source_type', '외부 문서'))
            row = licenses.setdefault(key, dict(url=doc['url'], source_type=key[1], documents=0,
                                                condition=doc.get('license', '개별 원문 이용 조건 확인 필요')))
            row['documents'] += 1
    report = dict(catalog_places=len(catalog), locations_with_documents=sum(bool(p.get('research_documents')) for p in catalog),
                  index_counts=counts(), query=question, place=target['name'], retrieval_comparison=variants,
                  chunk_comparison=chunk_variants, sample_metadata=metadata_text(target),
                  gms_key_configured=bool(os.getenv('GMS_KEY', '').strip()),
                  live_gms_tested=False, response_quality='미확인',
                  licenses=list(licenses.values()))
    out = ROOT / 'data/validation'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'offline_verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'rag_graph.mmd').write_text(graph.get_graph().draw_mermaid(), encoding='utf-8')
    lines = ['# 실제 로컬 검색·설정 비교', '', f"장소 {len(catalog)}곳 / 색인 {report['index_counts']}", '',
             f"같은 질문: {question}", f"선택 장소: {target['name']}", '',
             '|검색|Top-k|검색 단계 시간(초)|반환 근거|', '|---|---:|---:|---|']
    lines += [f"|{v['mode']}|{v['top_k']}|{v['seconds']}|{' / '.join(v['titles'])}|" for v in variants]
    lines += ['', '검색 시간은 로컬 임베딩과 벡터 검색만의 실측이다. 첫 회에는 모델 초기화 시간이 포함된다. '
              'GMS·외부 수집·답변 생성 전체 시간이나 답변 정확도 결과가 아니다.', '',
              '|청크/겹침|실제 자료 청크 수|합성 긴 문서 청크 수|', '|---|---:|---:|']
    lines += [f"|{v['chunk_size']}/{v['overlap']}|{v['actual_corpus_chunks']}|{v['synthetic_fixture_chunks']}|" for v in chunk_variants]
    lines += ['', '현재 공공 원문과 요약은 매우 짧아 두 설정의 실제 자료 청크 수가 같을 수 있다. '
              '이를 설정이 적용되지 않은 것으로 오해하지 않도록 합성 긴 문서의 결과를 별도로 표시했다. '
              '합성 문서는 동작 검증용이며 실제 촬영지 자료나 품질 평가 결과가 아니다.', '',
              '실제 GMS 답변·캡처 정확도·전체 처리 시간·상호 점검·개별 웹 원문/이미지 재사용 허가는 아직 미확인이다.']
    (out / 'retrieval_comparison.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('catalog_places','locations_with_documents','index_counts','live_gms_tested')}, ensure_ascii=False))


if __name__ == '__main__':
    run()
