"""실제 키·외부 호출 없이 캡처→검색→근거 후보와 캐시를 검증한다."""
import io
import json
import os
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from streamlit.testing.v1 import AppTest

from services.scene_finder import find_scene, prepare_image, Findings, validate_findings, Clues, source_excerpt


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

    # 네 번째 검색 기사, 긴 본문 뒤의 촬영지 문장, 시각 미확인도 후보 유지.
    location_quote = "드라마 남자친구 8회 갈대밭 장면은 시흥 갯골생태공원에서 촬영했다."
    article = "일반 소개 문장. " * 600 + location_quote
    excerpt = source_excerpt({'text': '갈대밭 전망대 촬영 안내'}, article, '남자친구')
    assert location_quote in excerpt and len(excerpt) <= 1000
    articles = [dict(title='촬영 기사 '+str(i), url='https://example.com/article/'+str(i),
                     text='드라마 관련 기사 요약', source_type='웹 검색 요약') for i in range(6)]
    unconfirmed = Findings.model_validate({'candidates': [{'place': '시흥 갯골생태공원',
        'reason': '기사에서 해당 작품의 촬영지로 명시', 'differences': '캡처와 일치 여부는 미확인',
        'visual_match': 'unconfirmed', 'evidence': [{'source_id': 4, 'quote': location_quote}]}],
        'uncertainty': '기사의 촬영지이며 현재 장면의 정답인지는 확인 필요'})
    def fake_json(stage, messages, schema, identity):
        if stage == 'clues':
            return Clues.model_validate(clues), {'cache_hit': False}
        prompt = messages[0]['content'][0]['text']
        assert location_quote in prompt and '시각 비교가 불확실해도 후보를 남긴다' in prompt
        return unconfirmed, {'cache_hit': False}
    with patch('services.scene_finder.call_json', side_effect=fake_json), \
         patch('services.scene_finder.search_web', return_value=articles), \
         patch('services.scene_finder.fetch_text', side_effect=lambda url: article if url.endswith('/3') else '다른 소개') as fetch:
        result = find_scene('남자친구', raw, '갈대밭 전망대', [], compare_photos=False)
        assert fetch.call_count == 6, '앞의 두 기사만 읽으면 뒤쪽 촬영지를 놓친다'
        assert result['candidates'][0]['place'] == '시흥 갯골생태공원'
        assert result['candidates'][0]['visual_match'] == 'unconfirmed'
        assert not result['candidates'][0]['reference_ids']

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
