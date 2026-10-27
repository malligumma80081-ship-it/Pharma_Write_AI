import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.models import DraftRevision, LiteratureWorkflow, User, WorkflowAssignment
from app.db.session import get_db
from app.schemas.assignments import (
    AssignmentCompleteRequest,
    AssignmentCreateRequest,
    AssignmentDecisionRequest,
    AssignmentDraftUpdateRequest,
)
from app.services.review_service import (
    ReviewError,
    create_revision,
    get_current_revision,
)
from app.services.workflow_assignments import (
    AssignmentError,
    assignable_role,
    complete_writer_assignment,
    forward_assignment,
    list_my_assignments,
    record_review_decision,
    start_workflow_assignment,
)

router = APIRouter(
    prefix="/api/v1/workflow-assignments",
    tags=["Workflow Assignments"],
)


def _workflow_or_404(db: Session, workflow_id: uuid.UUID) -> LiteratureWorkflow:
    workflow = db.get(LiteratureWorkflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    if workflow.status not in ("completed", "draft_requires_human_review"):
        raise HTTPException(
            status_code=409,
            detail="Workflow does not have a reviewable result.",
        )
    return workflow


def _handle_assignment_error(error: AssignmentError) -> None:
    raise HTTPException(status_code=409, detail=str(error)) from error


def _serialize_revision(revision: DraftRevision) -> dict:
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


@router.get("/mine")
def my_assignments(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {"items": list_my_assignments(db, user)}


@router.get("/unassigned")
def unassigned_workflows(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only administrators can list unassigned workflows.",
        )
    statement = (
        select(LiteratureWorkflow)
        .where(
            LiteratureWorkflow.status == "completed",
            LiteratureWorkflow.current_stage.in_(
                (
                    "pending_human_review",
                    "submitted_to_team_lead",
                    "changes_requested_by_team_lead",
                )
            ),
            ~exists().where(
                WorkflowAssignment.workflow_id == LiteratureWorkflow.id
            ),
        )
        .order_by(LiteratureWorkflow.updated_at.asc())
        .limit(100)
    )
    workflows = db.scalars(statement).all()
    return {
        "items": [
            {
                "workflow_id": str(workflow.id),
                "project_id": workflow.project_id,
                "research_question": workflow.research_question,
                "current_stage": workflow.current_stage,
            }
            for workflow in workflows
        ]
    }


@router.get("/{workflow_id}/eligible-users")
def eligible_users(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workflow = _workflow_or_404(db, workflow_id)
    try:
        role = assignable_role(db, workflow, user)
    except AssignmentError as error:
        _handle_assignment_error(error)

    users = db.scalars(
        select(User)
        .where(User.role == role, User.is_active.is_(True))
        .order_by(User.email.asc())
    ).all()
    return {
        "role": role,
        "items": [
            {"id": str(item.id), "email": item.email, "role": item.role}
            for item in users
        ],
    }


@router.post("/{workflow_id}/assign")
def assign_work(
    workflow_id: uuid.UUID,
    request: AssignmentCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workflow = _workflow_or_404(db, workflow_id)
    try:
        if (
            user.role == "admin"
            and workflow.current_stage in (
                "pending_human_review",
                "submitted_to_team_lead",
                "changes_requested_by_team_lead",
            )
        ):
            stage = start_workflow_assignment(
                db,
                workflow,
                user,
                request.user_ids,
            )
        else:
            stage = forward_assignment(
                db,
                workflow,
                user,
                request.user_ids,
            )
    except AssignmentError as error:
        _handle_assignment_error(error)

    return {"workflow_id": str(workflow.id), "current_stage": stage}


@router.get("/{workflow_id}/draft")
def read_assigned_draft(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workflow = _workflow_or_404(db, workflow_id)
    if workflow.current_stage != "assigned_to_writer" or user.role != "writer":
        raise HTTPException(status_code=403, detail="This draft is not assigned to you.")
    assignment = db.scalar(
        select(WorkflowAssignment).where(
            WorkflowAssignment.workflow_id == workflow.id,
            WorkflowAssignment.stage == workflow.current_stage,
            WorkflowAssignment.assigned_user_id == user.id,
            WorkflowAssignment.status == "pending",
        )
    )
    if assignment is None:
        raise HTTPException(status_code=403, detail="You are not assigned to this draft.")
    try:
        revision = get_current_revision(
            db,
            workflow.project_id,
            workflow.id,
        )
    except ReviewError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"current_revision": _serialize_revision(revision)}


@router.put("/{workflow_id}/draft")
def update_assigned_draft(
    workflow_id: uuid.UUID,
    request: AssignmentDraftUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workflow = _workflow_or_404(db, workflow_id)
    if workflow.current_stage != "assigned_to_writer" or user.role != "writer":
        raise HTTPException(status_code=403, detail="This draft is not assigned to you.")
    assignment = db.scalar(
        select(WorkflowAssignment).where(
            WorkflowAssignment.workflow_id == workflow.id,
            WorkflowAssignment.stage == workflow.current_stage,
            WorkflowAssignment.assigned_user_id == user.id,
            WorkflowAssignment.status == "pending",
        )
    )
    if assignment is None:
        raise HTTPException(status_code=403, detail="You are not assigned to this draft.")
    try:
        revision = create_revision(
            db=db,
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            content=request.content,
            status="pending_review",
            comment=request.comment,
            reviewer_id=str(user.id),
        )
    except ReviewError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _serialize_revision(revision)


@router.post("/{workflow_id}/complete")
def complete_assignment(
    workflow_id: uuid.UUID,
    request: AssignmentCompleteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workflow = _workflow_or_404(db, workflow_id)
    try:
        get_current_revision(db, workflow.project_id, workflow.id)
        stage = complete_writer_assignment(
            db,
            workflow,
            user,
            request.comment,
        )
    except (AssignmentError, ReviewError) as error:
        if isinstance(error, AssignmentError):
            _handle_assignment_error(error)
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"workflow_id": str(workflow.id), "current_stage": stage}


@router.post("/{workflow_id}/decision")
def review_assignment(
    workflow_id: uuid.UUID,
    request: AssignmentDecisionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workflow = _workflow_or_404(db, workflow_id)
    try:
        stage = record_review_decision(
            db,
            workflow,
            user,
            request.decision,
            request.comment,
        )
    except AssignmentError as error:
        _handle_assignment_error(error)
    return {"workflow_id": str(workflow.id), "current_stage": stage}


@router.get("/{workflow_id}/revision")
def read_assignment_revision(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workflow = _workflow_or_404(db, workflow_id)
    assignment = db.scalar(
        select(WorkflowAssignment).where(
            WorkflowAssignment.workflow_id == workflow.id,
            WorkflowAssignment.stage == workflow.current_stage,
            WorkflowAssignment.assigned_user_id == user.id,
            WorkflowAssignment.status == "pending",
        )
    )
    if assignment is None:
        raise HTTPException(status_code=403, detail="You are not assigned to this review.")
    try:
        revision = get_current_revision(
            db,
            workflow.project_id,
            workflow.id,
        )
    except ReviewError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"current_revision": _serialize_revision(revision)}
