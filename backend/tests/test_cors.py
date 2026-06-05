from fastapi.testclient import TestClient

from app.main import app


def test_local_frontend_origin_is_allowed() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
