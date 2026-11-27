def test_security_headers_are_present(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_share_requires_csrf_token(client):
    response = client.post(
        "/share",
        json={
            "topic": "Python",
            "level": "مبتدئ",
            "roadmap": "## خارطة",
            "courses": [],
        },
    )
    assert response.status_code == 403


def test_stats_is_hidden_when_admin_token_is_not_configured(client):
    response = client.get("/stats")
    assert response.status_code == 404
