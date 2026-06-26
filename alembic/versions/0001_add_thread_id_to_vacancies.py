"""add thread_id to vacancies

Revision ID: 0001
Revises:
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default="0" satisfies NOT NULL for existing rows; dropped immediately after
    op.add_column("vacancies", sa.Column("thread_id", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("vacancies", "thread_id", server_default=None)


def downgrade() -> None:
    op.drop_column("vacancies", "thread_id")
