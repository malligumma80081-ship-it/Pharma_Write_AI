from fastapi.testclient import TestClient

from app.main import app


def test_root_reports_application():
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.json()["app"] == "PharmaWrite AI"


def test_health_reports_ok():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
