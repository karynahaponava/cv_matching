"""add persistent maintenance state

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    if sa.inspect(connection).has_table("maintenance_state"):
        # In local development uvicorn runs with --reload and the application
        # still calls Base.metadata.create_all(). A model reload can therefore
        # create this table before Alembic gets a chance to run the migration.
        return

    op.create_table(
        "maintenance_state",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.PrimaryKeyConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("maintenance_state")
