import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.auth import get_current_user
from app.db.models import Base, LiteratureWorkflow, Project, User
from app.db.session import get_db
from app.main import app


@pytest.fixture
def review_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with test_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    reviewer = User(
        id=UUID("79072db6-e0c7-442b-965d-45a6ee446bd4"),
        email="reviewer@example.com",
        hashed_password="not-used-in-tests",
        role="reviewer",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: reviewer
    try:
        with TestClient(app) as client:
            with test_session() as db:
                project = Project(
                    name="Draft review API project",
                    research_question="Does draft review preserve versions?",
                )
                db.add(project)
                db.flush()
                workflow = LiteratureWorkflow(
                    project_id=project.id,
                    research_question=project.research_question,
                    status="completed",
                    current_stage="pending_human_review",
                    result_json={
                        "draft": {
                            "title": "Generated title",
                            "executive_summary": "Generated summary",
                            "key_findings": [],
                            "citations": [],
                        },
                        "warnings": ["Review required"],
                    },
                )
                db.add(workflow)
                db.commit()
                project_id = project.id
                workflow_id = workflow.id

            yield client, project_id, workflow_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_draft_review_openapi_uses_integer_project_ids():
    paths = app.openapi()["paths"]
    operation = paths[
        "/api/v1/projects/{project_id}/workflows/{workflow_id}/review"
    ]["get"]
    project_id = next(
        parameter
        for parameter in operation["parameters"]
        if parameter["name"] == "project_id"
    )
    workflow_id = next(
        parameter
        for parameter in operation["parameters"]
        if parameter["name"] == "workflow_id"
    )

    assert project_id["schema"]["type"] == "integer"
    assert workflow_id["schema"]["format"] == "uuid"


def test_review_edit_decision_and_history_endpoints(review_client):
    client, project_id, workflow_id = review_client
    endpoint = (
        f"/api/v1/projects/{project_id}/workflows/{workflow_id}/review"
    )

    loaded = client.get(endpoint)
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["current_revision"]["version_number"] == 1
    assert loaded.json()["current_revision"]["content"] == {
        "title": "Generated title",
        "executive_summary": "Generated summary",
        "key_findings": [],
        "citations": [],
    }

    edited_content = {
        **loaded.json()["current_revision"]["content"],
        "title": "Reviewed title",
    }
    edited = client.put(
        endpoint,
        json={
            "content": edited_content,
            "comment": "Clarified title.",
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["version_number"] == 2
    assert edited.json()["reviewer_comment"] == "Clarified title."

    decision = client.post(
        f"{endpoint}/decision",
        json={"decision": "approved", "comment": "Approved."},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["version_number"] == 3
    assert decision.json()["status"] == "approved"
    assert decision.json()["content"] == edited_content

    history = client.get(
        f"/api/v1/projects/{project_id}/workflows/{workflow_id}/revisions"
    )
    assert history.status_code == 200, history.text
    assert [
        revision["version_number"]
        for revision in history.json()["revisions"]
    ] == [3, 2, 1]
    assert history.json()["revisions"][2]["content"] == {
        "title": "Generated title",
        "executive_summary": "Generated summary",
        "key_findings": [],
        "citations": [],
    }

    blocked_edit = client.put(
        endpoint,
        json={"content": edited_content},
    )
    assert blocked_edit.status_code == 409


def test_writer_cannot_access_review_endpoints(review_client):
    client, project_id, workflow_id = review_client
    writer = User(
        id=UUID("d9cb9f04-beba-4bdb-ae8c-3c7200210102"),
        email="writer@example.com",
        hashed_password="not-used-in-tests",
        role="writer",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: writer

    response = client.get(
        f"/api/v1/projects/{project_id}/workflows/{workflow_id}/review"
    )

    assert response.status_code == 403


def test_review_rejects_invalid_workflow_and_project_ids(review_client):
    client, project_id, _ = review_client

    invalid_project = client.get(
        f"/api/v1/projects/not-an-integer/workflows/{uuid.uuid4()}/review"
    )
    assert invalid_project.status_code == 422

    missing_workflow = client.get(
        f"/api/v1/projects/{project_id}/workflows/{uuid.uuid4()}/review"
    )
    assert missing_workflow.status_code == 404
