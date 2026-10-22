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
        st.link_button('장소명·주소로 지도에서 확인', 'https://map.naver.com/p/search/' + quote(name + ' ' + address))
        coordinate_mode = st.radio('지도에 표시할 위치', ['위치 후보 검색', '위도·경도 직접 입력', '좌표 없이 자료실에만 저장'],
                                    key=key + '_coordinate_mode')
        latitude = longitude = None
        coordinate_source = ''
        if coordinate_mode == '위치 후보 검색':
            st.caption('OpenStreetMap 기반 위치 후보입니다. 동명 장소가 있을 수 있으므로 주소와 지도 위치를 확인해 주세요.')
            query = (name + ' ' + address).strip()
            if st.button('이 장소의 위치 후보 찾기', key=key + '_geocode'):
                try:
                    with st.spinner('지도 위치 후보를 찾고 있어요…'):
                        st.session_state[key + '_geocoded'] = {'query': query, 'points': lookup(query)}
                except Exception:
                    st.warning('위치 후보를 찾지 못했어요. 잠시 후 다시 시도하거나 좌표를 직접 입력해 주세요.')
            found = st.session_state.get(key + '_geocoded', {})
            if found.get('query') == query:
                points = found['points']
                if points:
                    chosen = st.selectbox('주소와 일치하는 위치 후보', list(range(len(points))),
                                          format_func=lambda i: points[i]['label'], index=None,
                                          placeholder='위치 후보를 선택해 주세요', key=key + '_point_' + digest(query)[:8])
                    if chosen is not None:
                        point = points[chosen]
                        latitude, longitude, coordinate_source = point['latitude'], point['longitude'], point['source']
                else:
                    st.info('위치 후보가 없습니다. 정확한 좌표를 직접 입력하거나 좌표 없이 저장할 수 있어요.')
        elif coordinate_mode == '위도·경도 직접 입력':
            left, right = st.columns(2)
            lat_text = left.text_input('위도', placeholder='예: 37.5796', key=key + '_lat')
            lon_text = right.text_input('경도', placeholder='예: 126.9770', key=key + '_lon')
            if lat_text or lon_text:
                try:
                    latitude, longitude = float(lat_text), float(lon_text)
                    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                        raise ValueError
                    coordinate_source = '사용자가 외부 지도에서 확인한 좌표 직접 입력'
                except ValueError:
                    latitude = longitude = None
                    st.warning('올바른 위도·경도를 모두 입력해 주세요.')
        coordinates_confirmed = False
        if latitude is not None:
            st.map([{'lat': latitude, 'lon': longitude}], zoom=14, size=60, height=230)
            st.link_button('OpenStreetMap에서 이 좌표 확인',
                           f'https://www.openstreetmap.org/?mlat={latitude}&mlon={longitude}#map=17/{latitude}/{longitude}')
            coordinates_confirmed = st.checkbox('지도 표식이 이 장소의 위치인 것도 확인했어요',
                key=key + '_coordinate_ok_' + digest([name, address, latitude, longitude])[:12])
        ready = bool(name.strip() and address.strip() and region.strip()
                     and (coordinate_mode == '좌표 없이 자료실에만 저장' or coordinates_confirmed))
        if coordinate_mode == '좌표 없이 자료실에만 저장':
            st.caption('자료실에는 추가되지만, 지도 핀은 확인한 좌표를 추가한 뒤 표시돼요.')
        if st.button('맞아요, 확인한 장소를 저장할게요', type='primary', disabled=not ready, key=key + '_save'):
            try:
                with st.spinner('확인한 장소를 저장하고 검색 자료에 반영하고 있어요…'):
                    record = save_confirmed(candidate=candidate, sources=sources, work=work,
                        media_type=media_type, name=name, address=address, region=region, confirmed=True,
                        latitude=latitude, longitude=longitude, coordinates_confirmed=coordinates_confirmed,
                        coordinate_source=coordinate_source)
                    st.session_state[key + '_saved'] = record['id']
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
                           else '자료실에 저장했어요. 좌표를 확인하면 지도에도 표시할 수 있어요.')
                st.button('저장한 장소를 자료실에서 보기', key=key + '_open',
                          on_click=open_archive, args=(saved_id,))
