"""step7_skeleton.py에서 분리한 실제 인용 근거 표시."""
import re

CITE_PATTERN = re.compile(r"\[근거\s*([\d,\s]+)\]")


def cited_sources(answer: str, sources: list[dict]) -> list[tuple[int, dict]]:
    numbers = {
        int(n.strip())
        for group in CITE_PATTERN.findall(answer)
        for n in group.split(",")
        if n.strip().isdigit()
    }
    return [(i, source) for i, source in enumerate(sources, 1) if i in numbers]


def render_sources(answer: str, sources: list[dict]) -> None:
    import streamlit as st

    used = cited_sources(answer, sources)
    if not used:
        st.caption("답변에 인용된 근거가 없습니다.")
        return
    with st.expander(f"답변에 사용한 근거 {len(used)}건"):
        for number, source in used:
            st.write(f"[근거 {number}] {source['title']}")
            st.caption(source.get('source_type', '외부 문서'))
            st.link_button("원문 보기", source["url"])
