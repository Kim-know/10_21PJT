"""모델에 보낸 근거와 화면 인용이 어긋나는 상황·API 실패를 검증."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from services.llm import answer_with_usage
from ui.sources import cited_sources


def response(text):
    return SimpleNamespace(content=text, usage_metadata={}, response_metadata={'finish_reason': 'stop'})


def run():
    item = {'id': 'grounding-test', 'name': '테스트 장소'}
    docs = [dict(title='긴 문서', url='https://example.com/1', text='가' * 2000),
            dict(title='예산 밖 문서', url='https://example.com/2', text='나' * 2000)]
    with TemporaryDirectory() as directory, patch.dict(os.environ, {
            'APP_CACHE_DIR': directory, 'GMS_KEY': 'fake-test-only', 'MAX_CONTEXT_CHARS': '800'}), \
            patch('services.llm.ChatOpenAI') as model:
        model.return_value.invoke.return_value = response('근거 있는 내용 [근거 1]')
        result = answer_with_usage(item, '유효한 질문', docs, [])
        assert len(result['sources']) == 1 and len(result['sources'][0]['text']) == 800
        assert cited_sources(result['answer'], result['sources'])
        assert not result['grounding_rejected']
        model.return_value.invoke.return_value = response('전달하지 않은 문서 주장 [근거 2]')
        result = answer_with_usage(item, '잘못된 인용', docs, [])
        assert result['grounding_rejected'] and '전달하지 않은 문서 주장' not in result['answer']
        model.return_value.invoke.return_value = response('근거 없는 영업시간은 오전 9시입니다.')
        assert answer_with_usage(item, '인용 없음', docs, [])['grounding_rejected']
        model.return_value.invoke.return_value = response('문서에서 확인되지 않습니다.')
        assert not answer_with_usage(item, '알 수 없는 질문', docs, [])['grounding_rejected']
        assert cited_sources('근거 없는 안내', docs) == []
        model.return_value.invoke.side_effect = RuntimeError('TEST API FAILURE')
        try:
            answer_with_usage(item, 'API 실패 질문', docs, [])
            raise AssertionError('실패를 답변으로 저장하면 안 됨')
        except RuntimeError:
            pass
    print('PASS: context/citation alignment, invalid/missing citations blocked, refusal allowed, API failure propagation')


if __name__ == '__main__':
    run()
