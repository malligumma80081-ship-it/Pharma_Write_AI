from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import UserResponse, UserRoleUpdate

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Administration"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get("/users", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db)):
    return list(
        db.scalars(select(User).order_by(User.email.asc())).all()
    )


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: UUID,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("admin")),
):
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.id == current_admin.id and payload.role != "admin":
        raise HTTPException(
            status_code=409,
            detail="Administrators cannot remove their own administrator role.",
        )

    user.role = payload.role
    user.requested_role = None

    db.commit()
    db.refresh(user)
    return user
