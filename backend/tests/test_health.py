from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    res = TestClient(app).get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["database"] == "ok" and body["redis"] == "ok"
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
