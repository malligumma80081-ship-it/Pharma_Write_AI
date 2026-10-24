import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import workflow as workflow_routes
from app.db.models import Base
from app.db.session import get_db
from app.main import app
from app.services.workflow_service import make_chunks


@pytest.fixture
def client():
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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_make_chunks_preserves_page_numbers():
    text = (
        "--- Page 1 ---\n"
        "Study design and population details.\n"
        "--- Page 2 ---\n"
        "Outcomes and adverse events."
    )

    chunks = make_chunks(text, chunk_size=100, overlap=10)

    assert len(chunks) == 2
    assert chunks[0].page_start == 1
    assert chunks[1].page_start == 2


def test_make_chunks_empty_text():
    assert make_chunks("") == []


def test_workflow_endpoints_use_integer_project_ids(client, monkeypatch):
    project_response = client.post(
        "/api/v1/projects/",
        json={
            "name": "Workflow project",
            "research_question": "Can workflows use integer project IDs?",
        },
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    monkeypatch.setattr(
        workflow_routes,
        "run_literature_workflow",
        lambda **kwargs: None,
    )
    created = client.post(
        f"/api/v1/projects/{project_id}/workflows",
        json={
            "research_question": "Can workflows use integer project IDs?",
            "document_ids": [str(uuid.uuid4())],
        },
    )

    assert created.status_code == 200
    assert created.json()["project_id"] == project_id
    workflow_id = created.json()["workflow_id"]

    fetched = client.get(
        f"/api/v1/projects/{project_id}/workflows/{workflow_id}"
    )

    assert fetched.status_code == 200
    assert fetched.json()["project_id"] == project_id


def test_workflow_openapi_uses_integer_project_ids():
    paths = app.openapi()["paths"]

    for path in (
        "/api/v1/projects/{project_id}/workflows",
        "/api/v1/projects/{project_id}/workflows/{workflow_id}",
    ):
        operation = paths[path]["post" if path.endswith("/workflows") else "get"]
        project_id = next(
            parameter
            for parameter in operation["parameters"]
            if parameter["name"] == "project_id"
        )
        assert project_id["schema"]["type"] == "integer"