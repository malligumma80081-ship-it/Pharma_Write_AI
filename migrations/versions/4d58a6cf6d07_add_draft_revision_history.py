"""Add draft revision history.

Revision ID: 4d58a6cf6d07
Revises: 0c9254b33d16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision: str = "4d58a6cf6d07"
down_revision: Union[str, Sequence[str], None] = "0c9254b33d16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "draft_revisions" in inspector.get_table_names():
        columns = {
            column["name"]: column
            for column in inspector.get_columns("draft_revisions")
        }
        if isinstance(columns.get("project_id", {}).get("type"), sa.Integer):
            return

        row_count = bind.execute(
            text("SELECT count(*) FROM draft_revisions")
        ).scalar_one()
        if row_count:
            raise RuntimeError(
                "Cannot migrate draft_revisions rows because the existing "
                "project_id type is incompatible with integer project IDs. "
                "Export or resolve the existing draft revisions before "
                "running this migration."
            )

        op.drop_table("draft_revisions")

    op.create_table(
        "draft_revisions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("reviewer_comment", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["literature_workflows.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_id",
            "version_number",
            name="uq_draft_revision_workflow_version",
        ),
    )
    op.create_index(
        "ix_draft_revisions_project_id",
        "draft_revisions",
        ["project_id"],
    )
    op.create_index(
        "ix_draft_revisions_workflow_id",
        "draft_revisions",
        ["workflow_id"],
    )
    op.create_index(
        "ix_draft_revisions_status",
        "draft_revisions",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_draft_revisions_status",
        table_name="draft_revisions",
    )
    op.drop_index(
        "ix_draft_revisions_workflow_id",
        table_name="draft_revisions",
    )
    op.drop_index(
        "ix_draft_revisions_project_id",
        table_name="draft_revisions",
    )
    op.drop_table("draft_revisions")
