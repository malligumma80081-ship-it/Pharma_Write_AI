from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, DraftRevision, LiteratureWorkflow, Project
from app.services.review_service import create_revision


def test_revision_snapshots_are_preserved():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    original = {
        "title": "Original",
        "executive_summary": "Original summary",
    }
    revised = {
        "title": "Revised",
        "executive_summary": "Updated summary",
    }

    try:
        with Session(engine) as db:
            project = Project(
                name="Revision test project",
                research_question="Are draft snapshots preserved?",
            )
            db.add(project)
            db.flush()

            workflow = LiteratureWorkflow(
                project_id=project.id,
                research_question=project.research_question,
                status="completed",
                result_json=original,
            )
            db.add(workflow)
            db.commit()

            first_revision = create_revision(
                db=db,
                project_id=project.id,
                workflow_id=workflow.id,
                content=original,
                status="pending_review",
            )
            second_revision = create_revision(
                db=db,
                project_id=project.id,
                workflow_id=workflow.id,
                content=revised,
                status="pending_review",
            )

            db.expire_all()
            stored_revisions = (
                db.query(DraftRevision)
                .filter(DraftRevision.workflow_id == workflow.id)
                .order_by(DraftRevision.version_number)
                .all()
            )

            assert first_revision.version_number == 1
            assert second_revision.version_number == 2
            assert stored_revisions[0].content_json == original
            assert stored_revisions[1].content_json == revised
    finally:
        engine.dispose()
