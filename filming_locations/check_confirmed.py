"""사용자 확인 전 무저장·검수 후 저장·중복 병합·자료실 연동 검증."""
import hashlib
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from streamlit.testing.v1 import AppTest

from services.confirmed_places import save_confirmed, load_catalog, saved_records, pending_index_count, mark_indexed
from services.vector_store import build_index, retrieve_vectors, counts, collections

SOURCE = {'title': '테스트 장소 안내', 'url': 'https://example.com/review-test',
          'text': '검수테스트장소에서 테스트영화의 장면을 촬영했다. 테스트시 테스트로 10.'}
CANDIDATE = {'place': '검수테스트장소', 'address': '테스트시 테스트로 10', 'reason': '근거로 찾은 테스트 후보',
             'differences': '', 'evidence': [{'source_id': 1, 'quote': '검수테스트장소에서 테스트영화의 장면을 촬영했다'}],
             'reference_ids': [], 'map_url': 'https://example.com/map'}


def run():
    with TemporaryDirectory(ignore_cleanup_errors=True) as directory, patch.dict(os.environ, {
            'CONFIRMED_DB_PATH': str(Path(directory) / 'confirmed.sqlite3'),
            'VECTOR_DB_DIR': str(Path(directory) / 'vectors'),
            'APP_CACHE_DIR': str(Path(directory) / 'cache'), 'GMS_KEY': ''}):
        collections.cache_clear()
        params = dict(candidate=CANDIDATE, sources=[SOURCE], work='테스트영화', media_type='영화',
                      name=CANDIDATE['place'], address=CANDIDATE['address'], region='테스트시')
        initial = len(load_catalog())
        try:
            save_confirmed(**params)
            raise AssertionError('확인 전 저장 금지')
        except ValueError:
            pass
        assert not Path(os.environ['CONFIRMED_DB_PATH']).exists()
        for bad in ({'latitude': 37., 'longitude': 127., 'coordinates_confirmed': False},
                    {'latitude': 100., 'longitude': 127., 'coordinates_confirmed': True}):
            try:
                save_confirmed(**params, confirmed=True, **bad)
                raise AssertionError('좌표 검수 경계')
            except ValueError:
                pass
        one = save_confirmed(**params, confirmed=True)
        assert len(load_catalog()) == initial + 1 and one['latitude'] is None
        two = save_confirmed(**params, confirmed=True, latitude=37., longitude=127., coordinates_confirmed=True,
                             coordinate_source='테스트 좌표')
        assert two['id'] == one['id'] and len(load_catalog()) == initial + 1
        assert len(saved_records()) == 1 and len(two['research_documents']) == 1
        assert two['latitude'] == 37. and two['verified_works'] == [] and two['user_confirmed']
        assert pending_index_count() == 1
        build_index([two])
        assert counts() == {'metadata': 1, 'documents': 1}
        assert retrieve_vectors(two, '테스트영화 촬영지')[0]['item_id'] == two['id']
        mark_indexed(two['id'])
        assert pending_index_count() == 0
        # 별도의 UI 후보로 검수 전/거절/확인/저장 흐름을 검증한다.
        candidate = dict(CANDIDATE, place='UI검수장소', address='테스트시 UI로 20')
        buffer = io.BytesIO()
        Image.new('RGB', (20, 20), 'white').save(buffer, 'PNG')
        raw = buffer.getvalue()
        result = dict(clues={'description': '테스트 장면', 'visible_text': [], 'features': []},
                      candidates=[candidate], sources=[SOURCE], references=[], uncertainty='', notices=[], queries=[], usage=[])
        with patch('ui.clipboard_image.clipboard_image', return_value=raw), \
             patch('ui.place_review.build_index') as index, \
             patch('services.geocoding.resolve_address', side_effect=RuntimeError('offline')):
            app = AppTest.from_file('app.py', default_timeout=30).run()
            app.text_input[0].set_value('테스트영화').run()
            signature = hashlib.sha256(json.dumps(['영화', '테스트영화', '', '', True], ensure_ascii=False).encode()+raw).hexdigest()
            app.session_state.scene_result = result
            app.session_state.scene_signature = signature
            app.run()
            assert not app.exception and len(saved_records()) == 1
            next(r for r in app.radio if r.label == '장소 확인').set_value('다른 장소예요').run()
            assert len(saved_records()) == 1
            next(r for r in app.radio if r.label == '장소 확인').set_value('맞아요').run()
            assert not any(r.label == '지도에 표시할 위치' for r in app.radio)
            save = next(b for b in app.button if b.label == '맞아요, 확인한 장소를 저장할게요')
            assert not save.disabled
            save.click().run()
            assert not app.exception and len(saved_records()) == 2 and index.call_count == 1
            next(b for b in app.button if b.label == '저장한 장소를 자료실에서 보기').click().run()
            assert not app.exception
            assert next(r for r in app.radio if r.label == '메뉴').value == '촬영지 자료실'
            assert any('UI검수장소' in h.value for h in app.subheader)
        print('PASS: explicit confirmation, coordinate approval/range, durable DB, dedup, real vector index/retrieval, review UI, archive link')
        collections.cache_clear()


if __name__ == '__main__':
    run()
