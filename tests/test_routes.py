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
