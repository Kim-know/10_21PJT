"""실제 HTTP 경계·검수 토큰·DB·오류 비노출. GMS 응답만 모의화."""
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from api import app, _pending
from services.confirmed_places import saved_records


def run():
    with TemporaryDirectory() as directory, patch.dict(os.environ, {
            'CONFIRMED_DB_PATH': str(Path(directory) / 'confirmed.sqlite3'),
            'APP_CACHE_DIR': str(Path(directory) / 'cache'), 'RESEARCH_DB_PATH': str(Path(directory)/'research.sqlite3'), 'GMS_KEY': ''}), \
            TestClient(app, raise_server_exceptions=False) as client:
        assert client.get('/').status_code == 200
        assert client.get('/assets/app.js').status_code == 200
        assert len(client.get('/api/examples').json()['examples']) == 3
        status = client.get('/api/status')
        assert status.status_code == 200 and not status.json()['ai_ready']
        assert set(status.json()['index']) >= {'metadata', 'documents'}
        assert client.get('/api/places').json()['places']
        assert client.post('/api/chat', json={'place_id': 'missing', 'question': '질문'}).status_code == 503
        assert client.post('/api/chat', json={}).status_code == 422
        assert client.post('/api/index', json={}, headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.get('/api/places', headers={'Host': 'evil.example'}).status_code == 400
        source = dict(title='API 테스트 원문', url='https://example.com/api-test', text='API테스트장소에서 테스트영화 장면을 촬영했습니다.')
        candidate = dict(place='API테스트장소', address='테스트시 테스트로 1', reason='테스트 후보', differences='',
                         evidence=[dict(source_id=1, quote=source['text'])], reference_ids=[], map_url='https://example.com')
        result = dict(clues={'description': '테스트 배경', 'features': [], 'visible_text': []},
                      candidates=[candidate], sources=[source], references=[], notices=[], queries=[], uncertainty='', usage=[])
        data = io.BytesIO()
        Image.new('RGB', (10, 10)).save(data, 'PNG')
        with patch.dict(os.environ, {'GMS_KEY': 'fake-key-api-test'}), \
                patch('api.find_scene', return_value=result), patch('api.build_index', return_value={}) as index:
            found = client.post('/api/scene', data={'work': '테스트영화'}, files={'image': ('test.png', data.getvalue(), 'image/png')})
            assert found.status_code == 200, found.text
            token = found.json()['review_token']
            assert not saved_records()
            body = dict(review_token=token, candidate_index=0, name=candidate['place'], address=candidate['address'], region='테스트시')
            assert client.post('/api/confirm', json=body).status_code == 400
            assert not saved_records()
            body['confirmed'] = True
            saved = client.post('/api/confirm', json=body)
            assert saved.status_code == 200 and index.call_count == 1
            assert saved.json()['place']['user_confirmed'] and len(saved_records()) == 1
            assert client.post('/api/confirm', json=body).status_code == 200 and len(saved_records()) == 1
            assert any(p['name'] == candidate['place'] for p in client.get('/api/places').json()['places'])
            body['review_token'] = 'x'*32
            assert client.post('/api/confirm', json=body).status_code == 410
            with patch('api.graph.invoke', return_value={'sources': [source], 'result': {'answer': '확인한 내용 [근거 1]'}}):
                reply = client.post('/api/chat', json={'place_id': saved.json()['place']['id'], 'question': '질문', 'mode': 'mmr'})
                assert reply.status_code == 200 and reply.json()['sources'][0]['number'] == 1
            with patch('api.graph.invoke', side_effect=RuntimeError('PRIVATE_SERVER_TRACE')):
                place_id = saved.json()['place']['id']
                failed = client.post('/api/chat', json={'place_id': place_id, 'question': '질문'})
                assert failed.status_code == 500 and 'PRIVATE_SERVER_TRACE' not in failed.text
            place_id=saved.json()['place']['id']
            assert client.get('/api/reviews').status_code==200
            with patch('services.vector_store.sync_review_index'):
                edited=client.post('/api/revise',json={'place_id':place_id,'action':'correct','reason':'주소 정정','changes':{'address':'수정 주소'}})
                assert edited.status_code==200 and edited.json()['record']['address']=='수정 주소'
                assert client.post('/api/revise',json={'place_id':place_id,'action':'withdraw','reason':'장면 오인'}).status_code==200
                assert all(p['id']!=place_id for p in client.get('/api/places').json()['places'])
                assert client.post('/api/revise',json={'place_id':place_id,'action':'restore','reason':'재확인'}).status_code==200
            assert client.post('/api/revise',json={'place_id':'baseline-missing','action':'correct','reason':'허위','changes':{'address':'변경'}}).status_code==400
            assert client.get('/api/enrichment').json()['records']==[]
            with patch('services.scene_finder.refine_scene',return_value=result):
                refined=client.post('/api/refine',data={'review_token':token,'additional_hint':'8회 갈대밭'},files={'image':('test.png',data.getvalue(),'image/png')})
                assert refined.status_code==200 and refined.json()['review_token']!=token
        _pending.clear()
    print('PASS: frontend assets, API validation, key guard, origin/host guard, scene review token, explicit confirmation, DB dedup, safe errors')


if __name__ == '__main__':
    run()
