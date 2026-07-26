def test_pending_review(api_client):
    response = api_client.get(
        "/review/pending",
        params={
            "limit": 5,
        },
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
