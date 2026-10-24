"""Add users and project ownership.

Revision ID: 3f7c1a9d2b6e
Revises: 2ddb37bff73a
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "3f7c1a9d2b6e"
down_revision: Union[str, Sequence[str], None] = "2ddb37bff73a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=30), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    user_indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_email" not in user_indexes:
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    project_columns = {
        column["name"] for column in inspector.get_columns("projects")
    }
    project_foreign_keys = {
        foreign_key["name"]
        for foreign_key in inspector.get_foreign_keys("projects")
    }
    if "owner_id" not in project_columns:
        with op.batch_alter_table("projects") as batch_op:
            batch_op.add_column(
                sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_projects_owner_id_users",
                "users",
                ["owner_id"],
                ["id"],
            )
    elif "fk_projects_owner_id_users" not in project_foreign_keys:
        with op.batch_alter_table("projects") as batch_op:
            batch_op.create_foreign_key(
                "fk_projects_owner_id_users",
                "users",
                ["owner_id"],
                ["id"],
            )

    project_indexes = {
        index["name"] for index in inspect(op.get_bind()).get_indexes("projects")
    }
    if "ix_projects_owner_id" not in project_indexes:
        op.create_index("ix_projects_owner_id", "projects", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_projects_owner_id", table_name="projects")
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint(
            "fk_projects_owner_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("owner_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
