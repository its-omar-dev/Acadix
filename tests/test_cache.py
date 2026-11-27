from acadix import cache


def test_memory_cache_round_trip(monkeypatch):
    cache.clear_memory_cache()
    monkeypatch.setattr(cache, "set_cached_in_db", lambda *args: None)
    cache.set_cached("phase2-memory-round-trip", "مبتدئ", "خارطة تجريبية")
    assert cache.get_cached("phase2-memory-round-trip", "مبتدئ") == "خارطة تجريبية"
    cache.clear_memory_cache()


def test_popular_cache_has_priority(monkeypatch):
    cache.clear_memory_cache()
    cache.POPULAR["unique-phase2-topic|مبتدئ"] = "popular roadmap"
    monkeypatch.setattr(
        cache, "get_cached_from_db", lambda *args: (_ for _ in ()).throw(AssertionError())
    )
    assert cache.get_cached("unique-phase2-topic", "مبتدئ") == "popular roadmap"
    cache.POPULAR.pop("unique-phase2-topic|مبتدئ")


def test_database_failure_does_not_break_cache_lookup(monkeypatch):
    cache.clear_memory_cache()
    monkeypatch.setattr(
        cache, "get_cached_from_db", lambda *args: (_ for _ in ()).throw(RuntimeError())
    )
    assert cache.get_cached("missing-topic-phase2", "متقدم") is None


def test_database_failure_does_not_break_cache_write(monkeypatch):
    monkeypatch.setattr(
        cache, "set_cached_in_db", lambda *args: (_ for _ in ()).throw(RuntimeError())
    )
    cache.set_cached("offline-topic", "متوسط", "memory only")
    assert cache.get_cached("offline-topic", "متوسط") == "memory only"
    cache.clear_memory_cache()
