from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Test Service",
        "version": "0.1.0",
        "environment": "test",
    }
    assert response.headers["X-Request-ID"]


def test_ping(client: TestClient) -> None:
    response = client.get(
        "/api/v1/examples/ping",
        headers={"X-Request-ID": "test-request-id"},
    )

    assert response.status_code == 200
    assert response.json() == {"message": "pong"}
    assert response.headers["X-Request-ID"] == "test-request-id"


def test_echo_validation_error_uses_standard_shape(client: TestClient) -> None:
    response = client.post("/api/v1/examples/echo", json={"message": ""})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"]
    assert body["request_id"] == response.headers["X-Request-ID"]
