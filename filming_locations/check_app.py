"""외부 호출 없이 핵심 UI 흐름 확인: python check_app.py"""
import json
import os
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from services.catalog import validate_locations
from ui.sources import cited_sources

ROOT = Path(__file__).resolve().parent
records = [
    {"id": str(i), "name": f"테스트 장소 {i}", "region": "테스트 지역",
     "address": "테스트 주소", "works": ["테스트 작품"], "wiki_title": "테스트 문서",
     "source_url": "https://example.com", "latitude": None, "longitude": None}
    for i in range(2)
]
assert len(validate_locations(records)) == 2
try:
    validate_locations([records[0], records[0]])
except ValueError:
    pass
else:
    raise AssertionError("중복 ID를 거부해야 합니다")
assert cited_sources("문장 [근거 1, 3] [근거 99]", [{}, {}, {}]) == [(1, {}), (3, {})]

original_read = Path.read_text


def read_catalog(path, *args, **kwargs):
    if path == ROOT / "data/locations.json":
        return json.dumps(records, ensure_ascii=False)
    return original_read(path, *args, **kwargs)


page = {"title": "테스트 문서", "url": "https://example.com", "text": "테스트 근거"}
with patch.object(Path, "read_text", read_catalog), \
     patch.dict(os.environ, {"GMS_KEY": "test-not-a-real-key"}), \
     patch("services.wiki.fetch_page", return_value=page), \
     patch('archive.index_documents'), \
     patch('services.rag_graph.graph.invoke', return_value={'sources': [page], 'result': {
           'answer': '테스트 답변 [근거 1]', 'cache_hit': False, 'llm_called': True, 'usage': {}}}), \
     patch("services.llm.answer_with_usage", return_value={"answer": "테스트 답변 [근거 1]",
           "cache_hit": False, "llm_called": True, "usage": {}}):
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    app.radio[0].set_value("촬영지 자료실").run()
    assert not app.exception
    next(b for b in app.button if b.label == "장소의 위키 문서 불러오기").click().run()
    assert not app.exception
    assert not app.chat_input[0].disabled
    app.chat_input[0].set_value("테스트 질문").run()
    assert not app.exception
    assert len(app.chat_message) == 2
    next(s for s in app.selectbox if s.key=='archive_place').select("1").run()
    assert not app.exception
    assert len(app.chat_message) == 0, "다른 촬영지의 대화가 섞이면 안 됩니다"
    next(s for s in app.selectbox if s.key=='archive_place').select("0").run()
    assert len(app.chat_message) == 2, "원래 촬영지의 대화가 유지되어야 합니다"
    next(b for b in app.button if b.label == "이 촬영지 대화 지우기").click().run()
    assert len(app.chat_message) == 0
    with patch('ui.location_map.render_location_map', return_value=(0, {'place_id': '1', 'nonce': 'map-click-test'})):
        app.run()
        assert not app.exception
        assert next(s for s in app.selectbox if s.key=='archive_place').value == '1', '핀 클릭이 자료실 선택 항목을 바꿔야 합니다'
        assert any('테스트 장소 1' in h.value for h in app.subheader)
    with patch('archive.counts', return_value={'metadata': 0, 'documents': 0}):
        app.run()
        assert any('색인이 없습니다' in w.value for w in app.warning)
    next(b for b in app.button if b.label == '장소의 위키 문서 불러오기').click().run()
    with patch('services.rag_graph.graph.invoke', side_effect=RuntimeError('PRIVATE_TEST_TRACE')):
        app.chat_input[0].set_value('API 실패 확인').run()
        assert not app.exception
        assert any('답변을 받지 못했습니다' in e.value for e in app.error)
        assert not any('PRIVATE_TEST_TRACE' in m.value for m in app.markdown)
    with patch('services.rag_graph.graph.invoke', return_value={'sources': [page], 'result': {
            'answer': '문서에서 확인되지 않습니다.', 'cache_hit': False, 'llm_called': True, 'usage': {}}}):
        app.chat_input[0].set_value('자료에 없는 질문').run()
        assert not app.exception
        assert any('답변에 인용된 근거가 없습니다' in c.value for c in app.caption)

print("PASS: catalog validation, citations, document loading, chat isolation, map sync, no-index notice, safe API failure, uncited-answer notice")
