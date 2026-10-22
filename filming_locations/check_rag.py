"""실제 로컬 임베딩·Chroma와 LangGraph, 모의 GMS 조사 흐름 검증."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from services.vector_store import (build_index, counts, collections, retrieve_vectors,
                                    split_text, index_documents, metadata_text, mmr_indices)
from services.rag_graph import graph
from services.research import Queries, Selection, Matches, collect_for_question, explore

ROOT = Path(__file__).resolve().parent


def run():
    catalog = json.loads((ROOT / 'data/locations.json').read_text(encoding='utf-8'))
    assert len(catalog) >= 100 and sum(bool(p['research_documents']) for p in catalog) >= 100
    # Chroma는 Windows에서 프로세스 종료까지 mmap 핸들을 유지할 수 있다.
    with TemporaryDirectory(ignore_cleanup_errors=True) as directory, \
            patch.dict(os.environ, {'VECTOR_DB_DIR': directory}), \
            patch('services.research.ROOT', Path(directory) / 'research'):
        collections.cache_clear()
        subset = catalog[:3]
        first = build_index(subset)
        second = build_index(subset)
        assert first == second and first['metadata'] == 3
        for item in subset:
            evidence = retrieve_vectors(item, '어떤 영화의 장면을 촬영했나요?')
            assert evidence[0]['source_type'] == '항목 메타데이터'
            assert all(s['item_id'] == item['id'] for s in evidence)
            assert any(s['source_type'] != '항목 메타데이터' for s in evidence)
        with patch.dict(os.environ, {'RETRIEVAL_TOP_K': '2'}):
            assert len(retrieve_vectors(subset[0], '촬영 장면')) <= 2
            assert len(retrieve_vectors(subset[0], '촬영 장면', mode='mmr')) <= 2
        assert mmr_indices([1., 0.], [[1., 0.], [.999, .001], [.5, .866]], 2, weight=.3) == [0, 2]
        with patch('services.rag_graph.answer_with_usage', return_value={'answer': '자료 기반 답변 [근거 1]'}) as generate:
            state = graph.invoke({'item': subset[0], 'question': '촬영 작품은?', 'history': []})
            assert state['sources'][0]['item_id'] == subset[0]['id']
            assert generate.call_count == 1 and state['result']['answer']
        with patch.dict(os.environ, {'CHUNK_SIZE': '300', 'CHUNK_OVERLAP': '50'}):
            a = split_text('가' * 1200)
        with patch.dict(os.environ, {'CHUNK_SIZE': '700', 'CHUNK_OVERLAP': '100'}):
            b = split_text('가' * 1200)
        assert len(a) > len(b)
        # 수집단계의 모델/외부 네트워크만 모의화하고 실제 문서 색인 연결은 실행.
        item = subset[0]
        question = 'check-rag-unique-' + directory
        source = {'title': '검증용 문서', 'url': 'https://example.com/fixture', 'text': '검증 요약'}
        with patch('services.research.structured', side_effect=[Queries(queries=['장소 역사']), Selection(ids=[1])]), \
             patch('services.research.search_web', return_value=[source]), \
             patch('services.research.fetch_text', return_value='촬영지 설명을 담은 테스트 원문'):
            result = collect_for_question(item, question)
            assert len(result['documents']) == 1 and result['selected']
            with patch('services.research.search_web', side_effect=AssertionError('재수집 금지')):
                assert collect_for_question(item, question)['reused']
        # 수집 테스트 산출물만 정확한 경로로 정리한다.
        from services.cache import digest
        (Path(directory) / 'research/data/collected' / (digest([item['id'], question, 'research-v1']) + '.json')).unlink()
        candidate = {'item_id': item['id'], 'text': metadata_text(item), 'title': item['name']}
        with patch('services.research.structured', return_value=Matches(matches=[
                {'id': item['id'], 'quote': item['name']}, {'id': 'unknown', 'quote': '없음'}])):
            assert len(explore('장소 조건', [candidate])) == 1
        print(json.dumps({'test': 'PASS', 'index_twice': first, 'chunk_counts': [len(a), len(b)],
                          'graph_nodes': list(graph.nodes)}, ensure_ascii=False))
    collections.cache_clear()


if __name__ == '__main__':
    run()
