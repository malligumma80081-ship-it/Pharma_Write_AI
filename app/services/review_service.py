
from copy import deepcopy

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import DraftRevision, LiteratureWorkflow


class ReviewError(Exception):
    pass


class ReviewNotFoundError(ReviewError):
    pass


class ReviewConflictError(ReviewError):
    pass


def _get_workflow(
    db: Session,
    project_id,
    workflow_id,
) -> LiteratureWorkflow:
    workflow = db.scalar(
        select(LiteratureWorkflow).where(
            LiteratureWorkflow.id == workflow_id,
            LiteratureWorkflow.project_id == project_id,
        )
    )

    if workflow is None:
        raise ReviewNotFoundError("Workflow not found in this project.")

    if workflow.status not in ("completed", "draft_requires_human_review"):
        raise ReviewConflictError("Workflow does not have a reviewable result.")

    if not isinstance(workflow.result_json, dict):
        raise ReviewConflictError("Workflow has no valid draft result.")

    return workflow


def get_current_revision(
    db: Session,
    project_id,
    workflow_id,
) -> DraftRevision:
    workflow = _get_workflow(db, project_id, workflow_id)

    revision = db.scalar(
        select(DraftRevision)
        .where(DraftRevision.workflow_id == workflow_id)
        .order_by(DraftRevision.version_number.desc())
        .limit(1)
    )

    if revision is not None:
        return revision

    draft_snapshot = workflow.result_json.get("draft")
    if not isinstance(draft_snapshot, dict):
        draft_snapshot = workflow.result_json

    revision = DraftRevision(
        project_id=project_id,
        workflow_id=workflow_id,
        version_number=1,
        content_json=deepcopy(draft_snapshot),
        status="pending_review",
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)
    return revision


def create_revision(
    db: Session,
    project_id,
    workflow_id,
    content: dict,
    status: str,
    comment: str | None = None,
    reviewer_id: str | None = None,
) -> DraftRevision:
    _get_workflow(db, project_id, workflow_id)

    latest_version = db.scalar(
        select(func.max(DraftRevision.version_number)).where(
            DraftRevision.workflow_id == workflow_id
        )
    )

    revision = DraftRevision(
        project_id=project_id,
        workflow_id=workflow_id,
        version_number=(latest_version or 0) + 1,
        content_json=deepcopy(content),
        status=status,
        reviewer_comment=comment,
        reviewer_id=reviewer_id,
    )

    db.add(revision)
    db.commit()
    db.refresh(revision)
    return revision


def list_revisions(
    db: Session,
    project_id,
    workflow_id,
) -> list[DraftRevision]:
    _get_workflow(db, project_id, workflow_id)

    return list(
        db.scalars(
            select(DraftRevision)
            .where(
                DraftRevision.project_id == project_id,
                DraftRevision.workflow_id == workflow_id,
            )
            .order_by(DraftRevision.version_number.desc())
        ).all()
    )
