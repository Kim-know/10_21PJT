"""사용자 캡처와 검색 참고사진을 나란히 비교. 비교 자체는 GMS를 호출하지 않는다."""
from urllib.parse import urlparse
import streamlit as st


def render_photo_compare(image_bytes, references, candidate, key):
    photos=[r for r in references if urlparse(r.get('image_url','')).scheme in ('http','https')]
    st.markdown('#### 장면과 참고사진 비교')
    if not photos:
        st.caption('확보한 참고사진이 없습니다. 참고 사진 비교를 켜고 다시 검색하거나 장면 단서를 추가해 주세요.')
        return
    used=set(candidate.get('reference_ids',[]))
    photos.sort(key=lambda p:p['id'] not in used)
    choice=st.selectbox('비교할 참고사진',list(range(len(photos))),
        format_func=lambda i:photos[i].get('title') or f'참고사진 {i+1}',key='compare_photo_'+key)
    photo=photos[choice]
    st.caption('왼쪽은 보낸 캡처, 오른쪽은 검색에서 확보한 참고사진입니다. 사진을 눌러 확대할 수 있어요.')
    st.markdown("<style>[class*='st-key-photo_pair_'] [data-testid='stImage'] img{height:300px;object-fit:contain;background:#f6f6f0;border-radius:10px;}</style>",unsafe_allow_html=True)
    with st.container(key='photo_pair_'+key):
        left,right=st.columns(2,gap='medium')
        with left:
            st.markdown('**내가 보낸 장면**')
            st.image(image_bytes,width='stretch')
        with right:
            st.markdown('**검색 참고사진**')
            st.image(photo['image_url'],width='stretch')
            if urlparse(photo.get('url','')).scheme in ('http','https'):
                st.link_button('참고사진 출처',photo['url'])
    if photo['id'] not in used:
        st.caption('이 사진은 검색 참고자료이며 이 후보의 모델 비교 근거로 채택된 사진은 아닙니다.')
    st.caption('비교할 부분: 건물 형태 · 창문/간판 · 길과 지형. 시점·계절·카메라 각도가 다를 수 있고 사진만으로 촬영지를 확정하지 않습니다.')
