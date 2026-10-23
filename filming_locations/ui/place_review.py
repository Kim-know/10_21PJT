"""검색 후보는 사용자 확인 버튼을 누르기 전까지 저장하지 않는다."""
from urllib.parse import quote

import streamlit as st

from services.cache import digest
from services.confirmed_places import save_confirmed, load_catalog, mark_indexed
from services.geocoding import lookup
from services.vector_store import build_index


def open_archive(place_id):
    st.session_state['app_mode'] = '촬영지 자료실'
    st.session_state['pending_place'] = place_id


def render_place_review(candidate, sources, work, media_type, review_id):
    key = 'review_' + review_id
    st.divider()
    st.markdown('**찾던 장소가 맞나요?**')
    answer = st.radio('장소 확인', ['아직 검토 중', '맞아요', '다른 장소예요'],
                      horizontal=True, key=key + '_answer', label_visibility='collapsed')
    if answer != '맞아요':
        if answer == '다른 장소예요':
            st.caption('이 후보는 저장하지 않아요. 다른 후보나 캡처를 확인해 주세요.')
        else:
            st.caption('맞는 장소인지 확인한 뒤에만 자료실과 지도에 추가됩니다.')
        return
    with st.container(border=True):
        st.caption('저장할 정보를 검수해 주세요. 사용자 확인은 기관의 촬영 사실 검증과 구분해 기록합니다.')
        name = st.text_input('저장할 장소명', value=candidate['place'], max_chars=150, key=key + '_name')
        address = st.text_input('확인한 주소', value=candidate.get('address', ''), max_chars=300, key=key + '_address')
        region = st.text_input('지역', value=(candidate.get('address', '').split() or [''])[0],
                               max_chars=100, placeholder='예: 서울특별시 / 제주특별자치도', key=key + '_region')
        episode = st.text_input('회차·시점 (선택)', max_chars=80, key=key+'_episode', placeholder='예: 8회 / 00:32:10')
        scene_description = st.text_area('저장할 장면 설명 (선택)', max_chars=500, key=key+'_scene_description')
        st.link_button('장소명·주소로 지도에서 확인', 'https://map.naver.com/p/search/' + quote(name + ' ' + address))
        st.caption('주소로 저장하면 지도 위치를 자동으로 찾습니다. 위치 검색이 지연되어도 장소는 저장됩니다.')
        latitude = longitude = None
        coordinate_source = ''
        coordinates_confirmed = False
        ready = bool(name.strip() and address.strip() and region.strip())
        if st.button('맞아요, 확인한 장소를 저장할게요', type='primary', disabled=not ready, key=key + '_save'):
            try:
                with st.spinner('확인한 장소를 저장하고 검색 자료에 반영하고 있어요…'):
                    # 저장을 먼저 완료한다. 외부 지오코더 실패가 DB 저장을 막지 않는다.
                    record = save_confirmed(candidate=candidate, sources=sources, work=work,
                        media_type=media_type, name=name, address=address, region=region, confirmed=True,
                        latitude=latitude, longitude=longitude, coordinates_confirmed=coordinates_confirmed,
                        coordinate_source=coordinate_source, episode=episode, scene_description=scene_description)
                    st.session_state[key + '_saved'] = record['id']
                    try:
                        from services.geocoding import resolve_address
                        point = resolve_address(name, address, load_catalog())
                        if point:
                            record = save_confirmed(candidate=candidate, sources=sources, work=work,
                                media_type=media_type, name=name, address=address, region=region, confirmed=True,
                                latitude=point['latitude'], longitude=point['longitude'],
                                coordinates_confirmed=True, coordinate_source='주소 자동 변환 · ' + point['source'],
                                episode=episode, scene_description=scene_description)
                    except Exception:
                        st.info('장소는 저장했습니다. 지도 위치 자동 검색은 완료하지 못했습니다.')

                    try:
                        build_index([record])
                        mark_indexed(record['id'])
                    except Exception:
                        st.warning('장소는 저장됐지만 검색 색인 갱신은 끝내지 못했어요. 자료실의 기본 자료 색인 / 갱신으로 다시 반영할 수 있어요.')
            except ValueError as error:
                st.warning(str(error))
            except Exception:
                st.error('장소를 저장하지 못했어요. 저장 경로와 DB 상태를 확인해 주세요.')
        saved_id = st.session_state.get(key + '_saved')
        if saved_id:
            saved = next((p for p in load_catalog() if p['id'] == saved_id), None)
            if saved:
                st.success('자료실과 지도에 반영했어요.' if saved.get('latitude') is not None
                           else '주소로 자료실에 저장했습니다. 지도 위치는 아직 자동으로 찾지 못했습니다.')
                st.button('저장한 장소를 자료실에서 보기', key=key + '_open',
                          on_click=open_archive, args=(saved_id,))
