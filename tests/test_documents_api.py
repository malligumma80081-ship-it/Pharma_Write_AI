import pymupdf
import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.session import get_db
from app.main import app


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


def test_document_endpoints_use_integer_project_ids(client):
    project_response = client.post(
        "/api/v1/projects/",
        json={
            "name": "Document upload project",
            "research_question": "Can documents use integer project IDs?",
        },
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text(
        (72, 72),
        "This sample document contains enough readable text to verify "
        "that document upload and text extraction work with integer IDs.",
    )
    pdf_bytes = pdf.tobytes()
    pdf.close()

    upload_response = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_response.status_code == 201
    assert upload_response.json()["project_id"] == project_id

    list_response = client.get(f"/api/v1/projects/{project_id}/documents")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["filename"] == "sample.pdf"


def test_document_endpoints_reject_non_integer_project_ids(client):
    response = client.get("/api/v1/projects/not-an-integer/documents")

    assert response.status_code == 422


def test_index_route_accepts_quoted_document_uuid(client):
    project_response = client.post(
        "/api/v1/projects/",
        json={
            "name": "Quoted document ID project",
            "research_question": "Can quoted UUID path values be normalized?",
        },
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    document_id = uuid.uuid4()

    response = client.post(
        f'/api/v1/projects/{project_id}/documents/"{document_id}"/index'
    )

    # The UUID parses successfully; 404 confirms lookup happens instead of
    # request validation failing with "Value must be a Guid".
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found in this project."


def test_index_route_still_rejects_invalid_document_uuid(client):
    project_response = client.post(
        "/api/v1/projects/",
        json={
            "name": "Invalid document ID project",
            "research_question": "Are malformed UUID path values rejected?",
        },
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/documents/not-a-uuid/index"
    )

    assert response.status_code == 422


def test_document_openapi_uses_integer_project_ids():
    operations = app.openapi()["paths"]["/api/v1/projects/{project_id}/documents"]

    for method in ("get", "post"):
        parameter = operations[method]["parameters"][0]
        assert parameter["name"] == "project_id"
        assert parameter["schema"]["type"] == "integer"


def test_retrieval_openapi_uses_integer_project_ids():
    paths = app.openapi()["paths"]
    index_operation = paths[
        "/api/v1/projects/{project_id}/documents/{document_id}/index"
    ]["post"]
    search_operation = paths["/api/v1/projects/{project_id}/search"]["post"]

    for operation in (index_operation, search_operation):
        project_id = next(
            parameter
            for parameter in operation["parameters"]
            if parameter["name"] == "project_id"
        )
        assert project_id["schema"]["type"] == "integer"
