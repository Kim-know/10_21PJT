"""절약 동작 검증. GMS/위키 실제 호출 및 모델 다운로드 없음."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from services import cache
from services.llm import answer_with_usage, bounded_history
from services.retrieval import retrieve
from services.wiki import fetch_page


def run():
    with TemporaryDirectory() as directory, patch.dict(os.environ, {
        "APP_CACHE_DIR": directory, "GMS_KEY": "test-not-a-real-key",
        "DAILY_LLM_CALL_LIMIT": "2", "MAX_OUTPUT_TOKENS": "600",
        "MAX_CONTEXT_CHARS": "2600", "MAX_HISTORY_CHARS": "1000",
        "MAX_QUESTION_CHARS": "600", "CHUNK_SIZE": "700", "RETRIEVAL_TOP_K": "3",
    }):
        item = {"id": "test", "name": "테스트 장소"}
        # 본문 뒤에 있는 관련 구절도 검색되어야 한다.
        sources = [{"title": "장소 설명", "url": "https://example.com",
                    "text": "이곳의 역사 기록입니다. " * 1000 + "촬영지는 해변이며 영화 바다의 장면을 촬영했습니다."}]
        evidence = retrieve("영화 촬영지는?", sources, [])
        assert evidence and any("해변" in s["text"] for s in evidence)
        assert len(evidence) <= 3 and sum(len(s["text"]) for s in evidence) <= 2600
        assert retrieve("xyzxyz", sources, []) == []
        assert bounded_history([{"role": "user", "content": "a" * 600},
                                {"role": "assistant", "content": "b" * 600}], 1000) == []
        response = SimpleNamespace(content="해변입니다. [근거 1]",
                                   usage_metadata={"input_tokens": 100, "output_tokens": 20},
                                   response_metadata={"finish_reason": "stop"})
        with patch("services.llm.ChatOpenAI") as model:
            model.return_value.invoke.return_value = response
            first = answer_with_usage(item, "촬영지는?", evidence, [])
            second = answer_with_usage(item, "촬영지는?", evidence, [])
            assert first["llm_called"] and second["cache_hit"] and not second["llm_called"]
            assert model.return_value.invoke.call_count == 1
            assert model.call_args.kwargs["max_completion_tokens"] == 600
            assert model.call_args.kwargs["max_retries"] == 0
            assert cache.call_count() == 1
            # 문서 내용이 바뀌면 이전 답변을 재사용하지 않는다.
            changed = [dict(evidence[0], text="변경된 촬영 근거")]
            answer_with_usage(item, "촬영지는?", changed, [])
            assert model.return_value.invoke.call_count == 2
            try:
                answer_with_usage(item, "새 질문", evidence, [])
            except ValueError as error:
                assert "제한" in str(error)
            else:
                raise AssertionError("일일 호출 제한 미작동")
            assert model.return_value.invoke.call_count == 2
            # 한도에 도달한 후에도 기존 캐시와 근거 없음 응답은 무료로 동작한다.
            assert answer_with_usage(item, "촬영지는?", evidence, [])["cache_hit"]
            assert not answer_with_usage(item, "질문", [], [])["llm_called"]
        wiki_response = {"query": {"pages": [{"pageid": 1, "title": "문서",
                         "fullurl": "https://example.com", "extract": "실제 본문"}]}}
        with patch("services.wiki.request_wikipedia", return_value=wiki_response) as request:
            assert fetch_page("문서") == fetch_page("문서")
            assert request.call_count == 1
        # 새 DB 연결에서도 보존되며 만료된 값은 사용하지 않는다.
        cache.put("test", "expired", {"value": 1}, -1)
        assert cache.get("test", "expired") is None
        assert Path(directory, "service.sqlite3").exists()
    print("PASS: local retrieval, budgets, response/document caches, invalidation, daily cap, expiry")


if __name__ == "__main__":
    run()
