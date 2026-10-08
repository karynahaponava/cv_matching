"""add_trgm_indexes_for_fuzzy_search

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-06 13:51:43.475417

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_candidates_cv_text_trgm 
        ON candidates USING GIN (cv_text gin_trgm_ops);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_candidates_stack_trgm 
        ON candidates USING GIN (stack gin_trgm_ops);
    """)

def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_candidates_cv_text_trgm;")
    op.execute("DROP INDEX IF EXISTS ix_candidates_stack_trgm;")