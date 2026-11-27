from sqlalchemy import select

from acadix import create_app
from acadix.accounts import create_password_user, save_user_roadmap, user_roadmaps


def make_app():
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "GROQ_API_KEY": "test-key-not-real",
        }
    )


def csrf_for(client):
    with client.session_transaction() as session:
        return session["csrf_token"]


def test_registration_login_and_logout():
    app = make_app()
    client = app.test_client()

    response = client.get("/auth/register")
    assert response.status_code == 200
    assert "إنشاء حساب جديد".encode() in response.data

    response = client.post(
        "/auth/register",
        data={
            "csrf_token": csrf_for(client),
            "display_name": "Test User",
            "email": "TEST@example.com",
            "password": "a-strong-test-password",
        },
    )
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session.get("user_id")

    response = client.post("/auth/logout", data={"csrf_token": csrf_for(client)})
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert "user_id" not in session

    client.get("/auth/login")
    response = client.post(
        "/auth/login",
        data={
            "csrf_token": csrf_for(client),
            "email": "test@example.com",
            "password": "a-strong-test-password",
        },
    )
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session.get("user_id")


def test_registration_rejects_short_password_and_duplicate_email():
    app = make_app()
    client = app.test_client()
    client.get("/auth/register")
    response = client.post(
        "/auth/register",
        data={
            "csrf_token": csrf_for(client),
            "display_name": "Test User",
            "email": "test@example.com",
            "password": "short",
        },
    )
    assert response.status_code == 400

    response = client.post(
        "/auth/register",
        data={
            "csrf_token": csrf_for(client),
            "display_name": "Test User",
            "email": "test@example.com",
            "password": "a-strong-test-password",
        },
    )
    assert response.status_code == 302

    client.get("/auth/register")
    response = client.post(
        "/auth/register",
        data={
            "csrf_token": csrf_for(client),
            "display_name": "Another User",
            "email": "TEST@example.com",
            "password": "another-strong-password",
        },
    )
    assert response.status_code == 409


def test_oauth_provider_without_credentials_is_not_available():
    app = make_app()
    response = app.test_client().get("/auth/google")
    assert response.status_code == 503


def test_generated_roadmap_is_associated_with_its_owner():
    app = make_app()
    with app.app_context():
        user = create_password_user(
            "owner@example.com",
            "Owner",
            "test-password-hash",
        )
        roadmap_id = save_user_roadmap(
            user["id"],
            "Python",
            "مبتدئ",
            "## Python roadmap",
            [{"title": "Course", "platform": "Example", "link": "https://example.com"}],
        )
        engine = app.extensions["acadix_engine"]
        with engine.connect() as connection:
            row = connection.execute(
                select(user_roadmaps).where(user_roadmaps.c.id == roadmap_id)
            ).mappings().one()
        assert row["user_id"] == user["id"]
        assert row["topic"] == "Python"


def test_profile_requires_login_and_updates_display_name():
    app = make_app()
    client = app.test_client()
    assert client.get("/auth/profile").status_code == 302

    client.get("/auth/register")
    response = client.post(
        "/auth/register",
        data={
            "csrf_token": csrf_for(client),
            "display_name": "Original Name",
            "email": "profile@example.com",
            "password": "a-strong-test-password",
        },
    )
    assert response.status_code == 302

    response = client.get("/auth/profile")
    assert response.status_code == 200
    response = client.post(
        "/auth/profile",
        data={
            "csrf_token": csrf_for(client),
            "display_name": "Updated Name",
        },
    )
    assert response.status_code == 302
    response = client.get("/auth/profile")
    assert b"Updated Name" in response.data
