"""add CV source retry backoff

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    if "candidates" not in sa.inspect(connection).get_table_names():
        return

    op.add_column(
        "candidates",
        sa.Column(
            "cv_source_check_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "candidates",
        sa.Column("cv_source_next_check_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    connection = op.get_bind()
    if "candidates" not in sa.inspect(connection).get_table_names():
        return

    op.drop_column("candidates", "cv_source_next_check_at")
    op.drop_column("candidates", "cv_source_check_failures")
