from acadix import create_app
from acadix.models import (
    create_shared_roadmap,
    get_shared_roadmap,
    get_topic_stats,
    set_cached_in_db,
    get_cached_from_db,
)


def test_database_cache_and_share_round_trip():
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "GROQ_API_KEY": "test-key-not-real",
        }
    )
    with app.app_context():
        set_cached_in_db("Python", "مبتدئ", "cached markdown")
        assert get_cached_from_db("python", "مبتدئ") == "cached markdown"

        share_id = create_shared_roadmap(
            "Python", "مبتدئ", "shared markdown", [{"title": "Course", "platform": "Test", "link": "https://example.com"}]
        )
        assert len(share_id) == 12
        shared = get_shared_roadmap(share_id)
        assert shared["roadmap"] == "shared markdown"
        assert shared["courses"][0]["title"] == "Course"
        assert get_shared_roadmap("not-a-real-id") is None
        assert get_topic_stats()[0]["topic"] == "python"
