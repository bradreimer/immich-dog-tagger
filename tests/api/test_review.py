def test_review_queue(api_client):
    response = api_client.get(
        "/review",
        params={
            "limit": 5,
        },
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_review_stats(api_client):
    response = api_client.get("/review/stats")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] >= 0
    assert data["reviewed"] >= 0
    assert data["remaining"] >= 0

    assert data["remaining"] == (data["total"] - data["reviewed"])
