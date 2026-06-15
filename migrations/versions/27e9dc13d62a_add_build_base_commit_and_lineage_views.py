"""add build base_commit and lineage views

Revision ID: 27e9dc13d62a
Revises: 5c72a6312244
Create Date: 2026-06-15 11:50:21.685597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db_views import CREATE_VIEWS_SQL, DROP_VIEWS_SQL


# revision identifiers, used by Alembic.
revision: str = '27e9dc13d62a'
down_revision: Union[str, Sequence[str], None] = '5c72a6312244'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("builds", sa.Column("base_commit", sa.String(length=64), nullable=True))
    # Views read base_commit indirectly via builds; create after the column exists.
    for sql in CREATE_VIEWS_SQL:
        op.execute(sql)


def downgrade() -> None:
    """Downgrade schema."""
    for sql in DROP_VIEWS_SQL:
        op.execute(sql)
    op.drop_column("builds", "base_commit")
