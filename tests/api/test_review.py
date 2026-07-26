def test_review_queue(api_client):
    response = api_client.get(
        "/review",
        params={
            "limit": 5,
        },
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
