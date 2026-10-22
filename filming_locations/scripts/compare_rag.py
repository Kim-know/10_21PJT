"""F2015 평가 도구. 기본 실행은 로컬 근거만 수집, --run-gms일 때만 실호출."""
import argparse
import json
import os
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
from services import cache
from services.confirmed_places import load_catalog
from services.vector_store import retrieve_vectors
from services.rag_graph import graph
from settings import limits

CASES = [
    ('서연', '영화 촬영 당시의 집과 지금 방문하는 카페 건물은 같은 건물인가요?'),
    ('초원사진관', '지금의 사진관은 영화 촬영 당시부터 그대로 보존된 시설인가요?'),
    ('자하문', '어떤 작품의 어떤 장면과 관련된 장소인가요? 자료로 확인되는 범위만 알려주세요.'),
    ('혜원의 집', '어떤 작품과 관련된 집이고, 실제 방문 주소는 어디인가요?'),
    ('합천 영상', '이 장소의 내일 입장료와 운영시간을 지금 자료만으로 확정할 수 있나요?'),
]


def baseline(item, question):
    from langchain_openai import ChatOpenAI
    config = limits()
    model = ChatOpenAI(model=os.getenv('GMS_MODEL', 'gpt-5.4-nano'), api_key=os.environ['GMS_KEY'],
                       base_url=os.getenv('GMS_BASE_URL', 'https://gms.ssafy.io/gmsapi/api.openai.com/v1/'),
                       max_completion_tokens=config['output_tokens'], max_retries=0, timeout=40)
    call = cache.reserve_call(config['daily_calls'])
    response = model.invoke([{'role':'system','content':'촬영지 질문에 한국어로 5문장 이내로 답하세요. 알 수 없으면 모른다고 답하세요.'},
                             {'role':'user','content':item['name']+'\n'+question}])
    cache.record_usage(call, response.usage_metadata or {})
    return response.content


def run(live=False):
    if live and not os.getenv('GMS_KEY', '').strip():
        raise ValueError('실제 비교에는 로컬 GMS_KEY 설정이 필요합니다. 키 값은 출력하지 않습니다.')
    catalog, rows = load_catalog(), []
    for term, question in CASES:
        item = next((p for p in catalog if term in p['name']), None)
        if item is None:
            rows.append(dict(term=term, status='항목 없음'))
            continue
        sources = retrieve_vectors(item, question)
        row = dict(place=item['name'], question=question, references=[dict(title=s['title'],url=s['url'],text=s['text']) for s in sources],
                   baseline_answer=None, rag_answer=None, status='GMS 제외: 답변 비교 미실행',
                   human_review={'사실 정확성':None,'근거 제시':None,'모름 응답':None,'검토자':None,'메모':''})
        if live:
            started = perf_counter()
            row['baseline_answer'] = baseline(item, question)
            state = graph.invoke(dict(item=item, question=question, history=[]))
            row['rag_answer'] = state['result']['answer']
            row['seconds'] = round(perf_counter()-started,3)
            row['status'] = '실제 답변 확보 / 사람의 품질 채점 대기'
        rows.append(row)
    out = ROOT / 'data/validation'
    out.mkdir(exist_ok=True, parents=True)
    (out/'rag_quality_comparison.json').write_text(json.dumps(dict(real_gms_used=live,cases=rows),ensure_ascii=False,indent=2),encoding='utf-8')
    lines = ['# RAG 전후 답변 품질 비교', '', '판정: '+('실제 답변 확보, 수동 평가 대기' if live else 'GMS 실호출 제외 요청으로 답변 비교 미실행. 평가 질문 5개와 실제 로컬 근거만 준비함.'), '']
    for i,row in enumerate(rows,1):
        lines += [f"## {i}. {row.get('place',row.get('term'))}",row.get('question',''),'',
                  'RAG 이전 답변: '+str(row.get('baseline_answer') or '미실행'),'',
                  'RAG 이후 답변: '+str(row.get('rag_answer') or '미실행'),'',
                  '사실 정확성 / 근거 제시 / 모름 응답: 사람의 검토 대기','']
    (out/'rag_quality_comparison.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'cases':len(rows),'real_gms_used':live,'quality_passed':False},ensure_ascii=False))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-gms', action='store_true', help='실제 모델을 최대 10회 호출한다. 기본값은 호출하지 않음.')
    run(parser.parse_args().run_gms)
