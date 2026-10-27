from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

WorkspaceRole = Literal["writer", "reviewer", "project_manager"]


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    requested_role: WorkspaceRole = "writer"


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    requested_role: str | None = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class UserRoleUpdate(BaseModel):
    role: Literal["writer", "reviewer", "project_manager", "admin"]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"