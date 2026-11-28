def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200


def test_homepage_is_arabic_rtl(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b'dir="rtl"' in response.data


def test_stats_does_not_expose_data_without_token(client):
    response = client.get("/stats")

    assert response.status_code in {401, 403, 404}


def test_unknown_route_returns_404(client):
    response = client.get("/route-that-does-not-exist")

    assert response.status_code == 404

def test_tutor_rejects_missing_csrf(client):
    response = client.post(
        "/tutor/chat",
        json={"messages": [{"role": "user", "content": "اشرح بايثون"}]},
    )

    assert response.status_code == 403


def test_tutor_returns_answer_with_valid_csrf(client, monkeypatch):
    from acadix import routes

    monkeypatch.setattr(routes, "chat_with_tutor", lambda messages, mode, topic: "شرح تجريبي")
    with client.session_transaction() as session:
        session["csrf_token"] = "test-csrf-token"

    response = client.post(
        "/tutor/chat",
        headers={"X-CSRF-Token": "test-csrf-token"},
        json={
            "messages": [{"role": "user", "content": "ما هي المتغيرات؟"}],
            "mode": "simple",
            "topic": "Python",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["answer"] == "شرح تجريبي"
