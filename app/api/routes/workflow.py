import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.db.models import DraftRevision, Project, LiteratureWorkflow, User
from app.db.session import get_db
from app.schemas.workflow import (
    WorkflowCreateRequest,
    WorkflowCreateResponse,
    WorkflowStatusResponse,
)
from app.services.workflow_service import run_literature_workflow
from app.services.review_service import (
    ReviewConflictError,
    get_current_revision,
)


router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Literature Workflow"],
)


@router.post(
    "/{project_id}/workflows",
    response_model=WorkflowCreateResponse,
)
def start_workflow(
    project_id: int,
    request: WorkflowCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("writer", "admin")),
):
    project = db.query(Project).filter(
        Project.id == project_id
    ).first()

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    try:
        document_ids = list(dict.fromkeys(
            uuid.UUID(value) for value in request.document_ids
        ))
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="One or more document IDs are invalid",
        )

    workflow = LiteratureWorkflow(
        project_id=project_id,
        research_question=request.research_question,
        status="queued",
        current_stage="queued",
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    try:
        run_literature_workflow(
            db=db,
            workflow=workflow,
            document_ids=document_ids,
            top_k=request.top_k,
        )
    except Exception:
        # The failed state is saved by the service.
        pass

    db.refresh(workflow)

    return WorkflowCreateResponse(
        workflow_id=str(workflow.id),
        project_id=project_id,
        status=workflow.status,
        current_stage=workflow.current_stage,
        message=(
            "Workflow finished; human review is required."
            if workflow.status == "completed"
            else (
                workflow.error_message
                or "Workflow failed. Check its status and server logs."
            )
        ),
    )


@router.get(
    "/{project_id}/workflows/{workflow_id}",
    response_model=WorkflowStatusResponse,
)
def get_workflow_status(
    project_id: int,
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("writer", "reviewer", "admin")),
):
    workflow = db.query(LiteratureWorkflow).filter(
        LiteratureWorkflow.id == workflow_id,
        LiteratureWorkflow.project_id == project_id,
    ).first()

    if not workflow:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found",
        )

    project = db.get(Project, project_id)
    if (
        user.role != "admin"
        and project is not None
        and project.owner_id != user.id
        and user.role != "reviewer"
    ):
        raise HTTPException(status_code=404, detail="Workflow not found")

    latest_revision = db.scalar(
        select(DraftRevision)
        .where(DraftRevision.workflow_id == workflow_id)
        .order_by(DraftRevision.version_number.desc())
        .limit(1)
    )

    return WorkflowStatusResponse(
        workflow_id=str(workflow.id),
        project_id=workflow.project_id,
        status=workflow.status,
        current_stage=workflow.current_stage,
        review_status=(
            (
                "pending_human_review"
                if latest_revision.status == "pending_review"
                else latest_revision.status
            )
            if latest_revision is not None
            else (
                "pending_human_review"
                if workflow.status == "completed"
                else None
            )
        ),
        result=workflow.result_json,
        error_message=workflow.error_message,
    )


@router.post(
    "/{project_id}/workflows/{workflow_id}/submit-review",
)
def submit_workflow_for_review(
    project_id: int,
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("writer", "admin")),
):
    workflow = db.scalar(
        select(LiteratureWorkflow).where(
            LiteratureWorkflow.id == workflow_id,
            LiteratureWorkflow.project_id == project_id,
        )
    )
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    project = db.get(Project, project_id)
    if (
        user.role != "admin"
        and project is not None
        and project.owner_id != user.id
    ):
        raise HTTPException(status_code=404, detail="Workflow not found")

    if workflow.status != "completed":
        raise HTTPException(
            status_code=409,
            detail="Only completed summaries can be submitted for review.",
        )

    if workflow.current_stage not in (
        "pending_human_review",
        "submitted_to_team_lead",
        "changes_requested_by_team_lead",
    ):
        raise HTTPException(
            status_code=409,
            detail="This workflow is not ready for team-lead review.",
        )

    try:
        revision = get_current_revision(db, project_id, workflow_id)
    except ReviewConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if revision.status == "approved":
        raise HTTPException(
            status_code=409,
            detail="This summary has already been approved.",
        )
    if revision.status == "rejected":
        raise HTTPException(
            status_code=409,
            detail="The latest revision was rejected. Create a new revision before resubmitting.",
        )

    workflow.current_stage = "submitted_to_team_lead"
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    return {
        "workflow_id": str(workflow.id),
        "project_id": project_id,
        "status": workflow.status,
        "current_stage": workflow.current_stage,
        "review_status": (
            "pending_human_review"
            if revision.status == "pending_review"
            else revision.status
        ),
        "message": "Summary submitted to the Team Lead review queue.",
    }