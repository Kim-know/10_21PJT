"""실제 키·외부 호출 없이 캡처→검색→근거 후보와 캐시를 검증한다."""
import io
import json
import os
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from streamlit.testing.v1 import AppTest

from services.scene_finder import find_scene, prepare_image, Findings, validate_findings


def response(data):
    return SimpleNamespace(content=json.dumps(data, ensure_ascii=False), usage_metadata={"input_tokens": 100, "output_tokens": 80},
                           response_metadata={"finish_reason": "stop"})


def run():
    image = io.BytesIO()
    Image.new("RGB", (1600, 900), "#abcabc").save(image, "PNG")
    raw = image.getvalue()
    with Image.open(io.BytesIO(prepare_image(raw))) as checked:
        assert checked.width == 1280 and checked.height == 720
    try:
        prepare_image(b"not an image")
    except ValueError:
        pass
    else:
        raise AssertionError("이미지가 아닌 입력을 거부해야 합니다")

    clues = {"description": "바다 옆 작은 건물", "visible_text": [], "features": ["해변", "흰 건물"],
             "queries": ["테스트작품 해변 촬영지"]}
    findings = {"candidates": [{"place": "테스트해변", "address": "모델이 지어낸 주소 123",
                 "reason": "해안선이 비슷한 후보", "differences": "테스트 데이터이므로 확정할 수 없음",
                 "evidence": [{"source_id": 1, "quote": "테스트해변에서 영화의 바닷가 장면을 촬영했다"}],
                 "reference_ids": [1, 999]}], "uncertainty": "예시 검증용 응답"}
    sources = [{"title": "테스트 촬영 안내", "url": "https://example.com/film",
                "text": "테스트해변에서 영화의 바닷가 장면을 촬영했다. 실제 주소는 아직 확인하지 않았다.",
                "source_type": "테스트 검색 요약"}]
    bad = Findings.model_validate({"candidates": [{**findings["candidates"][0], "place": "없는장소"}], "uncertainty": ""})
    assert validate_findings(bad, sources, []) == []
    with TemporaryDirectory() as directory, patch.dict(os.environ, {
        "APP_CACHE_DIR": directory, "GMS_KEY": "fake-test-key", "DAILY_LLM_CALL_LIMIT": "30"
    }), patch("services.scene_finder.ChatOpenAI") as model, \
        patch("services.scene_finder.search_web") as search, \
        patch("services.scene_finder.fetch_text", return_value=""), \
        patch("services.scene_finder.fetch_public", return_value=(raw, "image/png", None)):
        model.return_value.invoke.side_effect = [response(clues), response(findings)]
        search.side_effect = lambda query, kind="text", limit=4: sources if kind == "text" else [
            {"title": "비교용 사진", "url": "https://example.com/photo", "image": "https://example.com/image.png"}]
        result = find_scene("테스트작품", raw, "", [], compare_photos=True)
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["address"] == "", "근거 없는 주소는 제거해야 합니다"
        assert result["candidates"][0]["reference_ids"] == [1]
        assert result["external_search_succeeded"]
        assert model.return_value.invoke.call_count == 2
        result2 = find_scene("테스트작품", raw, "", [], compare_photos=True)
        assert model.return_value.invoke.call_count == 2, "같은 이미지/근거는 GMS를 재호출하지 않아야 합니다"
        assert all(u["cache_hit"] for u in result2["usage"])
        with patch("services.scene_finder.search_web", return_value=[]):
            empty = find_scene("테스트작품", raw, "", [], compare_photos=False)
            assert empty["candidates"] == []
            assert model.return_value.invoke.call_count == 2

    with patch.dict(os.environ, {"GMS_KEY": ""}):
        app = AppTest.from_file("app.py", default_timeout=30).run()
        assert not app.exception
        assert app.radio[0].value == "장면으로 장소 찾기"
        assert len(app.get("file_uploader")) == 0
        assert app.text_input[0].label == "영화 제목"
        app.button[0].click().run()
        assert any("제목" in warning.value for warning in app.warning)
        assert not app.exception
    print("PASS: image validation, multimodal pipeline, external search, evidence/address guards, caching, main UI")


if __name__ == "__main__":
    run()
