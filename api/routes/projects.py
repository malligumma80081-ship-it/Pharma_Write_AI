import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Project
from db.session import get_db
from schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])

ALLOWED_STATUSES = {
    "draft",
    "in_progress",
    "review",
    "completed",
}


@router.post("/", response_model=ProjectResponse, status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
):
    project = Project(
        name=payload.name,
        research_question=payload.research_question,
        description=payload.description,
        status="draft", )
             

    db.add(project)
    db.commit()
    db.refresh(project)

    return project


@router.get("/", response_model=list[ProjectResponse])
def list_projects(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    statement = (
        select(Project)
        .order_by(Project.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update",
        )

    if "status" in changes:
        if changes["status"] not in ALLOWED_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"Status must be one of: {sorted(ALLOWED_STATUSES)}",
            )

    for field, value in changes.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)

    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    db.delete(project)
    db.commit()

    return Response(status_code=204)