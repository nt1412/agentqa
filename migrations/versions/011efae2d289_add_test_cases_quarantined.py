"""add test_cases.quarantined

Revision ID: 011efae2d289
Revises: 27e9dc13d62a
Create Date: 2026-06-15 12:43:44.962632

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011efae2d289'
down_revision: Union[str, Sequence[str], None] = '27e9dc13d62a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "test_cases",
        sa.Column("quarantined", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("test_cases", "quarantined")
