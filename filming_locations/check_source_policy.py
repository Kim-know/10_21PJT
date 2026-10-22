"""외부 수집 규칙·실패 시 수집 차단 검증."""
from unittest.mock import patch
from services.source_policy import allowed


def run():
    with patch('services.source_policy.cache.get', return_value={'rules':'User-agent: *\nDisallow: /private\nCrawl-delay: 2'}), \
            patch('services.throttle.wait_turn') as wait:
        assert not allowed('https://example.com/private/file')
        assert allowed('https://example.com/public/file')
        assert wait.call_args.kwargs['interval'] == 2
    with patch('services.source_policy.cache.get', return_value={'blocked': True}):
        assert not allowed('https://example.com/page')
    print('PASS: robots deny/allow, crawl-delay, unavailable policy fail-closed')


if __name__ == '__main__':
    run()
