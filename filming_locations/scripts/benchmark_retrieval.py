"""기존 공식 촬영 근거를 대상으로 검색 방식 3개의 근거 재발견율을 비교. 답변 정확도 평가와 구분."""
import json
import sys
from pathlib import Path
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.confirmed_places import load_catalog
from services.vector_store import retrieve_vectors

def run():
    cases=[]
    for item in load_catalog():
        document=next((d for d in item.get('research_documents',[]) if d.get('source_type')=='공식 문서의 사실 요약(조사자 작성)'),None)
        if not document:continue
        question=item['name']+' '+', '.join(item.get('verified_works',[]))+' 촬영 관계를 확인할 수 있나요?'
        cases.append((item,document,question))
    results=[]
    for mode in ('similarity','mmr','hybrid'):
        rows=[]
        for item,doc,question in cases:
            started=perf_counter();sources=retrieve_vectors(item,question,mode=mode)
            relevant=[s for s in sources if s.get('source_type')!='항목 메타데이터']
            rows.append(dict(place=item['name'],question=question,expected_url=doc['url'],
                expected_source_retrieved=any(s['url']==doc['url'] for s in relevant),
                seconds=round(perf_counter()-started,4),returned_urls=[s['url'] for s in relevant]))
        results.append(dict(mode=mode,cases=len(rows),source_recall=sum(r['expected_source_retrieved'] for r in rows)/max(1,len(rows)),
                            average_seconds=sum(r['seconds'] for r in rows)/max(1,len(rows)),rows=rows))
    report=dict(real_gms_used=False,evaluation='기존 공식 근거 재발견율: 답변·장면 정답률이 아님',
       limitation='기존 검증 자료에서 만든 내부 검색 평가이며 독립 사용자 질문 평가가 아니다. 순차 실행으로 첫 방식에 모델 초기화 비용 포함.',results=results)
    out=ROOT/'data/validation';out.mkdir(exist_ok=True,parents=True)
    (out/'retrieval_benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    text='# 검색 방식 비교\n\n실제 GMS 호출 없음. 기존 공식 근거를 다시 찾는 비율이며 답변/장면 정확도가 아니다.\n\n|방식|질문 수|근거 재발견율|평균 검색 시간(초)|\n|---|---:|---:|---:|\n'
    for r in results:text+=f"|{r['mode']}|{r['cases']}|{r['source_recall']:.1%}|{r['average_seconds']:.4f}|\n"
    text+='\n기존 자료 기반 내부 평가다. 첫 실행에는 모델 초기화 시간이 포함되므로 속도를 직접 우열 판정하지 않는다. 실제 GMS 답변 비교는 compare_rag.py의 별도 명시 실행으로 진행한다.\n'
    (out/'retrieval_benchmark.md').write_text(text,encoding='utf-8')
    print(json.dumps([{k:v for k,v in r.items() if k!='rows'} for r in results],ensure_ascii=False))
if __name__=='__main__':run()
