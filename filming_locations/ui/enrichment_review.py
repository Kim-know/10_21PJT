import streamlit as st
from services.enrichment import collect_official, records, review
from services.vector_store import index_documents, collections

def render_enrichment(catalog):
    with st.expander('공식 출처 본문 보강·검토 대기함'):
        st.caption('GMS 호출 없이 기존 공식 출처 최대 5개를 읽습니다. 수집 정책을 지키며 검토한 본문만 색인합니다.')
        if st.button('미수집 공식 출처 5개 본문 수집'):
            with st.spinner('허용된 공식 출처 본문을 수집하고 있어요…'):
                report=collect_official(catalog,5)
            st.info(f"수집 {len(report['collected'])} · 짧거나 빈 본문 {len(report['skipped'])} · 접근 실패 {len(report['failed'])}")
        pending=records('pending')
        st.caption(f'검토 대기 {len(pending)}개 · 승인 {len(records("approved"))}개')
        if pending:
            selected=st.selectbox('검토할 본문',pending,format_func=lambda r:next((p['name'] for p in catalog if p['id']==r['item_id']),r['item_id'])+' · '+r['document']['title'])
            doc=selected['document'];st.link_button('원문과 촬영 관계 확인',doc['url']);st.text(doc['text'][:5000])
            approved=st.checkbox('이 장소 관련 본문이며 원문 이용 조건을 확인했어요')
            if st.button('검토한 본문을 색인에 반영',disabled=not approved):
                try:
                    item=next(p for p in catalog if p['id']==selected['item_id'])
                    index_documents(item,[doc]);review(selected['id'],True);st.rerun()
                except Exception:st.error('본문 색인을 완료하지 못했습니다. 다시 시도해 주세요.')
            if st.button('관련 없는 본문으로 제외'):
                review(selected['id'],False);st.rerun()
