from fastapi.testclient import TestClient

from immich_dog_tagger.api.app import create_app
from immich_dog_tagger.enums import PipelineOperation


def test_health_endpoint():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "scheduler" in data


def test_schedules_crud_and_enable_disable(api_client):
    response = api_client.post(
        "/schedules",
        json={
            "name": "Nightly full pipeline",
            "operation": PipelineOperation.FULL_PIPELINE,
            "expression": "0 * * * *",
            "timezone_name": "UTC",
            "enabled": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Nightly full pipeline"
    assert payload["enabled"] is True

    schedule_id = payload["id"]

    list_response = api_client.get("/schedules")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    disable_response = api_client.post(f"/schedules/{schedule_id}/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["enabled"] is False

    enable_response = api_client.post(f"/schedules/{schedule_id}/enable")
    assert enable_response.status_code == 200
    assert enable_response.json()["enabled"] is True

    update_response = api_client.put(
        f"/schedules/{schedule_id}",
        json={"name": "Updated nightly sync"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated nightly sync"

    run_now_response = api_client.post(f"/schedules/{schedule_id}/run-now")
    assert run_now_response.status_code == 200
    assert run_now_response.json()["operation"] == PipelineOperation.FULL_PIPELINE
    assert api_client.app.state.fake_job_dispatcher.triggers == 1

    get_response = api_client.get(f"/schedules/{schedule_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == schedule_id
