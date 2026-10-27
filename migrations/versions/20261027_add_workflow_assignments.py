"""Add multi-assignee workflow routing."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261027_workflow_assignments"
down_revision: Union[str, Sequence[str], None] = "20261027_add_role_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_assignments",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("workflow_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("assigned_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("assigned_by_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("target_user_ids", sa.JSON(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["assigned_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["literature_workflows.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_assignments_assigned_user_id",
        "workflow_assignments",
        ["assigned_user_id"],
    )
    op.create_index(
        "ix_workflow_assignments_workflow_id",
        "workflow_assignments",
        ["workflow_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_assignments_workflow_id",
        table_name="workflow_assignments",
    )
    op.drop_index(
        "ix_workflow_assignments_assigned_user_id",
        table_name="workflow_assignments",
    )
    op.drop_table("workflow_assignments")
