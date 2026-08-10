def test_health(api_client):
    response = api_client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "scheduler" in data
