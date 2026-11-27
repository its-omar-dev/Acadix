from acadix import create_app
from acadix.models import create_shared_roadmap


def test_health_checks_configured_database_and_stats_requires_admin_token():
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "ADMIN_TOKEN": "test-admin-secret",
            "GROQ_API_KEY": "test-key-not-real",
        }
    )
    client = app.test_client()
    assert client.get("/health").status_code == 200
    assert client.get("/stats").status_code == 401

    with app.app_context():
        create_shared_roadmap("Python", "مبتدئ", "roadmap", [])
    response = client.get("/stats", headers={"Authorization": "Bearer test-admin-secret"})
    assert response.status_code == 200
    assert response.get_json()["topics"][0]["topic"] == "python"


def test_health_returns_503_when_configured_database_is_unavailable(monkeypatch):
    from acadix import routes

    app = create_app({"TESTING": True, "GROQ_API_KEY": "test-key-not-real"})
    app.config["DATABASE_URL"] = "postgresql+psycopg://unreachable"
    monkeypatch.setattr(routes, "check_database", lambda: False)
    assert app.test_client().get("/health").status_code == 503
