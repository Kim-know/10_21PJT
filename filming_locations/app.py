"""작품명과 캡처로 촬영지 후보를 찾는 Streamlit 앱."""
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')

from services.cache import call_count
from services.scene_finder import find_scene, prepare_image
from settings import limits
from ui.clipboard_image import clipboard_image
from services.confirmed_places import load_catalog
from ui.place_review import render_place_review

st.set_page_config(page_title='장면에서 여행으로', page_icon='🎬', layout='wide')
st.markdown('''<style>
@font-face {font-family:'Gowun Dodum';font-style:normal;font-weight:400;font-display:swap;src:url('https://fonts.gstatic.com/s/gowundodum/v12/3Jn5SD_00GqwlBnWc1TUJF0F.ttf') format('truetype');}
:root {--scene-font:'Gowun Dodum','Malgun Gothic',sans-serif;}
.stApp, .stApp p, .stApp label, .stApp input, .stApp textarea,
.stApp button, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp [data-testid="stMarkdownContainer"], .stApp [data-baseweb="select"] {
font-family:var(--scene-font) !important;
}
.stApp p {line-height:1.8;}
.stApp input, .stApp textarea, .stApp button {letter-spacing:.015em;}
.stApp h1, .stApp h2, .stApp h3 {letter-spacing:-.035em;font-weight:600;}
.block-container {max-width: 1120px; padding-top: 2.5rem;}
h1 {font-size:clamp(1.85rem,4vw,2.8rem) !important; line-height:1.45 !important; word-break:keep-all;}
.scene-kicker {color:#64748b; font-size:.86rem; letter-spacing:.13em; margin-bottom:.6rem;}
.scene-steps {color:#64748b; margin:1rem 0 2rem; font-size:.9rem; display:flex; flex-wrap:wrap; gap:.6rem 1rem;}
.scene-steps span {white-space:nowrap;}
.st-key-scene_layout {container-type:inline-size;}
.st-key-scene_layout [data-testid="stHorizontalBlock"] {align-items:stretch;}
.st-key-scene_layout [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {height:100%;}
.st-key-scene_layout [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"] {flex:1;}
.st-key-video_info_card, .st-key-scene_image_card {height:100%;box-sizing:border-box;}
@container (max-width:820px) {
  .st-key-scene_layout [data-testid="stHorizontalBlock"] {
    flex-direction:column !important; gap:1rem !important;
  }
  .st-key-scene_layout [data-testid="stColumn"] {
    width:100% !important; min-width:100% !important; max-width:100% !important;
    flex:1 1 100% !important;
  }
}
.st-key-video_info_card, .st-key-scene_image_card {
border:1.5px solid #b9c5d3 !important; border-radius:14px; padding:20px !important;
}
.section-label {font-size:1rem;font-weight:700;margin:0;color:var(--text-color,#243247);}
.section-label span {color:#64748b;font-size:.8rem;margin-right:.6rem;}
.st-key-scene_action {border-top:1.5px solid #cbd5e1;padding-top:18px;margin-top:4px;}
.st-key-video_info_card input, .st-key-video_info_card textarea {
border:1px solid #cbd5e1 !important; border-radius:8px;
}
</style>''', unsafe_allow_html=True)
with st.sidebar:
    st.header('🎬 장면에서 여행으로')
    mode = st.radio('메뉴', ['장면으로 장소 찾기', '촬영지 자료실'], key='app_mode')
    st.divider()
    config = limits()
    calls_display = st.empty()
    calls_display.caption(f"오늘 AI 호출 {call_count()} / {config['daily_calls']}회")
    st.caption('새 캡처 검색은 보통 AI 호출 2회입니다. 같은 입력과 자료는 저장한 결과를 재사용합니다.')
    if not os.getenv('GMS_KEY', '').strip():
        st.info('GMS 키 연결 전입니다. 작품명과 캡처 입력 화면을 먼저 확인할 수 있습니다.')

if mode == '촬영지 자료실':
    from archive import render_archive
    render_archive()
    st.stop()

st.markdown('<div class="scene-kicker">FROM SCENE TO PLACE</div>', unsafe_allow_html=True)
st.title('마음에 든 그 장면, 어디일까요?')
st.write('보고 있는 영상의 이름과 캡처 한 장을 보내 주세요. 장소를 찾을 단서와 촬영 정보를 함께 살펴봅니다.')
st.markdown('<div class="scene-steps"><span>01 작품과 장면 입력</span><span>02 배경 단서·촬영 정보 검색</span><span>03 장소 후보와 근거 확인</span></div>', unsafe_allow_html=True)

image_bytes = None
with st.container(key='scene_layout'):
    entry, picture = st.columns(2, gap='large')
    with entry, st.container(border=True, key='video_info_card'):
        st.markdown('<p class="section-label"><span>01</span>영상 정보</p>', unsafe_allow_html=True)
        st.divider()
        media_type = st.segmented_control('영상 종류', ['영화', '드라마', '유튜브', '기타 영상'],
                                          default='영화', selection_mode='single', key='scene_media_type') or '영화'
        labels = {'영화': ('영화 제목', '예: 기생충, 리틀 포레스트'),
                  '드라마': ('드라마 제목', '예: 도깨비, 미스터 션샤인'),
                  '유튜브': ('유튜브 영상 제목', '보고 있는 영상의 정확한 제목'),
                  '기타 영상': ('영상 제목', '예: 뮤직비디오, 예능 프로그램 제목')}
        label, placeholder = labels[media_type]
        work = st.text_input(label, placeholder=placeholder, max_chars=100, key='scene_title_' + media_type)
        channel = st.text_input('유튜브 채널명 (선택)', placeholder='예: 여행 채널 이름', max_chars=80,
                                key='scene_youtube_channel') if media_type == '유튜브' else ''
        hint = st.text_area('장면 설명 (선택)', placeholder='예: 3화에 나온 바닷가 / 주인공들이 비를 피해 내려가는 계단', max_chars=300, height=120)
        compare_photos = st.checkbox('웹에서 찾은 참고 사진도 함께 비교', value=True)
        st.caption('영상 제목은 정확하게, 캡처는 배경이 넓게 보이도록 붙여넣으면 도움이 됩니다.')
    with picture, st.container(border=True, key='scene_image_card'):
        st.markdown('<p class="section-label"><span>02</span>장면 캡처</p>', unsafe_allow_html=True)
        st.divider()
        try:
            image_bytes = clipboard_image()
        except ValueError as error:
            st.error(str(error))
    with st.container(key='scene_action'):
        submitted = st.button('이 장면의 장소 찾기', type='primary', width='stretch')

prepared = None
if image_bytes:
    try:
        prepared = prepare_image(image_bytes)
        with st.expander('올린 장면 미리보기', expanded=True):
            st.image(prepared, caption=work or '찾고 싶은 장면', width='stretch')
    except ValueError as error:
        st.error(str(error))

signature = hashlib.sha256(json.dumps([media_type, work, channel, hint, compare_photos], ensure_ascii=False).encode() + (image_bytes or b'')).hexdigest()
if submitted:
    if not work.strip():
        st.warning('보고 있는 영상의 제목을 입력해 주세요.')
    elif not prepared:
        st.warning('분석할 스크린샷을 Ctrl+V로 붙여넣어 주세요.')
    elif not os.getenv('GMS_KEY', '').strip():
        st.info('입력 화면이 준비됐습니다. GMS 키가 연결되면 실제 이미지 분석과 웹 검색을 시작할 수 있습니다.')
    else:
        try:
            catalog = load_catalog()
            with st.status('장면 속 장소를 찾고 있습니다.', expanded=True) as status:
                step = st.empty()
                result = find_scene(work.strip(), image_bytes, hint, catalog,
                                    compare_photos=compare_photos, progress=step.write,
                                    media_type=media_type, channel=channel.strip())
                status.update(label='검색과 후보 검토를 마쳤습니다.', state='complete')
            st.session_state.scene_result = result
            st.session_state.scene_signature = signature
            calls_display.caption(f"오늘 AI 호출 {call_count()} / {config['daily_calls']}회")
        except ValueError as error:
            st.warning(str(error))
        except Exception:
            st.error('검색을 마치지 못했습니다. GMS 키·이미지 입력 지원 모델·네트워크 설정을 확인해 주세요. 자동으로 재호출하지 않습니다.')

result = st.session_state.get('scene_result')
if result and st.session_state.get('scene_signature') != signature:
    st.caption('입력이 바뀌었습니다. 새 장면의 장소 찾기를 실행해 주세요.')
    result = None
if result:
    st.divider()
    st.subheader('장면에서 읽은 단서')
    st.write(result['clues']['description'])
    if result['clues']['visible_text']:
        st.write('읽힌 글자: ' + ' · '.join(result['clues']['visible_text']))
    if result['clues']['features']:
        st.caption('주요 특징: ' + ' · '.join(result['clues']['features']))
    st.subheader('찾아볼 장소 후보')
    st.caption('시각적 유사성과 촬영 자료를 바탕으로 좁힌 후보입니다. 검색 결과만으로 촬영 장소가 확정되지는 않습니다.')
    if not result['candidates']:
        st.info('현재 근거로는 장소를 좁히지 못했습니다. 다른 각도의 캡처나 회차·장면 설명을 추가해 주세요.')
    for index, candidate in enumerate(result['candidates'], 1):
        with st.container(border=True):
            st.markdown(f"### 후보 {index} · {candidate['place']}")
            st.write(candidate['reason'])
            if candidate['address']:
                st.write('자료에 나온 주소: ' + candidate['address'])
            else:
                st.caption('정확한 주소는 자료에서 확인하지 못했습니다.')
            if candidate['differences']:
                st.write('더 확인할 점: ' + candidate['differences'])
            st.link_button('지도에서 장소 검색', candidate['map_url'])
            for evidence in candidate['evidence']:
                source = result['sources'][evidence['source_id'] - 1]
                st.write('근거: ' + evidence['quote'])
                st.link_button(source['title'][:100] or '촬영 정보 출처', source['url'])
                st.caption(source.get('source_type', '검색 자료'))
            used_refs = [p for p in result['references'] if p['id'] in candidate['reference_ids']]
            for ref in used_refs:
                with st.expander('비교에 참고한 사진 · ' + ref['title'][:70]):
                    st.image(ref['image_url'], width='stretch')
                    st.link_button('사진이 실린 페이지', ref['url'])
            render_place_review(candidate, result['sources'], work.strip(), media_type,
                                hashlib.sha256((signature + str(index)).encode()).hexdigest()[:16])
    if result['uncertainty']:
        st.caption(result['uncertainty'])
    for notice in result['notices']:
        st.warning(notice)
    with st.expander('검색한 자료와 검색어 더 보기'):
        for query in result['queries']:
            st.link_button(query, 'https://www.google.com/search?q=' + quote(query))
        for source in result['sources']:
            st.link_button(source['title'][:100] or '수집 자료', source['url'])
            st.caption(source.get('source_type', '자료'))
    with st.expander('이번 검색 사용량'):
        for usage in result['usage']:
            if usage['cache_hit']:
                st.caption(usage['stage'] + ' · 저장 결과 재사용, GMS 호출 없음')
            else:
                tokens = usage['usage']
                st.caption(f"{usage['stage']} · 입력 {tokens.get('input_tokens', '미제공')} / 출력 {tokens.get('output_tokens', '미제공')}토큰")
else:
    from ui.examples import render_examples
    render_examples()
