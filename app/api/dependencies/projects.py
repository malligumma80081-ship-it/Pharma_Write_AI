from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Project, User
from app.api.dependencies.auth import get_current_user


def require_project_access(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.owner_id == user.id,
        )
        .first()
    )

    if project is None:
        # Do not reveal whether another customer's project exists.
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    return project