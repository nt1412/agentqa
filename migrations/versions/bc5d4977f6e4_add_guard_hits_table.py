"""add guard_hits table

Revision ID: bc5d4977f6e4
Revises: 4bef8cd70aab
Create Date: 2026-06-15 13:33:15.470453

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc5d4977f6e4'
down_revision: Union[str, Sequence[str], None] = '4bef8cd70aab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "guard_hits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("branch", sa.String(length=128), nullable=True),
        sa.Column("fixed_commit", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.create_index("ix_guard_hits_project_id", "guard_hits", ["project_id"])
    op.create_index("ix_guard_hits_case_id", "guard_hits", ["case_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_guard_hits_case_id", table_name="guard_hits")
    op.drop_index("ix_guard_hits_project_id", table_name="guard_hits")
    op.drop_table("guard_hits")
