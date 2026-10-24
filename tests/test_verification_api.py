import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import verification
from app.db.models import Base, Document
from app.db.session import get_db
from app.main import app
from app.schemas.verification import ClaimAssessment


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
        yield test_client, test_session
    app.dependency_overrides.clear()
    engine.dispose()


def create_project(client: TestClient) -> int:
    response = client.post(
        "/api/v1/projects/",
        json={
            "name": "Verification project",
            "research_question": "Can claims be verified against sources?",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def add_document(test_session, project_id: int) -> uuid.UUID:
    document_id = uuid.uuid4()
    with test_session() as db:
        db.add(
            Document(
                id=document_id,
                project_id=project_id,
                filename="study.pdf",
                content_type="application/pdf",
                file_size_bytes=100,
                page_count=1,
                extracted_text="Study evidence.",
                status="extracted",
            )
        )
        db.commit()
    return document_id


def verification_payload(document_id: uuid.UUID) -> dict:
    return {
        "claims": [
            {
                "claim_id": "claim-1",
                "statement": "The study reported an outcome.",
                "evidence_ids": ["E1"],
            }
        ],
        "citations": [
            {
                "evidence_id": "E1",
                "chunk_id": f"{document_id}_0",
                "document_id": str(document_id),
                "filename": "study.pdf",
                "page_start": 1,
                "page_end": 1,
            }
        ],
    }


def test_verification_route_accepts_integer_project_id_and_citations(
    client,
    monkeypatch,
):
    test_client, test_session = client
    project_id = create_project(test_client)
    document_id = add_document(test_session, project_id)

    def fake_verify_claim(claim, citation_lookup):
        assert citation_lookup["E1"]["document_id"] == str(document_id)
        return ClaimAssessment(
            claim_id=claim.claim_id,
            statement=claim.statement,
            verdict="supported",
            explanation="The supplied passage supports the claim.",
            supporting_evidence_ids=["E1"],
        )

    monkeypatch.setattr(verification, "verify_claim", fake_verify_claim)
    response = test_client.post(
        f"/api/v1/projects/{project_id}/claims/verify",
        json=verification_payload(document_id),
    )

    assert response.status_code == 200, response.text
    assert response.json()["project_id"] == str(project_id)
    assert response.json()["status"] == "human_review_required"
    assert response.json()["assessments"][0]["verdict"] == "supported"


def test_verification_requires_citations(client):
    test_client, _ = client
    project_id = create_project(test_client)

    response = test_client.post(
        f"/api/v1/projects/{project_id}/claims/verify",
        json={
            "claims": [
                {
                    "claim_id": "claim-1",
                    "statement": "The study reported an outcome.",
                    "evidence_ids": ["E1"],
                }
            ]
        },
    )

    assert response.status_code == 422


def test_verification_rejects_duplicate_evidence_ids(client):
    test_client, test_session = client
    project_id = create_project(test_client)
    document_id = add_document(test_session, project_id)
    payload = verification_payload(document_id)
    payload["citations"].append(payload["citations"][0].copy())

    response = test_client.post(
        f"/api/v1/projects/{project_id}/claims/verify",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Duplicate evidence IDs are not allowed"


def test_verification_rejects_document_from_another_project(client):
    test_client, test_session = client
    project_id = create_project(test_client)
    other_project_id = create_project(test_client)
    document_id = add_document(test_session, other_project_id)

    response = test_client.post(
        f"/api/v1/projects/{project_id}/claims/verify",
        json=verification_payload(document_id),
    )

    assert response.status_code == 422
