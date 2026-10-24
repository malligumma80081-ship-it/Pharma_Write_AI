"""add literature workflow

Revision ID: 32a7b0984bfc
Revises: 0004_create_study_evidence
Create Date: 2026-10-22 09:56:03.128675

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = '32a7b0984bfc'
down_revision: Union[str, Sequence[str], None] = '0004_create_study_evidence'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "literature_workflows" in inspector.get_table_names():
        columns = {
            column["name"]: column
            for column in inspector.get_columns("literature_workflows")
        }
        if isinstance(columns.get("project_id", {}).get("type"), sa.Integer):
            return

        row_count = bind.execute(
            text("SELECT count(*) FROM literature_workflows")
        ).scalar_one()
        if row_count:
            raise RuntimeError(
                "Cannot migrate literature_workflows rows with legacy project "
                "IDs because projects now use integer IDs. Export or remove "
                "the legacy workflow rows before running this migration."
            )
        op.drop_table("literature_workflows")

    op.create_table(
        "literature_workflows",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("research_question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("current_stage", sa.String(length=80), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_literature_workflows_project_id",
        "literature_workflows",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_literature_workflows_project_id",
        table_name="literature_workflows",
    )
    op.drop_table("literature_workflows")
