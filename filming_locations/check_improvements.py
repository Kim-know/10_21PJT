"""장면별 저장·정정·취소·복원과 실제 벡터 제거를 검사한다."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from services.confirmed_places import save_confirmed, revise_record, revision_history, load_catalog, saved_records
from services.vector_store import collections, build_index, sync_review_index, counts
from check_confirmed import CANDIDATE, SOURCE

def run():
    with TemporaryDirectory(ignore_cleanup_errors=True) as directory, patch.dict(os.environ, {
        'CONFIRMED_DB_PATH':str(Path(directory)/'reviews.sqlite3'), 'VECTOR_DB_DIR':str(Path(directory)/'vectors')}):
        collections.cache_clear()
        record=save_confirmed(candidate=CANDIDATE,sources=[SOURCE],work='테스트작품',media_type='드라마',
            name='정정테스트',address='테스트주소',region='테스트시',confirmed=True,
            episode='8회',scene_description='갈대밭 전망대',latitude=37.,longitude=127.,coordinates_confirmed=True)
        assert record['scenes'][0]['episode']=='8회'
        build_index([record])
        changed=revise_record(record['id'],action='correct',changes={'address':'새주소'},reason='주소 오기 정정')
        assert changed['latitude'] is None and changed['scenes'][0]['description']=='갈대밭 전망대'
        from services.vector_store import retrieve_vectors,search_items
        assert not any(s['item_id']==record['id'] for s in search_items('정정테스트')), '정정 전 메타데이터를 조건 검색에 사용하지 않는다'
        changed_item=next(p for p in load_catalog() if p['id']==record['id'])
        try:
            retrieve_vectors(changed_item,'촬영 근거')
        except ValueError:
            pass
        else:
            raise AssertionError('정정 전 오래된 색인 사용 금지')
        sync_review_index(record['id'])
        assert len(revision_history(record['id']))==1
        revise_record(record['id'],action='withdraw',reason='다른 장면이었다')
        sync_review_index(record['id'])
        assert not saved_records() and counts()=={'metadata':0,'documents':0}
        assert saved_records(include_inactive=True)[0]['withdrawn']
        revise_record(record['id'],action='restore',reason='근거를 다시 확인')
        sync_review_index(record['id'])
        assert len(saved_records())==1 and counts()['metadata']==1
        assert len(revision_history(record['id']))==3
        try:
            revise_record(record['id'],action='correct',changes={'latitude':999,'longitude':127,'coordinates_confirmed':True},reason='잘못된 좌표')
        except ValueError:
            pass
        else:
            raise AssertionError('잘못된 좌표 거부')
        assert len(revision_history(record['id']))==3
        baseline=next(p for p in load_catalog() if not p['id'].startswith('user-'))
        saved=save_confirmed(candidate=CANDIDATE,sources=[SOURCE],work='새검수작품',media_type='드라마',name=baseline['name'],address=baseline['address'],region=baseline['region'],confirmed=True)
        assert saved['id']==baseline['id']
        revise_record(saved['id'],action='withdraw',reason='기본 정보 보존 검사')
        sync_review_index(saved['id'])
        restored=next(p for p in load_catalog() if p['id']==baseline['id'])
        assert '새검수작품' not in restored['works'] and not restored.get('user_confirmed')
    from services.hybrid_search import lexical_rank, fuse
    pool=[dict(title='일반 안내',text='공원 방문 안내'),dict(title='갯골생태공원 8회 촬영지',text='남자친구 갈대밭 장면 촬영')]
    assert lexical_rank('갯골생태공원 8회',pool)[0]==1
    assert fuse(['a','b'],['b','c'],2)[0]=='b'
    from services.enrichment import stage, records, review, attach
    with TemporaryDirectory() as directory, patch.dict(os.environ,{'RESEARCH_DB_PATH':str(Path(directory)/'research.sqlite3')}):
        item={'id':'enrichment-test','research_documents':[]}
        source=dict(title='공식 안내',url='https://example.com/official')
        doc=stage(item,source,'장소의 촬영 관계를 설명하는 공식 본문. '*20)
        assert len(records('pending'))==1 and not attach([dict(item)]) [0]['research_documents']
        review(doc['document_id'],True)
        assert len(attach([dict(item,research_documents=[])])[0]['research_documents'])==1
        stage(item,source,doc['text'])
        assert len(records('approved'))==1
        stage(item,source,doc['text']+' 변경')
        assert len(records('pending'))==1, '변경된 원문은 다시 검수해야 한다'
    import io
    from PIL import Image
    from services.scene_finder import find_scene,refine_scene,Clues,Findings
    image=io.BytesIO();Image.new('RGB',(20,20)).save(image,'PNG');raw=image.getvalue()
    stages=[]
    def fake_call(stage,messages,schema,identity):
        stages.append(stage)
        if stage=='clues':return Clues(description='갈대밭',queries=['갈대밭 촬영지']),{'cache_hit':False}
        return Findings(candidates=[],uncertainty='장면 일치 미확인'),{'cache_hit':False}
    with patch('services.scene_finder.call_json',side_effect=fake_call),patch('services.scene_finder.search_web',return_value=[SOURCE]),patch('services.scene_finder.fetch_text',return_value=''):
        first=find_scene('테스트작품',raw,'',[],False)
        refined=refine_scene(first,raw,'8회 갈대밭',[],False)
        assert stages==['clues','match','match'] and refined['usage'][0]['cache_hit']
        assert '8회 갈대밭' in refined['queries'][0]
    with TemporaryDirectory(ignore_cleanup_errors=True) as directory, patch.dict(os.environ,{'VECTOR_DB_DIR':str(Path(directory)/'vectors')}):
        collections.cache_clear()
        item=dict(id='hybrid-test',name='테스트공원',address='주소',region='지역',works=['드라마'],source_url='https://example.com',research_documents=[
           dict(document_id='one',title='8회 갈대밭',text='남자친구 갯골생태공원 8회 갈대밭 촬영',url='https://example.com/one'),
           dict(document_id='two',title='일반 안내',text='공원 운영시간 안내',url='https://example.com/two')])
        build_index([item])
        from services.vector_store import retrieve_vectors
        found=retrieve_vectors(item,'남자친구 갯골생태공원 8회',mode='hybrid')
        assert found[0]['source_type']=='항목 메타데이터' and all(d['item_id']=='hybrid-test' for d in found)
        assert any(d['url']=='https://example.com/one' for d in found)
    print('PASS: scene records, correction, coordinate invalidation, withdraw/restore, audit, real index synchronization, enrichment review, hybrid ranking, refinement reuse')

if __name__=='__main__':
    run()
