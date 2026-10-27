import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.auth import get_current_user
from app.db.models import Base, DraftRevision, LiteratureWorkflow, Project, User
from app.db.session import get_db
from app.main import app


def test_assignment_api_routes_work_through_final_admin_approval():
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

    users = {
        role: User(
            id=uuid.uuid4(),
            email=f"{role}@assignment.test",
            hashed_password="not-used",
            role=role,
            is_active=True,
        )
        for role in ("admin", "project_manager", "reviewer", "writer")
    }
    active_user = {"user": users["admin"]}
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: active_user["user"]
    try:
        with TestClient(app) as client:
            with test_session() as db:
                db.add_all(users.values())
                db.flush()
                project = Project(
                    name="Assignment API project",
                    research_question="Can each role advance the workflow?",
                    owner_id=users["writer"].id,
                )
                db.add(project)
                db.flush()
                workflow = LiteratureWorkflow(
                    project_id=project.id,
                    research_question=project.research_question,
                    status="completed",
                    current_stage="pending_human_review",
                    result_json={"draft": {"title": "API draft"}},
                )
                db.add(workflow)
                db.flush()
                db.add(
                    DraftRevision(
                        project_id=project.id,
                        workflow_id=workflow.id,
                        version_number=1,
                        content_json={
                            "title": "API draft",
                            "key_findings": [],
                        },
                        status="pending_review",
                    )
                )
                db.commit()
                workflow_id = str(workflow.id)
                project_id = project.id

            base_url = "/api/v1/workflow-assignments"
            unassigned = client.get(f"{base_url}/unassigned")
            assert unassigned.status_code == 200, unassigned.text
            assert unassigned.json()["items"][0]["workflow_id"] == workflow_id
            assigned = client.post(
                f"{base_url}/{workflow_id}/assign",
                json={"user_ids": [str(users["project_manager"].id)]},
            )
            assert assigned.status_code == 200, assigned.text
            assert assigned.json()["current_stage"] == "assigned_to_project_manager"

            active_user["user"] = users["project_manager"]
            manager_inbox = client.get(f"{base_url}/mine")
            assert manager_inbox.status_code == 200
            assert manager_inbox.json()["items"][0]["workflow_id"] == workflow_id
            forwarded = client.post(
                f"{base_url}/{workflow_id}/assign",
                json={"user_ids": [str(users["reviewer"].id)]},
            )
            assert forwarded.status_code == 200, forwarded.text
            assert forwarded.json()["current_stage"] == "assigned_to_team_leader"

            active_user["user"] = users["reviewer"]
            forwarded = client.post(
                f"{base_url}/{workflow_id}/assign",
                json={"user_ids": [str(users["writer"].id)]},
            )
            assert forwarded.status_code == 200, forwarded.text
            assert forwarded.json()["current_stage"] == "assigned_to_writer"

            active_user["user"] = users["writer"]
            revision = client.get(f"{base_url}/{workflow_id}/draft")
            assert revision.status_code == 200, revision.text
            saved = client.put(
                f"{base_url}/{workflow_id}/draft",
                json={
                    "content": {
                        "title": "Updated by Writer",
                        "key_findings": [],
                    },
                    "comment": "Updated draft.",
                },
            )
            assert saved.status_code == 200, saved.text
            submitted = client.post(
                f"{base_url}/{workflow_id}/complete",
                json={"comment": "Ready for review."},
            )
            assert submitted.status_code == 200, submitted.text
            assert submitted.json()["current_stage"] == "team_lead_review"

            active_user["user"] = users["reviewer"]
            team_lead_review = client.get(
                f"/api/v1/projects/{project_id}/workflows/{workflow_id}/review"
            )
            assert team_lead_review.status_code == 200, team_lead_review.text
            team_lead_decision = client.post(
                f"/api/v1/projects/{project_id}/workflows/"
                f"{workflow_id}/review/decision",
                json={"decision": "approved", "comment": "Reviewed."},
            )
            assert team_lead_decision.status_code == 200, team_lead_decision.text
            assert team_lead_decision.json()["status"] == "pending_review"

            active_user["user"] = users["project_manager"]
            manager_decision = client.post(
                f"/api/v1/projects/{project_id}/workflows/"
                f"{workflow_id}/review/decision",
                json={"decision": "approved", "comment": "Reviewed."},
            )
            assert manager_decision.status_code == 200, manager_decision.text
            assert manager_decision.json()["status"] == "pending_review"

            active_user["user"] = users["admin"]
            admin_decision = client.post(
                f"/api/v1/projects/{project_id}/workflows/"
                f"{workflow_id}/review/decision",
                json={"decision": "approved", "comment": "Final approval."},
            )
            assert admin_decision.status_code == 200, admin_decision.text
            assert admin_decision.json()["status"] == "approved"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
