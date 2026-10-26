
import os
from pathlib import Path

import requests

API_BASE_URL = os.getenv(
    "PHARMAWRITE_API_URL",
    "http://localhost:8000",
).rstrip("/")

TIMEOUT = 60


class APIError(Exception):
    pass


def login(email: str, password: str) -> dict | None:
    return request_json(
        "POST",
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )


def register(email: str, password: str) -> dict | None:
    return request_json(
        "POST",
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )


def get_current_user(token: str) -> dict | None:
    return request_json("GET", "/api/v1/auth/me", token=token)


def get_ollama_status() -> dict:
    response = request_json("GET", "/health/ollama")
    if not isinstance(response, dict):
        raise APIError("The API returned an invalid Ollama status response.")
    return response


def list_projects(token: str, limit: int = 100, offset: int = 0):
    return request_json(
        "GET",
        "/api/v1/projects/",
        token=token,
        params={"limit": limit, "offset": offset},
    )


def create_project(
    name: str,
    research_question: str,
    token: str,
    description: str | None = None,
):
    return request_json(
        "POST",
        "/api/v1/projects/",
        token=token,
        json={
            "name": name,
            "research_question": research_question,
            "description": description,
        },
    )


def request_json(method, path, **kwargs):
    url = f"{API_BASE_URL}{path}"
    token = kwargs.pop("token", None)
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.request(
            method,
            url,
            timeout=kwargs.pop("timeout", TIMEOUT),
            headers=headers,
            **kwargs,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        detail = "The API request failed."
        response = getattr(exc, "response", None)

        if response is not None:
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = payload.get("detail", detail)
            except (ValueError, AttributeError, TypeError):
                pass

        raise APIError(str(detail)) from exc

    if not response.content:
        return None

    try:
        return response.json()
    except ValueError as exc:
        raise APIError("The API returned invalid JSON.") from exc


def upload_pdf(project_id: str, uploaded_file, token: str):
    return request_json(
        "POST",
        f"/api/v1/projects/{project_id}/documents",
        token=token,
        files={
            "file": (
                Path(uploaded_file.name).name,
                uploaded_file.getvalue(),
                "application/pdf",
            )
        },
        timeout=900,
    )


def list_documents(project_id: str, token: str):
    return request_json(
        "GET",
        f"/api/v1/projects/{project_id}/documents",
        token=token,
    )


def index_document(project_id: str, document_id: str, token: str):
    return request_json(
        "POST",
        f"/api/v1/projects/{project_id}/documents/{document_id}/index",
        token=token,
        timeout=300,
    )


def ask_knowledge_base(
    project_id: str,
    query: str,
    document_ids: list[str],
    token: str,
    top_k: int = 6,
):
    return request_json(
        "POST",
        f"/api/v1/projects/{project_id}/knowledge-base/ask",
        token=token,
        json={
            "query": query,
            "document_ids": document_ids,
            "top_k": top_k,
        },
        timeout=1900,
    )


def start_workflow(
    project_id: str,
    research_question: str,
    document_ids: list[str],
    token: str,
    top_k: int = 8,
):
    return request_json(
        "POST",
        f"/api/v1/projects/{project_id}/workflows",
        token=token,
        json={
            "research_question": research_question,
            "document_ids": document_ids,
            "top_k": top_k,
        },
        timeout=1900,
    )


def get_workflow(project_id: str, workflow_id: str, token: str):
    return request_json(
        "GET",
        f"/api/v1/projects/{project_id}/workflows/{workflow_id}",
        token=token,
    )


def submit_for_review(project_id: str, workflow_id: str, token: str):
    return request_json(
        "POST",
        f"/api/v1/projects/{project_id}/workflows/"
        f"{workflow_id}/submit-review",
        token=token,
    )


def get_review_queue(token: str):
    return request_json(
        "GET",
        "/api/v1/review-queue/",
        token=token,
    )


def get_review(project_id: str, workflow_id: str, token: str):
    return request_json(
        "GET",
        f"/api/v1/projects/{project_id}/workflows/"
        f"{workflow_id}/review",
        token=token,
    )


def save_review(
    project_id: str,
    workflow_id: str,
    content: dict,
    token: str,
    comment: str = "Draft edited; review required again.",
):
    return request_json(
        "PUT",
        f"/api/v1/projects/{project_id}/workflows/"
        f"{workflow_id}/review",
        token=token,
        json={"content": content, "comment": comment},
    )


def record_decision(
    project_id: str,
    workflow_id: str,
    decision: str,
    comment: str,
    token: str,
):
    return request_json(
        "POST",
        f"/api/v1/projects/{project_id}/workflows/"
        f"{workflow_id}/review/decision",
        token=token,
        json={
            "decision": decision,
            "comment": comment,
        },
    )


def download_export(
    project_id: str,
    workflow_id: str,
    file_format: str,
    token: str,
):
    if file_format not in ("pdf", "docx"):
        raise ValueError("Unsupported export format.")

    return requests.get(
        f"{API_BASE_URL}/api/v1/projects/{project_id}/"
        f"workflows/{workflow_id}/export",
        params={"format": file_format},
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )