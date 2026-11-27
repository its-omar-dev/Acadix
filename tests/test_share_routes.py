from acadix import create_app


def test_share_create_and_public_read_round_trip():
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "GROQ_API_KEY": "test-key-not-real",
        }
    )
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf_token = session["csrf_token"]

    response = client.post(
        "/share",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "topic": "Python",
            "level": "مبتدئ",
            "roadmap": "## خارطة طريق Python",
            "courses": [
                {
                    "title": "دورة تجريبية",
                    "platform": "YouTube",
                    "link": "https://youtube.com/",
                }
            ],
        },
    )
    assert response.status_code == 201
    share_path = response.get_json()["url"]
    assert share_path.startswith("/r/")

    shared = client.get(share_path)
    assert shared.status_code == 200
    assert "خارطة طريق Python".encode() in shared.data


def test_share_rejects_unsafe_course_url():
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "GROQ_API_KEY": "test-key-not-real",
        }
    )
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf_token = session["csrf_token"]

    response = client.post(
        "/share",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "topic": "Python",
            "level": "مبتدئ",
            "roadmap": "roadmap",
            "courses": [{"title": "bad", "platform": "test", "link": "javascript:alert(1)"}],
        },
    )
    assert response.status_code == 400
