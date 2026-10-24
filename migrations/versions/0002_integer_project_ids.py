import uuid

import sqlalchemy as sa
from alembic import op

revision = "0002_integer_project_ids"
down_revision = "0001_create_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    old_projects = sa.table(
        "projects",
        sa.column("id", sa.Uuid(as_uuid=True)),
        sa.column("name", sa.String(200)),
        sa.column("research_question", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("status", sa.String(30)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    new_projects = op.create_table(
        "projects_new",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("research_question", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
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
    )

    existing_projects = connection.execute(
        sa.select(old_projects).order_by(old_projects.c.created_at, old_projects.c.id)
    ).mappings()
    migrated_projects = [
        {
            "id": project_id,
            "name": project["name"],
            "research_question": project["research_question"],
            "description": project["description"],
            "status": project["status"],
            "created_at": project["created_at"],
            "updated_at": project["updated_at"],
        }
        for project_id, project in enumerate(existing_projects, start=1)
    ]
    if migrated_projects:
        connection.execute(new_projects.insert(), migrated_projects)

    op.drop_table("projects")
    op.rename_table("projects_new", "projects")
    op.create_index("ix_projects_name", "projects", ["name"])
    op.create_index("ix_projects_status", "projects", ["status"])


def downgrade() -> None:
    connection = op.get_bind()
    old_projects = sa.table(
        "projects",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String(200)),
        sa.column("research_question", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("status", sa.String(30)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    new_projects = op.create_table(
        "projects_uuid",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("research_question", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
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
    )

    existing_projects = connection.execute(
        sa.select(old_projects).order_by(old_projects.c.id)
    ).mappings()
    reverted_projects = [
        {
            "id": uuid.uuid4(),
            "name": project["name"],
            "research_question": project["research_question"],
            "description": project["description"],
            "status": project["status"],
            "created_at": project["created_at"],
            "updated_at": project["updated_at"],
        }
        for project in existing_projects
    ]
    if reverted_projects:
        connection.execute(new_projects.insert(), reverted_projects)

    op.drop_table("projects")
    op.rename_table("projects_uuid", "projects")
    op.create_index("ix_projects_name", "projects", ["name"])
    op.create_index("ix_projects_status", "projects", ["status"])
