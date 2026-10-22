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


FILM_CSS = "\n.example-grid{position:relative;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;background:#252b28;padding:34px 12px;border:1px solid #353b32;border-radius:5px;box-shadow:0 14px 32px #302c201c;isolation:isolate}\n.example-grid:before,.example-grid:after{content:'';position:absolute;left:14px;right:14px;height:10px;background:repeating-linear-gradient(90deg,#eee8da 0 15px,transparent 15px 29px);opacity:.9;pointer-events:none}.example-grid:before{top:11px}.example-grid:after{bottom:11px}\n.scene-example{background:radial-gradient(#7c6c4610 .65px,transparent .7px),#f3ecdc;background-size:5px 5px,auto;border:1px solid #141c16;border-radius:2px;padding:18px;display:flex;flex-direction:column;min-width:0;color:#343b2f;box-shadow:inset 0 0 25px #a7977620}\n.film-frame-number{display:flex;justify-content:space-between;gap:7px;color:#7f6840;border-bottom:1px solid #b8aa8666;padding-bottom:10px;margin-bottom:15px;font-size:10px;font-family:monospace;letter-spacing:1px}.film-frame-number span{font-size:8px;letter-spacing:.7px;align-self:center}\n.example-category{font-size:.75rem;color:#856940;font-weight:700;letter-spacing:.08em;margin-bottom:7px}.example-film{font-size:1.06rem;font-weight:700;margin-bottom:13px;word-break:keep-all}.example-film span{font-size:.75rem;color:#7b806e;font-weight:400}\n.scene-example img{width:100%;height:180px;object-fit:contain;background:#222b25;border-radius:2px;border:4px solid #252b28;display:block;filter:saturate(.9)}\n.example-question{font-size:.84rem;line-height:1.75;margin-top:13px;min-height:60px;word-break:keep-all}.example-arrow{color:#927745;text-align:center;padding:10px 0;font-size:1.2rem}.example-arrow span{font-size:.73rem;vertical-align:middle;margin-left:5px}\n.example-result{border-top:1px solid #b8aa8666;padding-top:16px;flex:1}.example-result h3{font-size:1.08rem!important;padding:0!important;margin:0 0 7px!important;color:#343b2f}.example-address{color:#777d6b;font-size:.76rem;line-height:1.6}.example-result p{font-size:.84rem;line-height:1.8;margin:12px 0;word-break:keep-all}.example-note{font-size:.74rem;line-height:1.75;color:#777d6b;background:#ded5bf60;padding:10px;border-radius:3px}\n.example-links{display:flex;flex-wrap:wrap;gap:14px;margin:18px 0 12px}.example-links a{font-size:.77rem;font-weight:600;color:#805c35;text-decoration:none}.example-credit,.example-credit a{font-size:.75rem;color:#626b59;line-height:1.8;overflow-wrap:anywhere}.example-credit a{text-decoration:underline}\n.st-key-example_gallery,.film-gallery{container-type:inline-size}\n@container(max-width:820px){.example-grid{grid-template-columns:1fr;padding:14px 30px;gap:14px}.example-grid:before,.example-grid:after{top:14px;bottom:14px;width:10px;height:auto;right:auto;background:repeating-linear-gradient(180deg,#eee8da 0 15px,transparent 15px 29px)}.example-grid:before{left:10px}.example-grid:after{left:auto;right:10px}.scene-example{padding:20px}.scene-example img{height:230px}.example-question{min-height:0}.film-frame-number span{font-size:9px}}\n"

FILM_CSS += '\n.example-grid{background:transparent;border:0;border-radius:0;box-shadow:none;padding:0;gap:28px}.example-grid:before,.example-grid:after{display:none}.scene-example{background:white;border:0;border-top:2px solid #202426;border-radius:0;padding:22px 0;box-shadow:none;color:#252a2c}.film-frame-number{display:none}.example-category{color:#a1352b;letter-spacing:0}.example-film{font-size:1.2rem}.scene-example img{border:0;border-radius:0;height:220px;background:#14191c;filter:none}.example-result{border-color:#d6d9d9}.example-result h3{color:#1b2023}.example-address,.example-note,.example-credit,.example-credit a{color:#5c6468}.example-note{background:#eeefed;border-radius:0}.example-arrow,.example-links a{color:#a1352b}.example-result p{color:#353b3e}\n@container(max-width:820px){.example-grid{padding:0;gap:22px}.scene-example{padding:20px 0}.scene-example img{height:240px}}\n'

FILM_CSS += '\n.scene-example img{object-fit:cover;object-position:center;background:transparent}\n'

def render_examples():
    st.divider()
    st.subheader('이런 장면을 찾아볼 수 있어요')
    st.caption('장면 속 단서를 실제 촬영지와 연결한 예시입니다.')
    cards = []
    for index,item in enumerate(EXAMPLES,1):
        e = {key: escape(value, quote=True) for key, value in item.items()}
        map_url = 'https://map.naver.com/p/search/' + quote(item['place'] + ' ' + item['region'])
        cards.append(f'''<article class="scene-example">
<div class="film-frame-number">FRAME {index:02d} <span>35 MM · SCENE TO PLACE</span></div>
<div class="example-category">{e['category']}</div>
<div class="example-film">{e['movie']} <span>({e['year']})</span></div>
<a href="{e['image_source']}" target="_blank" rel="noopener noreferrer" aria-label="{e['movie']} 장면 출처 보기"><img src="{e['image']}" alt="{e['movie']}의 {e['category']} 장면" loading="lazy" width="640" height="420" referrerpolicy="no-referrer"></a>
<div class="example-question">“{e['clue']}”</div>
<div class="example-arrow" aria-label="장면에서 장소로">↓ <span>이 장면의 장소</span></div>
<div class="example-result"><h3>{e['place']}</h3><div class="example-address">{e['region']}</div><p>{e['description']}</p><div class="example-note">{e['note']}</div></div>
<div class="example-links"><a href="{map_url}" target="_blank" rel="noopener noreferrer">지도 보기 ↗</a><a href="{e['source']}" target="_blank" rel="noopener noreferrer">촬영지 근거 ↗</a></div>
<div class="example-credit"><a href="{e['image_source']}" target="_blank" rel="noopener noreferrer">{e['credit']}</a><br>장소 정보: {e['authority']}</div>
</article>''')
    st.markdown('<style>'+FILM_CSS+'</style>',unsafe_allow_html=True)
    with st.container(key='example_gallery'):
        st.markdown('<div class="example-grid">' + ''.join(cards) + '</div>', unsafe_allow_html=True)
    st.caption('위 예시는 실시간 AI 검색 결과가 아닙니다. 세트장·CG이거나 배경 단서가 적은 장면은 위치를 찾기 어려울 수 있어요.')
