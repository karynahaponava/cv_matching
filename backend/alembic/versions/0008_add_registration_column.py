"""add registration column

Revision ID: a626e07acf71
Revises: 0007
Create Date: 2026-10-08 15:46:45.684398

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a626e07acf71'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('registration', sa.String(), nullable=True))
    op.drop_index(op.f('ix_candidates_cv_text_trgm'), table_name='candidates', postgresql_ops={'cv_text': 'gin_trgm_ops'}, postgresql_using='gin')
    op.drop_index(op.f('ix_candidates_stack_trgm'), table_name='candidates', postgresql_ops={'stack': 'gin_trgm_ops'}, postgresql_using='gin')


def downgrade() -> None:
    op.create_index(op.f('ix_candidates_stack_trgm'), 'candidates', ['stack'], unique=False, postgresql_ops={'stack': 'gin_trgm_ops'}, postgresql_using='gin')
    op.create_index(op.f('ix_candidates_cv_text_trgm'), 'candidates', ['cv_text'], unique=False, postgresql_ops={'cv_text': 'gin_trgm_ops'}, postgresql_using='gin')
    op.drop_column('candidates', 'registration')
