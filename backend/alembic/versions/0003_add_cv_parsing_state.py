"""add incremental CV parsing state

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-03

"""
import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PARSER_VERSION = 1


def _normalize_cv_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _content_hash(text: str) -> str:
    return hashlib.sha256(_normalize_cv_text(text).encode("utf-8")).hexdigest()


def upgrade() -> None:
    connection = op.get_bind()
    if "candidates" not in sa.inspect(connection).get_table_names():
        # On a brand-new installation the legacy migration chain does not create
        # candidates; Base.metadata.create_all creates it with the new columns.
        return

    op.add_column(
        "candidates", sa.Column("cv_source_revision", sa.String(128), nullable=True)
    )
    op.add_column(
        "candidates", sa.Column("cv_content_hash", sa.String(64), nullable=True)
    )
    op.add_column(
        "candidates", sa.Column("parsed_content_hash", sa.String(64), nullable=True)
    )
    op.add_column(
        "candidates", sa.Column("parsed_with_version", sa.Integer(), nullable=True)
    )

    candidates = sa.table(
        "candidates",
        sa.column("id", sa.Integer()),
        sa.column("cv_text", sa.Text()),
        sa.column("cv_content_hash", sa.String(64)),
        sa.column("parsed_content_hash", sa.String(64)),
        sa.column("parsed_with_version", sa.Integer()),
    )
    rows = connection.execute(
        sa.select(candidates.c.id, candidates.c.cv_text).where(
            candidates.c.cv_text.is_not(None), candidates.c.cv_text != ""
        )
    )
    for candidate_id, cv_text in rows:
        digest = _content_hash(cv_text)
        connection.execute(
            candidates.update()
            .where(candidates.c.id == candidate_id)
            .values(
                cv_content_hash=digest,
                parsed_content_hash=digest,
                parsed_with_version=PARSER_VERSION,
            )
        )


def downgrade() -> None:
    connection = op.get_bind()
    if "candidates" not in sa.inspect(connection).get_table_names():
        return

    op.drop_column("candidates", "parsed_with_version")
    op.drop_column("candidates", "parsed_content_hash")
    op.drop_column("candidates", "cv_content_hash")
    op.drop_column("candidates", "cv_source_revision")
