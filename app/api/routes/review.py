
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_roles
from app.db.models import User
from app.db.session import get_db
from app.schemas.review import (
    DraftEditRequest,
    DraftRevisionResponse,
    DraftReviewResponse,
    ReviewDecisionRequest,
)
from app.services.review_service import (
    ReviewConflictError,
    ReviewError,
    ReviewNotFoundError,
    create_revision,
    get_current_revision,
    list_revisions,
)

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Draft Review"],
    dependencies=[Depends(require_roles("reviewer", "admin"))],
)


def serialize_revision(revision) -> dict:
    return {
        "id": str(revision.id),
        "workflow_id": str(revision.workflow_id),
        "version_number": revision.version_number,
        "content": revision.content_json,
        "status": revision.status,
        "reviewer_comment": revision.reviewer_comment,
        "reviewer_id": revision.reviewer_id,
        "created_at": revision.created_at.isoformat(),
    }


def handle_error(error):
    if isinstance(error, ReviewNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, ReviewConflictError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    if isinstance(error, ReviewError):
        raise HTTPException(status_code=400, detail=str(error)) from error
    raise error


@router.get(
    "/{project_id}/workflows/{workflow_id}/review",
    response_model=DraftReviewResponse,
)
def read_review(
    project_id: int,
    workflow_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        revision = get_current_revision(db, project_id, workflow_id)
        return {
            "current_revision": serialize_revision(revision),
            "human_review_required": True,
        }
    except ReviewError as error:
        handle_error(error)


@router.put(
    "/{project_id}/workflows/{workflow_id}/review",
    response_model=DraftRevisionResponse,
)
def edit_draft(
    project_id: int,
    workflow_id: UUID,
    request: DraftEditRequest,
    db: Session = Depends(get_db),
):
    try:
        current = get_current_revision(db, project_id, workflow_id)

        if current.status == "approved":
            raise ReviewConflictError(
                "This version is approved. Create a new revision to edit it."
            )

        revision = create_revision(
            db=db,
            project_id=project_id,
            workflow_id=workflow_id,
            content=request.content,
            status="pending_review",
            comment=request.comment,
        )

        return serialize_revision(revision)
    except ReviewError as error:
        handle_error(error)


@router.post(
    "/{project_id}/workflows/{workflow_id}/review/decision",
    response_model=DraftRevisionResponse,
)
def record_decision(
    project_id: int,
    workflow_id: UUID,
    request: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    reviewer: User = Depends(get_current_user),
):
    try:
        current = get_current_revision(db, project_id, workflow_id)

        if current.status == "approved":
            raise ReviewConflictError(
                "This version is already approved. Create a new revision first."
            )

        revision = create_revision(
            db=db,
            project_id=project_id,
            workflow_id=workflow_id,
            content=current.content_json,
            status=request.decision,
            comment=request.comment,
            reviewer_id=str(reviewer.id),
        )

        return serialize_revision(revision)
    except ReviewError as error:
        handle_error(error)


@router.get("/{project_id}/workflows/{workflow_id}/revisions")
def read_revision_history(
    project_id: int,
    workflow_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        revisions = list_revisions(db, project_id, workflow_id)
        return {
            "workflow_id": str(workflow_id),
            "revisions": [
                serialize_revision(revision)
                for revision in revisions
            ],
        }
    except ReviewError as error:
        handle_error(error)