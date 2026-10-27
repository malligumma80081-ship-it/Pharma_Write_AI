"""Add requested roles to user accounts."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261027_add_role_requests"
down_revision: Union[str, Sequence[str], None] = "6e96cbd85802"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("requested_role", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "requested_role")
