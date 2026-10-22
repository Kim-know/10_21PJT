"""출처를 확인한 영화 장면과 촬영지의 사용 예시."""
from html import escape
from urllib.parse import quote

import streamlit as st

EXAMPLES = [
    dict(category='골목과 건물', movie='8월의 크리스마스', year='1998',
         image='https://www.koreafilm.or.kr/upload/programMovieManage/a8ae92e9-e788-43cb-bab6-b609e2e517d7.jpg',
         image_source='https://www.koreafilm.or.kr/movie/PM_007190', credit='한국영상자료원 · 영화 스틸',
         clue='사진관 간판과 낮은 건물이 보이는 이 골목은 어디일까요?',
         place='초원사진관', region='전북특별자치도 군산시 구영2길 12-1',
         description='정원이 운영하던 사진관. 영화 속 간판과 건물 외관을 단서로 장소를 찾아볼 수 있어요.',
         note='현재 관광지는 촬영 후 철거된 사진관을 복원한 공간입니다.',
         source='https://www.gunsan.go.kr/tour/m2230', authority='군산시 문화관광'),
    dict(category='바다와 자연', movie='봄날은 간다', year='2001',
         image='https://prettypictures.fr/uploads/2012/11/One_Fine_Spring_day_photo3-640x418.jpg',
         image_source='https://prettypictures.fr/catalogue/1995/one-fine-spring-day-film/', credit='Pretty Pictures · 영화 스틸',
         clue='두 사람이 파도 소리를 녹음하던 바닷가는 어디일까요?',
         place='맹방해수욕장', region='강원특별자치도 삼척시 근덕면 맹방해변 일대',
         description='상우와 은수가 소리를 채집하던 해변. 길게 이어진 모래사장과 해안 풍경을 함께 살펴봐요.',
         note='해변 단위의 촬영지 예시이며, 카메라의 정확한 위치를 뜻하지 않아요.',
         source='https://world.kbs.co.kr/service/contents_view.htm?board_code=traveler&board_seq=4164&id=&lang=k&menu_cate=travel&page=4', authority='KBS WORLD · 삼척 여행'),
    dict(category='카페와 실내', movie='건축학개론', year='2012',
         image='https://2.bp.blogspot.com/-CKVmVThlit0/UPAFz5j3AeI/AAAAAAAACgM/-_-NhvBiC7o/s1600/archi101%2B4.png',
         image_source='https://icrylikeyukooshima.blogspot.com/2013/01/kdrama-architecture-101.html', credit='영화 장면 · 게재: I cry like Yuko Oshima',
         clue='넓은 유리문이 있는 서연의 집은 어디일까요?',
         place='카페 서연의 집', region='제주특별자치도 서귀포시 남원읍 위미해안로 86',
         description='영화 속 서연의 제주 집을 바탕으로 조성한 카페. 유리문과 실내 구조도 장소를 찾는 단서가 됩니다.',
         note='영화의 임시 세트는 철거됐고, 현재 카페는 주요 건축 요소를 반영해 다시 지은 건물입니다.',
         source='https://www.visitjeju.net/kr/detail/view?contentsid=CNTS_000000000018357', authority='제주관광공사 · Visit Jeju'),
]


def render_examples():
    st.divider()
    st.subheader('이런 장면을 찾아볼 수 있어요')
    st.caption('영화 장면 한 장에서 여행할 장소까지. 촬영지 자료로 구성한 사용 예시입니다.')
    cards = []
    for item in EXAMPLES:
        e = {key: escape(value, quote=True) for key, value in item.items()}
        map_url = 'https://map.naver.com/p/search/' + quote(item['place'] + ' ' + item['region'])
        cards.append(f'''<article class="scene-example">
<div class="example-category">{e['category']}</div>
<div class="example-film">{e['movie']} <span>({e['year']})</span></div>
<a href="{e['image_source']}" target="_blank" rel="noopener noreferrer" aria-label="{e['movie']} 장면 출처 보기"><img src="{e['image']}" alt="{e['movie']}의 {e['category']} 장면" referrerpolicy="no-referrer"></a>
<div class="example-question">“{e['clue']}”</div>
<div class="example-arrow" aria-label="장면에서 장소로">↓ <span>이 장면의 장소</span></div>
<div class="example-result"><h3>{e['place']}</h3><div class="example-address">{e['region']}</div><p>{e['description']}</p><div class="example-note">{e['note']}</div></div>
<div class="example-links"><a href="{map_url}" target="_blank" rel="noopener noreferrer">지도 보기 ↗</a><a href="{e['source']}" target="_blank" rel="noopener noreferrer">촬영지 근거 ↗</a></div>
<div class="example-credit"><a href="{e['image_source']}" target="_blank" rel="noopener noreferrer">{e['credit']}</a><br>장소 정보: {e['authority']}</div>
</article>''')
    st.markdown('''<style>
.example-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;container-type:inline-size;}
.scene-example {border:1px solid #cbd5e1;border-radius:16px;overflow:hidden;padding:20px;display:flex;flex-direction:column;min-width:0;}
.example-category {font-size:.8rem;color:#a33e35;font-weight:700;letter-spacing:.04em;margin-bottom:8px;}
.example-film {font-size:1.12rem;font-weight:700;margin-bottom:14px;}.example-film span{font-size:.8rem;color:#64748b;font-weight:400;}
.scene-example img {width:100%;height:180px;object-fit:contain;background:#17202b;border-radius:9px;display:block;}
.example-question {font-size:.85rem;line-height:1.65;margin-top:13px;min-height:56px;word-break:keep-all;}
.example-arrow {color:#b6453b;text-align:center;padding:12px 0;font-size:1.3rem;}.example-arrow span {font-size:.75rem;vertical-align:middle;margin-left:5px;}
.example-result {border-top:1px solid #dce3eb;padding-top:16px;flex:1;}
.example-result h3 {font-size:1.14rem!important;padding:0!important;margin:0 0 7px!important;}
.example-address {color:#64748b;font-size:.78rem;line-height:1.6;}.example-result p {font-size:.87rem;line-height:1.75;margin:12px 0;word-break:keep-all;}
.example-note {font-size:.75rem;line-height:1.7;color:#64748b;background:rgba(148,163,184,.1);padding:10px;border-radius:8px;}
.example-links {display:flex;gap:16px;margin:18px 0 12px;}.example-links a {font-size:.8rem;font-weight:600;color:#a33e35;text-decoration:none;}
.example-credit,.example-credit a {font-size:.67rem;color:#64748b;line-height:1.7;}.example-credit a {text-decoration:underline;}
.st-key-example_gallery {container-type:inline-size;}
@container(max-width:820px){.example-grid{grid-template-columns:1fr;}.scene-example img{height:240px;}.example-question{min-height:0;}}
</style>''', unsafe_allow_html=True)
    with st.container(key='example_gallery'):
        st.markdown('<div class="example-grid">' + ''.join(cards) + '</div>', unsafe_allow_html=True)
    st.caption('위 예시는 실시간 AI 검색 결과가 아닙니다. 세트장·CG이거나 배경 단서가 적은 장면은 위치를 찾기 어려울 수 있어요.')
