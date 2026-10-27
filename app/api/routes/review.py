
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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
from app.db.models import (
    DraftRevision,
    LiteratureWorkflow,
    Project,
    WorkflowAssignment,
)
from app.services.review_service import (
    ReviewConflictError,
    ReviewError,
    ReviewNotFoundError,
    create_revision,
    get_current_revision,
    list_revisions,
)
from app.services.workflow_assignments import (
    AssignmentError,
    record_review_decision,
)

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Draft Review"],
    dependencies=[
        Depends(require_roles("reviewer", "project_manager", "admin"))
    ],
)
review_queue_router = APIRouter(
    prefix="/api/v1/review-queue",
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


def require_current_assignment(
    db: Session,
    workflow: LiteratureWorkflow,
    user: User,
) -> bool:
    has_assignment_history = db.scalar(
        select(WorkflowAssignment.id)
        .where(WorkflowAssignment.workflow_id == workflow.id)
        .limit(1)
    )
    if has_assignment_history is None:
        if user.role == "project_manager":
            raise HTTPException(
                status_code=403,
                detail="Project Managers may review only workflows assigned to them.",
            )
        return False

    if workflow.current_stage not in (
        "team_lead_review",
        "project_manager_review",
        "admin_review",
    ):
        raise HTTPException(
            status_code=403,
            detail="This workflow is at an assignment or writer stage, not a review stage.",
        )

    assigned = db.scalar(
        select(WorkflowAssignment.id).where(
            WorkflowAssignment.workflow_id == workflow.id,
            WorkflowAssignment.stage == workflow.current_stage,
            WorkflowAssignment.assigned_user_id == user.id,
            WorkflowAssignment.status == "pending",
        )
    )
    if assigned is None:
        raise HTTPException(
            status_code=403,
            detail="You are not assigned to the active workflow stage.",
        )
    return True


@review_queue_router.get("/")
def read_review_queue(
    db: Session = Depends(get_db),
):
    workflows = db.scalars(
        select(LiteratureWorkflow)
        .join(Project, Project.id == LiteratureWorkflow.project_id)
        .where(
            LiteratureWorkflow.status == "completed",
            LiteratureWorkflow.current_stage == "submitted_to_team_lead",
        )
        .order_by(LiteratureWorkflow.updated_at.asc())
        .limit(100)
    ).all()

    queue = []
    for workflow in workflows:
        revision = db.scalar(
            select(DraftRevision)
            .where(DraftRevision.workflow_id == workflow.id)
            .order_by(DraftRevision.version_number.desc())
            .limit(1)
        )
        if revision is None or revision.status != "pending_review":
            continue

        project = db.get(Project, workflow.project_id)
        queue.append(
            {
                "project_id": workflow.project_id,
                "project_name": project.name if project else "Unknown project",
                "workflow_id": str(workflow.id),
                "research_question": workflow.research_question,
                "review_status": (
                    "pending_human_review"
                    if revision.status == "pending_review"
                    else revision.status
                ),
                "submitted_at": workflow.updated_at.isoformat(),
            }
        )
    return {"items": queue}


@router.get(
    "/{project_id}/workflows/{workflow_id}/review",
    response_model=DraftReviewResponse,
)
def read_review(
    project_id: int,
    workflow_id: UUID,
    db: Session = Depends(get_db),
    reviewer: User = Depends(get_current_user),
):
    try:
        workflow = db.scalar(
            select(LiteratureWorkflow).where(
                LiteratureWorkflow.id == workflow_id,
                LiteratureWorkflow.project_id == project_id,
            )
        )
        if workflow is None:
            raise HTTPException(status_code=404, detail="Workflow not found.")
        require_current_assignment(db, workflow, reviewer)
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
    reviewer: User = Depends(get_current_user),
):
    try:
        workflow = db.scalar(
            select(LiteratureWorkflow).where(
                LiteratureWorkflow.id == workflow_id,
                LiteratureWorkflow.project_id == project_id,
            )
        )
        if workflow is None:
            raise HTTPException(status_code=404, detail="Workflow not found.")
        require_current_assignment(db, workflow, reviewer)
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
        workflow = db.scalar(
            select(LiteratureWorkflow).where(
                LiteratureWorkflow.id == workflow_id,
                LiteratureWorkflow.project_id == project_id,
            )
        )
        if workflow is None:
            raise HTTPException(status_code=404, detail="Workflow not found.")

        has_assignment_history = require_current_assignment(
            db,
            workflow,
            reviewer,
        )
        if has_assignment_history:
            current = get_current_revision(db, project_id, workflow_id)
            if current.status == "approved":
                raise ReviewConflictError(
                    "This version is already approved. Create a new revision first."
                )
            try:
                record_review_decision(
                    db,
                    workflow,
                    reviewer,
                    (
                        "approved"
                        if request.decision == "approved"
                        else "changes_requested"
                    ),
                    request.comment,
                )
            except AssignmentError as error:
                raise HTTPException(
                    status_code=409,
                    detail=str(error),
                ) from error
            db.refresh(current)
            return serialize_revision(current)

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
        workflow = db.scalar(
            select(LiteratureWorkflow).where(
                LiteratureWorkflow.id == workflow_id,
                LiteratureWorkflow.project_id == project_id,
            )
        )
        if workflow is not None:
            workflow.current_stage = (
                "approved_by_team_lead"
                if request.decision == "approved"
                else "changes_requested_by_team_lead"
            )
            db.add(workflow)
            db.commit()

        return serialize_revision(revision)
    except ReviewError as error:
        handle_error(error)


@router.get("/{project_id}/workflows/{workflow_id}/revisions")
def read_revision_history(
    project_id: int,
    workflow_id: UUID,
    db: Session = Depends(get_db),
    reviewer: User = Depends(get_current_user),
):
    try:
        workflow = db.scalar(
            select(LiteratureWorkflow).where(
                LiteratureWorkflow.id == workflow_id,
                LiteratureWorkflow.project_id == project_id,
            )
        )
        if workflow is None:
            raise HTTPException(status_code=404, detail="Workflow not found.")
        require_current_assignment(db, workflow, reviewer)
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