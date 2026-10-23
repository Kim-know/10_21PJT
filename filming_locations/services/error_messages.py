"""비밀값과 원문 응답을 노출하지 않는 API 오류 안내."""
def search_error_message(error):
    status = getattr(error, 'status_code', None)
    kind = type(error).__name__
    body = getattr(error, 'body', None)
    detail = body.get('error', body) if isinstance(body, dict) else {}
    code = detail.get('code', '') if isinstance(detail, dict) else ''
    if status == 401:
        message = 'GMS 인증이 거절됐습니다. 실행 앱의 키 설정과 키 변경 후 서버 재시작 여부를 확인해 주세요.'
    elif status == 403:
        message = 'GMS가 요청 권한을 거절했습니다. 사용 가능한 모델과 접근 권한을 확인해 주세요.'
    elif status == 429:
        if code in ('insufficient_quota', 'quota_exceeded', 'billing_hard_limit_reached'):
            message = 'GMS 서버가 할당량 제한을 응답했습니다. 계정 잔여량과 이 키·모델에 적용된 한도를 확인해 주세요.'
        else:
            message = 'GMS가 요청 제한을 응답했습니다. 잔여 토큰과 별개인 순간 호출 제한일 수 있습니다. 잠시 뒤 다시 실행해 주세요.'
    elif status == 400:
        message = 'GMS가 요청 형식을 거절했습니다. 설정한 모델의 이미지 입력 지원과 요청 옵션을 확인해야 합니다.'
    elif status == 404:
        message = '설정한 GMS 모델 또는 API 경로를 찾지 못했습니다.'
    elif status is not None and status >= 500:
        message = 'GMS 서버에서 일시적인 오류가 발생했습니다. 잠시 뒤 다시 실행해 주세요.'
    elif 'Timeout' in kind:
        message = 'GMS 응답 대기 시간이 초과됐습니다. 할당량 소진을 뜻하지 않습니다.'
    elif 'Connection' in kind or 'Connect' in kind:
        message = 'GMS 서버에 연결하지 못했습니다. 네트워크·프록시·서버 연결 상태를 확인해 주세요.'
    else:
        message = '검색 처리 중 오류가 발생했습니다. 이 오류만으로 GMS 잔여 할당량 부족이라고 판단할 수 없습니다.'
    # 예외 본문과 키/주소는 표시하지 않는다.
    allowed = {'AuthenticationError','PermissionDeniedError','RateLimitError','BadRequestError',
               'NotFoundError','InternalServerError','APITimeoutError','APIConnectionError',
               'TypeError','KeyError','AttributeError','RuntimeError','ImportError','ModuleNotFoundError'}
    diagnostic = kind if kind in allowed else '처리 오류'
    if isinstance(status, int):
        diagnostic += f' · HTTP {status}'
    return f'{message} (진단: {diagnostic}) 자동 재호출은 하지 않습니다.'
