"""add execution_reasoning embedding vector column

Revision ID: 5c72a6312244
Revises: 13de60bfa83f
Create Date: 2026-06-14 13:36:43.588748

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '5c72a6312244'
down_revision: Union[str, Sequence[str], None] = '13de60bfa83f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "execution_reasoning",
        sa.Column("embedding", Vector(384), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("execution_reasoning", "embedding")
