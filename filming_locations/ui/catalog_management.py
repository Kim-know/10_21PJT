"""사용자 확인 장소의 정정·취소·복원. 기본 공공데이터를 삭제하지 않는다."""
import streamlit as st
from services.confirmed_places import saved_records, revise_record, revision_history
from services.vector_store import sync_review_index


def apply_review(place_id, action, changes, reason):
    record = revise_record(place_id, action=action, changes=changes, reason=reason)
    try:
        sync_review_index(place_id)
    except Exception:
        st.warning('기록은 변경됐지만 색인 반영이 대기 중입니다. 자료실에서 기본 자료 색인 / 갱신을 실행해 주세요.')
        return
    st.session_state.get('documents', {}).pop(place_id, None)
    st.session_state.get('conversations', {}).pop(place_id, None)
    st.rerun()


def render_management(item):
    for scene in item.get('scenes', []):
        with st.expander('확인한 장면 · '+scene['work']+' '+scene.get('episode','')):
            st.write(scene.get('description') or '별도 장면 설명 없음')
            st.caption('사용자 장면 확인 기록 · 공식 기관 검증과 구분')
    records = saved_records(include_inactive=True)
    saved = next((r for r in records if r['id']==item['id'] and not r.get('withdrawn')),None)
    if saved:
        with st.expander('내가 저장한 장소 정정·저장 취소'):
            st.caption('정정 이력을 보존합니다. 이름·주소를 바꾸면 기존 좌표는 비워집니다. 취소한 기록은 복원할 수 있어요.')
            with st.form('correct_'+item['id']):
                name=st.text_input('정정 장소명', value=item['name'], max_chars=150)
                address=st.text_input('정정 주소', value=item['address'], max_chars=300)
                region=st.text_input('정정 지역', value=item['region'], max_chars=100)
                reason=st.text_input('정정·취소 이유', max_chars=500)
                edit=st.form_submit_button('장소 정보 정정')
                withdraw=st.form_submit_button('이 사용자 저장 기록 취소')
            if edit or withdraw:
                try:
                    apply_review(item['id'], 'correct' if edit else 'withdraw',
                        dict(name=name,address=address,region=region) if edit else None, reason)
                except ValueError as error:
                    st.warning(str(error))
            for revision in revision_history(item['id']):
                st.caption(revision['changed_at']+' · '+revision['action']+' · '+revision['reason'])
    inactive = [r for r in records if r.get('withdrawn')]
    if inactive:
        with st.expander('취소한 사용자 기록 복원'):
            selected=st.selectbox('복원할 기록', inactive, format_func=lambda r:r['name']+' · '+r['address'])
            reason=st.text_input('복원 이유', max_chars=500)
            if st.button('선택한 기록 복원'):
                try:
                    apply_review(selected['id'],'restore',None,reason)
                except ValueError as error:
                    st.warning(str(error))
