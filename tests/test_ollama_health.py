from fastapi.testclient import TestClient

import app.main as main_module
from app.services import ollama_client


def test_ollama_health_reports_connected(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "get_ollama_status",
        lambda: {
            "status": "connected",
            "model": "llama3.2",
            "model_available": True,
        },
    )

    response = TestClient(main_module.app).get("/health/ollama")

    assert response.status_code == 200
    assert response.json() == {
        "status": "connected",
        "model": "llama3.2",
        "model_available": True,
    }


def test_ollama_health_reports_disconnected(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "get_ollama_status",
        lambda: {
            "status": "disconnected",
            "model": "llama3.2",
            "model_available": False,
        },
    )

    response = TestClient(main_module.app).get("/health/ollama")

    assert response.status_code == 200
    assert response.json()["status"] == "disconnected"


def test_generation_uses_configured_long_timeout_and_reports_it(monkeypatch):
    observed = {}

    def timeout_request(*args, **kwargs):
        observed.update(kwargs)
        raise ollama_client.requests.Timeout("model did not respond in time")

    monkeypatch.setattr(ollama_client.requests, "post", timeout_request)

    try:
        ollama_client.generate_json("system", "prompt", {})
    except ollama_client.OllamaError as exc:
        assert "900 seconds" in str(exc)
    else:
        raise AssertionError("Expected an Ollama timeout.")

    assert observed["timeout"] == 900
