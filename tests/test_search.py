from acadix import search


def test_search_returns_safe_youtube_fallback_when_provider_fails(monkeypatch):
    class BrokenSearch:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(search, "VideosSearch", BrokenSearch)
    results = search.search_learning_links("تعلم Python")
    assert len(results) == 5
    assert results[0]["link"].startswith("https://www.youtube.com/results?")
    assert all(item["link"].startswith("https://") for item in results)
