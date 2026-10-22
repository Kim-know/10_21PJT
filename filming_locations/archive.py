"""촬영지 자료실: 두 컬렉션 RAG·자연어 탐색·문서 수집."""
import json
import os
from urllib.parse import quote
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from services.catalog import validate_locations
from services.llm import answer_with_usage
from services.retrieval import retrieve
from services.cache import call_count
from settings import limits
from services.wiki import fetch_page
from ui.sources import render_sources
from services.vector_store import counts, build_index, index_documents, search_items
from services.rag_graph import graph
from services.research import collect_for_question, explore
from services.confirmed_places import load_catalog, pending_index_count, saved_records, mark_indexed

def render_archive():
    st.title("🎬 장면에서 여행으로")
    st.caption("영화 촬영지 탐색 · 작품과 장소의 근거를 함께 모으는 여행 지도")
    config = limits()
    indexed = counts()
    with st.sidebar:
        st.caption(f"벡터 색인 · 장소 {indexed['metadata']}건 / 문서 청크 {indexed['documents']}건")
        search_method = st.segmented_control('근거 검색 방식', ['유사도', '다양성 MMR'], default='유사도', key='archive_search_method') or '유사도'
        if not indexed['metadata']:
            st.warning('색인이 없습니다. 아래 기본 자료 색인을 실행해 주세요.')
        st.caption(f"절약 모드 · 오늘 LLM 호출 {call_count()}/{config['daily_calls']}회")
        st.caption(f"근거 최대 {config['context_chars']}자 · 답변 한도 {config['output_tokens']}토큰")
    
    with st.sidebar:
        st.header("촬영지 선택")
        uploaded = st.file_uploader("촬영지 JSON 불러오기", type=["json"])
        try:
            raw = uploaded.getvalue().decode("utf-8-sig") if uploaded else (ROOT / "data/locations.json").read_text(encoding="utf-8-sig")
            locations = validate_locations(json.loads(raw) if uploaded else load_catalog(json.loads(raw)))
            raw = json.dumps(locations, ensure_ascii=False, sort_keys=True)
        except (ValueError, OSError, TypeError):
            st.error("촬영지 JSON 형식이 올바르지 않습니다. README의 필드와 ID·좌표·원문 URL을 확인하세요.")
            st.stop()
        st.caption(f"등록된 촬영지 {len(locations)}곳 / 목표 약 100곳 이상")
        if pending_index_count():
            st.warning('사용자 확인 장소 중 검색 색인이 대기 중인 항목이 있어요. 기본 자료 색인 / 갱신을 실행해 주세요.')
        if not locations:
            st.warning("촬영지 데이터가 없습니다. 확인한 데이터를 data/locations.json에 추가하거나 업로드하세요.")
            st.stop()
        if st.button('기본 자료 색인 / 갱신'):
            with st.status('로컬 임베딩으로 두 컬렉션을 색인합니다. 최초 실행은 모델을 다운로드합니다.'):
                try:
                    indexed = build_index(locations)
                    if not uploaded:
                        for saved in saved_records():
                            mark_indexed(saved['id'])
                    st.success(f"장소 {indexed['metadata']}건 · 문서 청크 {indexed['documents']}건")
                except Exception:
                    st.error('색인을 완료하지 못했습니다. 모델 다운로드 연결과 저장 경로를 확인해 주세요.')
        pending = st.session_state.pop('pending_place', None)
        if pending:
            st.session_state['archive_checked_only'] = False
            st.session_state['archive_region'] = '전체'
            st.session_state['archive_keyword'] = ''
            st.session_state['archive_place'] = pending
        checked_only = st.checkbox("촬영 관계를 별도 확인한 항목만", key='archive_checked_only')
        visible = [dict(p, works=p.get("verified_works", [])) for p in locations if p.get("verified_works")] if checked_only else locations
        if not visible:
            st.info("별도 문서로 확인한 항목이 없습니다.")
            st.stop()
        region = st.selectbox("지역", ["전체"] + sorted({p["region"] for p in visible}), key='archive_region')
        keyword = st.text_input("장소명·작품명 검색", key='archive_keyword')
        options = [p for p in visible if (region == "전체" or p["region"] == region)
                   and keyword.casefold() in (p["name"] + " " + " ".join(p["works"])).casefold()]
        if not options:
            st.info("조건에 맞는 촬영지가 없습니다.")
            st.stop()
        selected_id = st.selectbox("질문할 촬영지", [p["id"] for p in options],
                                   format_func=lambda value: next(p["name"] for p in options if p["id"] == value), key='archive_place')
        item = next(p for p in options if p["id"] == selected_id)
    
    # 데이터가 바뀌어도 같은 ID의 다른 장소에 이전 기록이 붙지 않게 초기화한다.
    if st.session_state.get("catalog_raw") != raw:
        previous = {p['id']: (p['name'], p['address']) for p in json.loads(st.session_state.get('catalog_raw', '[]'))}
        conversations = st.session_state.setdefault('conversations', {})
        documents = st.session_state.setdefault('documents', {})
        for place in locations:
            place_id = place['id']
            if place_id in previous and previous[place_id] != (place['name'], place['address']):
                conversations.pop(place_id, None)
                documents.pop(place_id, None)
            old = documents.get(place_id, [])
            combined = place.get('research_documents', []) + old
            documents[place_id] = list({(d['url'], d['text']): d for d in combined}.values())
        st.session_state.catalog_raw = raw
    messages = st.session_state.conversations.setdefault(selected_id, [])
    st.session_state.documents.setdefault(selected_id, item.get("research_documents", []))
    with st.sidebar:
        if st.button("이 촬영지 대화 지우기"):
            messages.clear()
    
    total, film_count, checked_count = st.columns(3)
    total.metric("수집 장소", len(locations))
    film_count.metric("관련 영화", len({work for p in locations for work in p["works"]}))
    checked_count.metric("별도 촬영 문서 확인 장소", sum(bool(p.get("verified_works")) for p in locations))
    st.caption(f"설명 자료 연결 {sum(bool(p.get('research_documents')) for p in locations)}곳 · "
               f"문서 {sum(len(p.get('research_documents', [])) for p in locations)}건. 공공 원문과 별도 검증 자료를 구분합니다.")
    with st.expander('조건으로 촬영지 찾기 · 자연어 탐색'):
        condition = st.text_input('원하는 장소 조건', placeholder='예: 부산에 있는 바닷가 촬영지', max_chars=300)
        if st.button('조건에 맞는 촬영지 찾기'):
            try:
                with st.spinner('의미 검색 후 조건을 검토하고 있습니다…'):
                    candidates = search_items(condition) if condition.strip() else []
                    if not candidates:
                        raise ValueError('원하는 장소 조건을 입력해 주세요.')
                    st.session_state.explored = {'condition': condition, 'matches': explore(condition, candidates)}
            except ValueError as error:
                st.warning(str(error))
            except Exception:
                st.error('조건 탐색을 완료하지 못했습니다. 색인과 GMS 설정을 확인해 주세요.')
        explored = st.session_state.get('explored', {})
        if explored.get('condition') == condition:
            if not explored['matches']:
                st.info('현재 자료에서 모든 조건을 확인할 수 있는 장소를 찾지 못했습니다.')
            for match in explored['matches']:
                st.markdown('**' + match['title'] + '**')
                st.caption('조건 근거: ' + match['quote'])
                st.link_button('등록 자료 원문', match['url'])
                if st.button('이 장소에 질문하기', key='explore_' + match['item_id']):
                    st.session_state.pending_place = match['item_id']
                    st.rerun()
    with st.expander("수집 목록 살펴보기 · 내려받기"):
        st.caption("한국문화정보원 2022년 원본과 별도 조사 자료를 결합했습니다. 전체 목록이 검증 완료된 것은 아닙니다.")
        st.dataframe([{"장소": p["name"], "지역": p["region"], "영화": ", ".join(p["works"]),
                       "별도 확인 작품": ", ".join(p.get("verified_works", [])),
                       "주소": p["address"], "출처": p["source_url"]} for p in options], hide_index=True)
        st.download_button("전체 촬영지 JSON 내려받기", json.dumps(locations, ensure_ascii=False, indent=2),
                           file_name="filming_locations.json", mime="application/json")
    
    st.subheader(item["name"])
    if item.get('user_confirmed'):
        st.caption('사용자가 검색 결과의 장면 일치를 확인해 저장한 장소입니다. 공식 기관 검증과는 구분됩니다.')
    st.write("관련 작품: " + ", ".join(item["works"]))
    st.write("주소: " + item["address"])
    if item.get("verified_works"):
        st.success("별도 문서로 촬영 관계 확인: " + ", ".join(item["verified_works"]))
        st.caption("확인 표시는 위 작품과 장소의 관계에만 적용됩니다. 현재 영업·개방 여부까지 확인한 표시는 아닙니다.")
    else:
        st.warning("공공데이터에 수록된 조사 후보입니다. 실제 촬영 관계와 현재 운영·개방 여부는 재확인이 필요합니다.")
    for note in item.get("research_notes", []):
        st.caption(note)
    if item.get("relations"):
        with st.expander("원본 데이터의 장면 설명·조사 상태"):
            for relation in item["relations"]:
                st.write(relation["work"] + " · " + relation["status"])
                if relation.get("description"):
                    st.text(relation["description"])
            st.caption("원본 설명에는 오류나 주변 관광 정보가 섞여 있을 수 있습니다. 운영시간 등은 현재 정보로 사용하지 않습니다.")
    st.link_button("등록 정보의 원문", item["source_url"])
    st.markdown('#### 촬영지 위치')
    from ui.location_map import render_location_map
    map_mode = st.radio('지도 범위', ['전체 촬영지', '선택 장소로 확대'], horizontal=True, key='archive_map_mode_v3')
    mapped_count, map_event = render_location_map(locations, selected_id, focus=map_mode == '선택 장소로 확대')
    if isinstance(map_event, dict) and map_event.get('nonce') != st.session_state.get('last_map_event'):
        st.session_state.last_map_event = map_event.get('nonce')
        clicked_id = map_event.get('place_id')
        if clicked_id != selected_id and clicked_id in {p['id'] for p in locations}:
            st.session_state.pending_place = clicked_id
            st.rerun()
    st.caption(f'전체 {len(locations)}곳 중 좌표가 있는 {mapped_count}곳 표시 · 좌표 미확보 {len(locations)-mapped_count}곳. 지도는 지역·검색 필터와 관계없이 전체 목록을 보여줍니다.')
    st.caption('축소하면 밀집도와 장소 수, 확대하면 개별 핀이 보여요. 숫자는 확대, 개별 핀은 장소 설명과 채팅 대상을 바꿉니다.')
    if item.get('latitude') is None or item.get('longitude') is None:
        st.info('선택한 장소는 좌표가 없어 지도 핀을 표시하지 않았어요. 아래 지도 검색으로 확인해 주세요.')
    else:
        st.caption('선택 장소: ' + item['name'] + ' · ' + item.get('coordinate_status', '등록된 좌표'))
    st.link_button('네이버 지도에서 이 장소 보기', 'https://map.naver.com/p/search/' + quote(item['name'] + ' ' + item['address']))
    
    if st.button("장소의 위키 문서 불러오기"):
        with st.status("장소 설명 문서를 수집하고 있습니다…") as status:
            try:
                page = fetch_page(item["wiki_title"])
                if page and page["text"].strip():
                    st.session_state.documents[selected_id] = item.get("research_documents", []) + [page]
                    index_documents(item, [page])
                    status.update(label="문서 수집 완료", state="complete")
                else:
                    status.update(label="본문이 있는 문서를 찾지 못했습니다", state="error")
            except Exception:
                status.update(label="문서 수집 실패. 연락처 설정과 네트워크를 확인하세요.", state="error")
    
    sources = st.session_state.documents.get(selected_id, [])
    with st.expander('질문으로 외부 설명 자료 추가 수집'):
        st.caption('검색어 추출 → 후보 문서 선별 → 본문 수집·색인. 새 질문은 GMS 최대 2회, 같은 완료 수집은 영구 재사용합니다.')
        research_question = st.text_input('설명 자료를 찾을 질문', max_chars=config['question_chars'])
        if st.button('이 질문으로 설명 자료 수집'):
            try:
                with st.status('검색어 추출·문서 선별·본문 색인 중…') as status:
                    report = collect_for_question(item, research_question)
                    st.session_state.documents[selected_id] = sources + [d for d in report['documents']
                        if d['url'] not in {s['url'] for s in sources}]
                    st.session_state.research_report = dict(report, item_id=selected_id)
                    status.update(label='자료 수집 검토 완료', state='complete')
            except ValueError as error:
                st.warning(str(error))
            except Exception:
                st.error('외부 설명 자료 수집을 완료하지 못했습니다. GMS·네트워크 설정을 확인해 주세요.')
        if st.session_state.get('research_report', {}).get('item_id') == selected_id:
            report = st.session_state.research_report
            st.write('검색어: ' + ' / '.join(report['queries']))
            st.caption(f"선택 {len(report['selected'])}개 · 제외 {len(report['rejected'])}개 · 본문 확보 {len(report['documents'])}개")
            if report.get('failed'):
                st.warning('일부 원문을 받지 못했습니다. 해당 문서는 색인하지 않았습니다.')
            if report.get('notice'):
                st.info(report['notice'])
    for source in sources:
        with st.expander("수집한 문서: " + source["title"]):
            st.link_button("문서 원문", source["url"])
            st.text(source["text"][:3000])
            st.caption("본문 미리보기 최대 3,000자. '공식 문서의 사실 요약'은 조사자가 작성한 요약이며 원문 전문이 아닙니다.")
    
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                render_sources(message["content"], message["sources"])
    
    has_key = bool(os.getenv("GMS_KEY", "").strip())
    if not has_key:
        st.warning("채팅하려면 프로젝트 폴더의 .env에 GMS_KEY를 설정하세요.")
    if not sources:
        st.caption("채팅 전에 장소의 위키 문서를 불러오세요.")
    question = st.chat_input("이 촬영지에 대해 물어보세요", disabled=not has_key or not sources,
                             max_chars=config["question_chars"])
    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                with st.spinner("문서를 바탕으로 답변을 만드는 중…"):
                    state = graph.invoke({'item': item, 'question': question, 'history': messages,
                                          'search_mode': 'mmr' if search_method == '다양성 MMR' else 'similarity'})
                    evidence, result = state['sources'], state['result']
                    answer = result["answer"]
                st.markdown(answer)
                render_sources(answer, evidence)
                if result["cache_hit"]:
                    st.caption("저장된 답변 재사용 · 이번 GMS 호출 없음")
                elif result["llm_called"]:
                    usage = result["usage"]
                    st.caption(f"GMS 1회 호출 · 입력 {usage.get('input_tokens', '미제공')} / 출력 {usage.get('output_tokens', '미제공')}토큰")
                else:
                    st.caption("관련 근거 없음 · GMS 호출 없음")
                if result.get("truncated"):
                    st.warning("출력 한도로 답변이 중간에 끝났을 수 있습니다. 질문 범위를 좁혀 주세요.")
            except ValueError as error:
                st.warning(str(error))
            except Exception:
                st.error("답변을 받지 못했습니다. 키·모델 설정과 네트워크를 확인한 뒤 다시 질문하세요.")
            else:
                messages.extend([
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer, "sources": evidence},
                ])
