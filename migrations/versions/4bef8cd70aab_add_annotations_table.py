"""add annotations table

Revision ID: 4bef8cd70aab
Revises: 011efae2d289
Create Date: 2026-06-15 12:49:41.261097

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4bef8cd70aab'
down_revision: Union[str, Sequence[str], None] = '011efae2d289'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "annotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.create_index("ix_annotations_entity_type", "annotations", ["entity_type"])
    op.create_index("ix_annotations_entity_id", "annotations", ["entity_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_annotations_entity_id", table_name="annotations")
    op.drop_index("ix_annotations_entity_type", table_name="annotations")
    op.drop_table("annotations")
