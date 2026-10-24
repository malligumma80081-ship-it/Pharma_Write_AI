import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0004_create_study_evidence"
down_revision = "0003_create_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "study_evidence" in inspector.get_table_names():
        columns = {
            column["name"]: column
            for column in inspector.get_columns("study_evidence")
        }
        if isinstance(columns.get("project_id", {}).get("type"), sa.Integer):
            indexes = {
                index["name"]
                for index in inspector.get_indexes("study_evidence")
            }
            if "ix_study_evidence_project_id" not in indexes:
                op.create_index(
                    "ix_study_evidence_project_id",
                    "study_evidence",
                    ["project_id"],
                )
            return

        row_count = bind.execute(
            text("SELECT count(*) FROM study_evidence")
        ).scalar_one()
        if row_count:
            raise RuntimeError(
                "Cannot migrate study_evidence rows with UUID project IDs "
                "because projects now use integer IDs. Export or remove the "
                "legacy evidence rows before running this migration."
            )
        op.drop_table("study_evidence")

    op.create_table(
        "study_evidence",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("query", sa.String(length=2000), nullable=False),
        sa.Column("extraction_json", sa.JSON(), nullable=False),
        sa.Column("citations_json", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_study_evidence_project_id",
        "study_evidence",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_study_evidence_project_id",
        table_name="study_evidence",
    )
    op.drop_table("study_evidence")
