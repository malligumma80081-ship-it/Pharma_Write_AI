from fastapi.testclient import TestClient
from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import evidence as evidence_route
from app.db.models import Base, StudyEvidence
from app.db.session import get_db
from app.main import app
from app.schemas.evidence import EvidenceField, StudyEvidenceExtraction


def test_evidence_and_draft_routes_use_integer_project_ids():
    paths = app.openapi()["paths"]

    for path in (
        "/api/v1/projects/{project_id}/evidence/extract",
        "/api/v1/projects/{project_id}/drafts",
    ):
        project_id = next(
            parameter
            for parameter in paths[path]["post"]["parameters"]
            if parameter["name"] == "project_id"
        )
        assert project_id["schema"]["type"] == "integer"

    assert isinstance(StudyEvidence.__table__.c.project_id.type, Integer)


def test_evidence_extraction_accepts_integer_project_id(monkeypatch):
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
    extraction = StudyEvidenceExtraction(
        study_design=EvidenceField(value="Trial", evidence_ids=["E1"], status="reported"),
        study_population=EvidenceField(value="Adults", evidence_ids=["E1"], status="reported"),
        sample_size=EvidenceField(value="Not reported", status="not_reported"),
        intervention=EvidenceField(value="Treatment", evidence_ids=["E1"], status="reported"),
        comparator=EvidenceField(value="Placebo", evidence_ids=["E1"], status="reported"),
        endpoints=EvidenceField(value="Endpoint", evidence_ids=["E1"], status="reported"),
        outcomes=EvidenceField(value="Outcome", evidence_ids=["E1"], status="reported"),
        adverse_events=EvidenceField(value="Not reported", status="not_reported"),
        study_limitations=EvidenceField(value="Not reported", status="not_reported"),
    )
    monkeypatch.setattr(
        evidence_route,
        "extract_study_evidence",
        lambda **kwargs: (extraction, [], []),
    )

    try:
        with TestClient(app) as client:
            project_response = client.post(
                "/api/v1/projects/",
                json={
                    "name": "Evidence project",
                    "research_question": "Can evidence use integer project IDs?",
                },
            )
            assert project_response.status_code == 201
            project_id = project_response.json()["id"]

            response = client.post(
                f"/api/v1/projects/{project_id}/evidence/extract",
                json={"query": "What study design was used?"},
            )

        assert response.status_code == 200, response.text
        assert response.json()["project_id"] == str(project_id)
        with test_session() as db:
            record = db.query(StudyEvidence).one()
            assert record.project_id == project_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
