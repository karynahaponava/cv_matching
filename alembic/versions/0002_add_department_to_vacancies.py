"""add department to vacancies

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("vacancies", sa.Column("department", sa.String(), nullable=False, server_default="N/A"))
    op.alter_column("vacancies", "department", server_default=None)


def downgrade() -> None:
    op.drop_column("vacancies", "department")
