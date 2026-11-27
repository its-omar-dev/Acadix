"""Three-tier roadmap cache: popular JSON, process memory, PostgreSQL."""
import json
import threading
import time
from pathlib import Path

from acadix.models import get_cached_from_db, set_cached_in_db

CACHE_TTL = 6 * 60 * 60
_lock = threading.Lock()
_memory = {}
_popular_path = Path(__file__).resolve().parent.parent / "popular.json"


def _load_popular():
    try:
        with _popular_path.open(encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


POPULAR = _load_popular()


def _key(topic, level):
    return f"{topic.strip().lower()}|{level}"


def get_cached(topic, level):
    key = _key(topic, level)
    if key in POPULAR:
        return POPULAR[key]
    with _lock:
        cached = _memory.get(key)
        if cached and time.time() - cached[0] < CACHE_TTL:
            return cached[1]
        _memory.pop(key, None)
    value = get_cached_from_db(topic, level)
    if value:
        with _lock:
            _memory[key] = (time.time(), value)
    return value


def set_cached(topic, level, data):
    key = _key(topic, level)
    with _lock:
        if len(_memory) > 500:
            _memory.clear()
        _memory[key] = (time.time(), data)
    set_cached_in_db(topic, level, data)


def clear_memory_cache():
    with _lock:
        _memory.clear()
