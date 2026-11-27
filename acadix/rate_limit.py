"""Small in-process IP rate limiter retained from the original application."""
import threading
import time

_lock = threading.Lock()
_hits = {}


def too_many(ip, limit=6, window=3600):
    now = time.time()
    with _lock:
        recent = [stamp for stamp in _hits.get(ip, []) if now - stamp < window]
        blocked = len(recent) >= limit
        if not blocked:
            recent.append(now)
        _hits[ip] = recent
        if len(_hits) > 5000:
            _hits.clear()
        return blocked


def clear_rate_limits():
    with _lock:
        _hits.clear()
