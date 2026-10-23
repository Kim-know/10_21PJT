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
.stApp h1, .stApp h2, .stApp h3 {letter-spacing:-.035em;font-weight:600;word-break:keep-all;text-wrap:balance;}
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
from ui.slate_theme import apply_slate_theme, CLAPPER, HEADER, HERO
apply_slate_theme()

st.markdown("""<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"]{display:none!important}
.st-key-top_navigation{background:#f7f7f5;border-bottom:1px solid #d9dada;padding:8px 0;margin-bottom:14px}
[data-testid="stLayoutWrapper"]:has(>.st-key-top_navigation){position:sticky;top:3.75rem;z-index:990;background:#f7f7f5;box-shadow:0 6px 12px #171b1d06}
.st-key-top_navigation [role="radiogroup"]{gap:30px;justify-content:center}
.st-key-top_navigation [data-testid="stRadioOption"]{padding:12px 0!important;margin:0!important;border-bottom:2px solid transparent;cursor:pointer}
.st-key-top_navigation [data-testid="stRadioOption"][data-selected="true"]{border-bottom-color:#b33b30}
.st-key-top_navigation [data-testid="stRadioOption"]>div>div>div:not([data-testid="stMarkdownContainer"]){display:none!important}
.st-key-top_navigation [data-testid="stRadioOption"]>div>div{gap:0!important}
.st-key-top_navigation [data-testid="stRadioOption"] p{font-size:14px;font-weight:600;color:#555d61}
.st-key-top_navigation [data-testid="stRadioOption"][data-selected="true"] p{color:#171b1d}
.st-key-top_navigation [data-testid="stRadioOption"]:focus-within{outline:2px solid #b33b30;outline-offset:4px}
.nav-brand{font-size:21px;font-weight:800;letter-spacing:-.05em;color:#171b1d;line-height:1.6;padding:8px 0;margin-bottom:12px}
.stMainBlockContainer.block-container{padding-top:5rem!important}
#scene-search{scroll-margin-top:135px}
@media(max-width:480px){.st-key-top_navigation [role="radiogroup"]{gap:25px}.st-key-top_navigation [data-testid="stRadioOption"] p{font-size:13px}}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="nav-brand">장면에서 여행으로</div>', unsafe_allow_html=True)
with st.container(key='top_navigation'):
    mode = st.radio('메뉴', ['장면으로 장소 찾기', '촬영지 자료실'], horizontal=True,
                    label_visibility='collapsed', key='app_mode')
config = limits()
with st.expander('AI 사용 안내', expanded=False):
    calls_display = st.empty()
    calls_display.caption(f"오늘 AI 호출 {call_count()} / {config['daily_calls']}회")
    st.caption('새 캡처 검색은 보통 AI 호출 2회입니다. 같은 입력과 자료는 저장한 결과를 재사용합니다.')
    if not os.getenv('GMS_KEY', '').strip():
        st.info('GMS 키 연결 전입니다. 작품명과 캡처 입력 화면을 먼저 확인할 수 있습니다.')

if mode == '촬영지 자료실':
    from archive import render_archive
    render_archive()
    st.stop()

st.markdown(HERO, unsafe_allow_html=True)
st.markdown('<div id="scene-search"></div>', unsafe_allow_html=True)
image_bytes = None
with st.container(key='scene_layout'):
    st.markdown(CLAPPER+HEADER,unsafe_allow_html=True)
    entry, picture = st.columns(2, gap='large')
    with entry, st.container(border=True, key='video_info_card'):
        st.markdown('<p class="section-label"><span>SCENE 01</span>영상 정보</p>', unsafe_allow_html=True)
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
        st.markdown('<p class="section-label"><span>FRAME 02</span>장면 캡처</p>', unsafe_allow_html=True)
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
        except Exception as error:
            from services.error_messages import search_error_message
            st.error(search_error_message(error))

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
    with st.expander('검색 결과에 단서 추가하기'):
        st.caption('현재 캡처와 이전 검색 자료를 유지하고 회차·대사·주변 풍경을 추가합니다. 이미지 단서 분석을 재사용하고 최종 후보 검토는 최대 1회 AI 호출합니다.')
        extra_hint = st.text_input('추가 단서',max_chars=200,key='scene_extra_hint')
        if st.button('현재 캡처에 단서 추가해 다시 찾기'):
            try:
                from services.scene_finder import refine_scene
                with st.spinner('기존 단서와 새 검색 자료를 함께 검토하고 있어요…'):
                    refined = refine_scene(result,image_bytes,extra_hint,load_catalog(),compare_photos=compare_photos)
                st.session_state.scene_result = refined
                st.rerun()
            except ValueError as error:
                st.warning(str(error))
            except Exception:
                st.error('추가 검색을 완료하지 못했습니다. 기존 결과는 유지됩니다.')
    st.subheader('찾아볼 장소 후보')
    st.caption('시각적 유사성과 촬영 자료를 바탕으로 좁힌 후보입니다. 검색 결과만으로 촬영 장소가 확정되지는 않습니다.')
    if not result['candidates']:
        st.info('현재 근거로는 장소를 좁히지 못했습니다. 다른 각도의 캡처나 회차·장면 설명을 추가해 주세요.')
    for index, candidate in enumerate(result['candidates'], 1):
        with st.container(border=True):
            st.markdown(f"### 후보 {index} · {candidate['place']}")
            status = candidate.get('visual_match', 'unconfirmed')
            st.caption({'consistent': '자료 속 촬영지 후보 · 장면 공통 특징 확인', 'different': '자료 속 촬영지 후보 · 캡처와 불일치 있음', 'unconfirmed': '자료 속 촬영지 후보 · 캡처 일치 여부 미확인'}.get(status, '캡처 일치 여부 미확인'))
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
            from ui.photo_compare import render_photo_compare
            render_photo_compare(prepared,result['references'],candidate,signature[:12]+'_'+str(index))
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
