import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.db.models import Project, LiteratureWorkflow, User
from app.db.session import get_db
from app.schemas.workflow import (
    WorkflowCreateRequest,
    WorkflowCreateResponse,
    WorkflowStatusResponse,
)
from app.services.workflow_service import run_literature_workflow


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
            else "Workflow failed. Check its status and server logs."
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

    return WorkflowStatusResponse(
        workflow_id=str(workflow.id),
        project_id=workflow.project_id,
        status=workflow.status,
        current_stage=workflow.current_stage,
        result=workflow.result_json,
        error_message=workflow.error_message,
    )