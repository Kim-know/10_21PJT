"""프로세스 내 외부 요청 간 최소 간격."""
import threading
import time
from urllib.parse import urlparse

_lock = threading.Lock()
_last = {}


def wait_turn(url, interval=1.0):
    host = urlparse(url).netloc or url
    with _lock:
        delay = interval - (time.monotonic() - _last.get(host, 0))
        if delay > 0:
            time.sleep(delay)
        _last[host] = time.monotonic()
