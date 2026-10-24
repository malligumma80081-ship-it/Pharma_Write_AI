import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0003_create_documents"
down_revision = "0002_integer_project_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "documents" in inspector.get_table_names():
        columns = {column["name"]: column for column in inspector.get_columns("documents")}
        project_id_type = columns.get("project_id", {}).get("type")
        if isinstance(project_id_type, sa.Integer):
            if "ix_documents_project_id" not in {
                index["name"] for index in inspector.get_indexes("documents")
            }:
                op.create_index(
                    "ix_documents_project_id",
                    "documents",
                    ["project_id"],
                )
            return

        document_count = bind.execute(
            text("SELECT count(*) FROM documents")
        ).scalar_one()
        if document_count:
            raise RuntimeError(
                "Cannot migrate documents with UUID project IDs because project "
                "IDs are now integers. Export or remove the legacy documents "
                "before running this migration."
            )
        op.drop_table("documents")

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_documents_project_id",
        "documents",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_table("documents")
